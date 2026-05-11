# sinpapel

> **alpha v0.1.0** — Workflow + audit trail + digital signature engine for Django.
>
> Reusable across projects de trámites: extraído de [creditos](https://github.com/jadrians/creditos) (E12), planificado para SEP, FONDESO y cualquier sistema Django que necesite **transiciones versionadas + auditoría inmutable + firma electrónica pluggable** sin reinventar el motor.

---

## Table of Contents

1. [What is sinpapel?](#1-what-is-sinpapel)
2. [Installation](#2-installation)
3. [Settings](#3-settings)
4. [Migrations](#4-migrations)
5. [Decorate your model](#5-decorate-your-model)
6. [Configure the workflow](#6-configure-the-workflow)
7. [First transition](#7-first-transition)
8. [Signing backends](#8-signing-backends)
9. [Audit trail](#9-audit-trail)
10. [Side effects](#10-side-effects)
11. [Testing](#11-testing)
12. [Known limitations](#12-known-limitations)
13. [License & versioning](#13-license--versioning)

---

## 1. What is sinpapel?

`sinpapel` proporciona tres capacidades genéricas para sistemas de trámites Django:

- **Workflow**: motor versionado de transiciones entre estados, configurable desde admin (no hardcoded). El decorator `@workflow_enabled` marca tu modelo de dominio (Solicitud, Trámite, etc.) como elegible. El motor consulta `ConfiguracionTransicion` desde DB.
- **Audit trail**: historial inmutable de cada cambio sobre modelos clave vía [django-simple-history](https://django-simple-history.readthedocs.io/), con `history_user` populado por middleware en requests reales.
- **Digital signature**: Port + Adapter pattern — `FielBackend` (México SAT con FIEL/RSA-SHA256+X.509), `ManualBackend` (universal con timestamp + scanned image), `FakeBackend` (determinista para tests). Selección via setting.

Las transiciones, requisitos documentales, audit y firmas son **datos, no código**. Esto significa que tu app puede mutar el flujo sin redeploy.

---

## 2. Installation

`sinpapel` aún no está en PyPI público. Instala directamente desde Git mientras la API se estabiliza:

```bash
pip install "git+ssh://git@github.com/jadrians/creditos.git#subdirectory=sinpapel&egg=sinpapel"

# O con tag fijo:
pip install "git+ssh://git@github.com/jadrians/creditos.git@v0.1.0#subdirectory=sinpapel&egg=sinpapel"
```

**Dependencia adicional (`trazable`):** `sinpapel` usa el mixin `trazable.models.Trazable` (creado/actualizado/autor/modificador). Tampoco está en PyPI público; instálalo aparte:

```bash
pip install "git+ssh://git@github.com/jadrians/trazable.git"
```

**Python:** requiere `>=3.13`. **Django:** `>=5.0`.

Verificación post-install:

```python
>>> import sinpapel
>>> sinpapel.__version__
'0.1.0'
>>> from sinpapel import workflow_enabled, WorkflowRegistry
>>> from sinpapel.signing.backends.fiel import FielBackend
```

---

## 3. Settings

Agrega `sinpapel` (y deps) a `INSTALLED_APPS` **antes de tu app de dominio**:

```python
# settings.py
INSTALLED_APPS = [
    # ... django.contrib.* ...
    "simple_history",   # base — required by HistoricalRecords
    "trazable",
    "sinpapel",         # antes de tu app de dominio para FK string-resolution
    "tu_app",           # ej. "creditos", "sep", "fondeso"
]
```

Activa el middleware de audit user (después de `AuthenticationMiddleware`):

```python
MIDDLEWARE = [
    # ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",  # popula history_user
    # ...
]
```

Configura el backend de firma (default puede sobrescribirse via env var):

```python
import os

# Puede ser "fiel", "manual", "fake" o ruta importable a tu propio backend
SINPAPEL_SIGNATURE_BACKEND = os.environ.get(
    "SINPAPEL_SIGNATURE_BACKEND",
    "sinpapel.signing.backends.fiel.FielBackend",
)
```

> **CI tip:** en pipelines de test usa `SINPAPEL_SIGNATURE_BACKEND=sinpapel.signing.backends.fake.FakeBackend` para evitar generar keypairs reales.

---

## 4. Migrations

`sinpapel` shipea 3 migraciones que crean los modelos del paquete (workflow, documentos, firma, audit history):

```bash
python manage.py migrate sinpapel
```

Migraciones aplicadas:

- `0001_initial` — `Estado`, `VersionFlujo`, `ConfiguracionTransicion`, `RegistroFirma`, `SeguimientoWorkflow`, `ExpedienteAdjunto`, `TipoDocumento`, `Documento`, `InstanciaDocumento`, `RazonRechazoDocumento`, `RequisitoEstadoDocumento`.
- `0002_extract_remaining_models` — refinamientos de FK + GenericForeignKey.
- `0003_historical_records` — tablas `historical*` para los 5 modelos auditables.

> **Heads up:** las tablas SQL preservan el prefijo `creditos_*` (decisión histórica de extracción). Esto es transparente para el ORM. Si tu proyecto es greenfield y prefieres `sinpapel_*`, abre un issue.

---

## 5. Decorate your model

Aplica `@workflow_enabled` al modelo que avanza entre estados:

```python
# tu_app/models.py
from django.db import models
from sinpapel import workflow_enabled


@workflow_enabled(state_field="estado", workflow_key="solicitud")
class Solicitud(models.Model):
    folio = models.CharField(max_length=50, unique=True)
    estado = models.ForeignKey("sinpapel.Estado", on_delete=models.CASCADE, null=True)

    # Tu modelo de dominio puede tener cualquier otro campo:
    monto = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    solicitante = models.ForeignKey("auth.User", on_delete=models.CASCADE)

    def resolve_workflow_version(self):
        """Hook polimórfico para resolver el VersionFlujo activo de esta instancia.

        El motor llama a este método cuando necesita validar una transición.
        Debes retornar un VersionFlujo (o None — fallback a configuración global).
        """
        # Ejemplo: cada Solicitud tiene un Producto asociado al VersionFlujo
        from sinpapel.models import VersionFlujo
        return VersionFlujo.objects.filter(activo=True, nombre=self.tipo_tramite).first()
```

El decorator inyecta tres métodos:

- `solicitud.available_transitions(user)` → list of `Estado` permitidos para este user en este estado.
- `solicitud.can_transition_to(estado_destino_nombre, user)` → `(bool, str | None)` tuple.
- `solicitud.transition(target_state_name, user, **kwargs)` → ejecuta + audit + side effects.

`state_field` debe ser un FK a `sinpapel.Estado`. `workflow_key` identifica el flujo en el registry.

---

## 6. Configure the workflow

Crea `Estado`, `VersionFlujo`, `ConfiguracionTransicion` desde admin o via data migration:

```python
# tu_app/migrations/0002_seed_workflow.py
from django.db import migrations


def seed(apps, schema_editor):
    Estado = apps.get_model("sinpapel", "Estado")
    VersionFlujo = apps.get_model("sinpapel", "VersionFlujo")
    ConfiguracionTransicion = apps.get_model("sinpapel", "ConfiguracionTransicion")

    captura, _ = Estado.objects.get_or_create(nombre="CAPTURA", activo=True)
    revision, _ = Estado.objects.get_or_create(nombre="EN_REVISION", activo=True)
    aprobada, _ = Estado.objects.get_or_create(nombre="APROBADA", activo=True)

    flujo = VersionFlujo.objects.create(nombre="Flujo Estándar v1", activo=True)

    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=captura, estado_destino=revision,
    )
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=revision, estado_destino=aprobada,
    )


class Migration(migrations.Migration):
    dependencies = [("sinpapel", "0003_historical_records"), ("tu_app", "0001_initial")]
    operations = [migrations.RunPython(seed, reverse_code=migrations.RunPython.noop)]
```

Si necesitas restringir transiciones por grupo Django, agrega members a `ConfiguracionTransicion.grupos_permitidos`.

---

## 7. First transition

Con el flujo configurado, ejecutar una transición es:

```python
# tu_app/views.py o servicio
from sinpapel.exceptions import SinpapelError

def avanzar_solicitud(request, solicitud_id):
    solicitud = Solicitud.objects.get(pk=solicitud_id)
    try:
        seguimiento = solicitud.transition(
            target_state_name="EN_REVISION",
            user=request.user,
            comentarios="Captura completa, lista para revisión",
        )
    except SinpapelError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"seguimiento_id": seguimiento.pk, "nuevo_estado": seguimiento.estado_nuevo.nombre})
```

`transition()` valida (estado origen, permisos del user, gates documentales) y persiste un `SeguimientoWorkflow` con timestamp, IP, comentarios + dispatch de side effects registrados.

Errores comunes:

- `WorkflowConfigurationError` — el modelo no está decorado con `@workflow_enabled` o falta `resolve_workflow_version()`.
- `PermissionError` — el user no tiene grupo permitido para esta transición.
- `ValueError` — el `target_state_name` no existe o no es destino válido desde el estado actual.

---

## 8. Signing backends

`sinpapel.signing` define un Protocol `SignatureBackend` con tres operaciones: `request_signature`, `verify`, `revoke`. Tres implementaciones shipped:

| Backend | Identificador | Cuándo usar |
|---------|---------------|-------------|
| `FielBackend` | `fiel` | Producción México: firma RSA-SHA256 con cert X.509 emitido por SAT (Servicio de Administración Tributaria). Verifica firma + extrae RFC del subject. |
| `ManualBackend` | `manual` | Universal: registro manual con scanned image + witness name + timestamp. Sin crypto. Ideal para flujos donde la firma es presencial / papel escaneado. |
| `FakeBackend` | `fake` | Tests / CI: deterministico (hash SHA-256 fijo). Nunca usar en producción. |

Selección del backend en runtime via setting `SINPAPEL_SIGNATURE_BACKEND` (ver §3) o invocación directa:

```python
from sinpapel.signing.factory import get_signature_backend
from sinpapel.signing.backends.fiel import FielBackend

# Vía settings (recomendado)
backend = get_signature_backend()

# O instanciación directa
backend = FielBackend()

# Firmar (FIEL): contenido a firmar + firma RSA + cert del SAT
registro = backend.request_signature(
    content=b"contenido canónico a firmar",
    signer=request.user,                        # opcional, mejor pasarlo
    firma_b64=request_data["firma_b64"],        # firma generada client-side
    certificado_cer_b64=request_data["cer_b64"],
    is_required=True,
)
# → RegistroFirma persistido con verification_result="VALIDA" + backend_metadata FIEL

# Verificar
result = backend.verify(registro)
assert result.valid is True

# Revocar
backend.revoke(registro, reason="cert comprometido")
# → verification_result="INVALIDA" + history audit entry
```

Para `ManualBackend`:

```python
backend = ManualBackend()
registro = backend.request_signature(
    content=b"acta firmada presencialmente",
    signer=request.user,
    scanned_image_path="/media/firmas/acta_42.jpg",
    witness_name="Mtra. Pérez",
)
```

---

## 9. Audit trail

Todos los cambios sobre 5 modelos clave (`RegistroFirma`, `InstanciaDocumento`, `ConfiguracionTransicion`, `VersionFlujo`, `RequisitoEstadoDocumento`) generan entradas en tablas `historical*` automáticamente.

Consulta el historial via API queryset estándar:

```python
from sinpapel.models import RegistroFirma

rf = RegistroFirma.objects.get(pk=42)

# Historial completo
for entry in rf.history.all():
    print(f"{entry.history_date} {entry.history_type} {entry.history_user} → {entry.verification_result}")
# Output:
# 2026-04-27 10:30 ~ admin → INVALIDA   (revoke)
# 2026-04-27 10:25 + carlos → VALIDA    (creación)

# Diff entre versiones
latest = rf.history.first()
previous = latest.prev_record
delta = latest.diff_against(previous)
for change in delta.changes:
    print(f"{change.field}: {change.old} → {change.new}")
```

`history_user` se popula automáticamente desde el request gracias a `HistoryRequestMiddleware` (§3). En contextos sin request (management commands, celery tasks), `history_user` será `None` salvo que uses `bulk_create_with_history` o `update_change_reason` explícitamente.

> **Trazable vs simple-history:** ambos coexisten sin redundancia. `Trazable` mantiene metadata de last-write (`autor`, `modificador`) optimizada para queries rápidas. `simple-history` captura cada cambio como fila inmutable separada. Distintos consumidores.

---

## 10. Side effects

Asocia handlers a transiciones específicas via decorator. Los handlers se ejecutan **dentro** de la transacción atómica de `transition()`, después de persistir el `SeguimientoWorkflow`:

```python
# tu_app/services/side_effects.py
from sinpapel.services.side_effects import register_side_effect


@register_side_effect("APROBADA")
def generar_oficio_aprobacion(solicitud, usuario, **kwargs):
    """Side effect ejecutado tras transición a estado APROBADA."""
    from tu_app.services.oficios import OficioService
    OficioService.generar(solicitud=solicitud, autor=usuario)
    return {"oficio_id": ...}


@register_side_effect("RECHAZADA")
def notificar_rechazo(solicitud, usuario, **kwargs):
    from tu_app.services.notificaciones import enviar_email
    enviar_email(
        to=solicitud.solicitante.email,
        subject="Tu solicitud fue rechazada",
        body=kwargs.get("comentarios", ""),
    )
```

Los handlers reciben `(instance, user, **kwargs)` donde `kwargs` incluye los argumentos pasados a `transition()`. Si un handler lanza una excepción, la transición completa hace rollback (atomicidad).

Para registrarlos al boot de la app, importa el módulo en `tu_app/apps.py:ready()`:

```python
# tu_app/apps.py
from django.apps import AppConfig

class TuAppConfig(AppConfig):
    name = "tu_app"

    def ready(self):
        from tu_app.services import side_effects  # noqa — registra los handlers
```

---

## 11. Testing

Para tests que necesitan firmas reales (sin sandbox SAT), genera un keypair RSA + cert auto-firmado in-memory:

```python
# tu_app/tests/conftest.py
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
        x509.NameAttribute(NameOID.COMMON_NAME, "TEST FIRMANTE"),
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

Si solo necesitas que la firma "funcione" sin validar criptografía (caso típico en tests de workflow):

```python
# settings_test.py
SINPAPEL_SIGNATURE_BACKEND = "sinpapel.signing.backends.fake.FakeBackend"
```

`FakeBackend` produce un `RegistroFirma` con hash determinístico, sin generar keypair real — mucho más rápido en suites grandes.

Para verificar que `history_user` se popula correctamente en tests con request real:

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
        # Tu mutación dentro de la request lifecycle
        ...

    HistoryRequestMiddleware(_do_mutation)(request)
    # Tus assertions sobre obj.history.first().history_user
```

---

## 12. Known limitations

`sinpapel v0.1.0` es **alpha** — la API puede cambiar antes de v1.0. Limitaciones explícitas que un consumer debe conocer:

- **i18n hardcoded en español:** `verbose_name`, `help_text`, mensajes de error y choices están en ES. Si tu proyecto es multi-idioma, abre un issue — refactor a `gettext_lazy` está planificado pero no en v0.1.x.
- **API `0.x.y` puede tener breaking changes en cada minor.** SemVer pre-1.0 no garantiza estabilidad. Pin a un commit/tag en producción y revisa los changelogs antes de upgrade.
- **`WorkflowService` legacy en `creditos` no fue migrado.** Si extraes patrones del repo `creditos`, nota que `WorkflowService.cambiar_estado()` (con `TRANSICIONES` dict + `PERMISOS_ACCION` fallback) coexiste con `Solicitud.transition()`. La auditoría de los 9 callers vive en `creditos/work/epics/e12-sinpapel/notes/workflow-service-audit.md`. En tu proyecto greenfield, usa solo `instance.transition(...)`.
- **`trazable` no está en PyPI público.** Instalación via git URL — coordina con el owner si necesitas el repo accesible.
- **Sin `py.typed` marker.** El paquete tiene type annotations pero no ships type stubs externos. Mypy/pyright en strict mode pueden requerir configuración adicional.
- **Migración del prefijo `creditos_*`:** las tablas SQL retienen el prefijo histórico. No es un blocker funcional, pero si te importa el naming en greenfield, abre un issue.

---

## 13. License & versioning

**License:** MIT (ver `LICENSE`). Uso comercial e institucional permitido. Sin garantía.

**Versioning:** [SemVer 2.0](https://semver.org). Pre-1.0 (`0.y.z`):

- Cambios de **`y` (minor)** pueden incluir breaking changes en API pública.
- Cambios de **`z` (patch)** son bug fixes / cambios internos sin breaking API.

Cuando la API se estabilice (v1.0.0), el contrato será:

- `MAJOR`: breaking changes.
- `MINOR`: features nuevas backwards-compatible.
- `PATCH`: bug fixes.

**Roadmap visible:**

- v0.2 — i18n vía `gettext_lazy`, `py.typed`, eliminar `WorkflowService` legacy del consumer ejemplo.
- v0.3 — soporte para PAdES (firma PDF universal vía endesive) como adapter adicional.
- v1.0 — API estable + publicación a PyPI público (decisión final de nombre + licencia).

**Reportar issues / proponer cambios:** [github.com/jadrians/creditos/issues](https://github.com/jadrians/creditos/issues).
