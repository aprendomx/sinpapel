# sinpapel

> **v0.7.1** — Versioned state machines, immutable audit trail, and pluggable electronic signatures for Django.

[![PyPI](https://img.shields.io/pypi/v/sinpapel.svg)](https://pypi.org/project/sinpapel/)
[![Python](https://img.shields.io/pypi/pyversions/sinpapel.svg)](https://pypi.org/project/sinpapel/)
[![Django](https://img.shields.io/badge/django-5.0%20%7C%205.1-blue)](https://www.djangoproject.com/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/aprendomx/sinpapel/blob/main/LICENSE)
[![Tests](https://img.shields.io/badge/tests-280%20passing-brightgreen)](#)

🇪🇸 [Leer en Español](https://github.com/aprendomx/sinpapel/blob/main/README.es.md)

---

## Why sinpapel?

Building paperless processes in Django usually means stitching together a state-machine library, an audit framework, a signing layer, and a forms toolkit. **sinpapel** ships them as one coherent package: declarative versioned workflows, immutable history, pluggable e-signature backends, schema-based metadata capture, transition predicates, SLA timers, and custom domain signals — designed to be adopted incrementally in any Django 5+ project.

## Features

- **Workflow Engine** — versioned state machines via `VersionFlujo` + `ConfiguracionTransicion`, with permission groups, document-requirement gates, and a `WorkflowEngine` service. Convenience methods (`available_transitions`, `can_transition_to`, `transition`, `preview_transition`) are injected onto every `@workflow_enabled` model.
- **Document Requirements** — both a coarse per-state flag (`Estado.expediente_obligatorio`) and fine-grained per-type rules (`RequisitoEstadoDocumento`: document type + minimum completion percentage) are enforced on every transition; system-generated documents (`auto_carga=True`) do not block.
- **Transition Predicates** — Python paths, restricted JSON Logic, and Django-ORM-backed predicates, ordered per transition.
- **Structured Metadata Capture** — `MetadatosCapturables` mixin with schema-declared `CampoMetadato` fields, validated at save.
- **Dynamic Forms & Serializers** — `MetaFormFactory` builds Django Forms from metadata schema; DRF Serializer mode also supported.
- **Pluggable Signing Backends** — `SignatureBackend` strategy interface plus reference backends: `FakeBackend` (tests), `ManualBackend` (default), and `FielBackend` (FIEL/SAT, RSA-SHA256 + X.509).
- **Immutable Audit Trail** — `Trazable` mixin, `SeguimientoWorkflow` history, `RegistroFirma`, plus `django-simple-history` integration.
- **SLA Timers & Preview Transitions** — `SLAConfiguracion` models per-state time limits and `SLAEngine` detects breaches, firing the `sla_breached` signal. ⚠️ **0.7.x status:** the built-in actions (notify / escalate / reject / flag) are reporting stubs — they describe the configured action but do not execute it; subscribe to `sla_breached` / `sla_action_executed` to implement real behavior for now (full execution planned for 1.0). `preview_transition()` returns an impact report (blocking reasons, missing documents, failed predicates) without mutating state — available both as `WorkflowEngine.preview_transition()` and as a method on the instance.
- **Custom Domain Signals** — `predicate_failed`, `sla_breached`, `sla_action_executed`, `transition_preview_requested` for observability and side-effect wiring.

## Installation

```bash
pip install sinpapel
```

Requires Python 3.10+ and Django 5.0+.

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "simple_history",
    "sinpapel",
    "my_app",  # your app that defines workflow-enabled models
]
```

Run migrations:

```bash
python manage.py migrate sinpapel
```

## Quick Start

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

    def resolve_workflow_version(self):
        from sinpapel.models import VersionFlujo
        return VersionFlujo.objects.get(nombre="solicitudes", activo=True)
```

Drive a state transition through the methods injected on the instance:

```python
# Preview before committing (no mutation, returns an impact report)
preview = solicitud.preview_transition("APROBADA", user=request.user)
if not preview["permitido"]:
    # razones_bloqueo aggregates permission, predicate and document failures;
    # documentos_faltantes lists missing per-type requirements, e.g.
    # {"tipo": "requisito_documento", "tipo_documento": "INE",
    #  "porcentaje_requerido": 100, "porcentaje_actual": 0, "mensaje": "..."}
    raise ValueError(preview["razones_bloqueo"][0]["mensaje"])

# Execute the transition (validates, creates audit row, fires signals).
# Raises PermissionError if validation (groups, predicates, documents) fails.
solicitud.transition("APROBADA", user=request.user, comentarios="Cumple requisitos")
```

The same logic is also reachable through the `WorkflowEngine` service directly
(`WorkflowEngine().preview_transition(solicitud, "APROBADA", user)` /
`.cambiar_estado(...)`) when you need it outside a model instance.

Subscribe to a custom signal:

```python
from django.dispatch import receiver
from sinpapel.signals import sla_breached

@receiver(sla_breached)
def on_sla_breach(sender, instance, sla, **kwargs):
    notify_team(instance, sla)
```

Full end-to-end examples, schema seeding, predicate cookbook, signing backend setup, and admin integration live in [`docs/usage/en.md`](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md).

## What's Inside

| Subsystem | Module | Docs |
|---|---|---|
| Workflow Engine | `sinpapel.services.workflow_engine` | [USAGE §State Transitions](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md#8-state-transitions) |
| Predicates | `sinpapel.services.predicate_engine` | [USAGE §Transition Predicates](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md#9-transition-predicates) |
| Metadata | `sinpapel.mixins` | [USAGE §Metadata](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md#10-structured-metadata-capture) |
| Forms Factory | `sinpapel.forms` | [USAGE §Forms](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md#11-formserializer-factory) |
| Signing | `sinpapel.signing` | [USAGE §Signing](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md#12-signing-backends) |
| Audit Trail | `sinpapel.models` + `sinpapel.mixins.Trazable` | [USAGE §Audit](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md#13-audit-trail) |
| SLA Engine | `sinpapel.services.sla_engine` | [USAGE §SLA](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md) |
| Custom Signals | `sinpapel.signals` | [USAGE §Signals](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md) |
| Schema Export/Import | `sinpapel.schemas` + management commands | [USAGE §Schema](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md) |

## Configuration

Optional Django settings:

```python
# settings.py
# Dotted path to the signature backend (default: ManualBackend).
SINPAPEL_SIGNATURE_BACKEND = "sinpapel.signing.backends.fiel.FielBackend"
SINPAPEL_ALLOW_SERVER_SIGNING = False  # gate FIEL server-side signing (legal review)
SINPAPEL_EMIT_PREVIEW_EVENTS = False   # set True to fire transition_preview_requested signal
```

See [USAGE §Settings](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md#4-settings) for the full reference.

## Compatibility

| Python | Django |
|---|---|
| 3.10, 3.11, 3.12, 3.13 | 5.0, 5.1 |

CI runs the test suite across the full matrix.

## Documentation

- [Usage Guide](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/en.md) — full reference (EN)
- [Guía de Uso](https://github.com/aprendomx/sinpapel/blob/main/docs/usage/es.md) — full reference (ES)
- [Changelog](https://github.com/aprendomx/sinpapel/blob/main/docs/development/changelog.md)
- [Contributing](https://github.com/aprendomx/sinpapel/blob/main/docs/development/contributing.md)
- [Code of Conduct](https://github.com/aprendomx/sinpapel/blob/main/CODE_OF_CONDUCT.md)

## Versioning & Stability

sinpapel follows [Semantic Versioning](https://semver.org/). The current release is **v0.7.1 (Beta)**. Public APIs (`WorkflowEngine`, `PredicateEngine`, `SLAEngine`, signals, model fields, schema JSON v0.2) are stable in the 0.x series; breaking changes will bump the minor version and be flagged in `docs/development/changelog.md` until 1.0.0. **Upgrading to 0.7.0:** `transition()` / `cambiar_estado()` no longer accept the `monto_aprobado` parameter (removed in 0.7.0) — carry domain data via metadata (`MetadatosCapturables`) or `condiciones` / `comentarios` instead. Since 0.6.0, transitions also enforce any `RequisitoEstadoDocumento` rules that were previously configured but never evaluated — review existing flows before upgrading.

## Contributing

Pull requests are welcome. Please read [docs/development/contributing.md](https://github.com/aprendomx/sinpapel/blob/main/docs/development/contributing.md) for development setup, commit conventions, and the Developer Certificate of Origin (DCO) sign-off requirement.

## License

Copyright (C) 2024-2026 Julio Adrián.

sinpapel is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

sinpapel is distributed in the hope that it will be useful, but **WITHOUT ANY WARRANTY**; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [GNU General Public License](https://github.com/aprendomx/sinpapel/blob/main/LICENSE) for more details.
