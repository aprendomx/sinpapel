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
        """Verifica requisitos documentales. Retorna lista de faltantes."""
        faltantes = []
        if estado_actual.expediente_obligatorio:
            expedientes = getattr(instance, "expedientes", None)
            if expedientes is not None and not expedientes.exists():
                faltantes.append({
                    "tipo": "expediente",
                    "mensaje": f"Se requiere adjuntar al menos un documento antes de avanzar desde '{estado_actual.nombre}'.",
                })
        return faltantes

    def _validar_predicados(self, config_transicion, instance, user):
        """Evalúa condiciones de transición. Retorna lista de fallidas."""
        from sinpapel.models.predicates import CondicionTransicion
        from sinpapel.services.predicate_engine import PredicateEngine

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
                    "mensaje": msg or condicion.mensaje_error,
                })
        return fallidas

    def preview_transition(
        self,
        instance: "models.Model",
        target_state_name: str,
        user: "User",
    ) -> dict[str, Any]:
        """Preview a transition without executing it.

        Returns detailed validation results.
        """
        config = self._get_config(instance)
        estado_actual = getattr(instance, config.state_field, None)
        if estado_actual is None:
            return {
                "can_transition": False,
                "error": "Instance has no current state",
            }

        estado_destino, error = self._validar_estado_destino(target_state_name)
        if error:
            return {
                "can_transition": False,
                "error": error,
            }

        flujo = self._resolve_flujo(instance, config)
        config_transicion, error = self._validar_configuracion_transicion(
            estado_actual, estado_destino, flujo
        )
        if error:
            return {
                "can_transition": False,
                "error": error,
            }

        result: dict[str, Any] = {
            "can_transition": True,
            "estado_destino": estado_destino,
            "config_transicion": config_transicion,
        }

        if not user.is_superuser:
            documentos_faltantes = self._validar_documentos(instance, estado_actual)
            if documentos_faltantes:
                result["can_transition"] = False
                result["documentos_faltantes"] = documentos_faltantes

            permisos_ok, error = self._validar_grupos_permitidos(config_transicion, user)
            if not permisos_ok:
                result["can_transition"] = False
                result["permisos_error"] = error

            predicados_fallidos = self._validar_predicados(config_transicion, instance, user)
            if predicados_fallidos:
                result["can_transition"] = False
                result["predicados_fallidos"] = predicados_fallidos

        return result

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
        config = self._get_config(instance)
        estado_actual = getattr(instance, config.state_field, None)
        if estado_actual is None:
            return False, "Instance has no current state"

        estado_destino, error = self._validar_estado_destino(target_state_name)
        if error:
            return False, error

        flujo = self._resolve_flujo(instance, config)
        config_transicion, error = self._validar_configuracion_transicion(
            estado_actual, estado_destino, flujo
        )
        if error:
            return False, error

        if user.is_superuser:
            return True, "OK"

        documentos_faltantes = self._validar_documentos(instance, estado_actual)
        if documentos_faltantes:
            return False, documentos_faltantes[0]["mensaje"]

        permisos_ok, error = self._validar_grupos_permitidos(config_transicion, user)
        if not permisos_ok:
            return False, error

        predicados_fallidos = self._validar_predicados(config_transicion, instance, user)
        if predicados_fallidos:
            return False, predicados_fallidos[0]["mensaje"]

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
