"""Tests audit trail de InstanciaDocumento."""
from __future__ import annotations

import pytest

from sinpapel.models.documents import Documento, InstanciaDocumento, TipoDocumento


@pytest.mark.django_db
def test_instancia_documento_create_appends_history_entry():
    """Crear InstanciaDocumento deja 1 entrada history con history_type='+'."""
    tipo = TipoDocumento.objects.create(nombre="Test Tipo", activo=True)
    doc = Documento.objects.create(
        nombre="Test Doc", tipo_documento=tipo, valor="test", activo=True
    )
    inst = InstanciaDocumento.objects.create(documento=doc, metadatos={"v": 1})
    assert inst.history.count() == 1
    assert inst.history.first().history_type == "+"


@pytest.mark.django_db
def test_instancia_documento_update_metadatos_appends_history():
    """Actualizar metadatos genera entrada '~' con diff."""
    tipo = TipoDocumento.objects.create(nombre="Test Tipo 2", activo=True)
    doc = Documento.objects.create(
        nombre="Test Doc 2", tipo_documento=tipo, valor="test2", activo=True
    )
    inst = InstanciaDocumento.objects.create(documento=doc, metadatos={"v": 1})
    inst.metadatos = {"v": 2, "rotated": True}
    inst.save()

    assert inst.history.count() == 2
    latest = inst.history.first()
    assert latest.history_type == "~"
    diff = latest.diff_against(inst.history.last())
    assert "metadatos" in {c.field for c in diff.changes}
