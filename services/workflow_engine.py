"""Sinpapel — WorkflowEngine genérico.

Motor de transiciones que opera sobre cualquier modelo decorado con
@workflow_enabled. Lee `_workflow_config` (state_field, version_field,
workflow_key) inyectado por el decorator para resolver runtime behavior.

NO contiene lógica creditos-específica:
- Sin dict TRANSICIONES hardcoded → toda la matriz vive en ConfiguracionTransicion
- Sin dict PERMISOS_ACCION → grupos validados via ConfiguracionTransicion.grupos_permitidos
- Sin _generar_credito_automatico ni notificaciones específicas → eso queda en
  side_effects handlers de creditos (ADR-004)

Resolución de flujo activo:
1. Si _workflow_config.version_field set: getattr(instance, version_field)
2. Else, si instance.resolve_workflow_version() callable: usarlo
3. Else: None (consultas a ConfiguracionTransicion sin filtro de flujo)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction

from sinpapel.cache import (
    get_estado_by_name,
    get_transitions_for,
)
from sinpapel.models import (
    CondicionTransicion,
    ConfiguracionTransicion,
    Estado,
    SeguimientoWorkflow,
)
from sinpapel.services.predicate_engine import PredicateEngine
from sinpapel.services.side_effects import ejecutar_side_effects

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django.db import models

    from sinpapel.models import VersionFlujo
    from sinpapel.registry import WorkflowConfig


class WorkflowEngine:
    """Motor genérico de transiciones de workflow."""

    def _validar_estado_destino(self, target_state_name: str):
        """Valida que el estado destino existe."""
        from sinpapel.cache import get_estado_by_name
        estado_destino = get_estado_by_name(target_state_name)
        if estado_destino is None:
            return None, f"Estado destino '{target_state_name}' no existe"
        return estado_destino, None

    def _validar_configuracion_transicion(
        self, estado_actual, estado_destino, flujo
    ):
        """Busca la configuración de transición."""
        from sinpapel.models import ConfiguracionTransicion
        qs = ConfiguracionTransicion.objects.filter(
            estado_origen=estado_actual,
            estado_destino=estado_destino,
        )
        if flujo is not None:
            qs = qs.filter(flujo=flujo)
        config_transicion = qs.first()
        if config_transicion is None:
            return None, (
                f"No se puede cambiar de '{estado_actual.nombre}' a "
                f"'{estado_destino.nombre}'"
            )
        return config_transicion, None

    def _validar_grupos_permitidos(self, config_transicion, user):
        """Valida que el usuario tiene permisos."""
        if user.is_superuser:
            return True, None
        grupos_requeridos = list(
            config_transicion.grupos_permitidos.values_list("name", flat=True)
        )
        if grupos_requeridos:
            grupos_user = list(user.groups.values_list("name", flat=True))
            if not any(g in grupos_requeridos for g in grupos_user):
                return False, "No tiene permisos para realizar esta acción"
        return True, None

    def _validar_documentos(self, instance, estado_actual):
        """Verifica requisitos documentales. Retorna lista de faltantes.

        Dos niveles, ambos sobre el estado actual:

        1. Flag coarse `Estado.expediente_obligatorio`: requiere ≥1
           ExpedienteAdjunto (vía la GenericRelation `expedientes`).
        2. Reglas finas `RequisitoEstadoDocumento` (tipo_documento + porcentaje
           mínimo), consultadas vía cache `get_requisitos_for` (invalidado por
           signal). El "documento presente por tipo" sale de InstanciaDocumento
           (liga el tipo vía documento.tipo_documento y la instancia vía la GFK
           target); el porcentaje actual = max(InstanciaDocumento.porcentaje) de
           ese tipo (0 si no hay ninguno). Requisitos con auto_carga=True NO
           bloquean (documento generado por el sistema).
        """
        faltantes = []

        # 1. Flag coarse: expediente_obligatorio
        if estado_actual.expediente_obligatorio:
            expedientes = getattr(instance, "expedientes", None)
            if expedientes is not None and not expedientes.exists():
                faltantes.append({
                    "tipo": "expediente",
                    "mensaje": f"Se requiere adjuntar al menos un documento antes de avanzar desde '{estado_actual.nombre}'.",
                })

        # 2. Reglas finas: RequisitoEstadoDocumento por tipo/porcentaje
        from django.contrib.contenttypes.models import ContentType

        from sinpapel.cache import get_requisitos_for
        from sinpapel.models import InstanciaDocumento

        requisitos = get_requisitos_for(estado_actual.id)
        if requisitos:
            content_type = ContentType.objects.get_for_model(type(instance))
            for requisito in requisitos:
                if requisito.auto_carga:
                    # Documento generado por el sistema: no bloquea al usuario.
                    continue
                porcentaje_actual = max(
                    InstanciaDocumento.objects.filter(
                        target_content_type=content_type,
                        target_object_id=instance.pk,
                        documento__tipo_documento_id=requisito.tipo_documento_id,
                    ).values_list("porcentaje", flat=True),
                    default=0,
                )
                if porcentaje_actual < requisito.porcentaje:
                    nombre_tipo = requisito.tipo_documento.nombre
                    faltantes.append({
                        "tipo": "requisito_documento",
                        "tipo_documento": nombre_tipo,
                        "porcentaje_requerido": requisito.porcentaje,
                        "porcentaje_actual": porcentaje_actual,
                        "mensaje": (
                            f"Falta el documento '{nombre_tipo}' "
                            f"(requerido {requisito.porcentaje}%, "
                            f"actual {porcentaje_actual}%)."
                        ),
                    })

        return faltantes

    def _validar_predicados(self, config_transicion, instance, user):
        """Evalúa condiciones de transición. Retorna lista de fallidas.

        Fires `sinpapel.signals.predicate_failed` (send_robust) for each
        condition that rejects. Receivers run after the engine returns;
        errors in receivers do not abort the workflow.
        """
        from sinpapel.models.predicates import CondicionTransicion
        from sinpapel.services.predicate_engine import PredicateEngine
        from sinpapel.signals import predicate_failed

        fallidas = []
        condiciones = CondicionTransicion.objects.filter(
            transicion=config_transicion,
            activo=True,
        ).order_by("orden")

        for condicion in condiciones:
            pasa, msg = PredicateEngine.evaluar(condicion, instance, user)
            if not pasa:
                fallidas.append({
                    "condicion_id": condicion.id,
                    "tipo": condicion.tipo,
                    "mensaje": condicion.mensaje_error or msg,
                })
                predicate_failed.send_robust(
                    sender=type(instance),
                    target=instance,
                    condicion=condicion,
                    user=user,
                    target_state=config_transicion.estado_destino.nombre,
                )
        return fallidas

    def preview_transition(
        self,
        instance: "models.Model",
        target_state_name: str,
        user: "User",
    ) -> dict[str, Any]:
        """Simula una transición y retorna un reporte de impacto.

        NO muta la instancia ni persiste nada.

        Returns:
            dict con keys: permitido, razones_bloqueo, side_effects,
            documentos_faltantes, predicados_fallidos, aprobadores_requeridos,
            historial_reciente
        """
        from sinpapel.services.side_effects import SIDE_EFFECTS
        from sinpapel.models import SeguimientoWorkflow

        config = self._get_config(instance)
        estado_actual = getattr(instance, config.state_field, None)

        reporte: dict[str, Any] = {
            "permitido": True,
            "razones_bloqueo": [],
            "side_effects": [],
            "documentos_faltantes": [],
            "predicados_fallidos": [],
            "aprobadores_requeridos": [],
            "historial_reciente": [],
        }

        # 1. Validar estado actual
        if estado_actual is None:
            reporte["permitido"] = False
            reporte["razones_bloqueo"].append({
                "tipo": "estado",
                "mensaje": "Instance has no current state",
            })
            return reporte

        # 2. Validar estado destino
        estado_destino, error = self._validar_estado_destino(target_state_name)
        if error:
            reporte["permitido"] = False
            reporte["razones_bloqueo"].append({
                "tipo": "estado",
                "mensaje": error,
            })
            return reporte

        # 3. Validar configuración de transición
        flujo = self._resolve_flujo(instance, config)
        config_transicion, error = self._validar_configuracion_transicion(
            estado_actual, estado_destino, flujo
        )
        if error:
            reporte["permitido"] = False
            reporte["razones_bloqueo"].append({
                "tipo": "transicion",
                "mensaje": error,
            })
            return reporte

        # 4. Documentos faltantes
        documentos = self._validar_documentos(instance, estado_actual)
        if documentos:
            reporte["documentos_faltantes"] = documentos
            reporte["permitido"] = False
            for doc in documentos:
                reporte["razones_bloqueo"].append({
                    "tipo": "documento",
                    "mensaje": doc["mensaje"],
                })

        # 5. Permisos (si no es superuser)
        if not user.is_superuser:
            permisos_ok, error = self._validar_grupos_permitidos(config_transicion, user)
            if not permisos_ok:
                reporte["permitido"] = False
                reporte["razones_bloqueo"].append({
                    "tipo": "permiso",
                    "mensaje": error,
                })

        # 6. Predicados
        predicados = self._validar_predicados(config_transicion, instance, user)
        if predicados:
            reporte["predicados_fallidos"] = predicados
            reporte["permitido"] = False
            for pred in predicados:
                reporte["razones_bloqueo"].append({
                    "tipo": "predicado",
                    "mensaje": pred["mensaje"],
                })

        # 7. Side effects
        reporte["side_effects"] = [
            name for name in SIDE_EFFECTS.keys()
            if name == target_state_name
        ]

        # 8. Historial reciente
        reporte["historial_reciente"] = self._obtener_historial_reciente(instance)

        # Opt-in audit signal (default OFF — avoids noise from frequent previews).
        from django.conf import settings as _settings
        if getattr(_settings, "SINPAPEL_EMIT_PREVIEW_EVENTS", False):
            from sinpapel.signals import transition_preview_requested
            transition_preview_requested.send_robust(
                sender=type(instance),
                target=instance,
                target_state=target_state_name,
                user=user,
                reporte=reporte,
            )

        return reporte

    def _obtener_historial_reciente(self, instance: "models.Model") -> list[dict]:
        """Retorna últimos seguimientos de la instancia."""
        from sinpapel.models import SeguimientoWorkflow
        try:
            seguimientos = SeguimientoWorkflow.objects.filter(
                target=instance
            ).order_by("-fecha_accion")[:5]
            return [
                {
                    "fecha": seg.fecha_accion.isoformat(),
                    "transicion": f"{seg.estado_anterior.nombre if seg.estado_anterior else 'Nuevo'} → {seg.estado_nuevo.nombre}",
                    "usuario": seg.usuario_accion.username if seg.usuario_accion else None,
                    "comentarios": seg.comentarios,
                }
                for seg in seguimientos
            ]
        except Exception:
            return []

    def puede_cambiar_estado(
        self,
        instance: "models.Model",
        target_state_name: str,
        user: "User",
    ) -> tuple[bool, str | None]:
        """Valida si la transición está permitida.

        Args:
            instance: instancia decorada con @workflow_enabled
            target_state_name: nombre del Estado destino
            user: User que intenta la transición

        Returns:
            (puede: bool, mensaje: str | None)
        """
        preview = self.preview_transition(instance, target_state_name, user)
        if not preview["permitido"]:
            return False, preview["razones_bloqueo"][0]["mensaje"]
        return True, "OK"

    def available_transitions(
        self,
        instance: "models.Model",
        user: "User",
    ) -> list[Estado]:
        """Lista de Estado destino válidos desde el estado actual.

        No filtra por permisos del user — eso lo hace puede_cambiar_estado.
        Filtra por flujo activo si se puede resolver.
        """
        config = self._get_config(instance)
        estado_actual = getattr(instance, config.state_field, None)
        if estado_actual is None:
            return []

        flujo = self._resolve_flujo(instance, config)
        if flujo is not None:
            # S13.1: cache helper para path con flujo (caso 80% en producción)
            transitions = get_transitions_for(flujo.id, estado_actual.id)
            return [t.estado_destino for t in transitions]
        # Sin flujo: legacy fallback (sin cache) — preservado por backward compat
        qs = ConfiguracionTransicion.objects.filter(
            estado_origen=estado_actual,
        ).select_related("estado_destino")
        return [t.estado_destino for t in qs]

    @transaction.atomic
    def cambiar_estado(
        self,
        instance: "models.Model",
        target_state_name: str,
        user: "User",
        comentarios: str = "",
        monto_aprobado: Any = None,
        condiciones: str | None = None,
        ip_address: str | None = None,
        firma_payload: dict | None = None,
    ) -> dict[str, Any]:
        """Ejecuta la transición a target_state_name (atómica).

        Args:
            instance: instancia decorada con @workflow_enabled
            target_state_name: nombre del Estado destino
            user: User que ejecuta
            comentarios: justificación
            monto_aprobado: opcional, propagado al SeguimientoWorkflow + side_effects
            condiciones: opcional
            ip_address: opcional
            firma_payload: opcional, dual shape (S13.6):
                - Modo A: dict con keys {contenido, firma_b64, certificado_cer_b64} →
                  FielBackend.request_signature verifica + persiste RegistroFirma.
                - Modo B: dict con key {registro_firma_id: int} → RegistroFirma
                  pre-creado por el caller (viewset invocó sign_server_side antes).

        Returns:
            dict con keys: success, instance_id, estado_anterior, estado_nuevo,
            seguimiento_id, + extra del side_effects dispatch.

        Raises:
            PermissionError: si la transición no es válida (delega a puede_cambiar_estado)
        """
        # 1. Validar permisos + transición válida
        puede, mensaje = self.puede_cambiar_estado(instance, target_state_name, user)
        if not puede:
            raise PermissionError(mensaje)

        # 2. Resolver estados (S13.1: cache helper para estado_nuevo)
        config = self._get_config(instance)
        estado_anterior = getattr(instance, config.state_field)
        estado_nuevo = get_estado_by_name(target_state_name)
        if estado_nuevo is None:
            # No debería pasar — puede_cambiar_estado ya validó arriba.
            # Defensive: race condition entre check y resolve.
            raise ValueError(f"Estado '{target_state_name}' no existe")

        # 3. Procesar firma si aplica (S13.6: dual shape)
        # Modo A — dict con verify-fields → FielBackend.request_signature (verifica + persiste)
        # Modo B — dict {"registro_firma_id": int} → RegistroFirma pre-creado por viewset
        #          (viewset invocó sign_server_side antes para descartar key inmediato)
        registro_firma = None
        if firma_payload is not None:
            if "registro_firma_id" in firma_payload:
                from sinpapel.models import RegistroFirma
                registro_firma = RegistroFirma.objects.get(
                    pk=firma_payload["registro_firma_id"]
                )
            elif "contenido" in firma_payload:
                from sinpapel.signing.backends.fiel import FielBackend
                registro_firma = FielBackend().request_signature(
                    content=firma_payload["contenido"],
                    signer=user,
                    firma_b64=firma_payload["firma_b64"],
                    certificado_cer_b64=firma_payload["certificado_cer_b64"],
                    is_required=True,
                )

        # 4. Crear SeguimientoWorkflow (target via GFK)
        seguimiento = SeguimientoWorkflow.objects.create(
            target=instance,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            usuario_accion=user,
            comentarios=comentarios,
            monto_aprobado=monto_aprobado,
            condiciones=condiciones,
            ip_address=ip_address,
            firma_registro=registro_firma,
            autor=user,
            modificador=user,
        )

        # 5. Actualizar estado en la instance
        setattr(instance, config.state_field, estado_nuevo)
        instance.save(update_fields=[config.state_field, "actualizado"])

        # 6. Side-effects (errors logged, no re-raised — ADR-004)
        resultado_extra = ejecutar_side_effects(
            target_state_name,
            instance,
            user,
            monto_aprobado=monto_aprobado,
        )

        return {
            "success": True,
            "instance_id": instance.id,
            "estado_anterior": estado_anterior.nombre if estado_anterior else None,
            "estado_nuevo": estado_nuevo.nombre,
            "seguimiento_id": seguimiento.id,
            **resultado_extra,
        }

    # ─── Helpers privados ──────────────────────────────────────────────────

    def _get_config(self, instance: "models.Model") -> "WorkflowConfig":
        """Recupera _workflow_config de la clase del instance.

        Raises:
            AttributeError: si la clase no fue decorada con @workflow_enabled
        """
        return type(instance)._workflow_config  # type: ignore[attr-defined,no-any-return]

    def _resolve_flujo(
        self,
        instance: "models.Model",
        config: "WorkflowConfig",
    ) -> "VersionFlujo | None":
        """Resuelve el VersionFlujo activo del instance.

        Estrategia:
        1. Si config.version_field set → getattr(instance, version_field)
        2. Else, si instance.resolve_workflow_version() callable → usarlo
        3. Else → None (consultas a ConfiguracionTransicion sin filtro de flujo)
        """
        if config.version_field:
            return getattr(instance, config.version_field, None)

        resolver = getattr(instance, "resolve_workflow_version", None)
        if callable(resolver):
            return resolver()

        return None
