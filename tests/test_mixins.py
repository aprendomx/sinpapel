"""Tests for inlined Trazable and Catalogo mixins."""
from __future__ import annotations

import pytest
from django.db import models

from sinpapel.mixins import CampoMetadato, Catalogo, Trazable


class _TestTrazableModel(Trazable):
    name = models.CharField(max_length=50)

    class Meta:
        app_label = "tests"


class _TestCatalogoModel(Catalogo):
    extra = models.CharField(max_length=50)

    class Meta:
        app_label = "tests"


@pytest.mark.django_db
def test_trazable_fields_exist():
    """Trazable model instances have creado, actualizado, autor, modificador."""
    from django.contrib.auth.models import User

    user = User.objects.create_user("traz_test", password="x")
    obj = _TestTrazableModel.objects.create(name="a", autor=user, modificador=user)
    assert obj.creado is not None
    assert obj.actualizado is not None
    assert obj.autor == user
    assert obj.modificador == user


@pytest.mark.django_db
def test_catalogo_fields_exist():
    """Catalogo inherits Trazable and adds nombre, activo, orden, etc."""
    obj = _TestCatalogoModel.objects.create(nombre="cat", activo=True, orden=1, extra="x")
    assert obj.nombre == "cat"
    assert obj.activo is True
    assert obj.orden == 1
    assert str(obj) == "cat"


def test_campo_metadato_dataclass():
    """CampoMetadato frozen dataclass stores schema definition."""
    campo = CampoMetadato("rfc", str, requerido=True, etiqueta="RFC")
    assert campo.nombre == "rfc"
    assert campo.tipo is str
    assert campo.requerido is True
    assert campo.etiqueta == "RFC"
    assert campo.default is None
    assert campo.choices is None
