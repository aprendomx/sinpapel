# sinpapel

> **v0.2.0-alpha** — Workflow engine + audit trail + digital signature + structured metadata capture for Django.
>
> Extracted from [creditos](https://github.com/jadrians/creditos) (E12). Designed for SEP, FONDESO, and any Django project that needs **versioned state transitions + immutable audit + pluggable electronic signatures + schema-based metadata** without reinventing the wheel.
>
> [🇪🇸 Leer en Español](README.es.md)

---

## Table of Contents

1. [What is sinpapel?](#1-what-is-sinpapel)
2. [Features](#2-features)
3. [Installation](#3-installation)
4. [Settings](#4-settings)
5. [Migrations](#5-migrations)
6. [Quick Start](#6-quick-start)
7. [Workflow Configuration](#7-workflow-configuration)
8. [State Transitions](#8-state-transitions)
9. [Structured Metadata Capture](#9-structured-metadata-capture)
10. [Signing Backends](#10-signing-backends)
11. [Audit Trail](#11-audit-trail)
12. [Side Effects](#12-side-effects)
13. [Testing](#13-testing)
14. [API Reference](#14-api-reference)
15. [Contributing](#15-contributing)
16. [License & Versioning](#16-license--versioning)

---

## 1. What is sinpapel?

`sinpapel` is a Django package that provides four reusable capabilities for transaction-processing systems:

- **Workflow Engine**: Versioned state machine with transitions configured via Django admin or data migrations — no hardcoded state logic. The `@workflow_enabled` decorator marks your domain model (Loan Application, Permit, Ticket, etc.) as workflow-capable. The engine queries `ConfiguracionTransicion` from the database at runtime.
- **Audit Trail**: Immutable history of every change on key models via [django-simple-history](https://django-simple-history.readthedocs.io/), with `history_user` populated by middleware during real requests.
- **Digital Signatures**: Port + Adapter pattern with three shipped backends:
  - `FielBackend` — Mexico SAT FIEL/RSA-SHA256 + X.509
  - `ManualBackend` — Universal scanned-image + witness + timestamp (no cryptography)
  - `FakeBackend` — Deterministic for tests/CI
- **Structured Metadata Capture**: `MetadatosCapturables` mixin with schema-declared fields, type-safe proxy access (`instance.meta.field`), automatic validation, and JSON serialization.

Transitions, document requirements, audit, signatures, and metadata are **data, not code**. Your application can mutate business flows without redeployment.

---

## 2. Features

| Feature | Description |
|---------|-------------|
| `@workflow_enabled` decorator | Injects `available_transitions()`, `can_transition_to()`, `transition()` into your model |
| `VersionFlujo` | Versioned workflow definitions; active/inactive flags for A/B rollout |
| `ConfiguracionTransicion` | Directed edges between states with group-based permissions |
| `SeguimientoWorkflow` | Immutable audit log of every transition with timestamp, IP, comments |
| `MetadatosCapturables` | Schema-based metadata capture with type validation and proxy access |
| `Trazable` / `Catalogo` | Reusable mixins for created/updated tracking and catalog models |
| `RegistroFirma` | Cryptographic signature records with backend-agnostic verification |
| `ExpedienteAdjunto` | Generic file attachments with content-type linking |
| `django-simple-history` integration | Automatic historical tables for 5+ models |
| Side effects | Decorator-based handlers executed atomically within transitions |
| i18n ready | All model metadata wrapped in `gettext_lazy` |
| Type hints | `py.typed` marker included for PEP 561 compliance |

---

## 3. Installation

`sinpapel` is not yet on PyPI. Install directly from Git while the API stabilizes:

```bash
pip install "git+ssh://git@github.com/aprendomx/sinpapel.git@develop"

# Or with a fixed tag:
pip install "git+ssh://git@github.com/aprendomx/sinpapel.git@v0.2.0"
```

**Requirements:**
- Python `>=3.10`
- Django `>=5.0`

Post-install verification:

```python
>>> import sinpapel
>>> sinpapel.__version__
'0.2.0'
>>> from sinpapel import workflow_enabled, WorkflowRegistry
>>> from sinpapel.signing.backends.fiel import FielBackend
```

---

## 4. Settings

Add `sinpapel` (and dependencies) to `INSTALLED_APPS` **before your domain app**:

```python
# settings.py
INSTALLED_APPS = [
    # ... django.contrib.* ...
    "simple_history",   # required by HistoricalRecords
    "sinpapel",         # before your domain app for string FK resolution
    "your_app",         # e.g. "creditos", "sep", "fondeso"
]
```

Enable the audit user middleware (after `AuthenticationMiddleware`):

```python
MIDDLEWARE = [
    # ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",  # populates history_user
    # ...
]
```

Configure the signing backend (overridable via environment variable):

```python
import os

SINPAPEL_SIGNATURE_BACKEND = os.environ.get(
    "SINPAPEL_SIGNATURE_BACKEND",
    "sinpapel.signing.backends.fiel.FielBackend",
)
```

> **CI tip:** Use `SINPAPEL_SIGNATURE_BACKEND=sinpapel.signing.backends.fake.FakeBackend` in test pipelines to avoid generating real keypairs.

---

## 5. Migrations

Run sinpapel migrations to create all workflow, document, signature, and audit tables:

```bash
python manage.py migrate sinpapel
```

Shipped migrations:

- `0001_initial` — Creates all models: `Etapa`, `Estado`, `VersionFlujo`, `ConfiguracionTransicion`, `SeguimientoWorkflow`, `RequisitoEstadoDocumento`, `TipoDocumento`, `Documento`, `InstanciaDocumento`, `RazonRechazoDocumento`, `ExpedienteAdjunto`, `RegistroFirma`, plus `historical_*` tables.

> **Breaking change in v0.2.0:** Migration history was squashed into a single `0001_initial`. Existing deployments must `migrate --fake` or recreate the database.

---

## 6. Quick Start

Apply `@workflow_enabled` to the model that moves between states:

```python
# your_app/models.py
from django.db import models
from sinpapel import workflow_enabled
from sinpapel.mixins import MetadatosCapturables, Trazable


@workflow_enabled(state_field="estado", workflow_key="solicitud")
class Solicitud(MetadatosCapturables, Trazable):
    SCHEMA_METADATOS = [
        CampoMetadato("rfc", str, requerido=True, etiqueta="RFC"),
        CampoMetadato("monto_solicitado", Decimal, default=Decimal("0")),
        CampoMetadato("tipo_credito", str, choices=["FOVISSSTE", "INFONAVIT"], requerido=True),
    ]

    folio = models.CharField(max_length=50, unique=True)
    estado = models.ForeignKey("sinpapel.Estado", on_delete=models.CASCADE, null=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    solicitante = models.ForeignKey("auth.User", on_delete=models.CASCADE)

    def resolve_workflow_version(self):
        """Polymorphic hook to resolve the active VersionFlujo for this instance.

        The engine calls this method when validating a transition.
        Return a VersionFlujo (or None for global fallback).
        """
        from sinpapel.models import VersionFlujo
        return VersionFlujo.objects.filter(activo=True, nombre=self.tipo_tramite).first()
```

The decorator injects three methods:

- `solicitud.available_transitions(user)` → list of permitted `Estado` objects for this user in the current state.
- `solicitud.can_transition_to(target_state_name, user)` → `(bool, str | None)` tuple.
- `solicitud.transition(target_state_name, user, **kwargs)` → executes transition + audit + side effects.

`state_field` must be a ForeignKey to `sinpapel.Estado`. `workflow_key` identifies the flow in the registry.

---

## 7. Workflow Configuration

Create `Etapa`, `Estado`, `VersionFlujo`, and `ConfiguracionTransicion` via admin or data migration:

```python
# your_app/migrations/0002_seed_workflow.py
from django.db import migrations


def seed(apps, schema_editor):
    Etapa = apps.get_model("sinpapel", "Etapa")
    Estado = apps.get_model("sinpapel", "Estado")
    VersionFlujo = apps.get_model("sinpapel", "VersionFlujo")
    ConfiguracionTransicion = apps.get_model("sinpapel", "ConfiguracionTransicion")

    etapa_inicial = Etapa.objects.create(nombre="Inicial", activo=True)
    captura, _ = Estado.objects.get_or_create(nombre="CAPTURA", activo=True, etapa=etapa_inicial)
    revision, _ = Estado.objects.get_or_create(nombre="EN_REVISION", activo=True, etapa=etapa_inicial)
    aprobada, _ = Estado.objects.get_or_create(nombre="APROBADA", activo=True, etapa=etapa_inicial)

    flujo = VersionFlujo.objects.create(nombre="Flujo Estándar v1", activo=True)

    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=captura, estado_destino=revision,
    )
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=revision, estado_destino=aprobada,
    )


class Migration(migrations.Migration):
    dependencies = [("sinpapel", "0001_initial"), ("your_app", "0001_initial")]
    operations = [migrations.RunPython(seed, reverse_code=migrations.RunPython.noop)]
```

To restrict transitions by Django group, add members to `ConfiguracionTransicion.grupos_permitidos`.

---

## 8. State Transitions

With the workflow configured, executing a transition is straightforward:

```python
# your_app/views.py or service layer
from sinpapel.exceptions import SinpapelError


def advance_solicitud(request, solicitud_id):
    solicitud = Solicitud.objects.get(pk=solicitud_id)
    try:
        seguimiento = solicitud.transition(
            target_state_name="EN_REVISION",
            user=request.user,
            comentarios="Capture complete, ready for review",
        )
    except SinpapelError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({
        "seguimiento_id": seguimiento.pk,
        "nuevo_estado": seguimiento.estado_nuevo.nombre,
    })
```

`transition()` validates (source state, user permissions, document gates) and persists a `SeguimientoWorkflow` with timestamp, IP, comments + dispatch of registered side effects.

Common errors:

- `WorkflowConfigurationError` — Model not decorated with `@workflow_enabled` or missing `resolve_workflow_version()`.
- `PermissionError` — User does not belong to a permitted group for this transition.
- `ValueError` — `target_state_name` does not exist or is not a valid destination from the current state.

---

## 9. Structured Metadata Capture

Models inheriting from `MetadatosCapturables` declare a schema of capturable metadata fields:

```python
from decimal import Decimal
from sinpapel.mixins import CampoMetadato, MetadatosCapturables


class MiModelo(MetadatosCapturables):
    SCHEMA_METADATOS = [
        CampoMetadato("rfc", str, requerido=True, etiqueta="RFC"),
        CampoMetadato("monto", Decimal, default=Decimal("0")),
        CampoMetadato("tipo", str, choices=["A", "B"], requerido=True),
    ]
```

Runtime usage:

```python
obj = MiModelo.objects.create(...)
obj.meta.rfc = "ABCD010101ABC"
obj.meta.monto = Decimal("500000")
obj.meta.tipo = "A"
obj.save()  # validates schema automatically

# Serialization
obj.meta.to_dict()
# → {"rfc": "ABCD010101ABC", "monto": Decimal("500000"), "tipo": "A"}

obj.meta.to_dict(incluir_defaults=False)
# → only fields explicitly set
```

Validation:

- Unknown fields raise `AttributeError`
- Wrong types raise `TypeError`
- Invalid choices raise `ValueError`
- Missing required fields raise `ValidationError` on `save()`

Supported types: `str`, `int`, `bool`, `Decimal`, `date`.

---

## 10. Signing Backends

`sinpapel.signing` defines a `SignatureBackend` Protocol with three operations: `request_signature`, `verify`, `revoke`. Three implementations are shipped:

| Backend | Identifier | When to use |
|---------|-----------|-------------|
| `FielBackend` | `fiel` | Production Mexico: RSA-SHA256 signature with X.509 certificate issued by SAT (Servicio de Administración Tributaria). Verifies signature + extracts RFC from subject. |
| `ManualBackend` | `manual` | Universal: manual registration with scanned image + witness name + timestamp. No cryptography. Ideal for flows where signature is in-person / paper scanned. |
| `FakeBackend` | `fake` | Tests / CI: deterministic (fixed SHA-256 hash). Never use in production. |

Backend selection at runtime via `SINPAPEL_SIGNATURE_BACKEND` setting (see §4) or direct instantiation:

```python
from sinpapel.signing.factory import get_signature_backend
from sinpapel.signing.backends.fiel import FielBackend

# Via settings (recommended)
backend = get_signature_backend()

# Or direct instantiation
backend = FielBackend()

# Sign (FIEL): content to sign + RSA signature + SAT certificate
registro = backend.request_signature(
    content=b"canonical content to sign",
    signer=request.user,                        # optional, recommended
    firma_b64=request_data["firma_b64"],        # client-generated signature
    certificado_cer_b64=request_data["cer_b64"],
    is_required=True,
)
# → RegistroFirma persisted with verification_result="VALIDA" + FIEL backend_metadata

# Verify
result = backend.verify(registro)
assert result.valid is True

# Revoke
backend.revoke(registro, reason="compromised certificate")
# → verification_result="INVALIDA" + history audit entry
```

For `ManualBackend`:

```python
backend = ManualBackend()
registro = backend.request_signature(
    content=b"document signed in person",
    signer=request.user,
    scanned_image_path="/media/signatures/doc_42.jpg",
    witness_name="Mtra. Pérez",
)
```

---

## 11. Audit Trail

All changes on 5 key models (`RegistroFirma`, `InstanciaDocumento`, `ConfiguracionTransicion`, `VersionFlujo`, `RequisitoEstadoDocumento`) automatically generate entries in `historical_*` tables.

Query history via standard queryset API:

```python
from sinpapel.models import RegistroFirma

rf = RegistroFirma.objects.get(pk=42)

# Full history
for entry in rf.history.all():
    print(f"{entry.history_date} {entry.history_type} {entry.history_user} → {entry.verification_result}")
# Output:
# 2026-04-27 10:30 ~ admin → INVALIDA   (revoke)
# 2026-04-27 10:25 + carlos → VALIDA    (creation)

# Diff between versions
latest = rf.history.first()
previous = latest.prev_record
delta = latest.diff_against(previous)
for change in delta.changes:
    print(f"{change.field}: {change.old} → {change.new}")
```

`history_user` is automatically populated from the request via `HistoryRequestMiddleware` (§4). In contexts without a request (management commands, Celery tasks), `history_user` will be `None` unless you use `bulk_create_with_history` or `update_change_reason` explicitly.

> **Trazable vs simple-history:** Both coexist without redundancy. `Trazable` maintains last-write metadata (`autor`, `modificador`) optimized for fast queries. `simple-history` captures every change as a separate immutable row. Different consumers.

---

## 12. Side Effects

Associate handlers to specific transitions via decorator. Handlers execute **inside** the atomic transaction of `transition()`, after persisting the `SeguimientoWorkflow`:

```python
# your_app/services/side_effects.py
from sinpapel.services.side_effects import register_side_effect


@register_side_effect("APROBADA")
def generar_oficio_aprobacion(solicitud, usuario, **kwargs):
    """Side effect executed after transition to APROBADA state."""
    from your_app.services.oficios import OficioService
    return {"oficio_id": OficioService.generar(solicitud=solicitud, autor=usuario)}


@register_side_effect("RECHAZADA")
def notificar_rechazo(solicitud, usuario, **kwargs):
    from your_app.services.notificaciones import enviar_email
    enviar_email(
        to=solicitud.solicitante.email,
        subject="Your application was rejected",
        body=kwargs.get("comentarios", ""),
    )
```

Handlers receive `(instance, user, **kwargs)` where `kwargs` includes arguments passed to `transition()`. If a handler raises an exception, the entire transition rolls back (atomicity).

To register them at app boot, import the module in `your_app/apps.py:ready()`:

```python
# your_app/apps.py
from django.apps import AppConfig


class YourAppConfig(AppConfig):
    name = "your_app"

    def ready(self):
        from your_app.services import side_effects  # noqa — registers handlers
```

---

## 13. Testing

### Running sinpapel's own test suite

```bash
pytest tests/ --ds=tests.settings
```

### Testing with FakeBackend

For tests that need signatures to "work" without real cryptography:

```python
# settings_test.py
SINPAPEL_SIGNATURE_BACKEND = "sinpapel.signing.backends.fake.FakeBackend"
```

`FakeBackend` produces a `RegistroFirma` with a deterministic hash, without generating a real keypair — much faster in large suites.

### Testing with real RSA + self-signed certificate

For tests that need real signatures (without a SAT sandbox):

```python
# your_app/tests/conftest.py
import datetime as _dt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


@pytest.fixture
def keypair_and_cert():
    """RSA private key + self-signed cert DER, in-memory (no sandbox)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "TEST SIGNER"),
        x509.NameAttribute(NameOID.SERIAL_NUMBER, "TESTRFC000"),
    ])
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=1))
        .not_valid_after(now + _dt.timedelta(days=365))
        .sign(private_key, hashes.SHA256()))
    return private_key, cert.public_bytes(serialization.Encoding.DER)
```

### Testing history_user population

```python
import pytest
from django.test import RequestFactory
from simple_history.middleware import HistoryRequestMiddleware


@pytest.mark.django_db
def test_history_user_populated(user):
    factory = RequestFactory()
    request = factory.post("/")
    request.user = user

    def _do_mutation(req):
        # Your mutation within the request lifecycle
        ...

    HistoryRequestMiddleware(_do_mutation)(request)
    # Your assertions on obj.history.first().history_user
```

---

## 14. API Reference

### `@workflow_enabled(state_field, workflow_key, expose_endpoints=False)`

Class decorator that registers the model in `WorkflowRegistry` and injects workflow methods.

**Parameters:**
- `state_field` (str): Name of the ForeignKey to `sinpapel.Estado`.
- `workflow_key` (str): Unique identifier for this workflow in the registry.
- `expose_endpoints` (bool): Whether to auto-register REST endpoints (future feature).

**Requires:** `resolve_workflow_version()` method on the decorated class.

### `WorkflowEngine`

Core service for transition validation and execution.

**Methods:**
- `puede_cambiar_estado(instance, target_state_name, user) → (bool, str | None)`
- `cambiar_estado(instance, target_state_name, user, comentarios="", firma_payload=None) → dict`
- `available_transitions(instance, user) → list[Estado]`

### `MetadatosCapturables`

Abstract Django model mixin. Add to your model alongside `Trazable`.

**Class attributes:**
- `SCHEMA_METADATOS: list[CampoMetadato]`

**Instance properties:**
- `meta: MetadatosProxy` — type-safe read/write proxy

**Methods:**
- `clean()` — validates required fields
- `save()` — calls `clean()` before persisting

### `CampoMetadato`

Frozen dataclass defining a metadata field schema.

**Fields:**
- `nombre: str`
- `tipo: type` — `str`, `int`, `bool`, `Decimal`, `date`
- `requerido: bool = False`
- `default: Any = None`
- `choices: list[str] | None = None`
- `etiqueta: str = ""`
- `ayuda: str = ""`

### `MetadatosProxy`

Runtime proxy attached to `instance.meta`.

**Methods:**
- `errores() → dict[str, str]` — validates all required fields
- `to_dict(incluir_defaults=True) → dict[str, Any]` — serializes all schema fields

---

## 15. Contributing

Contributions are welcome. Please open an issue before large changes.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with tests
4. Ensure the test suite passes: `pytest tests/ -q`
5. Commit with clear messages
6. Push and open a Pull Request

Development setup:

```bash
git clone git@github.com:aprendomx/sinpapel.git
cd sinpapel
pip install -e ".[dev]"
pytest tests/ -q
```

---

## 16. License & Versioning

**License:** MIT (see `LICENSE`). Commercial and institutional use permitted. No warranty.

**Versioning:** [SemVer 2.0](https://semver.org). Pre-1.0 (`0.y.z`):

- **`y` (minor)** changes may include breaking changes in public API.
- **`z` (patch)** changes are bug fixes / internal changes without breaking API.

When the API stabilizes (v1.0.0), the contract will be:

- `MAJOR`: breaking changes.
- `MINOR`: new backwards-compatible features.
- `PATCH`: bug fixes.

**Visible Roadmap:**

- v0.2 — i18n via `gettext_lazy`, `py.typed`, `sinpapel_*` tables, `Etapa` model, standalone tests, `MetadatosCapturables` mixin. **(DONE)**
- v0.3 — PAdES support (universal PDF signing via endesive) as an additional adapter.
- v1.0 — Stable API + PyPI public release (final naming and licensing decision).

**Report issues / propose changes:** [github.com/aprendomx/sinpapel/issues](https://github.com/aprendomx/sinpapel/issues)
