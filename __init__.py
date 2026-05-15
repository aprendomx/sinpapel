"""Sinpapel — Trámites y Workflow reutilizable.

WorkflowEngine se importa explícitamente desde sinpapel.services.workflow_engine
(no re-exportado aquí porque carga sinpapel.models y rompería el import order
durante Django app loading).
"""
from sinpapel.decorators import workflow_enabled
from sinpapel.exceptions import (
    SinpapelError,
    WorkflowConfigurationError,
    WorkflowDuplicateKeyError,
)
from sinpapel.registry import WorkflowConfig, WorkflowRegistry

__version__ = "0.2.0"

__all__ = [
    "SinpapelError",
    "WorkflowConfigurationError",
    "WorkflowDuplicateKeyError",
    "WorkflowConfig",
    "WorkflowRegistry",
    "workflow_enabled",
    "__version__",
]
