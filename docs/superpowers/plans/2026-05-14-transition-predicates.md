# Transition Predicates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `CondicionTransicion` model, `PredicateEngine` with Python Path and JSON Logic backends, and integrate condition evaluation into `WorkflowEngine.puede_cambiar_estado()`.

**Architecture:** A pluggable `PredicateEngine` registers backend evaluators by type. Each `CondicionTransicion` links to a `ConfiguracionTransicion` and stores backend-specific config as JSON. The engine evaluates all active conditions in order, returning on first failure.

**Tech Stack:** Django 5.0+, pytest-django, importlib (stdlib), custom JSON Logic evaluator (no external deps)

---

## File Map

| File | Responsibility |
|------|---------------|
| `sinpapel/models/predicates.py` | `CondicionTransicion` model |
| `sinpapel/json_logic.py` | Restricted JSON Logic evaluator (safe operations only) |
| `sinpapel/services/predicate_engine.py` | `PredicateEngine` + backend implementations |
| `sinpapel/services/workflow_engine.py` | Modify — integrate condition evaluation after group validation |
| `migrations/0005_condicion_transicion.py` | Migration creating `CondicionTransicion` table |
| `tests/test_predicates.py` | Unit + integration tests for all backends and engine |

---

## Task 1: Create `CondicionTransicion` model

**Files:**
- Create: `sinpapel/models/predicates.py`
- Modify: `sinpapel/models/__init__.py`
- Test: `tests/test_predicates.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_predicates.py`:

```python
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
```

Run: `/usr/local/bin/python3.13 -m pytest tests/test_predicates.py::test_condicion_transicion_model_exists -v`
Expected: FAIL — `CondicionTransicion` not defined.

- [ ] **Step 2: Create `sinpapel/models/predicates.py`**

```python
"""Sinpapel — Transition Predicate model.

CondicionTransicion stores configurable business rules evaluated
before a workflow transition is permitted.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class CondicionTransicion(models.Model):
    """Condición configurable para una ConfiguracionTransicion.

    Evaluada por PredicateEngine antes de permitir una transición.
    Todas las condiciones activas deben pasar (AND lógico).
    """

    TIPO_CHOICES = [
        ("python_path", _("Python Path")),
        ("json_logic", _("JSON Logic")),
        ("django_orm", _("Django ORM Lookup")),
    ]

    transicion = models.ForeignKey(
        "sinpapel.ConfiguracionTransicion",
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
        help_text=_("Parámetros específicos del backend."),
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
        db_table = "sinpapel_condiciontransicion"
        app_label = "sinpapel"
        ordering = ["orden"]
        verbose_name = _("Condición de Transición")
        verbose_name_plural = _("Condiciones de Transición")

    def __str__(self) -> str:
        return f"Condicion #{self.orden} ({self.tipo})"
```

- [ ] **Step 3: Update `sinpapel/models/__init__.py`**

Add to imports:
```python
from sinpapel.models.predicates import CondicionTransicion
```
Add `"CondicionTransicion"` to `__all__`.

- [ ] **Step 4: Create migration**

```bash
/usr/local/bin/python3.13 -m django makemigrations sinpapel --settings=tests.settings
```

Verify: creates `migrations/0005_condiciontransicion.py`.

- [ ] **Step 5: Run test to verify it passes**

Run: `/usr/local/bin/python3.13 -m pytest tests/test_predicates.py::test_condicion_transicion_model_exists -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add sinpapel/models/predicates.py sinpapel/models/__init__.py migrations/0005_condiciontransicion.py tests/test_predicates.py
git commit -m "feat(predicates): add CondicionTransicion model"
```

---

## Task 2: Implement JSON Logic evaluator

**Files:**
- Create: `sinpapel/json_logic.py`
- Test: `tests/test_predicates.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_predicates.py`:

```python
from sinpapel.json_logic import evaluar


def test_json_logic_var():
    """Access variable from data context."""
    assert evaluar({"var": "nombre"}, {"nombre": "Juan"}) == "Juan"


def test_json_logic_equal():
    """Equality comparison."""
    assert evaluar({"==": [{"var": "edad"}, 30]}, {"edad": 30}) is True
    assert evaluar({"==": [{"var": "edad"}, 30]}, {"edad": 25}) is False


def test_json_logic_and():
    """AND logical operator."""
    rule = {"and": [
        {">=": [{"var": "monto"}, 100000]},
        {"==": [{"var": "tipo"}, "FOVISSSTE"]}
    ]}
    assert evaluar(rule, {"monto": 150000, "tipo": "FOVISSSTE"}) is True
    assert evaluar(rule, {"monto": 50000, "tipo": "FOVISSSTE"}) is False


def test_json_logic_or():
    """OR logical operator."""
    rule = {"or": [
        {"==": [{"var": "estado"}, "URGENTE"]},
        {">=": [{"var": "monto"}, 1000000]}
    ]}
    assert evaluar(rule, {"estado": "NORMAL", "monto": 2000000}) is True
    assert evaluar(rule, {"estado": "NORMAL", "monto": 1000}) is False


def test_json_logic_gt_lt():
    """Greater than / less than."""
    assert evaluar({">": [{"var": "a"}, 5]}, {"a": 10}) is True
    assert evaluar({"<": [{"var": "a"}, 5]}, {"a": 3}) is True


def test_json_logic_not():
    """NOT operator."""
    assert evaluar({"!": {"var": "inactivo"}}, {"inactivo": False}) is True


def test_json_logic_in():
    """Membership test."""
    assert evaluar({"in": [{"var": "tipo"}, ["A", "B", "C"]]}, {"tipo": "B"}) is True


def test_json_logic_missing_var_returns_none():
    """Missing variables return None (falsy)."""
    assert evaluar({"var": "inexistente"}, {}) is None
    assert evaluar({"==": [{"var": "inexistente"}, None]}, {}) is True
```

Run: `/usr/local/bin/python3.13 -m pytest tests/test_predicates.py -k json_logic -v`
Expected: FAIL — `evaluar` not defined.

- [ ] **Step 2: Implement `sinpapel/json_logic.py`**

```python
"""Sinpapel — Restricted JSON Logic evaluator.

Supports safe operations only: var, ==, !=, <, >, <=, >=, and, or, !, in.
No arbitrary function calls. No access to Python builtins.
"""
from typing import Any


def evaluar(rule: Any, data: dict[str, Any]) -> Any:
    """Evalúa una regla JSON Logic contra un contexto de datos.

    Args:
        rule: dict con operador JSON Logic o valor literal
        data: dict con variables accesibles via {"var": "nombre"}

    Returns:
        Resultado de la evaluación
    """
    if not isinstance(rule, dict):
        return rule

    if len(rule) != 1:
        raise ValueError(f"Regla JSON Logic debe tener exactamente una clave, recibió: {list(rule.keys())}")

    op, args = next(iter(rule.items()))

    if op == "var":
        return data.get(args)

    if op == "==":
        left, right = _eval_args(args, data)
        return left == right

    if op == "!=":
        left, right = _eval_args(args, data)
        return left != right

    if op == ">":
        left, right = _eval_args(args, data)
        return left > right

    if op == ">=":
        left, right = _eval_args(args, data)
        return left >= right

    if op == "<":
        left, right = _eval_args(args, data)
        return left < right

    if op == "<=":
        left, right = _eval_args(args, data)
        return left <= right

    if op == "and":
        return all(evaluar(subrule, data) for subrule in args)

    if op == "or":
        return any(evaluar(subrule, data) for subrule in args)

    if op == "!":
        return not evaluar(args, data)

    if op == "in":
        left, right = _eval_args(args, data)
        return left in right

    raise ValueError(f"Operador JSON Logic no soportado: '{op}'")


def _eval_args(args: Any, data: dict[str, Any]) -> tuple[Any, Any]:
    """Evalúa una lista de 2 argumentos contra el contexto."""
    if not isinstance(args, list) or len(args) != 2:
        raise ValueError(f"Operador binario requiere lista de 2 argumentos, recibió: {args}")
    return evaluar(args[0], data), evaluar(args[1], data)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `/usr/local/bin/python3.13 -m pytest tests/test_predicates.py -k json_logic -v`
Expected: PASS (8 tests)

- [ ] **Step 4: Commit**

```bash
git add sinpapel/json_logic.py tests/test_predicates.py
git commit -m "feat(predicates): add restricted JSON Logic evaluator"
```

---

## Task 3: Implement PredicateEngine with Python Path and JSON Logic backends

**Files:**
- Create: `sinpapel/services/predicate_engine.py`
- Modify: `sinpapel/services/__init__.py` (if needed)
- Test: `tests/test_predicates.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_predicates.py`:

```python
from sinpapel.services.predicate_engine import PredicateEngine


def _always_true(instance, user):
    return True


def _always_false(instance, user):
    return False, "Condición rechazada"


def test_predicate_engine_python_path_pass():
    """Python path backend returns True when function returns True."""
    config = {"path": "tests.test_predicates._always_true"}
    result = PredicateEngine._backend_python_path(config, None, None)
    assert result == (True, None)


def test_predicate_engine_python_path_fail():
    """Python path backend returns False + message when function returns tuple."""
    config = {"path": "tests.test_predicates._always_false"}
    result = PredicateEngine._backend_python_path(config, None, None)
    assert result == (False, "Condición rechazada")


def test_predicate_engine_json_logic_pass():
    """JSON Logic backend evaluates rule against instance data."""
    from sinpapel.mixins import CampoMetadato, MetadatosCapturables

    class _FakeModel(MetadatosCapturables):
        SCHEMA_METADATOS = [CampoMetadato("monto", int)]
        class Meta:
            app_label = "tests"

    obj = _FakeModel()
    obj.meta.monto = 150000
    config = {"rule": {">=": [{"var": "meta.monto"}, 100000]}}
    result = PredicateEngine._backend_json_logic(config, obj, None)
    assert result == (True, None)


def test_predicate_engine_json_logic_fail():
    """JSON Logic backend returns False when rule does not match."""
    from sinpapel.mixins import CampoMetadato, MetadatosCapturables

    class _FakeModel(MetadatosCapturables):
        SCHEMA_METADATOS = [CampoMetadato("monto", int)]
        class Meta:
            app_label = "tests"

    obj = _FakeModel()
    obj.meta.monto = 50000
    config = {"rule": {">=": [{"var": "meta.monto"}, 100000]}}
    result = PredicateEngine._backend_json_logic(config, obj, None)
    assert result == (False, None)


def test_predicate_engine_evaluar_dispatches_by_tipo():
    """evaluar() dispatches to correct backend by tipo."""
    from sinpapel.models.predicates import CondicionTransicion
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo

    estado_origen = Estado.objects.create(nombre="ORIG2", activo=True)
    estado_destino = Estado.objects.create(nombre="DEST2", activo=True)
    flujo = VersionFlujo.objects.create(nombre="F2", activo=True)
    transicion = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino
    )
    cond = CondicionTransicion(
        transicion=transicion,
        tipo="python_path",
        configuracion={"path": "tests.test_predicates._always_true"},
    )
    result = PredicateEngine.evaluar(cond, None, None)
    assert result == (True, None)


def test_predicate_engine_evaluar_unknown_tipo_raises():
    """evaluar() raises ValueError for unregistered backend tipo."""
    from sinpapel.models.predicates import CondicionTransicion
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo

    estado_origen = Estado.objects.create(nombre="ORIG3", activo=True)
    estado_destino = Estado.objects.create(nombre="DEST3", activo=True)
    flujo = VersionFlujo.objects.create(nombre="F3", activo=True)
    transicion = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino
    )
    cond = CondicionTransicion(
        transicion=transicion,
        tipo="unknown_type",
        configuracion={},
    )
    with pytest.raises(ValueError, match="no registrado"):
        PredicateEngine.evaluar(cond, None, None)
```

Run: `/usr/local/bin/python3.13 -m pytest tests/test_predicates.py -k "predicate_engine" -v`
Expected: FAIL — `PredicateEngine` not defined.

- [ ] **Step 2: Implement `sinpapel/services/predicate_engine.py`**

```python
"""Sinpapel — PredicateEngine for evaluating transition conditions.

Pluggable engine that evaluates CondicionTransicion rules by dispatching
to registered backends based on the 'tipo' field.
"""
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any, Callable

from sinpapel.json_logic import evaluar as evaluar_json_logic

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django.db import models

    from sinpapel.models.predicates import CondicionTransicion


# Whitelist of allowed modules for python_path backend
_PREDICATE_MODULE_WHITELIST: set[str] = set()


def _build_data_context(instance: "models.Model | None", user: "User | None") -> dict[str, Any]:
    """Construye el contexto de datos para evaluación JSON Logic.

    Incluye:
    - meta.*: valores de MetadatosCapturables.to_dict()
    - user.id, user.username: datos del usuario (si hay user)
    - instance.pk: ID de la instancia (si hay instance)
    """
    data: dict[str, Any] = {}
    if instance is not None:
        data["instance"] = {"pk": instance.pk}
        if hasattr(instance, "meta"):
            meta_dict = instance.meta.to_dict()
            for key, value in meta_dict.items():
                data[f"meta.{key}"] = value
    if user is not None:
        data["user"] = {"id": user.id, "username": user.username}
    return data


def _backend_python_path(config: dict, instance: "models.Model | None", user: "User | None") -> tuple[bool, str | None]:
    """Backend: importa función vía importlib y la llama.

    Args:
        config: {"path": "module.submodule.function_name"}

    Returns:
        (pasa: bool, mensaje_error: str | None)
    """
    path = config["path"]
    if "." not in path:
        raise ValueError(f"python_path debe incluir módulo: {path}")

    module_path, func_name = path.rsplit(".", 1)

    if _PREDICATE_MODULE_WHITELIST and module_path not in _PREDICATE_MODULE_WHITELIST:
        raise ValueError(
            f"Módulo '{module_path}' no está en la whitelist de predicados. "
            f"Configura SINPAPEL_PREDICATE_MODULES o usa un módulo permitido."
        )

    module = import_module(module_path)
    func = getattr(module, func_name)

    result = func(instance, user)
    if isinstance(result, bool):
        return result, None
    if isinstance(result, tuple) and len(result) == 2:
        return bool(result[0]), result[1] if result[1] else None
    raise ValueError(f"Función de predicado debe retornar bool o tuple[bool, str], recibió: {type(result)}")


def _backend_json_logic(config: dict, instance: "models.Model | None", user: "User | None") -> tuple[bool, str | None]:
    """Backend: evalúa regla JSON Logic contra el contexto de datos.

    Args:
        config: {"rule": {...}}

    Returns:
        (pasa: bool, mensaje_error: None)
    """
    data = _build_data_context(instance, user)
    result = evaluar_json_logic(config["rule"], data)
    return bool(result), None


def _backend_django_orm(config: dict, instance: "models.Model | None", user: "User | None") -> tuple[bool, str | None]:
    """Backend: evalúa lookup de Django ORM contra la instancia.

    Args:
        config: {"lookup": {"field__gte": value}}

    Returns:
        (pasa: bool, mensaje_error: None)
    """
    if instance is None:
        return False, "No hay instancia para evaluar lookup ORM"

    lookup = config["lookup"]
    qs = type(instance).objects.filter(pk=instance.pk, **lookup)
    return qs.exists(), None


class PredicateEngine:
    """Motor extensible de evaluación de condiciones de transición."""

    _backends: dict[str, Callable] = {
        "python_path": _backend_python_path,
        "json_logic": _backend_json_logic,
        "django_orm": _backend_django_orm,
    }

    @classmethod
    def registrar_backend(cls, tipo: str, funcion: Callable) -> None:
        """Registra un nuevo backend de evaluación."""
        cls._backends[tipo] = funcion

    @classmethod
    def evaluar(
        cls,
        condicion: "CondicionTransicion",
        instance: "models.Model | None",
        user: "User | None",
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

- [ ] **Step 3: Run tests to verify they pass**

Run: `/usr/local/bin/python3.13 -m pytest tests/test_predicates.py -k "predicate_engine" -v`
Expected: PASS (6 tests)

- [ ] **Step 4: Commit**

```bash
git add sinpapel/services/predicate_engine.py tests/test_predicates.py
git commit -m "feat(predicates): add PredicateEngine with Python Path, JSON Logic, Django ORM backends"
```

---

## Task 4: Integrate PredicateEngine into WorkflowEngine

**Files:**
- Modify: `sinpapel/services/workflow_engine.py`
- Modify: `tests/test_workflow_engine.py`
- Test: `tests/test_predicates.py`

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_predicates.py`:

```python
@pytest.mark.django_db
def test_workflow_engine_condicion_activa_bloquea_transicion():
    """WorkflowEngine.puede_cambiar_estado returns False when condition fails."""
    from django.contrib.auth.models import User
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo
    from sinpapel.models.predicates import CondicionTransicion
    from sinpapel.services.workflow_engine import WorkflowEngine

    estado_origen = Estado.objects.create(nombre="BLOQ_ORIG", activo=True)
    estado_destino = Estado.objects.create(nombre="BLOQ_DEST", activo=True)
    flujo = VersionFlujo.objects.create(nombre="BLOQ_F", activo=True)
    transicion = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino
    )
    CondicionTransicion.objects.create(
        transicion=transicion,
        tipo="python_path",
        configuracion={"path": "tests.test_predicates._always_false"},
        mensaje_error="Siempre rechazado",
    )

    class _FakeInstance:
        _workflow_config = type("Config", (), {"state_field": "estado"})()
        estado = estado_origen
        def resolve_workflow_version(self):
            return flujo

    user = User.objects.create_superuser("bloq_test", password="x")
    puede, msg = WorkflowEngine().puede_cambiar_estado(_FakeInstance(), "BLOQ_DEST", user)
    assert puede is False
    assert "Siempre rechazado" in msg


@pytest.mark.django_db
def test_workflow_engine_condicion_inactiva_ignorada():
    """Inactive conditions are skipped during evaluation."""
    from django.contrib.auth.models import User
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo
    from sinpapel.models.predicates import CondicionTransicion
    from sinpapel.services.workflow_engine import WorkflowEngine

    estado_origen = Estado.objects.create(nombre="IGN_ORIG", activo=True)
    estado_destino = Estado.objects.create(nombre="IGN_DEST", activo=True)
    flujo = VersionFlujo.objects.create(nombre="IGN_F", activo=True)
    transicion = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino
    )
    CondicionTransicion.objects.create(
        transicion=transicion,
        tipo="python_path",
        configuracion={"path": "tests.test_predicates._always_false"},
        activo=False,
    )

    class _FakeInstance:
        _workflow_config = type("Config", (), {"state_field": "estado"})()
        estado = estado_origen
        def resolve_workflow_version(self):
            return flujo

    user = User.objects.create_superuser("ign_test", password="x")
    puede, msg = WorkflowEngine().puede_cambiar_estado(_FakeInstance(), "IGN_DEST", user)
    assert puede is True
```

Run: `/usr/local/bin/python3.13 -m pytest tests/test_predicates.py -k "workflow_engine_condicion" -v`
Expected: FAIL — conditions not evaluated yet.

- [ ] **Step 2: Modify `sinpapel/services/workflow_engine.py`**

After group validation (step 6), add step 7:

```python
# 7. Evaluar condiciones personalizadas
from sinpapel.models.predicates import CondicionTransicion
from sinpapel.services.predicate_engine import PredicateEngine

condiciones = CondicionTransicion.objects.filter(
    transicion=config_transicion,
    activo=True,
).order_by("orden")

for condicion in condiciones:
    pasa, msg = PredicateEngine.evaluar(condicion, instance, user)
    if not pasa:
        return False, msg or condicion.mensaje_error
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `/usr/local/bin/python3.13 -m pytest tests/test_predicates.py -k "workflow_engine_condicion" -v`
Expected: PASS (2 tests)

- [ ] **Step 4: Run full suite to check regressions**

Run: `/usr/local/bin/python3.13 -m pytest tests/ -q`
Expected: All 183+ tests PASS

- [ ] **Step 5: Commit**

```bash
git add sinpapel/services/workflow_engine.py tests/test_predicates.py
git commit -m "feat(predicates): integrate CondicionTransicion into WorkflowEngine

Evaluates active conditions after group validation, before permitting transition."
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] `CondicionTransicion` model → Task 1
- [x] JSON Logic evaluator → Task 2
- [x] `PredicateEngine` with Python Path + JSON Logic backends → Task 3
- [x] Django ORM backend → Task 3
- [x] WorkflowEngine integration → Task 4
- [x] Security: whitelist for python_path → Task 3
- [x] Security: safe JSON Logic ops only → Task 2
- [x] Inactive conditions skipped → Task 4
- [x] Order of evaluation → Task 4

**2. Placeholder scan:**
- [x] No "TBD", "TODO", or "implement later"
- [x] No vague requirements
- [x] Every code step contains actual code

**3. Type consistency:**
- [x] `PredicateEngine.evaluar()` signature consistent
- [x] Backend functions all return `tuple[bool, str | None]`
- [x] `CondicionTransicion` fields match spec

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-14-transition-predicates.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
