# State Timers / SLA + Preview Transition Design Spec

> **Date:** 2026-05-14
> **Status:** Approved
> **Scope:** Two features for sinpapel v0.4.0 roadmap:
> 1. **State Timers / SLA** (`SLAConfiguracion`) — configurable time limits per state with automatic actions (notify, escalate, reject, flag)
> 2. **Preview Transition** (`WorkflowEngine.preview_transition()`) — simulate a transition without executing it, returning an impact report

---

## Context

`sinpapel` v0.3.0 has a working workflow engine with group-based permissions, document gates, transition predicates (Python Path, JSON Logic, ORM), and structured metadata capture. These two features fill the biggest remaining operational gaps.

**State Timers / SLA** addresses the limitation that there is no automated monitoring of how long an instance remains in a given state. In real-world transaction processing (government, financial, etc.), SLAs are critical for compliance and operational efficiency. Currently, developers must implement ad-hoc cron jobs or Celery tasks to handle overdue states.

**Preview Transition** addresses the user experience gap where approvers cannot see the full impact of a transition before clicking "Approve". They need visibility into: failing predicates, missing documents, side effects that will trigger, and recent history.

---

## 1. State Timers / SLA

### 1.1 Goal

Add an `SLAConfiguracion` model linked to `Estado`. Each SLA config defines a maximum time limit (`dias_maximos`) and an action (`accion_vencimiento`) to execute when the limit is exceeded. A management command `sinpapel_verificar_slas` evaluates all active SLAs against workflow-enabled instances and executes the configured actions.

### 1.2 Architecture

Three components:

| Component | Responsibility |
|-----------|---------------|
| `SLAConfiguracion` | Model storing SLA rules (estado, dias_maximos, accion, configuracion JSON, activo) |
| `SLAEngine` | Evaluates SLAs against instances and dispatches actions |
| `sinpapel_verificar_slas` | Management command that triggers SLA evaluation |

### 1.3 Actions

| Action | `accion_vencimiento` | `configuracion_accion` schema | Behavior |
|--------|----------------------|------------------------------|----------|
| **Notify** | `notificar` | `{"grupo_id": int, "template": str}` | Send email/notification to a Django group |
| **Escalate** | `escalar` | `{"estado_destino": "nombre_estado"}` | Auto-transition instance to target state |
| **Reject** | `rechazar` | `{"estado_destino": "nombre_estado"}` | Auto-transition instance to rejection state |
| **Flag** | `alertar` | `{"campo": str, "valor": any}` | Set a boolean/flag field on the instance |

### 1.4 Data Model

```python
class SLAConfiguracion(models.Model):
    """Configuración de SLA por estado: tiempo máximo y acción al vencer."""

    ACCION_CHOICES = [
        ("notificar", _("Notificar")),
        ("escalar", _("Escalar")),
        ("rechazar", _("Rechazar")),
        ("alertar", _("Alertar / Bandera")),
    ]

    estado = models.ForeignKey(
        "sinpapel.Estado",
        on_delete=models.CASCADE,
        related_name="slas",
        verbose_name=_("Estado"),
    )
    dias_maximos = models.PositiveIntegerField(
        verbose_name=_("Días máximos"),
        help_text=_("Tiempo máximo permitido en este estado antes de ejecutar la acción."),
    )
    accion_vencimiento = models.CharField(
        max_length=20,
        choices=ACCION_CHOICES,
        verbose_name=_("Acción al vencer"),
    )
    configuracion_accion = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Configuración de acción"),
        help_text=_("Parámetros específicos de la acción (ver documentación)."),
    )
    activo = models.BooleanField(
        default=True,
        verbose_name=_("Activo"),
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sinpapel_sla_configuracion"
        app_label = "sinpapel"
        verbose_name = _("Configuración SLA")
        verbose_name_plural = _("Configuraciones SLA")
        unique_together = [["estado", "accion_vencimiento"]]

    def __str__(self) -> str:
        return f"{self.estado.nombre}: {self.dias_maximos}d → {self.accion_vencimiento}"
```

### 1.5 SLAEngine

```python
class SLAEngine:
    """Motor de evaluación y ejecución de SLAs."""

    @classmethod
    def verificar_todos(cls) -> dict[str, int]:
        """Evalúa todos los SLAs activos contra todas las instancias workflow-enabled.

        Returns:
            dict con conteo por acción ejecutada: {"notificar": 5, "escalar": 2, ...}
        """
        ...

    @classmethod
    def evaluar_instancia(cls, instance: models.Model) -> list[dict]:
        """Evalúa SLAs para una instancia específica.

        Returns:
            Lista de acciones ejecutadas (para logging/auditoría)
        """
        ...

    @classmethod
    def _accion_notificar(cls, instance, config: dict) -> None:
        """Envía notificación al grupo configurado."""
        ...

    @classmethod
    def _accion_escalar(cls, instance, config: dict) -> None:
        """Ejecuta transición automática al estado destino."""
        ...

    @classmethod
    def _accion_rechazar(cls, instance, config: dict) -> None:
        """Ejecuta transición automática al estado de rechazo."""
        ...

    @classmethod
    def _accion_alertar(cls, instance, config: dict) -> None:
        """Activa bandera en la instancia."""
        ...
```

### 1.6 Management Command

```bash
# Verificar todos los SLAs
python manage.py sinpapel_verificar_slas

# Verbose output
python manage.py sinpapel_verificar_slas --verbosity=2

# Dry run (solo reporta, no ejecuta)
python manage.py sinpapel_verificar_slas --dry-run
```

### 1.7 Integration Points

- **Celery beat:** `sinpapel_verificar_slas` can be scheduled as a periodic task
- **Audit trail:** Each SLA action execution creates a `SeguimientoWorkflow` entry (for escalate/reject) or log entry (for notify/flag)
- **Transition predicates:** Escalate/reject actions go through `WorkflowEngine.cambiar_estado()`, so predicates and permissions are respected

### 1.8 Testing Strategy

| Test | What it verifies |
|------|-----------------|
| `test_sla_model_creation` | SLAConfiguracion can be created and linked to Estado |
| `test_sla_notificar` | Notify action sends notification to correct group |
| `test_sla_escalar` | Escalate action transitions instance to target state |
| `test_sla_rechazar` | Reject action transitions instance to rejection state |
| `test_sla_alertar` | Flag action sets boolean field on instance |
| `test_sla_dry_run` | Dry run reports but does not execute actions |
| `test_sla_inactive_ignored` | Inactive SLAs are skipped |
| `test_sla_no_double_execution` | Same SLA not executed twice for same instance |
| `test_sla_management_command` | Command runs without errors and reports counts |

---

## 2. Preview Transition

### 2.1 Goal

Add `WorkflowEngine.preview_transition()` that simulates a transition without executing it, returning a detailed impact report. This enables approvers to see the full consequences before committing.

### 2.2 Architecture

Single method on existing `WorkflowEngine` class. Refactors validation logic from `puede_cambiar_estado()` into reusable private methods.

### 2.3 API

```python
class WorkflowEngine:
    def preview_transition(
        self,
        instance: models.Model,
        target_state_name: str,
        user: User,
    ) -> dict[str, Any]:
        """Simula una transición y retorna un reporte de impacto.

        NO muta la instancia ni persiste nada.

        Returns:
            {
                "permitido": bool,
                "razones_bloqueo": list[dict],      # por qué no se puede
                "side_effects": list[str],           # handlers que se ejecutarían
                "documentos_faltantes": list[dict],  # requisitos no cumplidos
                "predicados_fallidos": list[dict],   # condiciones que no pasan
                "aprobadores_requeridos": list[dict], # placeholder para cadenas
                "historial_reciente": list[dict],    # últimos seguimientos
            }
        """
        ...
```

### 2.4 Report Structure

```python
{
    "permitido": False,
    "razones_bloqueo": [
        {
            "tipo": "predicado",
            "campo": "monto_solicitado",
            "mensaje": "El monto debe ser al menos $100,000",
        },
        {
            "tipo": "documento",
            "requisito": "INE",
            "mensaje": "Falta adjuntar INE",
        },
        {
            "tipo": "permiso",
            "mensaje": "No tiene permisos para realizar esta acción",
        },
    ],
    "side_effects": [
        "generar_oficio_aprobacion",
        "notificar_rechazo",
    ],
    "documentos_faltantes": [
        {"tipo": "INE", "porcentaje_requerido": 100},
        {"tipo": "Comprobante de domicilio", "porcentaje_requerido": 100},
    ],
    "predicados_fallidos": [
        {"condicion_id": 1, "tipo": "python_path", "mensaje": "Monto insuficiente"},
    ],
    "aprobadores_requeridos": [],  # placeholder para Approval Chains
    "historial_reciente": [
        {
            "fecha": "2026-05-14T10:30:00Z",
            "transicion": "CAPTURA → EN_REVISION",
            "usuario": "juan.perez",
            "comentarios": "Captura completa",
        },
    ],
}
```

### 2.5 Refactoring Strategy

Extract validation logic from `puede_cambiar_estado()` into private methods:

```python
def _validar_estado_destino(self, target_state_name: str) -> Estado | None:
    """Valida que el estado destino existe."""
    ...

def _validar_configuracion_transicion(
    self, instance, estado_actual, estado_destino, flujo
) -> ConfiguracionTransicion | None:
    """Busca la configuración de transición."""
    ...

def _validar_grupos_permitidos(
    self, config_transicion, user
) -> tuple[bool, str | None]:
    """Valida que el usuario tiene permisos."""
    ...

def _validar_documentos(
    self, instance, estado_actual
) -> list[dict]:
    """Verifica requisitos documentales. Retorna lista de faltantes."""
    ...

def _validar_predicados(
    self, config_transicion, instance, user
) -> list[dict]:
    """Evalúa condiciones de transición. Retorna lista de fallidas."""
    ...

def _obtener_side_effects(self, target_state_name: str) -> list[str]:
    """Retorna nombres de handlers registrados para el estado destino."""
    ...

def _obtener_historial_reciente(self, instance) -> list[dict]:
    """Retorna últimos N seguimientos de la instancia."""
    ...
```

Then `puede_cambiar_estado()` becomes:
```python
def puede_cambiar_estado(self, instance, target_state_name, user):
    preview = self.preview_transition(instance, target_state_name, user)
    if preview["razones_bloqueo"]:
        return False, preview["razones_bloqueo"][0]["mensaje"]
    return True, "OK"
```

### 2.6 Testing Strategy

| Test | What it verifies |
|------|-----------------|
| `test_preview_transition_permitido` | Returns permitido=True with no razones_bloqueo |
| `test_preview_transition_bloqueado_predicado` | Returns permitido=False with failing predicate details |
| `test_preview_transition_bloqueado_documento` | Returns permitido=False with missing documents |
| `test_preview_transition_bloqueado_permiso` | Returns permitido=False with permission error |
| `test_preview_transition_side_effects` | Lists registered side effect handlers |
| `test_preview_transition_historial` | Includes recent seguimientos |
| `test_preview_no_muta_instancia` | Instance state unchanged after preview |
| `test_puede_cambiar_estado_uses_preview` | Refactored puede_cambiar_estado delegates to preview |

---

## 3. Files to Create / Modify

### State Timers / SLA

| File | Action | Responsibility |
|------|--------|---------------|
| `sinpapel/models/sla.py` | **Create** | `SLAConfiguracion` model |
| `sinpapel/services/sla_engine.py` | **Create** | `SLAEngine` + action implementations |
| `sinpapel/management/commands/sinpapel_verificar_slas.py` | **Create** | Management command |
| `migrations/0006_sla_configuracion.py` | **Create** | Migration for new model |
| `tests/test_sla.py` | **Create** | Unit + integration tests |

### Preview Transition

| File | Action | Responsibility |
|------|--------|---------------|
| `sinpapel/services/workflow_engine.py` | **Modify** | Add `preview_transition()`, refactor `puede_cambiar_estado()` |
| `tests/test_workflow_engine.py` | **Modify** | Add preview tests |
| `tests/test_predicates.py` | **Modify** | Verify predicate details in preview |

---

## 4. Dependencies

- **State Timers**: No new external dependencies. Optional Celery integration (graceful degradation without Celery).
- **Preview Transition**: No new dependencies.

---

## 5. Self-Review Checklist

**Spec coverage:**
- [x] State Timers: model, engine, 4 actions, management command, dry run
- [x] Preview Transition: API, report structure, refactoring strategy, no mutation guarantee
- [x] Integration points: Celery (optional), audit trail, transition predicates

**Placeholder scan:**
- [x] No "TBD", "TODO", or "implement later"
- [x] No vague requirements
- [x] Every component has concrete code examples

**Type consistency:**
- [x] `SLAConfiguracion` fields match design
- [x] `SLAEngine` method signatures consistent
- [x] `preview_transition()` return type matches report structure

---

## 6. Next Steps

1. **User approval** of this design spec
2. **Write implementation plan** via `writing-plans` skill
3. **Implement** State Timers first (independent, simpler)
4. **Implement** Preview Transition second (depends on refactoring)
5. **Integration testing** of both features together
