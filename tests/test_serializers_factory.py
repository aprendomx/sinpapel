"""Tests for MetaFormFactory DRF Serializer generation."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from sinpapel.forms import MetaFormFactory
from sinpapel.mixins import CampoMetadato

try:
    from rest_framework import serializers

    HAS_DRF = True
except ImportError:
    HAS_DRF = False


@pytest.mark.skipif(not HAS_DRF, reason="djangorestframework no instalado")
class TestSerializerFactory:
    def test_build_serializer_str_field(self):
        schema = [CampoMetadato("nombre", str)]
        Serializer = MetaFormFactory.build_serializer(schema)
        assert issubclass(Serializer, serializers.Serializer)
        assert isinstance(Serializer().fields["nombre"], serializers.CharField)

    def test_build_serializer_int_field(self):
        schema = [CampoMetadato("edad", int)]
        Serializer = MetaFormFactory.build_serializer(schema)
        assert isinstance(Serializer().fields["edad"], serializers.IntegerField)

    def test_build_serializer_decimal_field(self):
        schema = [CampoMetadato("monto", Decimal)]
        Serializer = MetaFormFactory.build_serializer(schema)
        field = Serializer().fields["monto"]
        assert isinstance(field, serializers.DecimalField)
        assert field.max_digits == 15
        assert field.decimal_places == 2

    def test_build_serializer_date_field(self):
        schema = [CampoMetadato("fecha", date)]
        Serializer = MetaFormFactory.build_serializer(schema)
        assert isinstance(Serializer().fields["fecha"], serializers.DateField)

    def test_build_serializer_bool_field(self):
        schema = [CampoMetadato("activo", bool)]
        Serializer = MetaFormFactory.build_serializer(schema)
        assert isinstance(Serializer().fields["activo"], serializers.BooleanField)

    def test_build_serializer_choices(self):
        schema = [CampoMetadato("tipo", str, choices=["A", "B", "C"])]
        Serializer = MetaFormFactory.build_serializer(schema)
        field = Serializer().fields["tipo"]
        assert isinstance(field, serializers.ChoiceField)
        assert dict(field.choices) == {"A": "A", "B": "B", "C": "C"}

    def test_build_serializer_required_and_label(self):
        schema = [CampoMetadato("rfc", str, requerido=True, etiqueta="RFC")]
        Serializer = MetaFormFactory.build_serializer(schema)
        field = Serializer().fields["rfc"]
        assert field.required is True
        assert field.label == "RFC"

    def test_build_serializer_help_text(self):
        schema = [CampoMetadato("rfc", str, ayuda="Formato: ABCD010101ABC")]
        Serializer = MetaFormFactory.build_serializer(schema)
        assert Serializer().fields["rfc"].help_text == "Formato: ABCD010101ABC"

    def test_build_serializer_default(self):
        schema = [CampoMetadato("nombre", str, default="sin nombre")]
        Serializer = MetaFormFactory.build_serializer(schema)
        field = Serializer().fields["nombre"]
        assert field.default == "sin nombre"

    def test_build_serializer_empty_schema(self):
        Serializer = MetaFormFactory.build_serializer([])
        assert Serializer().fields == {}

    def test_build_serializer_unsupported_type(self):
        schema = [CampoMetadato("campo", float)]
        with pytest.raises(ValueError, match="Tipo no soportado"):
            MetaFormFactory.build_serializer(schema)

    def test_build_serializer_kwargs_collision(self):
        schema = [CampoMetadato("nombre", str)]
        with pytest.raises(ValueError, match="colisionan"):
            MetaFormFactory.build_serializer(schema, nombre="foo")

    def test_build_serializer_custom_name(self):
        schema = [CampoMetadato("nombre", str)]
        Serializer = MetaFormFactory.build_serializer(schema, name="MiSerializer")
        assert Serializer.__name__ == "MiSerializer"


def test_build_serializer_import_error():
    import sys

    rf_keys = [
        k
        for k in sys.modules
        if k == "rest_framework" or k.startswith("rest_framework.")
    ]
    with patch.dict("sys.modules", {k: None for k in rf_keys}):
        with pytest.raises(ImportError, match="djangorestframework"):
            MetaFormFactory.build_serializer([])
