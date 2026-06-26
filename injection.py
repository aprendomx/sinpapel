"""Sinpapel — Métodos inyectados por @workflow_enabled.

Estos métodos se vinculan a la clase decorada via setattr en el decorator.
Se importan localmente desde decorators.py para evitar circular imports.

Métodos:
    available_transitions(self, user) -> list[Estado]
    can_transition_to(self, target_state_name, user) -> tuple[bool, str | None]
    transition(self, target_state_name, user, **kwargs)
    preview_transition(self, target_state_name, user) -> dict

Estrategia: `available_transitions` consulta `ConfiguracionTransicion` en DB
directamente; `can_transition_to`, `transition` y `preview_transition` delegan en
`sinpapel.services.workflow_engine.WorkflowEngine` (el único motor; `WorkflowService`
no existe).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.contrib.auth.models import User

    from sinpapel.models import Estado


def available_transitions(self, user: "User") -> list["Estado"]:
    """Retorna lista de Estado destino válidos desde el estado actual.

    Consulta ConfiguracionTransicion filtrando por estado_origen.
    No filtra por user permissions — eso lo hace can_transition_to.

    Args:
        user: usuario consultando (no se usa para filtrar en S12.3, reservado
              para S12.4 cuando WorkflowEngine considere flujo activo + grupos)

    Returns:
        lista de instancias Estado destino válidos. Vacía si no hay estado actual.
    """
    from sinpapel.models import ConfiguracionTransicion

    config = type(self)._workflow_config  # type: ignore[attr-defined]
    estado_actual = getattr(self, config.state_field, None)
    if estado_actual is None:
        return []

    transiciones = ConfiguracionTransicion.objects.filter(
        estado_origen=estado_actual,
    ).select_related("estado_destino")
    return [t.estado_destino for t in transiciones]


def can_transition_to(self, target_state_name: str, user: "User") -> tuple[bool, str | None]:
    """Valida si la transición a target_state_name está permitida.

    Delega a sinpapel.services.workflow_engine.WorkflowEngine (S12.4).

    Args:
        target_state_name: nombre del Estado destino (ej. "EN_JEFATURA")
        user: usuario que intenta la transición

    Returns:
        tuple (puede: bool, mensaje: str | None)
    """
    # Import local: WorkflowEngine carga sinpapel.models, no top-level.
    from sinpapel.services.workflow_engine import WorkflowEngine

    return WorkflowEngine().puede_cambiar_estado(self, target_state_name, user)


def transition(self, target_state_name: str, user: "User", **kwargs: Any) -> Any:
    """Ejecuta la transición a target_state_name.

    Delega a sinpapel.services.workflow_engine.WorkflowEngine (S12.4).

    Args:
        target_state_name: nombre del Estado destino
        user: usuario que ejecuta la transición
        **kwargs: parámetros adicionales (comentarios, monto_aprobado,
                  condiciones, ip_address, firma_payload)

    Returns:
        dict con keys: success, instance_id, estado_anterior, estado_nuevo,
        seguimiento_id, + extra del side_effects dispatch
    """
    from sinpapel.services.workflow_engine import WorkflowEngine

    comentarios = kwargs.pop("comentarios", "")
    return WorkflowEngine().cambiar_estado(
        instance=self,
        target_state_name=target_state_name,
        user=user,
        comentarios=comentarios,
        **kwargs,
    )


def preview_transition(self, target_state_name: str, user: "User") -> dict:
    """Simula la transición a target_state_name sin mutar ni persistir nada.

    Delega a sinpapel.services.workflow_engine.WorkflowEngine.

    Args:
        target_state_name: nombre del Estado destino
        user: usuario que consulta el preview

    Returns:
        dict con keys: permitido, razones_bloqueo, side_effects,
        documentos_faltantes, predicados_fallidos, aprobadores_requeridos,
        historial_reciente
    """
    from sinpapel.services.workflow_engine import WorkflowEngine

    return WorkflowEngine().preview_transition(self, target_state_name, user)
