# sinpapel

> **v0.4.0-alpha** — Workflow engine + audit trail + digital signature + structured metadata capture + transition predicates + dynamic forms + state timers / SLA + preview transitions for Django.
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
9. [Transition Predicates](#9-transition-predicates)
10. [Structured Metadata Capture](#10-structured-metadata-capture)
11. [Form/Serializer Factory](#11-formserializer-factory)
12. [Signing Backends](#12-signing-backends)
13. [Audit Trail](#13-audit-trail)
14. [State Timers / SLA](#14-state-timers--sla)
15. [Preview Transition](#15-preview-transition)
16. [Side Effects](#16-side-effects)
17. [Testing](#17-testing)
18. [API Reference](#18-api-reference)
19. [Contributing](#19-contributing)
20. [License & Versioning](#20-license--versioning)

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

> **Visual Designer:** [sinpapel-designer](https://github.com/aprendomx/sinpapel-designer) is a standalone Vue 3 + Quasar companion app for drawing workflows visually. It round-trips JSON with sinpapel via `sinpapel_export_flujo` / `sinpapel_import_flujo` management commands.

---

## 2. Features

| Feature | Description |
|---------|-------------|
| `@workflow_enabled` decorator | Injects `available_transitions()`, `can_transition_to()`, `transition()` into your model |
| `VersionFlujo` | Versioned workflow definitions; active/inactive flags for A/B rollout |
| `ConfiguracionTransicion` | Directed edges between states with group-based permissions |
| `SeguimientoWorkflow` | Immutable audit log of every transition with timestamp, IP, comments |
| `MetadatosCapturables` | Schema-based metadata capture with type validation and proxy access |
| `MetaFormFactory` | Dynamic Django Form / DRF Serializer generation from `SCHEMA_METADATOS` |
| `CondicionTransicion` | Configurable transition predicates with pluggable backends (Python, JSON Logic, ORM) |
| `PredicateEngine` | Extensible engine for evaluating business rules before state transitions |
| `SLAConfiguracion` | Per-state time limits with configurable actions (notify, escalate, reject, flag) |
| `SLAEngine` | Evaluates active SLAs and dispatches actions for overdue instances |
| `preview_transition()` | Simulates a transition without executing it, returning a detailed impact report |
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

> **Designer tip:** You can also configure workflows visually with [sinpapel-designer](https://github.com/aprendomx/sinpapel-designer) and import them via `python manage.py sinpapel_import_flujo flujo.json`.

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

## 9. Transition Predicates

Attach configurable business rules to any `ConfiguracionTransicion` via `CondicionTransicion`. The `WorkflowEngine` evaluates all active conditions (in `orden`) after group validation and before permitting the transition.

**Backends:**

| Backend | `tipo` | Use case |
|---------|--------|----------|
| **Python Path** | `python_path` | Complex logic, reusable validators, external API calls. Whitelisted modules only (`SINPAPEL_PREDICATE_MODULES`). |
| **JSON Logic** | `json_logic` | Simple declarative rules editable by non-devs via UI. Safe operators only: `var`, `==`, `!=`, `<`, `>`, `<=`, `>=`, `and`, `or`, `!`, `in`. |
| **Django ORM** | `django_orm` | Conditions on related model fields via ORM lookups. |

**Example — Python Path:**

```python
# your_app/validators.py
def monto_minimo_100k(instance, user):
    if instance.meta.monto_solicitado >= 100_000:
        return True
    return False, "El monto debe ser al menos $100,000"
```

```python
# Admin or migration
from sinpapel.models.predicates import CondicionTransicion

CondicionTransicion.objects.create(
    transicion=transicion_aprobacion,
    tipo="python_path",
    configuracion={"path": "your_app.validators.monto_minimo_100k"},
    mensaje_error="No cumple con las condiciones de monto",
    orden=1,
)
```

**Example — JSON Logic:**

```python
CondicionTransicion.objects.create(
    transicion=transicion_aprobacion,
    tipo="json_logic",
    configuracion={
        "rule": {
            "and": [
                {">=": [{"var": "meta.monto_solicitado"}, 100000]},
                {"==": [{"var": "meta.tipo_credito"}, "FOVISSSTE"]},
            ]
        }
    },
    mensaje_error="Solo FOVISSSTE con monto >= $100k puede avanzar",
    orden=2,
)
```

**Security:** The `python_path` backend only imports from modules listed in `SINPAPEL_PREDICATE_MODULES` (Django setting). An empty whitelist blocks all imports by default.

---

## 10. Structured Metadata Capture

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

## 11. Form/Serializer Factory

Generate Django Forms and DRF Serializers dynamically from `SCHEMA_METADATOS` — no need to write matching Form/Serializer classes manually.

### Django Forms

```python
from sinpapel.forms import MetaFormFactory

MetaForm = MetaFormFactory.build_form(
    Solicitud.SCHEMA_METADATOS,
    name="SolicitudMetaForm",
)

# In a view
form = MetaForm(request.POST or None, initial=solicitud.meta.to_dict())
if form.is_valid():
    for key, value in form.cleaned_data.items():
        setattr(solicitud.meta, key, value)
    solicitud.save()
```

### DRF Serializers

```python
from sinpapel.forms import MetaFormFactory

MetaSerializer = MetaFormFactory.build_serializer(
    Solicitud.SCHEMA_METADATOS,
    name="SolicitudMetaSerializer",
)

# In a viewset
serializer = MetaSerializer(data=request.data)
if serializer.is_valid():
    for key, value in serializer.validated_data.items():
        setattr(solicitud.meta, key, value)
    solicitud.save()
```

> **Note:** DRF is an optional dependency. `build_serializer()` raises `ImportError` with installation instructions if `djangorestframework` is not installed.

### Field Mapping

| `CampoMetadato.tipo` | Django Form Field | DRF Field |
|----------------------|-------------------|-----------|
| `str` (no choices) | `CharField` | `CharField` |
| `str` (with choices) | `ChoiceField` | `ChoiceField` |
| `int` | `IntegerField` | `IntegerField` |
| `bool` | `BooleanField` | `BooleanField` |
| `Decimal` | `DecimalField(max_digits=15, decimal_places=2)` | `DecimalField(max_digits=15, decimal_places=2)` |
| `date` | `DateField` | `DateField` |

**Mapped metadata:**
- `requerido` → `required`
- `default` → `initial` (Django) / `default` (DRF)
- `etiqueta` → `label`
- `ayuda` → `help_text`

---

## 12. Signing Backends

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

## 13. Audit Trail

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

## 14. State Timers / SLA

Configure time limits per state and automatic actions when instances exceed them. `SLAConfiguracion` links to `Estado` and defines `dias_maximos` plus an action to execute on expiration.

**Actions:**

| Action | `accion_vencimiento` | Behavior |
|--------|---------------------|----------|
| **Notify** | `notificar` | Returns notification target (group, template) for the caller to dispatch |
| **Escalate** | `escalar` | Returns target state for automatic escalation |
| **Reject** | `rechazar` | Returns rejection target state |
| **Flag** | `alertar` | Sets a boolean field on the instance (e.g., `alerta_sla=True`) |

**Example:**

```python
from sinpapel.models import Estado
from sinpapel.models.sla import SLAConfiguracion

revision = Estado.objects.get(nombre="EN_REVISION")
SLAConfiguracion.objects.create(
    estado=revision,
    dias_maximos=5,
    accion_vencimiento="notificar",
    configuracion_accion={"grupo_id": grupo_revisores.id, "template": "sla_vencido"},
)
```

Evaluate SLAs for a single instance:

```python
from sinpapel.services.sla_engine import SLAEngine

acciones = SLAEngine.evaluar_instancia(solicitud)
# → [{"accion": "notificar", "grupo": "Revisores", "template": "sla_vencido"}]
```

Run the management command to check all active SLAs:

```bash
python manage.py sinpapel_verificar_slas

# Dry run (report only, no actions)
python manage.py sinpapel_verificar_slas --dry-run
```

Inactive SLAs (`activo=False`) are skipped. The engine uses `instance.creado` as the time reference; if the instance lacks this field, the SLA is never considered expired.

---

## 15. Preview Transition

Simulate a transition without executing it. `preview_transition()` returns a detailed impact report that UI layers can use to show the user why a transition is blocked (or what will happen if they proceed).

```python
from sinpapel.services.workflow_engine import WorkflowEngine

reporte = WorkflowEngine().preview_transition(
    solicitud, "APROBADA", request.user
)
```

**Report structure:**

```python
{
    "permitido": False,
    "razones_bloqueo": [
        {"tipo": "permiso", "mensaje": "No tiene permisos para realizar esta acción"},
        {"tipo": "predicado", "mensaje": "Monto debe ser al menos $100,000"},
    ],
    "documentos_faltantes": [],
    "predicados_fallidos": [
        {"condicion_id": 3, "tipo": "json_logic", "mensaje": "Monto debe ser al menos $100,000"},
    ],
    "side_effects": ["APROBADA"],  # registered side effects for target state
    "aprobadores_requeridos": [],
    "historial_reciente": [
        {
            "fecha": "2026-05-15T10:30:00+00:00",
            "transicion": "CAPTURA → EN_REVISION",
            "usuario": "analista1",
            "comentarios": "Documentos completos",
        },
    ],
}
```

The preview **never mutates** the instance. `puede_cambiar_estado()` delegates to `preview_transition()` internally, so both methods share the same validation logic.

---

## 16. Side Effects

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

## 17. Testing

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

## 18. API Reference

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
- `preview_transition(instance, target_state_name, user) → dict` — simulates transition, returns impact report

### `CondicionTransicion`

Model storing a configurable predicate for a transition.

**Fields:**
- `transicion: ForeignKey[ConfiguracionTransicion]` — the transition this condition applies to
- `tipo: str` — backend type: `python_path`, `json_logic`, `django_orm`
- `configuracion: JSONField` — backend-specific parameters
- `mensaje_error: str` — error message shown when condition fails
- `orden: int` — evaluation order (lower first)
- `activo: bool` — whether this condition is evaluated

### `PredicateEngine`

Pluggable engine for evaluating transition conditions.

**Class Methods:**
- `registrar_backend(tipo: str, funcion: callable) → None` — register a custom backend
- `evaluar(condicion, instance, user) → (bool, str | None)` — evaluate a single condition

**Built-in backends:**
- `python_path` — imports and calls a Python function from a whitelisted module
- `json_logic` — evaluates a JSON Logic rule against instance metadata
- `django_orm` — evaluates a Django ORM lookup against the instance

**Settings:**
- `SINPAPEL_PREDICATE_MODULES: list[str]` — whitelist of modules for `python_path` backend

### `SLAConfiguracion`

Per-state SLA configuration model.

**Fields:**
- `estado: ForeignKey[Estado]` — the state this SLA applies to
- `dias_maximos: int` — maximum allowed days in this state before triggering action
- `accion_vencimiento: str` — action on expiration: `notificar`, `escalar`, `rechazar`, `alertar`
- `configuracion_accion: JSONField` — action-specific parameters (group ID, target field, etc.)
- `activo: bool` — whether this SLA is evaluated

**Constraints:**
- `unique_together = ("estado", "accion_vencimiento")`

### `SLAEngine`

Evaluates SLA rules and dispatches configured actions.

**Class Methods:**
- `evaluar_instancia(instance) → list[dict]` — evaluates all active SLAs for the instance, returns executed actions
- `verificar_todos() → dict[str, int]` — stub for batch evaluation across all workflow-enabled models

**Actions:**
- `_accion_notificar` — returns `{"accion": "notificar", "grupo": "...", "template": "..."}`
- `_accion_escalar` — returns `{"accion": "escalar", "estado_destino": "..."}`
- `_accion_rechazar` — returns `{"accion": "rechazar", "estado_destino": "..."}`
- `_accion_alertar` — sets instance field via `setattr`, returns `{"accion": "alertar", "campo": "...", "valor": ...}`

### `MetaFormFactory`

Factory for generating Django Forms and DRF Serializers from `SCHEMA_METADATOS`.

**Class Methods:**
- `build_form(schema, name=None, **kwargs) → type[forms.Form]` — generate a Django Form
- `build_serializer(schema, name=None, **kwargs) → type[serializers.Serializer]` — generate a DRF Serializer (raises `ImportError` if DRF not installed)

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

## 19. Contributing

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

## 20. License & Versioning

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
- v0.3 — Transition Predicates (`CondicionTransicion` + `PredicateEngine`), Form/Serializer Factory (`MetaFormFactory`), JSON Logic evaluator, pluggable predicate backends. **(DONE)**
- v0.4 — State Timers / SLA (`SLAConfiguracion` + `SLAEngine`), Preview Transition (`preview_transition()`), SLA export/import in schema v0.2+. **(DONE)**
- v0.5 — PAdES support (universal PDF signing via endesive) as an additional adapter.
- v1.0 — Stable API + PyPI public release (final naming and licensing decision).

**Report issues / propose changes:** [github.com/aprendomx/sinpapel/issues](https://github.com/aprendomx/sinpapel/issues)
