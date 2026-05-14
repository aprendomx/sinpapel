"""Tests for inlined Trazable and Catalogo mixins."""
from __future__ import annotations

import dataclasses
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import models

from sinpapel.mixins import CampoMetadato, Catalogo, MetadatosCapturables, MetadatosProxy, Trazable


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

    def __init__(self, datos=None):
        self.datos_capturados = datos or {}


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


def test_proxy_errores_empty_when_all_present():
    """errores() returns empty dict when all required fields are present."""
    schema = [
        CampoMetadato("rfc", str, requerido=True),
        CampoMetadato("monto", Decimal, requerido=True),
    ]
    instance = _FakeInstance({"rfc": "ABCD010101ABC", "monto": "100.00"})
    proxy = MetadatosProxy(instance, schema)
    assert proxy.errores() == {}


def test_proxy_errores_when_required_missing():
    """errores() returns errors when required fields are missing."""
    schema = [
        CampoMetadato("rfc", str, requerido=True),
        CampoMetadato("monto", Decimal, requerido=True),
    ]
    proxy = MetadatosProxy(_FakeInstance(), schema)
    errores = proxy.errores()
    assert "rfc" in errores
    assert "monto" in errores


def test_proxy_to_dict_includes_defaults():
    """to_dict() includes all fields with defaults."""
    schema = [
        CampoMetadato("nombre", str, default="sin nombre"),
        CampoMetadato("edad", int, default=0),
    ]
    proxy = MetadatosProxy(_FakeInstance(), schema)
    d = proxy.to_dict()
    assert d == {"nombre": "sin nombre", "edad": 0}


def test_proxy_to_dict_excludes_defaults():
    """to_dict(incluir_defaults=False) only includes set fields."""
    schema = [
        CampoMetadato("nombre", str, default="sin nombre"),
        CampoMetadato("edad", int, default=0),
    ]
    instance = _FakeInstance({"nombre": "Juan"})
    proxy = MetadatosProxy(instance, schema)
    d = proxy.to_dict(incluir_defaults=False)
    assert d == {"nombre": "Juan"}


def test_proxy_date_roundtrip():
    """date survives JSON round-trip via ISO string serialization."""
    schema = [CampoMetadato("fecha", date)]
    instance = _FakeInstance()
    proxy = MetadatosProxy(instance, schema)
    proxy.fecha = date(2024, 1, 15)
    assert proxy.fecha == date(2024, 1, 15)
    assert instance.datos_capturados == {"fecha": "2024-01-15"}


def test_proxy_bool_handling():
    """bool fields are stored and retrieved correctly."""
    schema = [CampoMetadato("activo", bool)]
    instance = _FakeInstance()
    proxy = MetadatosProxy(instance, schema)
    proxy.activo = True
    assert proxy.activo is True
    assert instance.datos_capturados == {"activo": True}
    proxy.activo = False
    assert proxy.activo is False
    assert instance.datos_capturados == {"activo": False}


class _TestCapturable(MetadatosCapturables):
    SCHEMA_METADATOS = [
        CampoMetadato("rfc", str, requerido=True),
        CampoMetadato("edad", int, default=0),
    ]

    class Meta:
        app_label = "tests"


@pytest.mark.django_db
def test_capturable_clean_valid():
    """clean() passes when required fields are present."""
    obj = _TestCapturable()
    obj.datos_capturados = {"rfc": "ABCD010101ABC"}
    obj.clean()  # no raise


@pytest.mark.django_db
def test_capturable_clean_missing_required():
    """clean() raises ValidationError when required field missing."""
    obj = _TestCapturable()
    with pytest.raises(ValidationError):
        obj.clean()


@pytest.mark.django_db
def test_capturable_meta_property():
    """instance.meta returns a MetadatosProxy."""
    obj = _TestCapturable()
    assert obj.meta.rfc is None
    obj.meta.rfc = "XYZ"
    assert obj.datos_capturados == {"rfc": "XYZ"}


@pytest.mark.django_db
def test_integration_workflow_and_metadatos():
    """Modelo con workflow_enabled + MetadatosCapturables funciona end-to-end."""
    from tests.models import TestSolicitudConMetadatos
    from sinpapel.models import Estado

    estado = Estado.objects.create(nombre="META_CAPTURA", activo=True)
    obj = TestSolicitudConMetadatos(
        folio="META-001",
        estado=estado,
    )
    obj.meta.rfc = "ABCD010101ABC"
    obj.meta.monto_solicitado = Decimal("500000")
    obj.meta.tipo_credito = "FOVISSSTE"
    obj.save()

    obj.refresh_from_db()
    assert obj.meta.rfc == "ABCD010101ABC"
    assert obj.meta.monto_solicitado == Decimal("500000")
    assert obj.meta.tipo_credito == "FOVISSSTE"

    # to_dict
    d = obj.meta.to_dict()
    assert d["rfc"] == "ABCD010101ABC"
    assert d["monto_solicitado"] == Decimal("500000")
    assert d["tipo_credito"] == "FOVISSSTE"


@pytest.mark.django_db
def test_integration_validation_blocks_save():
    """Faltan campos requeridos → ValidationError en save."""
    from tests.models import TestSolicitudConMetadatos
    from sinpapel.models import Estado

    estado = Estado.objects.create(nombre="META_INVALID", activo=True)
    obj = TestSolicitudConMetadatos(folio="META-002", estado=estado)
    # No seteamos rfc ni tipo_credito
    with pytest.raises(ValidationError):
        obj.save()
