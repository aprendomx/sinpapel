"""Sinpapel — WorkflowRegistry.

Singleton module-level que cataloga modelos workflow-enabled. Decoradores
@workflow_enabled registran su modelo aquí en class-creation time.

API:
    WorkflowRegistry.register(workflow_key, config)
    WorkflowRegistry.get(workflow_key) -> WorkflowConfig
    WorkflowRegistry.list_keys() -> list[str]
    WorkflowRegistry.unregister(workflow_key)  # útil para tests
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sinpapel.exceptions import WorkflowDuplicateKeyError

if TYPE_CHECKING:
    from django.db import models


@dataclass(frozen=True)
class WorkflowConfig:
    """Configuración de un modelo workflow-enabled.

    Frozen dataclass para inmutabilidad — una vez registrada, no se modifica.

    S13.4 (E13b): expose_endpoints + endpoint_slug habilitan auto-routing
    via SinpapelRouter (sinpapel-drf). Defaults preservan backward compat.
    """

    model: type[models.Model]
    state_field: str
    workflow_key: str
    version_field: str | None = None
    expose_endpoints: bool = False
    endpoint_slug: str | None = None

    @property
    def effective_slug(self) -> str:
        """endpoint_slug explícito o default pluralización (workflow_key + 's').

        Usado por SinpapelRouter para construir URL prefix
        (`/sinpapel/api/<effective_slug>/<pk>/...`).
        """
        return self.endpoint_slug or f"{self.workflow_key}s"


class _RegistryImpl:
    """Implementación del registry. No instanciar directamente — usar `WorkflowRegistry`."""

    def __init__(self) -> None:
        self._configs: dict[str, WorkflowConfig] = {}

    def register(self, workflow_key: str, config: WorkflowConfig) -> None:
        """Registra una configuración bajo workflow_key.

        Idempotente para el MISMO modelo. Raises si workflow_key ya está
        registrado por un modelo distinto.
        """
        existing = self._configs.get(workflow_key)
        if existing is not None:
            if existing.model is config.model:
                # Re-registro idempotente del mismo modelo (Django auto-reload, re-import en tests)
                return
            raise WorkflowDuplicateKeyError(
                f"workflow_key '{workflow_key}' already registered by "
                f"{existing.model.__name__}; cannot re-register for "
                f"{config.model.__name__}"
            )
        self._configs[workflow_key] = config

    def get(self, workflow_key: str) -> WorkflowConfig:
        """Recupera config por workflow_key. Raises KeyError si no existe."""
        return self._configs[workflow_key]

    def list_keys(self) -> list[str]:
        """Lista de workflow_keys registrados."""
        return list(self._configs.keys())

    def unregister(self, workflow_key: str) -> None:
        """Elimina entrada del registry. No-op si workflow_key no existe.

        Útil para tests que crean/destruyen modelos workflow-enabled dinámicamente.
        """
        self._configs.pop(workflow_key, None)

    def list_exposed(self) -> list[WorkflowConfig]:
        """S13.4: Retorna solo configs con expose_endpoints=True, sorted por workflow_key.

        Usado por SinpapelRouter (sinpapel-drf) para auto-registrar ViewSets.
        Sort estable garantiza orden determinista en URL patterns.
        """
        return sorted(
            (c for c in self._configs.values() if c.expose_endpoints),
            key=lambda c: c.workflow_key,
        )


# Singleton module-level
WorkflowRegistry = _RegistryImpl()
