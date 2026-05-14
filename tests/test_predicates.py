"""Tests for Transition Predicates (CondicionTransicion + PredicateEngine)."""
from __future__ import annotations

import pytest
from django.db import models

from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo
from sinpapel.models.predicates import CondicionTransicion


@pytest.mark.django_db
def test_condicion_transicion_model_exists():
    """CondicionTransicion can be created and linked to ConfiguracionTransicion."""
    estado_origen = Estado.objects.create(nombre="ORIG", activo=True)
    estado_destino = Estado.objects.create(nombre="DEST", activo=True)
    flujo = VersionFlujo.objects.create(nombre="F1", activo=True)
    transicion = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino
    )
    cond = CondicionTransicion.objects.create(
        transicion=transicion,
        tipo="python_path",
        configuracion={"path": "tests.test_predicates._always_true"},
        mensaje_error="Falló validación",
        orden=1,
    )
    assert cond.tipo == "python_path"
    assert cond.activo is True
    assert str(cond) == "Condicion #1 (python_path)"
