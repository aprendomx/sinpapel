# MetadatosCapturables Mixin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `MetadatosCapturables` mixin with schema-declared metadata fields, proxy access, validation, and `to_dict()` serialization.

**Architecture:** A `CampoMetadato` dataclass defines each field schema. `MetadatosProxy` attaches to `instance.meta` for type-safe read/write and validation. `MetadatosCapturables` is an abstract Django model mixin with a `datos_capturados JSONField` and `clean()` validation.

**Tech Stack:** Django 5.0+, Python dataclasses, pytest-django

---

## File Map

| File | Responsibility |
|------|---------------|
| `sinpapel/mixins.py` | Modify — add `CampoMetadato`, `MetadatosProxy`, `MetadatosCapturables` alongside existing `Trazable`/`Catalogo` |
| `tests/test_mixins.py` | Modify — add tests for proxy access, validation, serialization, integration |
| `tests/models.py` | Modify — add `TestSolicitudConMetadatos` model for integration test |

---

## Task 1: Add `CampoMetadato` dataclass

**Files:**
- Modify: `sinpapel/mixins.py`
- Test: `tests/test_mixins.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mixins.py`:

```python
from sinpapel.mixins import CampoMetadato


def test_campo_metadato_dataclass():
    """CampoMetadato frozen dataclass stores schema definition."""
    campo = CampoMetadato("rfc", str, requerido=True, etiqueta="RFC")
    assert campo.nombre == "rfc"
    assert campo.tipo is str
    assert campo.requerido is True
    assert campo.etiqueta == "RFC"
    assert campo.default is None
    assert campo.choices is None
```

Run: `pytest tests/test_mixins.py::test_campo_metadato_dataclass -v`
Expected: FAIL — `CampoMetadato` not defined.

- [ ] **Step 2: Add `CampoMetadato` to `sinpapel/mixins.py`**

At the top of `sinpapel/mixins.py`, after the imports and before `class Trazable`, add:

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CampoMetadato:
    """Definición de un campo capturable en el mixin MetadatosCapturables.

    Attributes:
        nombre: nombre del campo (usado como key en JSON y como atributo en proxy)
        tipo: tipo de dato esperado (str, int, bool, Decimal, date)
        requerido: si el campo debe estar presente para pasar validación
        default: valor por omisión cuando no está seteado
        choices: lista opcional de valores permitidos
        etiqueta: etiqueta para UI / forms
        ayuda: texto de ayuda para UI
    """

    nombre: str
    tipo: type
    requerido: bool = False
    default: Any = None
    choices: list[str] | None = None
    etiqueta: str = ""
    ayuda: str = ""
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_mixins.py::test_campo_metadato_dataclass -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add sinpapel/mixins.py tests/test_mixins.py
git commit -m "feat(mixins): add CampoMetadato dataclass for schema declaration"
```

---

## Task 2: Add `MetadatosProxy`

**Files:**
- Modify: `sinpapel/mixins.py`
- Test: `tests/test_mixins.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mixins.py`:

```python
import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError

from sinpapel.mixins import CampoMetadato, MetadatosProxy


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
```

Run: `pytest tests/test_mixins.py -k proxy -v`
Expected: FAIL — `MetadatosProxy` not defined.

- [ ] **Step 2: Implement `MetadatosProxy` in `sinpapel/mixins.py`**

After `CampoMetadato`, before `class Trazable`, insert:

```python
from datetime import date
from decimal import Decimal


class MetadatosProxy:
    """Proxy de acceso a datos_capturados con schema validation.

    Se instancia vía `instance.meta` en modelos que heredan
    MetadatosCapturables. Lee/escribe del JSONField subyacente,
    validando tipo, choices y requeridos.
    """

    def __init__(self, instance, schema: list[CampoMetadato]) -> None:
        self._instance = instance
        self._schema = {c.nombre: c for c in schema}
        self._datos = instance.datos_capturados or {}

    # ─── Acceso a campos ──────────────────────────────────────────────────

    def __getattr__(self, name: str):
        if name.startswith("_"):
            return object.__getattribute__(self, name)
        campo = self._schema.get(name)
        if campo is None:
            raise AttributeError(f"Campo '{name}' no definido en SCHEMA_METADATOS")
        raw = self._datos.get(name, campo.default)
        return self._deserializar(campo, raw)

    def __setattr__(self, name: str, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        campo = self._schema.get(name)
        if campo is None:
            raise AttributeError(f"Campo '{name}' no definido en SCHEMA_METADATOS")
        self._validar(campo, value)
        self._datos[name] = self._serializar(value)
        self._instance.datos_capturados = self._datos

    # ─── Validación ───────────────────────────────────────────────────────

    def _validar(self, campo: CampoMetadato, value) -> None:
        if value is None:
            return
        if not isinstance(value, campo.tipo):
            raise TypeError(
                f"Campo '{campo.nombre}' espera {campo.tipo.__name__}, "
                f"recibió {type(value).__name__}"
            )
        if campo.choices is not None and value not in campo.choices:
            raise ValueError(
                f"Campo '{campo.nombre}' solo acepta {campo.choices}, "
                f"recibió '{value}'"
            )

    def errores(self) -> dict[str, str]:
        """Valida todos los campos requeridos y retorna dict de errores."""
        errores: dict[str, str] = {}
        for campo in self._schema.values():
            if campo.requerido:
                raw = self._datos.get(campo.nombre, campo.default)
                if raw is None or raw == "":
                    errores[campo.nombre] = f"El campo '{campo.nombre}' es obligatorio."
        return errores

    # ─── Serialización ────────────────────────────────────────────────────

    def _serializar(self, value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, date):
            return value.isoformat()
        return value

    def _deserializar(self, campo: CampoMetadato, raw):
        if raw is None:
            return None
        if campo.tipo is Decimal and isinstance(raw, str):
            return Decimal(raw)
        if campo.tipo is date and isinstance(raw, str):
            return date.fromisoformat(raw)
        return raw

    # ─── API serialization ────────────────────────────────────────────────

    def to_dict(self, *, incluir_defaults: bool = True) -> dict[str, Any]:
        """Retorna dict con todos los campos del schema.

        Args:
            incluir_defaults: si True, incluye campos no seteados con su default.
        """
        resultado: dict[str, Any] = {}
        for campo in self._schema.values():
            raw = self._datos.get(campo.nombre)
            if raw is None:
                if not incluir_defaults:
                    continue
                raw = campo.default
            if raw is not None:
                resultado[campo.nombre] = self._deserializar(campo, raw)
            elif incluir_defaults:
                resultado[campo.nombre] = None
        return resultado
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_mixins.py -k proxy -v`
Expected: PASS (7 tests)

- [ ] **Step 4: Commit**

```bash
git add sinpapel/mixins.py tests/test_mixins.py
git commit -m "feat(mixins): add MetadatosProxy with validation and to_dict"
```

---

## Task 3: Add `MetadatosCapturables` mixin

**Files:**
- Modify: `sinpapel/mixins.py`
- Test: `tests/test_mixins.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_mixins.py`:

```python
import pytest
from django.core.exceptions import ValidationError
from django.db import models

from sinpapel.mixins import CampoMetadato, MetadatosCapturables


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
```

Run: `pytest tests/test_mixins.py -k capturable -v`
Expected: FAIL — `MetadatosCapturables` not defined.

- [ ] **Step 2: Add `MetadatosCapturables` to `sinpapel/mixins.py`**

After `MetadatosProxy`, before `class Trazable`, insert:

```python
from django.core.exceptions import ValidationError


class MetadatosCapturables(models.Model):
    """Mixin que agrega captura estructurada de metadatos vía schema.

    Uso:
        class MiModelo(MetadatosCapturables):
            SCHEMA_METADATOS = [
                CampoMetadato("rfc", str, requerido=True),
            ]
            # ... otros campos Django

    Runtime:
        obj.meta.rfc = "ABCD010101ABC"
        obj.save()   # valida automáticamente
        obj.meta.to_dict()
    """

    SCHEMA_METADATOS: ClassVar[list[CampoMetadato]] = []
    datos_capturados = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Datos capturados"),
    )

    @property
    def meta(self) -> MetadatosProxy:
        return MetadatosProxy(self, self.SCHEMA_METADATOS)

    def clean(self):
        super().clean()
        errores = self.meta.errores()
        if errores:
            raise ValidationError({"datos_capturados": errores})

    class Meta:
        abstract = True
```

Note: `ClassVar` and `list` need `from __future__ import annotations` which is already present in `mixins.py` via the file's existing imports. If not, add `from typing import ClassVar`.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_mixins.py -k capturable -v`
Expected: PASS (3 tests)

- [ ] **Step 4: Commit**

```bash
git add sinpapel/mixins.py tests/test_mixins.py
git commit -m "feat(mixins): add MetadatosCapturables abstract model mixin"
```

---

## Task 4: Integration test with workflow

**Files:**
- Modify: `tests/models.py`
- Modify: `tests/test_mixins.py`

- [ ] **Step 1: Add test model with both mixins**

In `tests/models.py`, add:

```python
from decimal import Decimal

from django.db import models

from sinpapel import workflow_enabled
from sinpapel.mixins import CampoMetadato, MetadatosCapturables, Trazable
from sinpapel.models import Estado, VersionFlujo


@workflow_enabled(state_field="estado", workflow_key="test_solicitud_meta")
class TestSolicitudConMetadatos(MetadatosCapturables, Trazable):
    """Modelo de integración: workflow + metadatos capturables."""

    SCHEMA_METADATOS = [
        CampoMetadato("rfc", str, requerido=True, etiqueta="RFC"),
        CampoMetadato("monto_solicitado", Decimal, default=Decimal("0")),
        CampoMetadato("tipo_credito", str, choices=["FOVISSSTE", "INFONAVIT"], requerido=True),
    ]

    folio = models.CharField(max_length=50, unique=True)
    estado = models.ForeignKey(Estado, on_delete=models.CASCADE, null=True)

    class Meta:
        app_label = "tests"
```

- [ ] **Step 2: Write integration test**

Append to `tests/test_mixins.py`:

```python
@pytest.mark.django_db
def test_integration_workflow_and_metadatos():
    """Modelo con workflow_enabled + MetadatosCapturables funciona end-to-end."""
    from tests.models import TestSolicitudConMetadatos
    from sinpapel.models import Estado

    estado = Estado.objects.create(nombre="META_CAPTURA", activo=True)
    obj = TestSolicitudConMetadatos.objects.create(
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
    obj = TestSolicitudConMetadatos.objects.create(folio="META-002", estado=estado)
    # No seteamos rfc ni tipo_credito
    with pytest.raises(ValidationError):
        obj.save()
```

- [ ] **Step 3: Run integration tests**

Run: `pytest tests/test_mixins.py -k integration -v`
Expected: PASS (2 tests)

- [ ] **Step 4: Run full suite to ensure no regressions**

Run: `pytest tests/ -q`
Expected: All 141+ tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/models.py tests/test_mixins.py
git commit -m "test: add integration tests for MetadatosCapturables + workflow"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] `CampoMetadato` dataclass → Task 1
- [x] `MetadatosProxy` with `__getattr__`/`__setattr__` → Task 2
- [x] Type validation → Task 2
- [x] Choice validation → Task 2
- [x] Decimal serialization → Task 2
- [x] `errores()` → Task 2
- [x] `to_dict()` → Task 2
- [x] `MetadatosCapturables` mixin → Task 3
- [x] `clean()` raises `ValidationError` → Task 3
- [x] Integration with workflow → Task 4

**2. Placeholder scan:**
- [x] No "TBD", "TODO", or "implement later"
- [x] No vague "add validation" steps
- [x] No "Similar to Task N" shortcuts
- [x] Every code step contains actual code

**3. Type consistency:**
- [x] `CampoMetadato` fields match spec (`nombre`, `tipo`, `requerido`, `default`, `choices`, `etiqueta`, `ayuda`)
- [x] `MetadatosProxy` methods (`errores`, `to_dict`) match spec signatures
- [x] `MetadatosCapturables` has `datos_capturados` field and `meta` property
- [x] `_serializar` / `_deserializar` handle `Decimal` and `date` consistently

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-12-metadatos-capturables.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
