"""Sinpapel — Documents models.

TipoDocumento, Documento, InstanciaDocumento, RazonRechazoDocumento
extraídos desde creditos en S12.2/T2 preservando tablas SQL existentes.
"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import TextField

from simple_history.models import HistoricalRecords
from sinpapel.mixins import Catalogo, Trazable


class TipoDocumento(Catalogo):
    class Meta:
        db_table = "sinpapel_tipodocumento"
        app_label = "sinpapel"
        verbose_name = _("Tipo de Documento")
        verbose_name_plural = _("Tipos de Documento")
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
        verbose_name=_("Tipo de Plantilla"),
    )
    configuracion_overlay = models.JSONField(
        blank=True,
        null=True,
        default=dict,
        verbose_name=_("Configuración de Overlay PDF"),
        help_text=_("Configuración de campos visibles y posiciones en el overlay PDF"),
    )

    class Meta:
        db_table = "sinpapel_documento"
        app_label = "sinpapel"
        verbose_name = _("Documento")
        verbose_name_plural = _("Documentos")


class InstanciaDocumento(Trazable):
    documento = models.ForeignKey(Documento, null=True, on_delete=models.CASCADE)

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Tipo de entidad"),
    )
    target_object_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("ID de entidad")
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
        verbose_name=_("Tipo de actor"),
    )
    actor_object_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("ID de actor")
    )
    actor = GenericForeignKey("actor_content_type", "actor_object_id")

    metadatos = models.JSONField(blank=True, null=True)

    porcentaje: models.IntegerField = models.IntegerField(
        default=100,
        verbose_name=_("Porcentaje de completitud"),
        help_text=_(
            "Porcentaje de completitud del documento (0-100). Se compara contra "
            "RequisitoEstadoDocumento.porcentaje al evaluar una transición. "
            "Default 100 (documento completo) para backward-compatibility."
        ),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    history = HistoricalRecords()

    class Meta:
        db_table = "sinpapel_instanciadocumento"
        app_label = "sinpapel"
        verbose_name = _("Instancia de Documento")
        verbose_name_plural = _("Instancias de Documentos")
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
        db_table = "sinpapel_razonrechazodocumento"
        app_label = "sinpapel"
        verbose_name = _("Razón de Rechazo de Documento")
        verbose_name_plural = _("Razones de Rechazo de Documento")
        ordering = ["clave"]

    def __str__(self) -> str:
        return f"{self.clave}: {self.descripcion}"
