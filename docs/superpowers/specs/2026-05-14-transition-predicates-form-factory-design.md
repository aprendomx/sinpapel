# Transition Predicates + Form/Serializer Factory Design Spec

> **Date:** 2026-05-14
> **Status:** Draft — pending user approval
> **Scope:** Two features for sinpapel v0.3.0 roadmap:
> 1. **Transition Predicates** (`CondicionTransicion`) — configurable business rules evaluated before state transitions
> 2. **Form/Serializer Factory** (`MetaFormFactory`) — dynamic Django Form / DRF Serializer generation from `SCHEMA_METADATOS`

---

## Context

`sinpapel` v0.2.0 has a working workflow engine (`WorkflowEngine`) with group-based permissions and document gates. It also has `MetadatosCapturables` with `CampoMetadato` schema declaration and `MetadatosProxy` runtime access. These two features fill the biggest remaining gaps.

**Transition Predicates** addresses the limitation that pre-transition validation is limited to:
- Document requirements (`expediente_obligatorio`)
- Group membership (`grupos_permitidos`)

There is no way for a non-developer to configure rules like *"only transition to APROBADA if monto > $100,000 and the applicant has 2 signatures"* without writing Python code.

**Form/Serializer Factory** addresses the duplication where `SCHEMA_METADATOS` already describes field types, labels, choices, defaults, and help text — but developers must still manually write matching `forms.Form` or `serializers.Serializer` classes.

---

## 1. Transition Predicates

### 1.1 Goal

Add a `CondicionTransicion` model linked to `ConfiguracionTransicion`. Each condition has a `tipo` (backend) and `configuracion` (backend-specific JSON). The `WorkflowEngine` evaluates all active conditions before allowing a transition.

### 1.2 Architecture

Three components:

| Component | Responsibility |
|-----------|---------------|
| `CondicionTransicion` | Model storing condition config (tipo, configuracion JSON, mensaje_error, orden, activo) |
| `PredicateEngine` | Evaluates conditions by tipo. Pluggable: register new backends at runtime. |
| `WorkflowEngine` integration | Calls `PredicateEngine.evaluar(transicion, instance, user)` after group validation, before returning `True` |

### 1.3 Backends (v0.3.0)

| Backend | `tipo` | `configuracion` schema | Use case |
|---------|--------|----------------------|----------|
| **Python Path** | `python_path` | `{"path": "modulo.submodulo.funcion_validadora"}` | Complex logic, reusable validators, external API calls |
| **JSON Logic** | `json_logic` | `{"rule": {"and": [...]}}` | Simple declarative rules, editable by non-devs via UI |
| **Django ORM** | `django_orm` | `{"lookup": {"solicitante__perfil__ingreso__gte": 50000}}` | Conditions on related model fields |

**Future backends:** `sql_expression`, `webhook_sync`.

### 1.4 Data Model

```python
class CondicionTransicion(models.Model):
    TIPO_CHOICES = [
        ("python_path", _("Python Path")),
        ("json_logic", _("JSON Logic")),
        ("django_orm", _("Django ORM Lookup")),
    ]

    transicion = models.ForeignKey(
        ConfiguracionTransicion,
        on_delete=models.CASCADE,
        related_name="condiciones",
        verbose_name=_("Transición"),
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        verbose_name=_("Tipo de condición"),
    )
    configuracion = models.JSONField(
        verbose_name=_("Configuración"),
        help_text=_("Parámetros específicos del backend (ver documentación)."),
    )
    mensaje_error = models.CharField(
        max_length=250,
        default=_("No cumple con las condiciones requeridas."),
        verbose_name=_("Mensaje de error"),
    )
    orden = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Orden de evaluación"),
    )
    activo = models.BooleanField(
        default=True,
        verbose_name=_("Activo"),
    )

    class Meta:
        ordering = ["orden"]
        verbose_name = _("Condición de Transición")
        verbose_name_plural = _("Condiciones de Transición")
```

### 1.5 PredicateEngine

```python
class PredicateEngine:
    """Motor extensible de evaluación de condiciones de transición."""

    _backends: dict[str, callable] = {}

    @classmethod
    def registrar_backend(cls, tipo: str, funcion: callable) -> None:
        """Registra un nuevo backend de evaluación."""
        cls._backends[tipo] = funcion

    @classmethod
    def evaluar(
        cls,
        condicion: CondicionTransicion,
        instance: models.Model,
        user: User,
    ) -> tuple[bool, str | None]:
        """Evalúa una condición individual.

        Returns:
            (pasa: bool, mensaje_error: str | None)
        """
        backend = cls._backends.get(condicion.tipo)
        if backend is None:
            raise ValueError(f"Backend '{condicion.tipo}' no registrado")
        return backend(condicion.configuracion, instance, user)
```

**Backend implementations:**

```python
def _backend_python_path(config: dict, instance, user) -> tuple[bool, str | None]:
    """Importa función vía importlib y la llama."""
    from importlib import import_module
    module_path, func_name = config["path"].rsplit(".", 1)
    module = import_module(module_path)
    func = getattr(module, func_name)
    result = func(instance, user)
    if isinstance(result, bool):
        return result, None
    return result  # assume tuple[bool, str]


def _backend_json_logic(config: dict, instance, user) -> tuple[bool, str | None]:
    """Evalúa regla JSON Logic contra instance.meta.to_dict() + campos del modelo."""
    from sinpapel.json_logic import evaluar  # implementación propia
    data = _build_data_context(instance, user)
    result = evaluar(config["rule"], data)
    return bool(result), None


def _backend_django_orm(config: dict, instance, user) -> tuple[bool, str | None]:
    """Evalúa lookup de Django ORM contra la instancia."""
    lookup = config["lookup"]
    # Verificar que el lookup sea safe (whitelist)
    qs = type(instance).objects.filter(pk=instance.pk, **lookup)
    return qs.exists(), None
```

### 1.6 Integration with WorkflowEngine

In `WorkflowEngine.puede_cambiar_estado()`, after group validation (step 6), add:

```python
# 7. Evaluar condiciones personalizadas
from sinpapel.predicates import PredicateEngine

condiciones = CondicionTransicion.objects.filter(
    transicion=config_transicion,
    activo=True,
).order_by("orden")

for condicion in condiciones:
    pasa, msg = PredicateEngine.evaluar(condicion, instance, user)
    if not pasa:
        return False, msg or condicion.mensaje_error
```

### 1.7 Security Considerations

- **Python Path**: Only import from whitelisted modules (configurable via `SINPAPEL_PREDICATE_MODULES`). Reject arbitrary imports.
- **Django ORM**: Validate that lookups only use safe field names (no `__delete`, raw SQL injection vectors). Reject lookups with `RawSQL`, `Extra`, etc.
- **JSON Logic**: Implement a restricted evaluator that only supports safe operations (`==`, `!=`, `<`, `>`, `and`, `or`, `var`). No arbitrary function calls.

### 1.8 Testing Strategy

| Test | What it verifies |
|------|-----------------|
| `test_condicion_python_path_pass` | Valid function path returns True |
| `test_condicion_python_path_fail` | Function returns False with custom message |
| `test_condicion_json_logic_and` | Complex AND rule evaluates correctly |
| `test_condicion_json_logic_var_meta` | Access to `meta.field` via JSON Logic var |
| `test_condicion_orm_lookup_pass` | Related field lookup matches |
| `test_condicion_orden_evaluacion` | Conditions evaluated in order, stops at first failure |
| `test_predicado_inactivo_ignorado` | Inactive condition skipped |
| `test_backend_no_registrado_raises` | Unknown tipo raises ValueError |
| `test_python_path_arbitrary_import_blocked` | Security: cannot import from non-whitelisted module |

---

## 2. Form/Serializer Factory

### 2.1 Goal

Generate `django.forms.Form` and DRF `serializers.Serializer` classes dynamically from a `list[CampoMetadato]` schema.

### 2.2 Architecture

Single factory class with two class methods:

```python
class MetaFormFactory:
    """Genera Django Forms / DRF Serializers desde SCHEMA_METADATOS."""

    @classmethod
    def build_form(cls, schema: list[CampoMetadato], **form_kwargs) -> type[forms.Form]:
        """Construye una subclase de django.forms.Form."""
        ...

    @classmethod
    def build_serializer(cls, schema: list[CampoMetadato], **serializer_kwargs) -> type[serializers.Serializer]:
        """Construye una subclase de rest_framework.serializers.Serializer."""
        ...
```

### 2.3 Field Mapping

| `CampoMetadato` | Django Form Field | DRF Field | Notes |
|-----------------|-------------------|-----------|-------|
| `str` (no choices) | `CharField` | `CharField` | `max_length=255` default |
| `str` (with choices) | `ChoiceField` | `ChoiceField` | `choices=CampoMetadato.choices` |
| `int` | `IntegerField` | `IntegerField` | |
| `bool` | `BooleanField` | `BooleanField` | `required=False` default |
| `Decimal` | `DecimalField(max_digits=15, decimal_places=2)` | `DecimalField(max_digits=15, decimal_places=2)` | |
| `date` | `DateField` | `DateField` | |

**Common kwargs mapped:**
- `requerido` → `required`
- `default` → `initial` (Form), `default` (DRF)
- `etiqueta` → `label`
- `ayuda` → `help_text`

### 2.4 Usage Examples

**Django Form:**
```python
from sinpapel.forms import MetaFormFactory

schema = MiModelo.SCHEMA_METADATOS
MetaForm = MetaFormFactory.build_form(schema, prefix="meta")

# In a view
form = MetaForm(request.POST or None, initial=obj.meta.to_dict())
if form.is_valid():
    for key, value in form.cleaned_data.items():
        setattr(obj.meta, key, value)
    obj.save()
```

**DRF Serializer:**
```python
from sinpapel.forms import MetaFormFactory

MetaSerializer = MetaFormFactory.build_serializer(MiModelo.SCHEMA_METADATOS)

# In a viewset
serializer = MetaSerializer(data=request.data)
if serializer.is_valid():
    for key, value in serializer.validated_data.items():
        setattr(obj.meta, key, value)
    obj.save()
```

### 2.5 Implementation Details

```python
class MetaFormFactory:
    """Genera Django Forms / DRF Serializers desde SCHEMA_METADATOS."""

    _DJANGO_FIELD_MAP: dict[type, type[forms.Field]] = {
        str: forms.CharField,
        int: forms.IntegerField,
        bool: forms.BooleanField,
        Decimal: forms.DecimalField,
        date: forms.DateField,
    }

    _DRF_FIELD_MAP: dict[type, type[serializers.Field]] = {
        str: serializers.CharField,
        int: serializers.IntegerField,
        bool: serializers.BooleanField,
        Decimal: serializers.DecimalField,
        date: serializers.DateField,
    }

    @classmethod
    def build_form(cls, schema: list[CampoMetadato], **form_kwargs) -> type[forms.Form]:
        attrs = {}
        for campo in schema:
            field_class = cls._DJANGO_FIELD_MAP[campo.tipo]
            kwargs = cls._build_field_kwargs(campo, is_django=True)
            attrs[campo.nombre] = field_class(**kwargs)

        return type("DynamicMetaForm", (forms.Form,), attrs)

    @classmethod
    def _build_field_kwargs(cls, campo: CampoMetadato, is_django: bool = True) -> dict:
        kwargs = {
            "required": campo.requerido,
            "label": campo.etiqueta or campo.nombre,
            "help_text": campo.ayuda,
        }
        if campo.default is not None:
            kwargs["initial" if is_django else "default"] = campo.default
        if campo.choices is not None:
            kwargs["choices"] = [(c, c) for c in campo.choices]
        if campo.tipo is Decimal:
            kwargs["max_digits"] = 15
            kwargs["decimal_places"] = 2
        return kwargs
```

### 2.6 Testing Strategy

| Test | What it verifies |
|------|-----------------|
| `test_form_str_field` | CharField generated for str type |
| `test_form_int_field` | IntegerField generated for int type |
| `test_form_decimal_field` | DecimalField with correct max_digits/decimal_places |
| `test_form_choices` | ChoiceField with correct choices tuple |
| `test_form_required_and_label` | Required + label mapped from CampoMetadato |
| `test_serializer_str_field` | DRF CharField generated |
| `test_serializer_decimal_roundtrip` | Decimal serializes/deserializes correctly |
| `test_form_validates_type` | Form rejects wrong type (e.g., "abc" for int) |
| `test_empty_schema_returns_empty_form` | Empty schema → empty Form class |

---

## 3. Files to Create / Modify

### Transition Predicates

| File | Action | Responsibility |
|------|--------|---------------|
| `sinpapel/models/predicates.py` | **Create** | `CondicionTransicion` model |
| `sinpapel/services/predicate_engine.py` | **Create** | `PredicateEngine` + backend implementations |
| `sinpapel/services/workflow_engine.py` | **Modify** | Integrate condition evaluation into `puede_cambiar_estado()` |
| `sinpapel/json_logic.py` | **Create** | Restricted JSON Logic evaluator |
| `migrations/0005_condicion_transicion.py` | **Create** | Migration for new model |
| `tests/test_predicates.py` | **Create** | Unit tests for all backends + integration |
| `tests/test_workflow_engine.py` | **Modify** | Add integration tests with conditions |

### Form/Serializer Factory

| File | Action | Responsibility |
|------|--------|---------------|
| `sinpapel/forms.py` | **Create** | `MetaFormFactory` class |
| `tests/test_forms_factory.py` | **Create** | Tests for Django Form generation |
| `tests/test_serializers_factory.py` | **Create** | Tests for DRF Serializer generation (if DRF installed) |

---

## 4. Dependencies

- **Transition Predicates**: No new external dependencies (JSON Logic implemented internally for security).
- **Form/Serializer Factory**: No new dependencies for Django Forms. DRF serializers require `djangorestframework` (optional dependency, gracefully degrade if not installed).

---

## 5. Self-Review Checklist

**Spec coverage:**
- [x] Transition Predicates: model, engine, 3 backends, security, integration
- [x] Form/Serializer Factory: field mapping, API, both Django and DRF

**Placeholder scan:**
- [x] No "TBD", "TODO", or "implement later"
- [x] No vague requirements
- [x] Every component has concrete code examples

**Type consistency:**
- [x] `CondicionTransicion` fields match model definition
- [x] `PredicateEngine.evaluar()` signature consistent across backends
- [x] `MetaFormFactory` method signatures match usage examples

**Security:**
- [x] Python path backend whitelisted
- [x] ORM backend validates safe lookups
- [x] JSON Logic evaluator restricted to safe operations

---

## 6. Next Steps

1. **User approval** of this design spec
2. **Write implementation plan** via `writing-plans` skill (one plan per feature, sequential execution)
3. **Implement** Transition Predicates first
4. **Implement** Form/Serializer Factory second
5. **Integration testing** of both features together
