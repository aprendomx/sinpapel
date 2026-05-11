"""Sinpapel — Firmas digitales (backend-agnostic).

RegistroFirma extraído desde creditos en S12.2 preservando la tabla SQL
`creditos_registrofirma` vía db_table override. El schema agnóstico de
backend (backend_name + backend_metadata JSON) fue establecido en S12.1/T6.
"""
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from simple_history.models import HistoricalRecords


class RegistroFirma(models.Model):
    """
    Registro inmutable de una firma electrónica.
    Backend-agnostic — los detalles específicos del backend (FIEL, PAdES, manual,
    DocuSign, etc.) viven en backend_metadata como JSON.

    No hereda Trazable — es de solo lectura una vez creado.
    """

    RESULTADO_CHOICES: list[tuple[str, str]] = [
        ("VALIDA", "Válida"),
        ("INVALIDA", "Inválida"),
        ("PENDIENTE", "Pendiente de verificación"),
    ]

    backend_name = models.CharField(
        max_length=50,
        default="fiel",
        verbose_name="Backend",
        help_text="Identificador del backend de firma (fiel, pades, docusign, manual, etc.)",
    )
    backend_metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadata del Backend",
        help_text="Datos específicos del backend (FIEL: pkcs7, cert, rfc, serie; etc.)",
    )

    signer = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="firmas",
        verbose_name="Firmante (User)",
        help_text="Usuario interno que firmó. NULL si la firma es externa.",
    )
    signer_display_name = models.CharField(
        max_length=255,
        verbose_name="Nombre del Firmante",
        help_text="Nombre del firmante para visualización (puede no coincidir con User.get_full_name).",
    )

    # Target opcional — algunos backends/casos vinculan la firma a una entidad específica
    target_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Tipo de entidad firmada",
    )
    target_object_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID de entidad firmada"
    )
    target = GenericForeignKey("target_content_type", "target_object_id")

    content_hash = models.CharField(
        max_length=128,
        verbose_name="Hash del contenido firmado",
        help_text="SHA-256 hex del payload canónico firmado",
    )
    is_required = models.BooleanField(
        default=False,
        verbose_name="¿Firma requerida?",
        help_text="True si la transición exigía firma obligatoria",
    )
    verification_result = models.CharField(
        max_length=10,
        choices=RESULTADO_CHOICES,
        default="PENDIENTE",
        verbose_name="Resultado de validación",
    )
    signed_at = models.DateTimeField(
        verbose_name="Timestamp de firma",
        help_text="Momento en que se realizó la firma (según el cliente)",
    )

    history = HistoricalRecords()

    class Meta:
        # Preserva tabla SQL existente — extracción a sinpapel sin data migration
        db_table = "sinpapel_registrofirma"
        app_label = "sinpapel"
        verbose_name = "Registro de Firma"
        verbose_name_plural = "Registros de Firma"
        indexes = [
            models.Index(fields=["target_content_type", "target_object_id"]),
            models.Index(fields=["signer", "-signed_at"]),
        ]

    def __str__(self) -> str:
        return f"Firma {self.signer_display_name} [{self.backend_name}/{self.verification_result}]"
