"""Sinpapel — Attachments models.

ExpedienteAdjunto extraído desde creditos en S12.2/T2 preservando tabla
SQL existente.
"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from trazable.models import Trazable


class ExpedienteAdjunto(Trazable):
    """
    Archivo adjunto a un trámite (Solicitud u otra entidad workflow-enabled),
    asociado opcionalmente a un evento/seguimiento.

    Un estado puede requerir que se adjunte al menos un expediente antes de avanzar
    (Estado.expediente_obligatorio).
    """

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="Tipo de entidad",
    )
    target_object_id = models.PositiveIntegerField(verbose_name="ID de entidad")
    target = GenericForeignKey("target_content_type", "target_object_id")

    event_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Tipo de evento",
    )
    event_object_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de evento"
    )
    event = GenericForeignKey("event_content_type", "event_object_id")

    nombre: models.CharField = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="Nombre del documento",
        help_text="Descripción breve del contenido del archivo.",
    )
    archivo: models.FileField = models.FileField(
        upload_to="expedientes/",
        verbose_name="Archivo",
    )

    class Meta:
        db_table = "creditos_expedienteadjunto"
        app_label = "sinpapel"
        verbose_name = "Expediente Adjunto"
        verbose_name_plural = "Expedientes Adjuntos"
        ordering = ["-creado"]
        indexes = [
            models.Index(fields=["target_content_type", "target_object_id"], name="exp_target_idx"),
        ]

    def __str__(self) -> str:
        nombre = self.nombre or "sin nombre"
        return f"{nombre} — {self.target_content_type.model} {self.target_object_id}"
