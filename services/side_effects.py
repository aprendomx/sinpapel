"""Sinpapel — Side-effects registry + dispatch (ADR-004).

Pattern: dict-based registry de handlers indexados por nombre de estado,
con scoping opcional por workflow_key (0.8.1): dos flujos con un estado
homónimo pueden tener handlers distintos.

- Global (compat): SIDE_EFFECTS["NOMBRE"] = handler o
  @register_side_effect("NOMBRE") — aplica a cualquier flujo.
- Scoped: @register_side_effect("NOMBRE", workflow_key="mi_flujo") — solo
  ese flujo. En el dispatch, el handler scoped tiene precedencia sobre el
  global.

ADR-004 garantía clave: errores de handler se loggean pero NO se re-raisen.
El WorkflowEngine ejecuta los side effects DESPUÉS de commitear su
transacción: la transición ya persistió, y un handler fallido no debe (ni
puede) revertirla. Los handlers deben ser idempotentes o tolerar reintentos
externos.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

SideEffectHandler = Callable[..., dict[str, Any]]

# Registry global (aplica a cualquier flujo). Handlers concretos lo poblan
# al cargar (creditos.services.workflow_side_effects en E12).
SIDE_EFFECTS: dict[str, SideEffectHandler] = {}

# Registry scoped por flujo: {(workflow_key, estado_nombre): handler}.
SIDE_EFFECTS_SCOPED: dict[tuple[str, str], SideEffectHandler] = {}


def register_side_effect(
    estado_nombre: str,
    workflow_key: str | None = None,
) -> Callable[[SideEffectHandler], SideEffectHandler]:
    """Decorator para registrar un handler de side effect.

    Uso:
        @register_side_effect("DISPERSADA")                      # global
        @register_side_effect("DISPERSADA", workflow_key="pyme") # solo pyme
        def _handle_dispersada(instance, user, **kwargs) -> dict:
            ...

    Args:
        estado_nombre: nombre del Estado destino que dispara el handler.
        workflow_key: opcional — limita el handler a ese flujo. El handler
            scoped tiene precedencia sobre el global en el dispatch.

    Returns:
        decorator function que retorna el handler sin modificar.
    """

    def decorator(handler: SideEffectHandler) -> SideEffectHandler:
        if workflow_key is None:
            SIDE_EFFECTS[estado_nombre] = handler
        else:
            SIDE_EFFECTS_SCOPED[(workflow_key, estado_nombre)] = handler
        return handler

    return decorator


def resolver_handler(
    estado_nombre: str,
    workflow_key: str | None = None,
) -> SideEffectHandler | None:
    """Resuelve el handler aplicable: scoped por flujo primero, global después."""
    if workflow_key is not None:
        handler = SIDE_EFFECTS_SCOPED.get((workflow_key, estado_nombre))
        if handler is not None:
            return handler
    return SIDE_EFFECTS.get(estado_nombre)


def ejecutar_side_effects(
    estado_nombre: str,
    instance: Any,
    usuario: Any,
    workflow_key: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Ejecuta el handler registrado para estado_nombre, si existe.

    ADR-004: errores son loggeados pero NO re-raised — la transición ya
    commiteó atómicamente y romper aquí dejaría estado inconsistente.

    Args:
        estado_nombre: nombre del Estado destino post-transición.
        instance: la instancia que transicionó (cualquier modelo workflow-enabled).
        usuario: User que ejecutó la transición.
        workflow_key: opcional — habilita el lookup scoped por flujo.
        **kwargs: parámetros adicionales pasados al handler (ej. condiciones).

    Returns:
        dict del handler si existe y retorna dict; {} si no hay handler;
        {"error": True, "estado": estado_nombre} si el handler levantó excepción.
    """
    handler = resolver_handler(estado_nombre, workflow_key)
    if handler is None:
        return {}

    try:
        result = handler(instance, usuario, **kwargs)
        return result if isinstance(result, dict) else {}
    except Exception:
        logger.exception(
            "Side-effect error for state %s on instance %s",
            estado_nombre,
            getattr(instance, "id", "?"),
        )
        return {"error": True, "estado": estado_nombre}
