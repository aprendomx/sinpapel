# Form/Serializer Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `MetaFormFactory` that generates Django `forms.Form` and DRF `serializers.Serializer` classes dynamically from a `list[CampoMetadato]` schema.

**Architecture:** A single factory class maps `CampoMetadato` type/choices/defaults to Django/DRF field classes. Supports both Django Forms and DRF Serializers (optional, gracefully degrades if DRF not installed).

**Tech Stack:** Django 5.0+, djangorestframework (optional), pytest-django

---

## File Map

| File | Responsibility |
|------|---------------|
| `sinpapel/forms.py` | `MetaFormFactory` class with `build_form()` and `build_serializer()` |
| `tests/test_forms_factory.py` | Tests for Django Form generation |
| `tests/test_serializers_factory.py` | Tests for DRF Serializer generation (skipped if DRF not installed) |

---

## Task 1: Implement `MetaFormFactory.build_form()`

**Files:**
- Create: `sinpapel/forms.py`
- Test: `tests/test_forms_factory.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_forms_factory.py`:

```python
"""Tests for MetaFormFactory Django Form generation."""
from __future__ import annotations

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
    from decimal import Decimal
    schema = [CampoMetadato("monto", Decimal)]
    MetaForm = MetaFormFactory.build_form(schema)
    field = MetaForm.base_fields["monto"]
    assert isinstance(field, forms.DecimalField)
    assert field.max_digits == 15
    assert field.decimal_places == 2


def test_build_form_date_field():
    """date CampoMetadato generates DateField."""
    from datetime import date
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
    from decimal import Decimal
    from datetime import date
    schema = [
        CampoMetadato("nombre", str),
        CampoMetadato("edad", int),
        CampoMetadato("monto", Decimal),
        CampoMetadato("fecha", date),
        CampoMetadato("activo", bool),
    ]
    MetaForm = MetaFormFactory.build_form(schema)
    form = MetaForm(data={
        "nombre": "Juan",
        "edad": "30",
        "monto": "150000.50",
        "fecha": "2024-01-15",
        "activo": "on",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["nombre"] == "Juan"
    assert form.cleaned_data["edad"] == 30
    assert form.cleaned_data["monto"] == Decimal("150000.50")
    assert form.cleaned_data["fecha"] == date(2024, 1, 15)
    assert form.cleaned_data["activo"] is True
```

Run: `/usr/local/bin/python3.13 -m pytest tests/test_forms_factory.py -v`
Expected: FAIL — `MetaFormFactory` not defined.

- [ ] **Step 2: Implement `sinpapel/forms.py`**

```python
"""Sinpapel — Form/Serializer Factory for MetadatosCapturables.

Generates Django Forms and DRF Serializers dynamically from
SCHEMA_METADATOS definitions.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, TypeVar

from django import forms
from django.utils.translation import gettext_lazy as _

from sinpapel.mixins import CampoMetadato

F = TypeVar("F", bound=forms.Form)


class MetaFormFactory:
    """Genera Django Forms / DRF Serializers desde SCHEMA_METADATOS."""

    _DJANGO_FIELD_MAP: dict[type, type[forms.Field]] = {
        str: forms.CharField,
        int: forms.IntegerField,
        bool: forms.BooleanField,
        Decimal: forms.DecimalField,
        date: forms.DateField,
    }

    @classmethod
    def build_form(
        cls,
        schema: list[CampoMetadato],
        **form_class_kwargs: Any,
    ) -> type[F]:
        """Construye una subclase de django.forms.Form a partir de un schema.

        Args:
            schema: lista de CampoMetadato
            **form_class_kwargs: kwargs adicionales para la clase Form

        Returns:
            Subclase de forms.Form con los campos definidos
        """
        attrs: dict[str, forms.Field] = {}
        for campo in schema:
            field_class = cls._DJANGO_FIELD_MAP[campo.tipo]
            kwargs = cls._build_field_kwargs(campo, is_django=True)
            attrs[campo.nombre] = field_class(**kwargs)

        return type("DynamicMetaForm", (forms.Form,), {**attrs, **form_class_kwargs})

    @classmethod
    def build_serializer(
        cls,
        schema: list[CampoMetadato],
        **serializer_class_kwargs: Any,
    ) -> type[Any]:
        """Construye una subclase de rest_framework.serializers.Serializer.

        Requiere que 'djangorestframework' esté instalado.

        Args:
            schema: lista de CampoMetadato
            **serializer_class_kwargs: kwargs adicionales para la clase Serializer

        Returns:
            Subclase de serializers.Serializer con los campos definidos

        Raises:
            ImportError: si djangorestframework no está instalado
        """
        try:
            from rest_framework import serializers
        except ImportError as exc:
            raise ImportError(
                "MetaFormFactory.build_serializer() requiere 'djangorestframework'. "
                "Instálalo con: pip install djangorestframework"
            ) from exc

        drf_field_map: dict[type, type[serializers.Field]] = {
            str: serializers.CharField,
            int: serializers.IntegerField,
            bool: serializers.BooleanField,
            Decimal: serializers.DecimalField,
            date: serializers.DateField,
        }

        attrs: dict[str, serializers.Field] = {}
        for campo in schema:
            field_class = drf_field_map[campo.tipo]
            kwargs = cls._build_field_kwargs(campo, is_django=False)
            attrs[campo.nombre] = field_class(**kwargs)

        return type("DynamicMetaSerializer", (serializers.Serializer,), {**attrs, **serializer_class_kwargs})

    @classmethod
    def _build_field_kwargs(cls, campo: CampoMetadato, *, is_django: bool) -> dict[str, Any]:
        """Construye kwargs para un campo Django o DRF desde CampoMetadato."""
        kwargs: dict[str, Any] = {
            "required": campo.requerido,
            "label": campo.etiqueta or campo.nombre.replace("_", " ").title(),
            "help_text": campo.ayuda,
        }

        if campo.default is not None:
            if is_django:
                kwargs["initial"] = campo.default
            else:
                kwargs["default"] = campo.default

        if campo.choices is not None:
            kwargs["choices"] = [(c, c) for c in campo.choices]

        if campo.tipo is Decimal:
            kwargs["max_digits"] = 15
            kwargs["decimal_places"] = 2

        return kwargs
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `/usr/local/bin/python3.13 -m pytest tests/test_forms_factory.py -v`
Expected: PASS (12 tests)

- [ ] **Step 4: Commit**

```bash
git add sinpapel/forms.py tests/test_forms_factory.py
git commit -m "feat(forms): add MetaFormFactory for Django Form generation from SCHEMA_METADATOS"
```

---

## Task 2: Implement `MetaFormFactory.build_serializer()` + tests

**Files:**
- Modify: `sinpapel/forms.py` (already done in Task 1)
- Create: `tests/test_serializers_factory.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_serializers_factory.py`:

```python
"""Tests for MetaFormFactory DRF Serializer generation.

Skips all tests if djangorestframework is not installed.
"""
from __future__ import annotations

import pytest

from sinpapel.mixins import CampoMetadato

try:
    from rest_framework import serializers
    from sinpapel.forms import MetaFormFactory
    DRF_INSTALLED = True
except ImportError:
    DRF_INSTALLED = False


pytestmark = pytest.mark.skipif(not DRF_INSTALLED, reason="djangorestframework not installed")


def test_build_serializer_str_field():
    """str CampoMetadato generates DRF CharField."""
    schema = [CampoMetadato("nombre", str)]
    MetaSerializer = MetaFormFactory.build_serializer(schema)
    assert issubclass(MetaSerializer, serializers.Serializer)
    assert isinstance(MetaSerializer().fields["nombre"], serializers.CharField)


def test_build_serializer_decimal_field():
    """Decimal CampoMetadato generates DRF DecimalField."""
    from decimal import Decimal
    schema = [CampoMetadato("monto", Decimal)]
    MetaSerializer = MetaFormFactory.build_serializer(schema)
    field = MetaSerializer().fields["monto"]
    assert isinstance(field, serializers.DecimalField)
    assert field.max_digits == 15
    assert field.decimal_places == 2


def test_build_serializer_choices():
    """str with choices generates DRF ChoiceField."""
    schema = [CampoMetadato("tipo", str, choices=["A", "B"])]
    MetaSerializer = MetaFormFactory.build_serializer(schema)
    field = MetaSerializer().fields["tipo"]
    assert isinstance(field, serializers.ChoiceField)
    assert field.choices == {"A": "A", "B": "B"}


def test_build_serializer_required_and_label():
    """required and etiqueta mapped to DRF field."""
    schema = [CampoMetadato("rfc", str, requerido=True, etiqueta="RFC")]
    MetaSerializer = MetaFormFactory.build_serializer(schema)
    field = MetaSerializer().fields["rfc"]
    assert field.required is True
    assert field.label == "RFC"


def test_build_serializer_default():
    """default mapped to DRF default."""
    schema = [CampoMetadato("nombre", str, default="sin nombre")]
    MetaSerializer = MetaFormFactory.build_serializer(schema)
    assert MetaSerializer().fields["nombre"].default == "sin nombre"


def test_build_serializer_empty_schema():
    """Empty schema returns empty Serializer."""
    MetaSerializer = MetaFormFactory.build_serializer([])
    assert MetaSerializer().fields == {}


def test_serializer_validates_type():
    """Generated serializer rejects wrong type."""
    schema = [CampoMetadato("edad", int)]
    MetaSerializer = MetaFormFactory.build_serializer(schema)
    serializer = MetaSerializer(data={"edad": "not_an_int"})
    assert serializer.is_valid() is False
    assert "edad" in serializer.errors


def test_serializer_accepts_valid_data():
    """Generated serializer accepts valid data."""
    from decimal import Decimal
    from datetime import date
    schema = [
        CampoMetadato("nombre", str),
        CampoMetadato("edad", int),
        CampoMetadato("monto", Decimal),
        CampoMetadato("fecha", date),
        CampoMetadato("activo", bool),
    ]
    MetaSerializer = MetaFormFactory.build_serializer(schema)
    serializer = MetaSerializer(data={
        "nombre": "Juan",
        "edad": 30,
        "monto": "150000.50",
        "fecha": "2024-01-15",
        "activo": True,
    })
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["nombre"] == "Juan"
    assert serializer.validated_data["edad"] == 30
    assert serializer.validated_data["monto"] == Decimal("150000.50")
    assert serializer.validated_data["fecha"] == date(2024, 1, 15)
    assert serializer.validated_data["activo"] is True
```

Run: `/usr/local/bin/python3.13 -m pytest tests/test_serializers_factory.py -v`
Expected: SKIP (all tests) — DRF not installed in dev environment.

If DRF is installed: Expected PASS (8 tests).

- [ ] **Step 2: Install DRF and verify tests pass (optional)**

If user wants DRF tests to run:
```bash
/usr/local/bin/python3.13 -m pip install djangorestframework
/usr/local/bin/python3.13 -m pytest tests/test_serializers_factory.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_serializers_factory.py
git commit -m "test(forms): add DRF Serializer factory tests"
```

---

## Task 3: Integration test with MetadatosCapturables

**Files:**
- Test: `tests/test_forms_factory.py`

- [ ] **Step 1: Write integration test**

Append to `tests/test_forms_factory.py`:

```python
@pytest.mark.django_db
def test_form_integration_with_metadatos_capturables():
    """Generated form writes correctly to MetadatosCapturables instance."""
    from decimal import Decimal
    from sinpapel.mixins import CampoMetadato, MetadatosCapturables

    class _TestModel(MetadatosCapturables):
        SCHEMA_METADATOS = [
            CampoMetadato("rfc", str, requerido=True),
            CampoMetadato("monto", Decimal, default=Decimal("0")),
        ]
        class Meta:
            app_label = "tests"

    obj = _TestModel()
    MetaForm = MetaFormFactory.build_form(_TestModel.SCHEMA_METADATOS)
    form = MetaForm(data={"rfc": "ABCD010101ABC", "monto": "500000"})
    assert form.is_valid(), form.errors

    # Write cleaned data to instance
    for key, value in form.cleaned_data.items():
        setattr(obj.meta, key, value)
    obj.save()

    obj.refresh_from_db()
    assert obj.meta.rfc == "ABCD010101ABC"
    assert obj.meta.monto == Decimal("500000")
```

- [ ] **Step 2: Run test**

Run: `/usr/local/bin/python3.13 -m pytest tests/test_forms_factory.py::test_form_integration_with_metadatos_capturables -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_forms_factory.py
git commit -m "test(forms): add integration test for Form + MetadatosCapturables"
```

---

## Task 4: Run full suite and push

- [ ] **Step 1: Run full test suite**

```bash
/usr/local/bin/python3.13 -m pytest tests/ -q
```
Expected: All 195+ tests PASS

- [ ] **Step 2: Push**

```bash
git push origin develop
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] `build_form()` for Django Forms → Task 1
- [x] `build_serializer()` for DRF → Task 2
- [x] Field type mapping (str, int, bool, Decimal, date) → Tasks 1-2
- [x] Choices support → Tasks 1-2
- [x] Required, default, label, help_text → Tasks 1-2
- [x] Empty schema → Tasks 1-2
- [x] Graceful degradation without DRF → Task 2
- [x] Integration with MetadatosCapturables → Task 3

**2. Placeholder scan:**
- [x] No "TBD", "TODO", or "implement later"
- [x] No vague requirements
- [x] Every code step contains actual code

**3. Type consistency:**
- [x] `MetaFormFactory.build_form()` signature consistent with spec
- [x] `MetaFormFactory.build_serializer()` raises ImportError gracefully
- [x] `_build_field_kwargs()` handles both Django and DRF consistently

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-14-form-serializer-factory.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
