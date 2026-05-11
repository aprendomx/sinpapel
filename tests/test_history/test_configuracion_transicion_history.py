"""Tests audit trail de ConfiguracionTransicion."""
from __future__ import annotations

import pytest
from django.contrib.auth.models import Group

from sinpapel.models.workflow import (
    ConfiguracionTransicion,
    Estado,
    VersionFlujo,
)


def _make_estados_y_flujo():
    flujo = VersionFlujo.objects.create(nombre="Test Flujo", activo=True)
    origen = Estado.objects.create(nombre="Origen", activo=True)
    destino = Estado.objects.create(nombre="Destino", activo=True)
    return flujo, origen, destino


@pytest.mark.django_db
def test_configuracion_transicion_create_appends_history():
    """Crear ConfiguracionTransicion deja 1 entrada history."""
    flujo, origen, destino = _make_estados_y_flujo()
    ct = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=origen, estado_destino=destino
    )
    assert ct.history.count() == 1
    assert ct.history.first().history_type == "+"


@pytest.mark.django_db
def test_configuracion_transicion_m2m_grupos_history():
    """Modificar grupos_permitidos (M2M) deja entrada en history del M2M."""
    flujo, origen, destino = _make_estados_y_flujo()
    grupo = Group.objects.create(name="Coordinadores")
    ct = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=origen, estado_destino=destino
    )
    ct.grupos_permitidos.add(grupo)

    # M2M history attached to most-recent record's m2m manager
    latest = ct.history.first()
    m2m_manager = latest.grupos_permitidos
    assert m2m_manager.count() == 1
    assert m2m_manager.first().group == grupo
