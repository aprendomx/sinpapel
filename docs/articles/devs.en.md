# sinpapel: stop rewriting the same government workflow

If you've built software for government — or for any organization with formal procedures — you've already written this system: an application comes in, goes through review, someone approves or rejects it, everything must be recorded, some decisions require an electronic signature, legal deadlines expire, and the rules change every fiscal year.

And you wrote it by hand. The state machine as `if`s scattered across views, the audit trail as a `Log` model somebody forgets to populate, the signature as a brittle integration, the deadlines as a cron job nobody monitors. Six months later the compliance office changes the process, and the change requires a deploy.

**sinpapel** ("without paper") is a Django framework (GPL-3.0, Python ≥3.10, Django ≥5.0) that solves this problem once, around one central idea: **the workflow is data, not code**.

## The flow lives in the database

In sinpapel, the states, the allowed transitions, who may execute them, which rules block them and which deadlines govern them are database records — versioned. Your domain model just gets decorated:

```python
from django.db import models
from sinpapel.decorators import workflow_enabled
from sinpapel.mixins import Trazable

@workflow_enabled(
    state_field="estado",
    workflow_key="building_permit",
    expose_endpoints=True,
)
class Application(Trazable):
    estado = models.ForeignKey("sinpapel.Estado", on_delete=models.PROTECT)
    folio = models.CharField(max_length=20)
```

The decorator injects the workflow API into the model:

```python
application.available_transitions(user)      # where can this user take it?
application.can_transition_to("Approved", user)
application.preview_transition("Approved", user)  # simulate without executing
application.transition("Approved", user, comentarios="Meets current regulation")
```

Every `transition()` is atomic: it checks group permissions, evaluates predicates, enforces required documents, runs the signature if the target state demands one, fires side effects, and writes the audit record. All or nothing.

When the process changes, you publish a new `VersionFlujo` (flow version). Existing case files remain governed by the version they were created under — which is exactly what an auditor will ask about.

## The five pillars

1. **Versioned workflow** — `Estado`, `VersionFlujo`, `ConfiguracionTransicion`. The transition graph is configuration per flow version, with Django groups as per-edge access control.
2. **Immutable audit trail** — every transition writes a `SeguimientoWorkflow` record (who, when, from where, with which signature), and the `Trazable` mixin (built on `django-simple-history`) versions field-level changes on the model itself.
3. **Pluggable electronic signature** — a Port/Adapter design. Ships with `FielBackend` for Mexico's SAT FIEL (client-side and server-side modes), plus manual and fake backends for development and tests. Writing your own means implementing a small `Protocol`.
4. **Transition predicates** — business rules that block a transition: whitelisted Python functions, restricted JSON Logic, or declarative ORM checks. Configured per transition, as data.
5. **Watched SLAs** — maximum time per state; on breach, the engine detects it and fires the `sla_breached` signal with the full case context, onto which you hang your actions (notify, escalate, reject). A management command on cron as the entry point. Built-in action execution lands in 1.0 — today the pattern is subscribing to the signal.

On top of that: structured per-instance metadata capture without migrations (`MetadatosCapturables`), domain signals, and full flow export/import as portable JSON.

## An ecosystem that composes, not a monolith

The core knows nothing about HTTP. Each layer is an optional package:

| Package | What it adds |
|---|---|
| [`sinpapel`](https://pypi.org/project/sinpapel/) | The engine: workflow, audit, signing, predicates, SLA, metadata. |
| [`sinpapel-drf`](https://pypi.org/project/sinpapel-drf/) | Auto-generated REST API per model: transitions, history, preview, documents, requirements — plus admin CRUD and flow portability endpoints. |
| [`sinpapel-webhooks`](https://pypi.org/project/sinpapel-webhooks/) | Outbound webhooks with HMAC signing (outbox pattern, Stripe-style) and an inbound receiver framework. |
| [`sinpapel-reports`](https://pypi.org/project/sinpapel-reports/) | Template-based document generation: PDF overlay and DOCX filled with case data. |
| [`sinpapel-designer`](https://github.com/aprendomx/sinpapel-designer) | A standalone SPA (Vue 3 + Quasar) for designing flows visually; exports the JSON the backend imports. |
| [`@aprendomx/sinpapel-vue`](https://github.com/aprendomx/sinpapel-vue) | Ready-made Vue 3 widgets: history timeline, transition dialog with signature, document panel, SLA status. |

The full loop: draw the process in the designer, import the JSON with a management command, decorate your model, mount the DRF router, and drop the Vue widgets into your frontend. From diagram to working API in an afternoon.

## What to know before adopting it

Honesty first:

- **It's 0.x.** The public API is stable in practice but still beta; pin exact versions (`sinpapel==0.7.1`).
- **i18n:** the framework's messages and verbose names are in Spanish. If your product ships in another language, you'll override strings in forms/serializers.
- **GPL-3.0.** Real copyleft. A great fit for government and public software; evaluate carefully if your business model is closed SaaS.
- **The FIEL signature backend is Mexico-specific** (SAT). For other schemes, the `SignatureBackend` contract is small and documented.

## Try it

All four backend packages are on PyPI:

```bash
pip install sinpapel sinpapel-drf sinpapel-webhooks sinpapel-reports
```

Code, bilingual docs and issues live at [github.com/aprendomx/sinpapel](https://github.com/aprendomx/sinpapel). If you build case-processing systems in Django, don't hand-write the next state machine.
