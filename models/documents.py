"""Sinpapel — Documents models.

TipoDocumento, Documento, InstanciaDocumento, RazonRechazoDocumento
extraídos desde creditos en S12.2/T2 preservando tablas SQL existentes.
"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import TextField

from simple_history.models import HistoricalRecords
from trazable.models import Catalogo, Trazable


class TipoDocumento(Catalogo):
    class Meta:
        db_table = "creditos_tipodocumento"
        app_label = "sinpapel"
        verbose_name = "Tipo de Documento"
        verbose_name_plural = "Tipos de Documento"
        ordering = ["id"]


class Documento(Catalogo):
    tipo_documento = models.ForeignKey(
        TipoDocumento, null=True, on_delete=models.CASCADE
    )
    valor = models.CharField(max_length=100)
    contenido = TextField(blank=True, null=True)
    plantilla = models.FileField(upload_to="plantillas/", blank=True, null=True)
    # producto FK removida en S12.1/T7 — la asociación producto↔documento vive
    # ahora en ProductoDocumentoCredito (creditos-específico).
    tipo_plantilla = models.CharField(
        max_length=10,
        choices=[("DOCX", "Word"), ("PDF", "PDF")],
        default="DOCX",
        verbose_name="Tipo de Plantilla",
    )
    configuracion_overlay = models.JSONField(
        blank=True,
        null=True,
        default=dict,
        verbose_name="Configuración de Overlay PDF",
        help_text="Configuración de campos visibles y posiciones en el overlay PDF",
    )

    class Meta:
        db_table = "creditos_documento"
        app_label = "sinpapel"
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"


class InstanciaDocumento(Trazable):
    documento = models.ForeignKey(Documento, null=True, on_delete=models.CASCADE)

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Tipo de entidad",
    )
    target_object_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de entidad"
    )
    target = GenericForeignKey("target_content_type", "target_object_id")

    archivo_generado = models.FileField(
        upload_to="documentos_generados/", blank=True, null=True
    )

    actor_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Tipo de actor",
    )
    actor_object_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de actor"
    )
    actor = GenericForeignKey("actor_content_type", "actor_object_id")

    metadatos = models.JSONField(blank=True, null=True)

    history = HistoricalRecords()

    class Meta:
        db_table = "creditos_instanciadocumento"
        app_label = "sinpapel"
        verbose_name = "Instancia de Documento"
        verbose_name_plural = "Instancias de Documentos"
        indexes = [
            models.Index(fields=["target_content_type", "target_object_id"], name="inst_doc_target_idx"),
            models.Index(fields=["actor_content_type", "actor_object_id"], name="inst_doc_actor_idx"),
        ]


class RazonRechazoDocumento(Trazable):
    """Catálogo de razones de rechazo para documentos."""

    clave: models.CharField = models.CharField(max_length=30, unique=True)
    descripcion: models.CharField = models.CharField(max_length=200)
    activa: models.BooleanField = models.BooleanField(default=True)

    class Meta:
        db_table = "creditos_razonrechazodocumento"
        app_label = "sinpapel"
        verbose_name = "Razón de Rechazo de Documento"
        verbose_name_plural = "Razones de Rechazo de Documento"
        ordering = ["clave"]

    def __str__(self) -> str:
        return f"{self.clave}: {self.descripcion}"
