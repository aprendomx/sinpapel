"""Tests audit trail de VersionFlujo."""
from __future__ import annotations

import pytest

from sinpapel.models.workflow import VersionFlujo


@pytest.mark.django_db
def test_version_flujo_create_appends_history():
    """Crear VersionFlujo deja 1 entrada history."""
    vf = VersionFlujo.objects.create(nombre="Flujo v1", activo=False)
    assert vf.history.count() == 1
    assert vf.history.first().history_type == "+"
    assert vf.history.first().activo is False


@pytest.mark.django_db
def test_version_flujo_activate_appends_update():
    """Activar VersionFlujo genera entrada '~' con activo=True."""
    vf = VersionFlujo.objects.create(nombre="Flujo v2", activo=False)
    vf.activo = True
    vf.descripcion = "Activado para producción"
    vf.save()

    assert vf.history.count() == 2
    latest = vf.history.first()
    assert latest.history_type == "~"
    assert latest.activo is True
    diff = latest.diff_against(vf.history.last())
    fields_changed = {c.field for c in diff.changes}
    assert "activo" in fields_changed
    assert "descripcion" in fields_changed
