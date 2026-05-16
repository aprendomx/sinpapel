# Preview Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `WorkflowEngine.preview_transition()` that simulates a transition without executing it, returning an impact report. Refactor `puede_cambiar_estado()` to delegate to preview.

**Architecture:** Extract validation logic from `puede_cambiar_estado()` into reusable private methods. `preview_transition()` calls these methods and assembles a report. `puede_cambiar_estado()` delegates to preview for backward compatibility.

**Tech Stack:** Django 5.0+, pytest-django, existing sinpapel models

---

## File Map

| File | Responsibility |
|------|---------------|
| `sinpapel/services/workflow_engine.py` | Modify — add `preview_transition()`, refactor `puede_cambiar_estado()` |
| `tests/test_workflow_engine.py` | Modify — add preview tests |
| `tests/test_predicates.py` | Modify — verify predicate details in preview |

---

## Task 1: Extract validation methods from `puede_cambiar_estado()`

**Files:**
- Modify: `sinpapel/services/workflow_engine.py`
- Test: `tests/test_workflow_engine.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_workflow_engine.py`:

```python
from sinpapel.services.workflow_engine import WorkflowEngine


def test_preview_transition_exists():
    """WorkflowEngine has preview_transition method."""
    assert hasattr(WorkflowEngine, "preview_transition")
```

Run: `/usr/local/bin/python3.13 -m pytest tests/test_workflow_engine.py::test_preview_transition_exists -v`
Expected: FAIL — `preview_transition` not defined.

- [ ] **Step 2: Extract validation methods**

In `sinpapel/services/workflow_engine.py`, refactor `puede_cambiar_estado()` by extracting these private methods (before `puede_cambiar_estado`):

```python
    def _validar_estado_destino(self, target_state_name: str):
        """Valida que el estado destino existe."""
        from sinpapel.cache import get_estado_by_name
        estado_destino = get_estado_by_name(target_state_name)
        if estado_destino is None:
            return None, f"Estado destino '{target_state_name}' no existe"
        return estado_destino, None

    def _validar_configuracion_transicion(
        self, estado_actual, estado_destino, flujo
    ):
        """Busca la configuración de transición."""
        from sinpapel.models import ConfiguracionTransicion
        qs = ConfiguracionTransicion.objects.filter(
            estado_origen=estado_actual,
            estado_destino=estado_destino,
        )
        if flujo is not None:
            qs = qs.filter(flujo=flujo)
        config_transicion = qs.first()
        if config_transicion is None:
            return None, (
                f"No se puede cambiar de '{estado_actual.nombre}' a "
                f"'{estado_destino.nombre}'"
            )
        return config_transicion, None

    def _validar_grupos_permitidos(self, config_transicion, user):
        """Valida que el usuario tiene permisos."""
        if user.is_superuser:
            return True, None
        grupos_requeridos = list(
            config_transicion.grupos_permitidos.values_list("name", flat=True)
        )
        if grupos_requeridos:
            grupos_user = list(user.groups.values_list("name", flat=True))
            if not any(g in grupos_requeridos for g in grupos_user):
                return False, "No tiene permisos para realizar esta acción"
        return True, None

    def _validar_documentos(self, instance, estado_actual):
        """Verifica requisitos documentales. Retorna lista de faltantes."""
        faltantes = []
        if estado_actual.expediente_obligatorio:
            expedientes = getattr(instance, "expedientes", None)
            if expedientes is not None and not expedientes.exists():
                faltantes.append({
                    "tipo": "expediente",
                    "mensaje": f"Se requiere adjuntar al menos un documento antes de avanzar desde '{estado_actual.nombre}'.",
                })
        return faltantes

    def _validar_predicados(self, config_transicion, instance, user):
        """Evalúa condiciones de transición. Retorna lista de fallidas."""
        from sinpapel.models.predicates import CondicionTransicion
        from sinpapel.services.predicate_engine import PredicateEngine

        fallidas = []
        condiciones = CondicionTransicion.objects.filter(
            transicion=config_transicion,
            activo=True,
        ).order_by("orden")

        for condicion in condiciones:
            pasa, msg = PredicateEngine.evaluar(condicion, instance, user)
            if not pasa:
                fallidas.append({
                    "condicion_id": condicion.id,
                    "tipo": condicion.tipo,
                    "mensaje": msg or condicion.mensaje_error,
                })
        return fallidas
```

- [ ] **Step 3: Refactor `puede_cambiar_estado()` to use extracted methods**

Replace the body of `puede_cambiar_estado()` with calls to extracted methods, keeping the same logic flow:

```python
    def puede_cambiar_estado(
        self,
        instance: "models.Model",
        target_state_name: str,
        user: "User",
    ) -> tuple[bool, str | None]:
        config = self._get_config(instance)
        estado_actual = getattr(instance, config.state_field, None)
        if estado_actual is None:
            return False, "Instance has no current state"

        estado_destino, error = self._validar_estado_destino(target_state_name)
        if error:
            return False, error

        flujo = self._resolve_flujo(instance, config)
        config_transicion, error = self._validar_configuracion_transicion(
            estado_actual, estado_destino, flujo
        )
        if error:
            return False, error

        if user.is_superuser:
            return True, "OK"

        documentos_faltantes = self._validar_documentos(instance, estado_actual)
        if documentos_faltantes:
            return False, documentos_faltantes[0]["mensaje"]

        permisos_ok, error = self._validar_grupos_permitidos(config_transicion, user)
        if not permisos_ok:
            return False, error

        predicados_fallidos = self._validar_predicados(config_transicion, instance, user)
        if predicados_fallidos:
            return False, predicados_fallidos[0]["mensaje"]

        return True, "OK"
```

- [ ] **Step 4: Run tests to verify refactoring didn't break anything**

Run: `/usr/local/bin/python3.13 -m pytest tests/test_workflow_engine.py -v`
Expected: PASS (all existing tests)

- [ ] **Step 5: Commit**

```bash
git add sinpapel/services/workflow_engine.py
git commit -m "refactor(workflow): extract validation methods from puede_cambiar_estado"
```

---

## Task 2: Implement `preview_transition()`

**Files:**
- Modify: `sinpapel/services/workflow_engine.py`
- Test: `tests/test_workflow_engine.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_workflow_engine.py`:

```python
from sinpapel.models import Estado
from sinpapel.services.side_effects import SIDE_EFFECTS


def test_preview_transition_permitido():
    """Preview returns permitido=True when all validations pass."""
    from django.contrib.auth.models import User
    from tests.models import TestSolicitud
    from sinpapel.models import Estado, VersionFlujo

    estado = Estado.objects.create(nombre="PREV_OK", activo=True)
    flujo = VersionFlujo.objects.create(nombre="PREV_F", activo=True)
    solicitud = TestSolicitud.objects.create(folio="PREV-001", estado=estado)
    user = User.objects.create_superuser("prev_ok", password="x")

    preview = WorkflowEngine().preview_transition(solicitud, "PREV_OK", user)
    assert preview["permitido"] is True
    assert preview["razones_bloqueo"] == []


def test_preview_transition_bloqueado_permiso():
    """Preview returns permitido=False with permission error."""
    from django.contrib.auth.models import User
    from tests.models import TestSolicitud
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo

    estado_origen = Estado.objects.create(nombre="PREV_ORIG", activo=True)
    estado_destino = Estado.objects.create(nombre="PREV_DEST", activo=True)
    flujo = VersionFlujo.objects.create(nombre="PREV_F2", activo=True)
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino
    )
    solicitud = TestSolicitud.objects.create(folio="PREV-002", estado=estado_origen)
    user = User.objects.create_user("prev_no", password="x")

    preview = WorkflowEngine().preview_transition(solicitud, "PREV_DEST", user)
    assert preview["permitido"] is False
    assert any(r["tipo"] == "permiso" for r in preview["razones_bloqueo"])


def test_preview_no_muta_instancia():
    """Preview does not change instance state."""
    from django.contrib.auth.models import User
    from tests.models import TestSolicitud
    from sinpapel.models import Estado

    estado = Estado.objects.create(nombre="PREV_MUTA", activo=True)
    solicitud = TestSolicitud.objects.create(folio="PREV-003", estado=estado)
    user = User.objects.create_superuser("prev_muta", password="x")

    estado_before = solicitud.estado
    WorkflowEngine().preview_transition(solicitud, "PREV_MUTA", user)
    assert solicitud.estado == estado_before
```

Run: `/usr/local/bin/python3.13 -m pytest tests/test_workflow_engine.py -k "preview" -v`
Expected: FAIL — `preview_transition` not defined.

- [ ] **Step 2: Implement `preview_transition()`**

Add to `WorkflowEngine` in `sinpapel/services/workflow_engine.py`:

```python
    def preview_transition(
        self,
        instance: "models.Model",
        target_state_name: str,
        user: "User",
    ) -> dict[str, Any]:
        """Simula una transición y retorna un reporte de impacto.

        NO muta la instancia ni persiste nada.

        Returns:
            dict con keys: permitido, razones_bloqueo, side_effects,
            documentos_faltantes, predicados_fallidos, aprobadores_requeridos,
            historial_reciente
        """
        from sinpapel.services.side_effects import SIDE_EFFECTS
        from sinpapel.models import SeguimientoWorkflow

        config = self._get_config(instance)
        estado_actual = getattr(instance, config.state_field, None)

        reporte: dict[str, Any] = {
            "permitido": True,
            "razones_bloqueo": [],
            "side_effects": [],
            "documentos_faltantes": [],
            "predicados_fallidos": [],
            "aprobadores_requeridos": [],
            "historial_reciente": [],
        }

        # 1. Validar estado actual
        if estado_actual is None:
            reporte["permitido"] = False
            reporte["razones_bloqueo"].append({
                "tipo": "estado",
                "mensaje": "Instance has no current state",
            })
            return reporte

        # 2. Validar estado destino
        estado_destino, error = self._validar_estado_destino(target_state_name)
        if error:
            reporte["permitido"] = False
            reporte["razones_bloqueo"].append({
                "tipo": "estado",
                "mensaje": error,
            })
            return reporte

        # 3. Validar configuración de transición
        flujo = self._resolve_flujo(instance, config)
        config_transicion, error = self._validar_configuracion_transicion(
            estado_actual, estado_destino, flujo
        )
        if error:
            reporte["permitido"] = False
            reporte["razones_bloqueo"].append({
                "tipo": "transicion",
                "mensaje": error,
            })
            return reporte

        # 4. Documentos faltantes
        documentos = self._validar_documentos(instance, estado_actual)
        if documentos:
            reporte["documentos_faltantes"] = documentos
            reporte["permitido"] = False
            for doc in documentos:
                reporte["razones_bloqueo"].append({
                    "tipo": "documento",
                    "mensaje": doc["mensaje"],
                })

        # 5. Permisos (si no es superuser)
        if not user.is_superuser:
            permisos_ok, error = self._validar_grupos_permitidos(config_transicion, user)
            if not permisos_ok:
                reporte["permitido"] = False
                reporte["razones_bloqueo"].append({
                    "tipo": "permiso",
                    "mensaje": error,
                })

        # 6. Predicados
        predicados = self._validar_predicados(config_transicion, instance, user)
        if predicados:
            reporte["predicados_fallidos"] = predicados
            reporte["permitido"] = False
            for pred in predicados:
                reporte["razones_bloqueo"].append({
                    "tipo": "predicado",
                    "mensaje": pred["mensaje"],
                })

        # 7. Side effects
        reporte["side_effects"] = [
            name for name in SIDE_EFFECTS.keys()
            if name == target_state_name
        ]

        # 8. Historial reciente
        reporte["historial_reciente"] = self._obtener_historial_reciente(instance)

        return reporte

    def _obtener_historial_reciente(self, instance: "models.Model") -> list[dict]:
        """Retorna últimos seguimientos de la instancia."""
        from sinpapel.models import SeguimientoWorkflow
        try:
            seguimientos = SeguimientoWorkflow.objects.filter(
                target=instance
            ).order_by("-fecha_accion")[:5]
            return [
                {
                    "fecha": seg.fecha_accion.isoformat(),
                    "transicion": f"{seg.estado_anterior.nombre if seg.estado_anterior else 'Nuevo'} → {seg.estado_nuevo.nombre}",
                    "usuario": seg.usuario_accion.username if seg.usuario_accion else None,
                    "comentarios": seg.comentarios,
                }
                for seg in seguimientos
            ]
        except Exception:
            return []
```

- [ ] **Step 3: Refactor `puede_cambiar_estado()` to delegate to preview**

Replace `puede_cambiar_estado()` body:

```python
    def puede_cambiar_estado(
        self,
        instance: "models.Model",
        target_state_name: str,
        user: "User",
    ) -> tuple[bool, str | None]:
        preview = self.preview_transition(instance, target_state_name, user)
        if not preview["permitido"]:
            return False, preview["razones_bloqueo"][0]["mensaje"]
        return True, "OK"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python3.13 -m pytest tests/test_workflow_engine.py -k "preview" -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run full suite to check regressions**

Run: `/usr/local/bin/python3.13 -m pytest tests/ -q`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add sinpapel/services/workflow_engine.py tests/test_workflow_engine.py
git commit -m "feat(workflow): add preview_transition() with impact report

Refactors puede_cambiar_estado() to delegate to preview_transition().
Extracts validation logic into reusable private methods."
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] preview_transition() API → Task 2
- [x] Impact report structure → Task 2
- [x] Refactoring of puede_cambiar_estado() → Task 1 + 2
- [x] No mutation guarantee → Task 2 (test_preview_no_muta_instancia)
- [x] Historial reciente → Task 2

**2. Placeholder scan:**
- [x] No "TBD", "TODO", or "implement later"
- [x] No vague requirements
- [x] Every code step contains actual code

**3. Type consistency:**
- [x] preview_transition() signature matches spec
- [x] Report structure matches spec
- [x] puede_cambiar_estado() delegates correctly

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-14-preview-transition.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
