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

import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction

from sinpapel.cache import (
    get_estado_by_name,
    get_transitions_for,
)
from sinpapel.models import (
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

logger = logging.getLogger(__name__)


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

    def evaluar_requisitos_documentales(self, instance, estado=None):
        """Evalúa TODOS los requisitos documentales del estado (no solo faltantes).

        Mecanismo público compartido: lo consumen `_validar_documentos` (engine)
        y `sinpapel-drf` (GET /requisitos/), evitando duplicar la lógica.

        Args:
            instance: instancia decorada con @workflow_enabled.
            estado: Estado a evaluar. Si es None, usa el estado actual de la
                instancia (config.state_field).

        Returns:
            list[dict] — un item por requisito, con su cumplimiento. Dos niveles:

            Coarse (flag `Estado.expediente_obligatorio`):
                {"nivel": "expediente", "satisfecho": bool, "mensaje": str}

            Typed (`RequisitoEstadoDocumento`, tipo_documento + porcentaje):
                {"nivel": "requisito_documento", "satisfecho": bool,
                 "mensaje": str, "tipo_documento": str, "tipo_documento_id": int,
                 "porcentaje_requerido": int, "porcentaje_actual": int,
                 "auto_carga": bool}

            El "documento presente por tipo" sale de InstanciaDocumento (liga el
            tipo vía documento.tipo_documento y la instancia vía la GFK target);
            porcentaje_actual = max(InstanciaDocumento.porcentaje) de ese tipo
            (0 si no hay ninguno). auto_carga=True ⇒ satisfecho=True (lo genera
            el sistema, no bloquea al usuario).
        """
        if estado is None:
            config = self._get_config(instance)
            estado = getattr(instance, config.state_field, None)

        resultado: list[dict] = []
        if estado is None:
            return resultado

        # 1. Flag coarse: expediente_obligatorio
        if estado.expediente_obligatorio:
            expedientes = getattr(instance, "expedientes", None)
            tiene = expedientes is not None and expedientes.exists()
            resultado.append({
                "nivel": "expediente",
                "satisfecho": bool(tiene),
                "mensaje": "" if tiene else (
                    f"Se requiere adjuntar al menos un documento antes de "
                    f"avanzar desde '{estado.nombre}'."
                ),
            })

        # 2. Reglas finas: RequisitoEstadoDocumento por tipo/porcentaje
        from django.contrib.contenttypes.models import ContentType

        from sinpapel.cache import get_requisitos_for
        from sinpapel.models import InstanciaDocumento

        requisitos = get_requisitos_for(estado.id)
        if requisitos:
            content_type = ContentType.objects.get_for_model(type(instance))
            for requisito in requisitos:
                porcentaje_actual = max(
                    InstanciaDocumento.objects.filter(
                        target_content_type=content_type,
                        target_object_id=instance.pk,
                        documento__tipo_documento_id=requisito.tipo_documento_id,
                    ).values_list("porcentaje", flat=True),
                    default=0,
                )
                satisfecho = (
                    requisito.auto_carga
                    or porcentaje_actual >= requisito.porcentaje
                )
                nombre_tipo = requisito.tipo_documento.nombre
                resultado.append({
                    "nivel": "requisito_documento",
                    "satisfecho": satisfecho,
                    "mensaje": "" if satisfecho else (
                        f"Falta el documento '{nombre_tipo}' "
                        f"(requerido {requisito.porcentaje}%, "
                        f"actual {porcentaje_actual}%)."
                    ),
                    "tipo_documento": nombre_tipo,
                    "tipo_documento_id": requisito.tipo_documento_id,
                    "porcentaje_requerido": requisito.porcentaje,
                    "porcentaje_actual": porcentaje_actual,
                    "auto_carga": requisito.auto_carga,
                })

        return resultado

    def _validar_documentos(self, instance, estado_actual):
        """Retorna la lista de requisitos documentales NO satisfechos (faltantes).

        Wrapper sobre `evaluar_requisitos_documentales` — una sola fuente de
        verdad. Proyecta a la forma histórica de `documentos_faltantes` (key
        `tipo`, etc.) que consume `preview_transition()` y `sinpapel-drf`.
        """
        faltantes = []
        for r in self.evaluar_requisitos_documentales(instance, estado_actual):
            if r["satisfecho"]:
                continue
            if r["nivel"] == "expediente":
                faltantes.append({"tipo": "expediente", "mensaje": r["mensaje"]})
            else:
                faltantes.append({
                    "tipo": "requisito_documento",
                    "tipo_documento": r["tipo_documento"],
                    "porcentaje_requerido": r["porcentaje_requerido"],
                    "porcentaje_actual": r["porcentaje_actual"],
                    "mensaje": r["mensaje"],
                })
        return faltantes

    def _validar_predicados(self, config_transicion, instance, user):
        """Evalúa condiciones de transición. Retorna lista de fallidas.

        Fires `sinpapel.signals.predicate_failed` (send_robust) for each
        condition that rejects. Receivers run after the engine returns;
        errors in receivers do not abort the workflow.
        """
        from sinpapel.models.predicates import CondicionTransicion
        from sinpapel.signals import predicate_failed

        fallidas = []
        condiciones = CondicionTransicion.objects.filter(
            transicion=config_transicion,
            activo=True,
        ).order_by("orden")

        for condicion in condiciones:
            try:
                pasa, msg = PredicateEngine.evaluar(condicion, instance, user)
            except Exception:
                # Config inválida (path fuera de whitelist, key faltante,
                # backend desconocido…) = bloqueo controlado, nunca un 500.
                logger.exception(
                    "CondicionTransicion id=%s mal configurada (tipo=%s)",
                    condicion.id,
                    condicion.tipo,
                )
                pasa, msg = False, (
                    "Condición de transición mal configurada; "
                    "contacta al administrador del flujo."
                )
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
            "firma_requerida": False,
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

        # 7b. Firma requerida (0.8.0): el preview informa si la transición
        # exigirá firma_payload, para que la UI pida la firma antes de ejecutar.
        reporte["firma_requerida"] = bool(
            config_transicion is not None and config_transicion.requiere_firma
        )

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
        """Retorna últimos seguimientos de la instancia.

        Filtra por (target_content_type, target_object_id) — una GFK no admite
        `filter(target=...)` directo.
        """
        from django.contrib.contenttypes.models import ContentType

        from sinpapel.models import SeguimientoWorkflow
        try:
            content_type = ContentType.objects.get_for_model(type(instance))
            seguimientos = SeguimientoWorkflow.objects.filter(
                target_content_type=content_type,
                target_object_id=instance.pk,
            ).select_related(
                "estado_anterior", "estado_nuevo", "usuario_accion"
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
            logger.exception(
                "No se pudo obtener historial reciente para %s pk=%s",
                type(instance).__name__,
                getattr(instance, "pk", "?"),
            )
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

    def cambiar_estado(
        self,
        instance: "models.Model",
        target_state_name: str,
        user: "User",
        comentarios: str = "",
        condiciones: str | None = None,
        ip_address: str | None = None,
        firma_payload: dict | None = None,
    ) -> dict[str, Any]:
        """Ejecuta la transición a target_state_name (atómica).

        Concurrencia: dentro de la transacción se re-lee el row con
        SELECT ... FOR UPDATE y se refresca el estado actual antes de validar,
        de modo que dos transiciones concurrentes desde el mismo estado no
        puedan pasar ambas la validación (la segunda ve el estado ya mutado).

        Side effects: se ejecutan DESPUÉS de que la transacción del motor
        commiteó — un fallo de side effect nunca puede dejar efectos externos
        de una transición que hizo rollback. Si el caller envuelve esta
        llamada en su propia transacción exterior, esa garantía pasa a ser
        responsabilidad del caller.

        Args:
            instance: instancia decorada con @workflow_enabled
            target_state_name: nombre del Estado destino
            user: User que ejecuta
            comentarios: justificación
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
        config = self._get_config(instance)

        with transaction.atomic():
            # 0. Lock pesimista: re-lee el row bajo FOR UPDATE y refresca el
            # estado actual en memoria. Cierra la carrera check-then-act:
            # una transición concurrente ya commiteada se vuelve visible aquí
            # y la validación del paso 1 la rechaza.
            locked = (
                type(instance).objects.select_for_update().get(pk=instance.pk)
            )
            setattr(
                instance,
                config.state_field,
                getattr(locked, config.state_field),
            )

            # 1. Validar permisos + transición válida (sobre el estado fresco)
            puede, mensaje = self.puede_cambiar_estado(
                instance, target_state_name, user
            )
            if not puede:
                raise PermissionError(mensaje)

            # 2. Resolver estados (S13.1: cache helper para estado_nuevo)
            estado_anterior = getattr(instance, config.state_field)
            estado_nuevo = get_estado_by_name(target_state_name)
            if estado_nuevo is None:
                # No debería pasar — puede_cambiar_estado ya validó arriba.
                raise ValueError(f"Estado '{target_state_name}' no existe")

            # 2b. Enforce de firma requerida (0.8.0): la exigencia vive en la
            # configuración de la transición, no en la buena fe del caller.
            flujo = self._resolve_flujo(instance, config)
            config_transicion, _err = self._validar_configuracion_transicion(
                estado_anterior, estado_nuevo, flujo
            )
            firma_requerida = bool(
                config_transicion is not None
                and config_transicion.requiere_firma
            )
            if firma_requerida and firma_payload is None:
                raise PermissionError(
                    f"La transición a '{target_state_name}' requiere firma "
                    f"electrónica (firma_payload)."
                )

            # 3. Procesar firma si aplica (dual shape, 0.8.0: vía factory)
            # Modo A — dict con 'contenido' (+ kwargs backend-specific) →
            #          get_signature_backend().request_signature(...)
            # Modo B — dict {"registro_firma_id": int} → RegistroFirma
            #          pre-creado por el caller (sign_server_side previo),
            #          validado: firmante == user, VALIDA y no vinculado.
            registro_firma = None
            if firma_payload is not None:
                if "registro_firma_id" in firma_payload:
                    registro_firma = self._resolver_registro_firma(
                        firma_payload["registro_firma_id"], user
                    )
                elif "contenido" in firma_payload:
                    from sinpapel.signing.factory import get_signature_backend

                    extra = {
                        k: v
                        for k, v in firma_payload.items()
                        if k != "contenido"
                    }
                    registro_firma = get_signature_backend().request_signature(
                        content=firma_payload["contenido"],
                        signer=user,
                        is_required=firma_requerida,
                        **extra,
                    )

            # 4. Crear SeguimientoWorkflow (target via GFK)
            seguimiento = SeguimientoWorkflow.objects.create(
                target=instance,
                estado_anterior=estado_anterior,
                estado_nuevo=estado_nuevo,
                usuario_accion=user,
                comentarios=comentarios,
                condiciones=condiciones,
                ip_address=ip_address,
                firma_registro=registro_firma,
                autor=user,
                modificador=user,
            )

            # 5. Actualizar estado en la instance
            setattr(instance, config.state_field, estado_nuevo)
            instance.save(update_fields=[config.state_field, "actualizado"])

        # 6. Side-effects — POST-commit de la transacción del motor.
        # Errores se loggean sin re-raise (ADR-004): la transición ya
        # persistió; el side effect fallido no debe revertirla.
        resultado_extra = ejecutar_side_effects(
            target_state_name,
            instance,
            user,
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

    def _resolver_registro_firma(self, registro_id: int, user: "User"):
        """Valida un RegistroFirma pre-creado (modo B) antes de vincularlo.

        Rechaza (PermissionError) si:
        - no existe,
        - el firmante no es el usuario que ejecuta la transición,
        - la firma no está en estado VALIDA,
        - ya está vinculado a otro SeguimientoWorkflow.
        """
        from sinpapel.models import RegistroFirma, SeguimientoWorkflow

        registro = RegistroFirma.objects.filter(pk=registro_id).first()
        if registro is None:
            raise PermissionError(
                f"RegistroFirma id={registro_id} no existe."
            )
        if registro.signer_id != getattr(user, "id", None):
            raise PermissionError(
                "El RegistroFirma pertenece a otro firmante; no puede "
                "vincularse a una transición ejecutada por este usuario."
            )
        if registro.verification_result not in RegistroFirma.RESULTADOS_VALIDOS:
            raise PermissionError(
                f"El RegistroFirma id={registro_id} no está en estado válido "
                f"(actual: {registro.verification_result})."
            )
        if SeguimientoWorkflow.objects.filter(firma_registro=registro).exists():
            raise PermissionError(
                f"El RegistroFirma id={registro_id} ya respalda otra "
                f"transición; una firma no puede reutilizarse."
            )
        return registro

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
