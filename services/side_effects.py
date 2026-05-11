"""Sinpapel — Side-effects registry + dispatch (ADR-004).

Pattern: dict-based registry de handlers indexados por nombre de estado.
Handlers concretos registran via SIDE_EFFECTS["NOMBRE"] = handler o vía
@register_side_effect("NOMBRE") decorator.

ADR-004 garantía clave: errores de handler se loggean pero NO se re-raisen
porque el cambio de estado ya commiteó (transacción atómica del WorkflowEngine).
Re-raisear rompería invariantes posteriores.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

SideEffectHandler = Callable[..., dict[str, Any]]

# Registry global. Handlers concretos lo poblan al cargar
# (creditos.services.workflow_side_effects en E12).
SIDE_EFFECTS: dict[str, SideEffectHandler] = {}


def register_side_effect(estado_nombre: str) -> Callable[[SideEffectHandler], SideEffectHandler]:
    """Decorator para registrar un handler en SIDE_EFFECTS.

    Uso:
        @register_side_effect("DISPERSADA")
        def _handle_dispersada(instance, user, **kwargs) -> dict:
            ...

    Args:
        estado_nombre: nombre del Estado destino que dispara el handler.

    Returns:
        decorator function que retorna el handler sin modificar.
    """

    def decorator(handler: SideEffectHandler) -> SideEffectHandler:
        SIDE_EFFECTS[estado_nombre] = handler
        return handler

    return decorator


def ejecutar_side_effects(
    estado_nombre: str,
    instance: Any,
    usuario: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Ejecuta el handler registrado para estado_nombre, si existe.

    ADR-004: errores son loggeados pero NO re-raised — la transición ya
    commiteó atómicamente y romper aquí dejaría estado inconsistente.

    Args:
        estado_nombre: nombre del Estado destino post-transición.
        instance: la instancia que transicionó (cualquier modelo workflow-enabled).
        usuario: User que ejecutó la transición.
        **kwargs: parámetros adicionales pasados al handler (ej. monto_aprobado).

    Returns:
        dict del handler si existe y retorna dict; {} si no hay handler;
        {"error": True, "estado": estado_nombre} si el handler levantó excepción.
    """
    handler = SIDE_EFFECTS.get(estado_nombre)
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
