"""Sinpapel — Transition Predicate model.

CondicionTransicion stores configurable business rules evaluated
before a workflow transition is permitted.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class CondicionTransicion(models.Model):
    """Condición configurable para una ConfiguracionTransicion.

    Evaluada por PredicateEngine antes de permitir una transición.
    Todas las condiciones activas deben pasar (AND lógico).
    """

    TIPO_CHOICES = [
        ("python_path", _("Python Path")),
        ("json_logic", _("JSON Logic")),
        ("django_orm", _("Django ORM Lookup")),
    ]

    transicion = models.ForeignKey(
        "sinpapel.ConfiguracionTransicion",
        on_delete=models.CASCADE,
        related_name="condiciones",
        verbose_name=_("Transición"),
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        verbose_name=_("Tipo de condición"),
    )
    configuracion = models.JSONField(
        verbose_name=_("Configuración"),
        help_text=_("Parámetros específicos del backend."),
    )
    mensaje_error = models.CharField(
        max_length=250,
        default=_("No cumple con las condiciones requeridas."),
        verbose_name=_("Mensaje de error"),
    )
    orden = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Orden de evaluación"),
    )
    activo = models.BooleanField(
        default=True,
        verbose_name=_("Activo"),
    )

    class Meta:
        db_table = "sinpapel_condiciontransicion"
        app_label = "sinpapel"
        ordering = ["orden"]
        verbose_name = _("Condición de Transición")
        verbose_name_plural = _("Condiciones de Transición")

    def __str__(self) -> str:
        return f"Condicion #{self.orden} ({self.tipo})"
