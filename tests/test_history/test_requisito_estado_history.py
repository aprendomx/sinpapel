"""Tests audit trail de RequisitoEstadoDocumento."""
from __future__ import annotations

import pytest

from sinpapel.models.documents import TipoDocumento
from sinpapel.models.workflow import Estado, RequisitoEstadoDocumento


@pytest.mark.django_db
def test_requisito_estado_create_appends_history():
    """Crear RequisitoEstadoDocumento deja 1 entrada history."""
    estado = Estado.objects.create(nombre="Estado X", activo=True)
    tipo = TipoDocumento.objects.create(nombre="Tipo Y", activo=True)
    req = RequisitoEstadoDocumento.objects.create(
        estado=estado, tipo_documento=tipo, porcentaje=80
    )
    assert req.history.count() == 1
    assert req.history.first().porcentaje == 80


@pytest.mark.django_db
def test_requisito_estado_delete_appends_history():
    """Eliminar RequisitoEstadoDocumento deja entrada history_type='-'."""
    estado = Estado.objects.create(nombre="Estado Z", activo=True)
    tipo = TipoDocumento.objects.create(nombre="Tipo W", activo=True)
    req = RequisitoEstadoDocumento.objects.create(
        estado=estado, tipo_documento=tipo, porcentaje=50
    )
    pk = req.pk
    req.delete()

    history = RequisitoEstadoDocumento.history.filter(id=pk).order_by("-history_date")
    assert history.count() == 2
    assert history.first().history_type == "-"
    assert history.last().history_type == "+"
