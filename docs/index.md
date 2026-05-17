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
- **Pluggable Signing Backends** — strategy interface plus reference backends: `SimuladoBackend`, `RSAFileBackend`, and `FielBackend` (RSA-SHA256 + X.509).
- **Immutable Audit Trail** — `Trazable` mixin, `SeguimientoWorkflow` history, `RegistroFirma`, plus `django-simple-history` integration.
- **SLA Timers & Preview Transitions** — `SLAEngine` with notify / escalate / reject / flag actions; `WorkflowEngine.preview_transition()` returns an impact report without mutating state.
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
from django.db import models
from sinpapel import workflow_enabled
from sinpapel.mixins import CampoMetadato, MetadatosCapturables, Trazable

@workflow_enabled
class Solicitud(MetadatosCapturables, Trazable):
    folio = models.CharField(max_length=20, unique=True)
    estado = models.ForeignKey("sinpapel.Estado", on_delete=models.PROTECT)

    SCHEMA_METADATOS = [
        CampoMetadato("monto", tipo="decimal", requerido=True),
        CampoMetadato("rfc", tipo="str", requerido=True),
    ]
```

Drive a transition:

```python
from sinpapel.services.workflow_engine import WorkflowEngine

engine = WorkflowEngine()
engine.cambiar_estado(solicitud, "APROBADA", user=request.user, comentarios="Cumple")
```

## Next Steps

- Read the full [Usage Guide](usage/en.md) (English) or [Guía de Uso](usage/es.md) (Español).
- Browse the [API Reference](api/index.md).
- See [Contributing](development/contributing.md) to get involved.
