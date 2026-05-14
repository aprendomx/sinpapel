"""Tests for inlined Trazable and Catalogo mixins."""
from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest
from django.db import models

from sinpapel.mixins import CampoMetadato, Catalogo, MetadatosProxy, Trazable


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
    assert campo.ayuda == ""
    with pytest.raises(dataclasses.FrozenInstanceError):
        campo.nombre = "x"


class _FakeInstance:
    """Fake Django model instance for testing MetadatosProxy in isolation."""
    datos_capturados = {}


def test_proxy_get_returns_default():
    """Proxy returns default when field not set."""
    schema = [CampoMetadato("monto", Decimal, default=Decimal("0"))]
    proxy = MetadatosProxy(_FakeInstance(), schema)
    assert proxy.monto == Decimal("0")


def test_proxy_set_and_get():
    """Proxy stores and retrieves values."""
    schema = [CampoMetadato("rfc", str)]
    instance = _FakeInstance()
    proxy = MetadatosProxy(instance, schema)
    proxy.rfc = "ABCD010101ABC"
    assert proxy.rfc == "ABCD010101ABC"
    assert instance.datos_capturados == {"rfc": "ABCD010101ABC"}


def test_proxy_unknown_field_raises():
    """Accessing unknown field raises AttributeError."""
    proxy = MetadatosProxy(_FakeInstance(), [CampoMetadato("rfc", str)])
    with pytest.raises(AttributeError, match="campo_inexistente"):
        proxy.campo_inexistente


def test_proxy_set_unknown_field_raises():
    """Setting unknown field raises AttributeError."""
    proxy = MetadatosProxy(_FakeInstance(), [CampoMetadato("rfc", str)])
    with pytest.raises(AttributeError, match="campo_inexistente"):
        proxy.campo_inexistente = "x"


def test_proxy_invalid_type_raises():
    """Setting wrong type raises TypeError."""
    proxy = MetadatosProxy(_FakeInstance(), [CampoMetadato("edad", int)])
    with pytest.raises(TypeError):
        proxy.edad = "not an int"


def test_proxy_invalid_choice_raises():
    """Setting value not in choices raises ValueError."""
    proxy = MetadatosProxy(_FakeInstance(), [CampoMetadato("tipo", str, choices=["A", "B"])])
    with pytest.raises(ValueError, match="tipo"):
        proxy.tipo = "C"


def test_proxy_decimal_roundtrip():
    """Decimal survives JSON round-trip via string serialization."""
    schema = [CampoMetadato("monto", Decimal)]
    instance = _FakeInstance()
    proxy = MetadatosProxy(instance, schema)
    proxy.monto = Decimal("123.45")
    assert proxy.monto == Decimal("123.45")
    assert instance.datos_capturados == {"monto": "123.45"}
