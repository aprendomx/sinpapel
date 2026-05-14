"""Tests for MetaFormFactory Django Form generation."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django import forms

from sinpapel.forms import MetaFormFactory
from sinpapel.mixins import CampoMetadato


def test_build_form_str_field():
    """str CampoMetadato generates CharField."""
    schema = [CampoMetadato("nombre", str)]
    MetaForm = MetaFormFactory.build_form(schema)
    assert issubclass(MetaForm, forms.Form)
    assert isinstance(MetaForm.base_fields["nombre"], forms.CharField)


def test_build_form_int_field():
    """int CampoMetadato generates IntegerField."""
    schema = [CampoMetadato("edad", int)]
    MetaForm = MetaFormFactory.build_form(schema)
    assert isinstance(MetaForm.base_fields["edad"], forms.IntegerField)


def test_build_form_decimal_field():
    """Decimal CampoMetadato generates DecimalField with correct digits."""
    schema = [CampoMetadato("monto", Decimal)]
    MetaForm = MetaFormFactory.build_form(schema)
    field = MetaForm.base_fields["monto"]
    assert isinstance(field, forms.DecimalField)
    assert field.max_digits == 15
    assert field.decimal_places == 2


def test_build_form_date_field():
    """date CampoMetadato generates DateField."""
    schema = [CampoMetadato("fecha", date)]
    MetaForm = MetaFormFactory.build_form(schema)
    assert isinstance(MetaForm.base_fields["fecha"], forms.DateField)


def test_build_form_bool_field():
    """bool CampoMetadato generates BooleanField."""
    schema = [CampoMetadato("activo", bool)]
    MetaForm = MetaFormFactory.build_form(schema)
    assert isinstance(MetaForm.base_fields["activo"], forms.BooleanField)


def test_build_form_choices():
    """str with choices generates ChoiceField with correct options."""
    schema = [CampoMetadato("tipo", str, choices=["A", "B", "C"])]
    MetaForm = MetaFormFactory.build_form(schema)
    field = MetaForm.base_fields["tipo"]
    assert isinstance(field, forms.ChoiceField)
    assert field.choices == [("A", "A"), ("B", "B"), ("C", "C")]


def test_build_form_required_and_label():
    """required and etiqueta mapped correctly."""
    schema = [CampoMetadato("rfc", str, requerido=True, etiqueta="RFC")]
    MetaForm = MetaFormFactory.build_form(schema)
    field = MetaForm.base_fields["rfc"]
    assert field.required is True
    assert field.label == "RFC"


def test_build_form_help_text():
    """ayuda mapped to help_text."""
    schema = [CampoMetadato("rfc", str, ayuda="Formato: ABCD010101ABC")]
    MetaForm = MetaFormFactory.build_form(schema)
    assert MetaForm.base_fields["rfc"].help_text == "Formato: ABCD010101ABC"


def test_build_form_default_initial():
    """default mapped to initial value."""
    schema = [CampoMetadato("nombre", str, default="sin nombre")]
    MetaForm = MetaFormFactory.build_form(schema)
    assert MetaForm.base_fields["nombre"].initial == "sin nombre"


def test_build_form_empty_schema():
    """Empty schema returns empty Form."""
    MetaForm = MetaFormFactory.build_form([])
    assert MetaForm.base_fields == {}


def test_form_validates_type():
    """Generated form rejects wrong type."""
    schema = [CampoMetadato("edad", int)]
    MetaForm = MetaFormFactory.build_form(schema)
    form = MetaForm(data={"edad": "not_an_int"})
    assert form.is_valid() is False
    assert "edad" in form.errors


def test_form_accepts_valid_data():
    """Generated form accepts valid data."""
    schema = [
        CampoMetadato("nombre", str),
        CampoMetadato("edad", int),
        CampoMetadato("monto", Decimal),
        CampoMetadato("fecha", date),
        CampoMetadato("activo", bool),
    ]
    MetaForm = MetaFormFactory.build_form(schema)
    form = MetaForm(
        data={
            "nombre": "Juan",
            "edad": "30",
            "monto": "150000.50",
            "fecha": "2024-01-15",
            "activo": "on",
        }
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["nombre"] == "Juan"
    assert form.cleaned_data["edad"] == 30
    assert form.cleaned_data["monto"] == Decimal("150000.50")
    assert form.cleaned_data["fecha"] == date(2024, 1, 15)
    assert form.cleaned_data["activo"] is True


# --- Review fixes ---


def test_build_form_auto_label():
    """Cuando etiqueta está vacía, se deriva de nombre.replace('_', ' ').title()."""
    schema = [CampoMetadato("primer_nombre", str)]
    MetaForm = MetaFormFactory.build_form(schema)
    assert MetaForm.base_fields["primer_nombre"].label == "Primer Nombre"


def test_build_form_unsupported_type():
    """Tipo no soportado levanta ValueError descriptivo."""
    schema = [CampoMetadato("campo", float)]
    with pytest.raises(ValueError, match="Tipo no soportado"):
        MetaFormFactory.build_form(schema)


def test_build_form_kwargs_collision():
    """Kwargs que colisionan con nombres de campo levantan ValueError."""
    schema = [CampoMetadato("nombre", str)]
    with pytest.raises(ValueError, match="colisionan"):
        MetaFormFactory.build_form(schema, nombre="foo")


def test_build_form_custom_name():
    """Se puede pasar name para parametrizar el nombre de la clase."""
    schema = [CampoMetadato("nombre", str)]
    MetaForm = MetaFormFactory.build_form(schema, name="MiForma")
    assert MetaForm.__name__ == "MiForma"


def test_build_form_default_is_initial_not_fallback():
    """default en Django Forms se mapea a initial (pre-relleno), no fallback real."""
    schema = [CampoMetadato("nombre", str, default="sin nombre", requerido=False)]
    MetaForm = MetaFormFactory.build_form(schema)
    # initial está seteado
    assert MetaForm.base_fields["nombre"].initial == "sin nombre"
    # Pero si no se envía el campo, no se usa como fallback
    form = MetaForm(data={})
    assert form.is_valid()
    assert form.cleaned_data.get("nombre") == ""
