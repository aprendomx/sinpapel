"""Test-only models for sinpapel integration tests.

These models are registered under the 'tests' app so workflow engine
tests do not depend on the creditos monolith.
"""
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from sinpapel import workflow_enabled
from sinpapel.mixins import Trazable
from sinpapel.models import Estado, VersionFlujo


@workflow_enabled(state_field="estado", workflow_key="test_solicitud")
class TestSolicitud(Trazable):
    folio = models.CharField(max_length=50, unique=True)
    estado = models.ForeignKey(
        Estado,
        on_delete=models.CASCADE,
        null=True,
    )
    producto = models.ForeignKey(
        "TestProducto",
        on_delete=models.CASCADE,
        null=True,
    )

    # GenericRelation expected by engine for expediente_obligatorio check
    expedientes = GenericRelation(
        "sinpapel.ExpedienteAdjunto",
        content_type_field="target_content_type",
        object_id_field="target_object_id",
    )

    def resolve_workflow_version(self):
        if self.producto_id and hasattr(self.producto, "flujo"):
            return self.producto.flujo
        return VersionFlujo.objects.filter(activo=True).first()

    class Meta:
        app_label = "tests"


class TestProducto(models.Model):
    nombre = models.CharField(max_length=100)
    flujo = models.ForeignKey(
        VersionFlujo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        app_label = "tests"


class TestProductoVersionFlujo(models.Model):
    producto = models.ForeignKey(TestProducto, on_delete=models.CASCADE)
    flujo = models.ForeignKey(VersionFlujo, on_delete=models.CASCADE)

    class Meta:
        app_label = "tests"
