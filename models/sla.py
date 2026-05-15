"""Sinpapel — SLA configuration model.

SLAConfiguracion defines time limits and actions for workflow states.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class SLAConfiguracion(models.Model):
    """Configuración de SLA por estado: tiempo máximo y acción al vencer."""

    ACCION_CHOICES = [
        ("notificar", _("Notificar")),
        ("escalar", _("Escalar")),
        ("rechazar", _("Rechazar")),
        ("alertar", _("Alertar / Bandera")),
    ]

    estado = models.ForeignKey(
        "sinpapel.Estado",
        on_delete=models.CASCADE,
        related_name="slas",
        verbose_name=_("Estado"),
    )
    dias_maximos = models.PositiveIntegerField(
        verbose_name=_("Días máximos"),
        help_text=_("Tiempo máximo permitido en este estado antes de ejecutar la acción."),
    )
    accion_vencimiento = models.CharField(
        max_length=20,
        choices=ACCION_CHOICES,
        verbose_name=_("Acción al vencer"),
    )
    configuracion_accion = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Configuración de acción"),
        help_text=_("Parámetros específicos de la acción (ver documentación)."),
    )
    activo = models.BooleanField(
        default=True,
        verbose_name=_("Activo"),
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sinpapel_sla_configuracion"
        app_label = "sinpapel"
        verbose_name = _("Configuración SLA")
        verbose_name_plural = _("Configuraciones SLA")
        unique_together = [["estado", "accion_vencimiento"]]

    def __str__(self) -> str:
        return f"{self.estado.nombre}: {self.dias_maximos}d → {self.accion_vencimiento}"
