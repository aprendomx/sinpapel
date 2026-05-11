"""Sinpapel — App config.

Trámites/workflow reusable extraído desde creditos (E12). Modelos viven en
sinpapel.models pero las tablas SQL siguen siendo `creditos_*` durante la
extracción (S12.2 vía db_table override; rename diferido a parking lot).
"""
from django.apps import AppConfig


class SinpapelConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sinpapel"
    verbose_name = "Sinpapel — Trámites y Workflow"

    def ready(self):
        # S13.2: registrar signal handlers para invalidación de cache
        # (post_save/post_delete/m2m_changed sobre Estado/VersionFlujo/
        # ConfigT/RequisitoEstadoDocumento)
        from sinpapel import signals  # noqa: F401  side-effect: registers receivers
