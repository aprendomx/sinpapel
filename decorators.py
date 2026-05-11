"""Sinpapel — @workflow_enabled decorator.

Decorator factory que marca un modelo Django como elegible para el motor de
workflow dinámico (ADR-007). Valida campos requeridos, registra en
WorkflowRegistry, e inyecta 3 métodos uniformes.

Uso:
    @workflow_enabled(state_field="estado", workflow_key="solicitud")
    class Solicitud(Trazable):
        estado = models.ForeignKey(Estado, ...)

Tras decorar:
    s = Solicitud.objects.first()
    s.available_transitions(user)  # lista de Estado destino válidos
    s.can_transition_to("X", user)  # (bool, str | None)
    s.transition("X", user, comentarios="...")  # ejecuta transición
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from django.core.exceptions import FieldDoesNotExist

from sinpapel.exceptions import WorkflowConfigurationError
from sinpapel.injection import available_transitions, can_transition_to, transition
from sinpapel.registry import WorkflowConfig, WorkflowRegistry

if TYPE_CHECKING:
    from django.db import models


# S13.4: endpoint_slug debe ser URL-safe (kebab-case lowercase + digits + hyphens)
_SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")


def workflow_enabled(
    *,
    state_field: str,
    workflow_key: str,
    version_field: str | None = None,
    expose_endpoints: bool = False,
    endpoint_slug: str | None = None,
):
    """Marca un modelo Django como elegible para el motor de workflow dinámico.

    Args:
        state_field: nombre del FK al modelo sinpapel.Estado (ej. "estado")
        workflow_key: identificador único del workflow (ej. "solicitud",
                      "tramite_sep"). Debe ser único en el proyecto.
        version_field: nombre opcional del FK a sinpapel.VersionFlujo. Si None,
                      el motor resuelve flujo activo por otra vía (ej. via Producto
                      en el caso de Solicitud).
        expose_endpoints: S13.4 — si True, el modelo se incluye en
                      `WorkflowRegistry.list_exposed()` y sinpapel-drf auto-genera
                      endpoints REST `/sinpapel/api/<slug>/<pk>/{action}/`.
                      Default False preserva backward compat.
        endpoint_slug: S13.4 — URL slug para los endpoints generados (kebab-case,
                      [a-z0-9-]+). Si None, default = workflow_key + 's'.

    Raises:
        WorkflowConfigurationError: state_field o version_field no existen en el modelo,
                                    O endpoint_slug no es URL-safe ([a-z0-9-]+)
        WorkflowDuplicateKeyError: workflow_key ya está registrado por otro modelo

    Returns:
        decorator function que retorna la clase decorada (sin alterar la clase
        más allá de inyectar métodos)
    """
    # S13.4 (D9): validar endpoint_slug en factory time, antes del decorator wrapper
    if endpoint_slug is not None and not _SLUG_PATTERN.match(endpoint_slug):
        raise WorkflowConfigurationError(
            f"endpoint_slug '{endpoint_slug}' must match [a-z0-9-]+ "
            f"(only lowercase letters, digits, hyphens; URL-safe kebab-case)"
        )

    def decorator(model_class: type["models.Model"]) -> type["models.Model"]:
        # 1. Validar campos requeridos
        try:
            model_class._meta.get_field(state_field)
        except FieldDoesNotExist as e:
            raise WorkflowConfigurationError(
                f"Model {model_class.__name__} has no field '{state_field}' "
                f"(required by @workflow_enabled state_field=)"
            ) from e

        if version_field is not None:
            try:
                model_class._meta.get_field(version_field)
            except FieldDoesNotExist as e:
                raise WorkflowConfigurationError(
                    f"Model {model_class.__name__} has no field '{version_field}' "
                    f"(required by @workflow_enabled version_field=)"
                ) from e

        # 2. Registrar en singleton
        config = WorkflowConfig(
            model=model_class,
            state_field=state_field,
            workflow_key=workflow_key,
            version_field=version_field,
            expose_endpoints=expose_endpoints,
            endpoint_slug=endpoint_slug,
        )
        WorkflowRegistry.register(workflow_key, config)

        # 3. Inyectar métodos + storage del config en la clase
        model_class._workflow_config = config  # type: ignore[attr-defined]
        model_class.available_transitions = available_transitions  # type: ignore[attr-defined]
        model_class.can_transition_to = can_transition_to  # type: ignore[attr-defined]
        model_class.transition = transition  # type: ignore[attr-defined]

        return model_class

    return decorator
