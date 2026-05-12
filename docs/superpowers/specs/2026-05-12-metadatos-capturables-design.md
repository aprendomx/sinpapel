# MetadatosCapturables Mixin Design Spec

> **Date:** 2026-05-12
> **Status:** Approved
> **Scope:** Add `MetadatosCapturables` mixin to `sinpapel.mixins` for structured metadata capture on workflow-enabled models.

---

## 1. Goal

Provide a reusable Django model mixin that allows any workflow-enabled model (or any model) to declare a schema of capturable metadata fields, with:
- **Type-safe access** via proxy object (`instance.meta.campo`)
- **Automatic validation** on `clean()` / `save()`
- **JSON serialization** for API consumption (`instance.meta.to_dict()`)
- **Integration** with existing `Trazable` / `@workflow_enabled` without hard coupling

---

## 2. Architecture

Three components live in `sinpapel.mixins`:

| Component | Responsibility |
|-----------|---------------|
| `CampoMetadato` | Frozen dataclass describing one metadata field (name, type, required, default, choices, label, help) |
| `MetadatosProxy` | Runtime proxy attached to `instance.meta`; validates reads/writes; serializes/deserializes; produces `to_dict()` |
| `MetadatosCapturables` | Abstract Django model mixin; adds `datos_capturados JSONField`; exposes `meta` property; validates in `clean()` |

---

## 3. API Design

### 3.1 Schema Declaration (model author)

```python
from decimal import Decimal
from sinpapel import workflow_enabled
from sinpapel.mixins import CampoMetadato, MetadatosCapturables, Trazable

@workflow_enabled(state_field="estado", workflow_key="solicitud")
class Solicitud(MetadatosCapturables, Trazable):
    SCHEMA_METADATOS = [
        CampoMetadato("rfc", str, requerido=True, etiqueta="RFC"),
        CampoMetadato("monto_solicitado", Decimal, default=Decimal("0")),
        CampoMetadato("tipo_credito", str, choices=["FOVISSSTE", "INFONAVIT"], requerido=True),
    ]
    estado = models.ForeignKey("sinpapel.Estado", on_delete=models.CASCADE)
```

### 3.2 Runtime Usage (business logic)

```python
s = Solicitud.objects.create(estado=captura)
s.meta.rfc = "ABCD010101ABC"
s.meta.monto_solicitado = Decimal("500000")
s.meta.tipo_credito = "FOVISSSTE"
s.save()  # triggers clean() → validates schema
```

### 3.3 API Serialization

```python
s.meta.to_dict()
# → {"rfc": "ABCD010101ABC", "monto_solicitado": "500000", "tipo_credito": "FOVISSSTE"}

s.meta.to_dict(incluir_defaults=False)
# → only fields explicitly set
```

### 3.4 Validation

```python
s2 = Solicitud.objects.create(estado=captura)
s2.meta.tipo_credito = "INVALIDO"  # raises ValueError on assignment

s3 = Solicitud.objects.create(estado=captura)
s3.save()  # raises ValidationError because "rfc" is required
```

---

## 4. Component Details

### 4.1 `CampoMetadato`

```python
@dataclass(frozen=True)
class CampoMetadato:
    nombre: str
    tipo: type
    requerido: bool = False
    default: Any = None
    choices: list[str] | None = None
    etiqueta: str = ""
    ayuda: str = ""
```

Supported types: `str`, `int`, `bool`, `Decimal`, `date`. More can be added later.

### 4.2 `MetadatosProxy`

- `__getattr__`: looks up schema, returns stored value or `default`. Raises `AttributeError` if field not in schema.
- `__setattr__`: validates type, validates choices if applicable, serializes `Decimal` → `str`, stores into underlying `datos_capturados` JSONField.
- `_serializar(value)`: `Decimal` → `str` (for JSON); dates → `YYYY-MM-DD`.
- `_deserializar(campo, raw)`: inverse of `_serializar`.
- `errores() → dict[str, str]`: checks all `requerido` fields present and valid; returns empty dict if clean.
- `to_dict(incluir_defaults=True) → dict[str, Any]`: iterates schema, includes defaults if flag is True. Values are deserialized (e.g. `str` back to `Decimal`).

### 4.3 `MetadatosCapturables`

```python
class MetadatosCapturables(models.Model):
    SCHEMA_METADATOS: ClassVar[list[CampoMetadato]] = []
    datos_capturados = models.JSONField(default=dict, blank=True)

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

---

## 5. Error Handling

| Scenario | Behavior |
|----------|----------|
| Assign to unknown field | `AttributeError` |
| Wrong type | `TypeError` with expected vs actual |
| Choice not in list | `ValueError` with allowed choices |
| Required field missing on `clean()` | `ValidationError` with field-level errors |
| Empty schema (`SCHEMA_METADATOS = []`) | Mixin behaves like plain `JSONField`; no validation |

---

## 6. Integration Points

- **Trazable**: `MetadatosCapturables` is intentionally independent; a model can inherit both (e.g. `class Solicitud(MetadatosCapturables, Trazable)`).
- **workflow_enabled**: No direct coupling. The decorator injects workflow methods; the mixin adds metadata capture. They coexist on the same class.
- **Audit trail**: `datos_capturados` is a regular field, so `django-simple-history` will snapshot it automatically if the model has `HistoricalRecords`.

---

## 7. Testing Strategy

| Test | What it verifies |
|------|-----------------|
| `test_meta_get_set` | Read/write defined fields via proxy |
| `test_meta_campo_inexistente_raises` | `AttributeError` on unknown field |
| `test_meta_tipo_invalido_raises` | `TypeError` on wrong type assignment |
| `test_meta_choice_invalido_raises` | `ValueError` on invalid choice |
| `test_meta_requerido_faltante` | `ValidationError` in `clean()` |
| `test_meta_decimal_serializacion` | `Decimal` survives JSON round-trip |
| `test_meta_to_dict_incluye_defaults` | `to_dict()` returns all schema fields |
| `test_meta_to_dict_solo_seteados` | `incluir_defaults=False` filters unset fields |
| `test_meta_errores_dict` | `errores()` returns per-field error map |
| `test_mixins_integration` | Model with both `MetadatosCapturables` + `Trazable` works |

---

## 8. Files to Modify

- `sinpapel/mixins.py` — add `CampoMetadato`, `MetadatosProxy`, `MetadatosCapturables`
- `tests/test_mixins.py` — add tests for new mixin
- `tests/models.py` — add `TestSolicitudConMetadatos` for integration test

---

## 9. Out of Scope (YAGNI)

- Nested schemas / sub-objects inside `datos_capturados`
- Dynamic schema changes at runtime
- Admin auto-generated forms from schema
- File/Image fields inside metadata
- Conditional validation rules

These can be added later if needed.

---

## 10. Open Questions (none)

Design approved by user on 2026-05-12.
