"""Sinpapel — Workflow models.

Estado, VersionFlujo, ConfiguracionTransicion, SeguimientoWorkflow,
RequisitoEstadoDocumento extraídos desde creditos en S12.2/T2 preservando
tablas SQL existentes vía db_table override.
"""
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from simple_history.models import HistoricalRecords
from sinpapel.mixins import Catalogo, Trazable


class Etapa(Catalogo):
    """Grupo de estados que representa una etapa del trámite."""

    class Meta:
        db_table = "creditos_etapa"
        app_label = "sinpapel"
        verbose_name = "Etapa"
        verbose_name_plural = "Etapas"
        ordering = ["orden"]


class Estado(Catalogo):
    etapa = models.ForeignKey(
        "sinpapel.Etapa",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="estados",
        verbose_name="Etapa",
    )
    permite_expediente: models.BooleanField = models.BooleanField(
        default=False,
        verbose_name="Permite expediente adjunto",
        help_text="Indica si se pueden adjuntar documentos mientras el trámite está en este estado.",
    )
    expediente_obligatorio: models.BooleanField = models.BooleanField(
        default=False,
        verbose_name="Expediente obligatorio",
        help_text="Si es True, debe adjuntarse al menos un expediente antes de avanzar al siguiente estado.",
    )
    icono: models.CharField = models.CharField(
        max_length=80,
        blank=True,
        default="circle",
        verbose_name="Ícono (Material Design)",
        help_text="Nombre del ícono de Material Design / Quasar (ej. check_circle, cancel).",
    )

    class Meta:
        db_table = "creditos_estado"
        app_label = "sinpapel"
        verbose_name = "Estado"
        verbose_name_plural = "Estados"
        ordering = ["orden"]


class VersionFlujo(models.Model):
    """
    Versión versionada de un flujo de aprobación configurable desde admin.

    Un VersionFlujo define el conjunto de transiciones permitidas y qué grupos
    pueden ejecutarlas. Puede activarse o desactivarse globalmente (ADR-007).
    """

    nombre: models.CharField = models.CharField(max_length=100, verbose_name="Nombre")
    descripcion: models.TextField = models.TextField(blank=True, verbose_name="Descripción")
    activo: models.BooleanField = models.BooleanField(
        default=False,
        verbose_name="Activo",
        help_text="Desactivar retira el flujo de todos los productos asignados (fallback al dict).",
    )
    metadatos: models.JSONField = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Metadatos",
        help_text="Posiciones de nodos en el canvas: {positions: {estado_id: {x, y}}}",
    )
    creado: models.DateTimeField = models.DateTimeField(auto_now_add=True, verbose_name="Creado en")
    creado_por: models.ForeignKey = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Creado por",
    )

    history = HistoricalRecords()

    class Meta:
        db_table = "creditos_versionflujo"
        app_label = "sinpapel"
        verbose_name = "Versión de Flujo"
        verbose_name_plural = "Versiones de Flujo"

    def __str__(self) -> str:
        estado = "activo" if self.activo else "inactivo"
        return f"{self.nombre} ({estado})"


class ConfiguracionTransicion(models.Model):
    """
    Transición entre dos estados dentro de un VersionFlujo.

    Define qué grupos Django pueden ejecutar la transición de estado_origen
    a estado_destino. Si grupos_permitidos está vacío, cualquier usuario puede
    ejecutarla (sin restricción de grupo).
    """

    flujo: models.ForeignKey = models.ForeignKey(
        VersionFlujo,
        on_delete=models.CASCADE,
        related_name="transiciones",
        verbose_name="Versión de Flujo",
    )
    estado_origen: models.ForeignKey = models.ForeignKey(
        Estado,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="Estado origen",
    )
    estado_destino: models.ForeignKey = models.ForeignKey(
        Estado,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="Estado destino",
    )
    grupos_permitidos: models.ManyToManyField = models.ManyToManyField(
        "auth.Group",
        blank=True,
        verbose_name="Grupos permitidos",
        help_text="Vacío = cualquier grupo puede ejecutar la transición.",
    )

    history = HistoricalRecords(m2m_fields=[grupos_permitidos])

    class Meta:
        db_table = "creditos_configuraciontransicion"
        app_label = "sinpapel"
        unique_together = [("flujo", "estado_origen", "estado_destino")]
        verbose_name = "Transición"
        verbose_name_plural = "Transiciones"

    def __str__(self) -> str:
        return f"{self.estado_origen} → {self.estado_destino}"


class SeguimientoWorkflow(Trazable):
    """
    Registro de cada acción/cambio de estado en un trámite.
    Proporciona trazabilidad completa del proceso de aprobación.

    Referencia al trámite vía GenericForeignKey `target` para soportar
    múltiples tipos de entidades workflow-enabled (S12.1 desacoplamiento).
    """

    target_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name="Tipo de entidad",
    )
    target_object_id = models.PositiveIntegerField(verbose_name="ID de entidad")
    target = GenericForeignKey("target_content_type", "target_object_id")

    # Reverse access para ExpedienteAdjunto.event que apunta a SeguimientoWorkflow
    expedientes = GenericRelation(
        "ExpedienteAdjunto",
        content_type_field="event_content_type",
        object_id_field="event_object_id",
    )

    estado_anterior = models.ForeignKey(
        Estado,
        on_delete=models.PROTECT,
        related_name="seguimientos_desde",
        verbose_name="Estado Anterior",
        null=True,
        blank=True,
    )

    estado_nuevo = models.ForeignKey(
        Estado,
        on_delete=models.PROTECT,
        related_name="seguimientos_hacia",
        verbose_name="Estado Nuevo",
    )

    usuario_accion = models.ForeignKey(
        "auth.User",
        on_delete=models.PROTECT,
        related_name="acciones_solicitud",
        verbose_name="Usuario que realizó la acción",
    )

    fecha_accion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Acción")

    comentarios = models.TextField(
        verbose_name="Comentarios/Justificación",
        help_text="Justificación de la decisión tomada",
    )

    documentos_adjuntos = models.JSONField(
        blank=True,
        null=True,
        default=list,
        verbose_name="Documentos Adjuntos",
        help_text="Lista de documentos asociados a esta acción",
    )

    monto_aprobado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Monto Aprobado",
        help_text="Monto aprobado (puede diferir del solicitado)",
    )

    condiciones = models.TextField(
        blank=True,
        null=True,
        verbose_name="Condiciones",
        help_text="Condiciones para la aprobación (si aplica)",
    )

    ip_address = models.GenericIPAddressField(verbose_name="Dirección IP", null=True, blank=True)

    firma_registro = models.OneToOneField(
        "sinpapel.RegistroFirma",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seguimiento",
        verbose_name="Registro de Firma",
        help_text="Evidencia criptográfica de la firma electrónica (si se firmó)",
    )

    class Meta:
        db_table = "creditos_seguimientoworkflow"
        app_label = "sinpapel"
        verbose_name = "Seguimiento de Workflow"
        verbose_name_plural = "Seguimientos de Workflow"
        ordering = ["-fecha_accion"]
        indexes = [
            models.Index(
                fields=["target_content_type", "target_object_id", "-fecha_accion"],
                name="seg_workflow_target_idx",
            ),
            models.Index(fields=["estado_nuevo", "fecha_accion"]),
            models.Index(fields=["usuario_accion", "-fecha_accion"]),
        ]

    def __str__(self):
        anterior = self.estado_anterior.nombre if self.estado_anterior else "Nuevo"
        target_label = getattr(self.target, "folio", None) or str(self.target)
        return f"{target_label}: {anterior} → {self.estado_nuevo.nombre}"


class RequisitoEstadoDocumento(Trazable):
    """Requisito documental por estado: qué tipo de documento y porcentaje mínimo
    debe tener un trámite para poder transitar a un estado destino."""

    estado: models.ForeignKey = models.ForeignKey(
        Estado,
        on_delete=models.CASCADE,
        related_name="requisitos_documentales",
    )
    tipo_documento: models.ForeignKey = models.ForeignKey(
        "sinpapel.TipoDocumento",
        on_delete=models.CASCADE,
        related_name="requisitos_estado",
    )
    porcentaje: models.IntegerField = models.IntegerField(
        default=100,
        help_text="Porcentaje mínimo requerido (0-100)",
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    auto_carga: models.BooleanField = models.BooleanField(default=False)

    history = HistoricalRecords()

    class Meta:
        db_table = "creditos_requisitoestadodocumento"
        app_label = "sinpapel"
        unique_together = [["estado", "tipo_documento"]]
        verbose_name = "Requisito Estado-Documento"
        verbose_name_plural = "Requisitos Estado-Documento"

    def __str__(self) -> str:
        return f"{self.estado.nombre} → {self.tipo_documento.nombre} ({self.porcentaje}%)"
