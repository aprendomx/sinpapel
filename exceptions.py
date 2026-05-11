"""Sinpapel — Exceptions específicas del paquete."""


class SinpapelError(Exception):
    """Base exception para errores del paquete sinpapel."""


class WorkflowConfigurationError(SinpapelError, ValueError):
    """Raised cuando la configuración de @workflow_enabled es inválida.

    Casos:
    - state_field no existe en el modelo decorado
    - version_field se especifica pero no existe en el modelo
    """


class WorkflowDuplicateKeyError(SinpapelError, ValueError):
    """Raised cuando se intenta registrar dos modelos distintos con el mismo workflow_key.

    Permitido: re-registrar el MISMO modelo con la misma key (idempotente,
    útil cuando Django re-importa módulos en dev auto-reload).
    """
