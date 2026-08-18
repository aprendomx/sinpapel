# sinpapel

> Versioned workflows, immutable audit, and pluggable e-signatures for Django.

---

## Why sinpapel?

Building paperless processes in Django usually means stitching together a state-machine library, an audit framework, a signing layer, and a forms toolkit. **sinpapel** ships them as one coherent package: declarative versioned workflows, immutable history, pluggable e-signature backends, schema-based metadata capture, transition predicates, SLA timers, and custom domain signals — designed to be adopted incrementally in any Django 5+ project.

## Features

- **Workflow Engine** — versioned state machines via `VersionFlujo` + `ConfiguracionTransicion`, with permission groups, mandatory-document gates, and a `WorkflowEngine` service.
- **Transition Predicates** — Python paths, restricted JSON Logic, and Django-ORM-backed predicates, ordered per transition.
- **Structured Metadata Capture** — `MetadatosCapturables` mixin with schema-declared `CampoMetadato` fields, validated at save.
- **Dynamic Forms & Serializers** — `MetaFormFactory` builds Django Forms from metadata schema; DRF Serializer mode also supported.
- **Pluggable Signing Backends** — strategy interface plus reference backends: `FakeBackend` (tests), `ManualBackend` (default), and `FielBackend` (FIEL/SAT, RSA-SHA256 + X.509).
- **Immutable Audit Trail** — `Trazable` mixin, `SeguimientoWorkflow` history, `RegistroFirma`, plus `django-simple-history` integration.
- **SLA Timers & Preview Transitions** — `SLAConfiguracion` models time limits per state and `SLAEngine` detects breaches (firing the `sla_breached` signal). ⚠️ In 0.7.x the built-in actions (notify / escalate / reject / flag) are **reporting stubs** — they describe the action but do not execute it yet; wire your own logic to the signals for now. Full action execution is planned for 1.0. `preview_transition()` returns an impact report without mutating state.
- **Custom Domain Signals** — `predicate_failed`, `sla_breached`, `sla_action_executed`, `transition_preview_requested` for observability and side-effect wiring.

## Quick Start

Install:

```bash
pip install sinpapel
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "simple_history",
    "sinpapel",
]
```

Declare a workflow-enabled model:

```python
from decimal import Decimal

from django.db import models
from sinpapel import workflow_enabled
from sinpapel.mixins import CampoMetadato, MetadatosCapturables, Trazable

@workflow_enabled(state_field="estado", workflow_key="solicitud")
class Solicitud(MetadatosCapturables, Trazable):
    folio = models.CharField(max_length=20, unique=True)
    estado = models.ForeignKey("sinpapel.Estado", on_delete=models.PROTECT)

    SCHEMA_METADATOS = [
        CampoMetadato("monto", Decimal, requerido=True),
        CampoMetadato("rfc", str, requerido=True),
    ]
```

Drive a transition through the methods injected on the instance:

```python
solicitud.transition("APROBADA", user=request.user, comentarios="Cumple")
```

## Next Steps

- Read the full [Usage Guide](usage/en.md) (English) or [Guía de Uso](usage/es.md) (Español).
- Browse the [API Reference](api/index.md).
- See [Contributing](development/contributing.md) to get involved.
