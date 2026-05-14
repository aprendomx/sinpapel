# sinpapel

> **v0.3.0-alpha** — Motor de workflow + auditoría + firma digital + captura de metadatos estructurados + predicados de transición + forms dinámicos para Django.
>
> Extraído de [creditos](https://github.com/jadrians/creditos) (E12). Diseñado para SEP, FONDESO, y cualquier proyecto Django que necesite **transiciones versionadas + auditoría inmutable + firmas electrónicas plugables + metadatos basados en schema** sin reinventar la rueda.
>
> [🇺🇸 Read in English](README.md)

---

## Tabla de Contenidos

1. [¿Qué es sinpapel?](#1-qué-es-sinpapel)
2. [Características](#2-características)
3. [Instalación](#3-instalación)
4. [Configuración](#4-configuración)
5. [Migraciones](#5-migraciones)
6. [Inicio Rápido](#6-inicio-rápido)
7. [Configuración del Workflow](#7-configuración-del-workflow)
8. [Transiciones de Estado](#8-transiciones-de-estado)
9. [Predicados de Transición](#9-predicados-de-transición)
10. [Captura de Metadatos Estructurados](#10-captura-de-metadatos-estructurados)
11. [Factory de Forms/Serializers](#11-factory-de-formsserializers)
12. [Backends de Firma](#12-backends-de-firma)
13. [Auditoría (Audit Trail)](#13-auditoría-audit-trail)
14. [Efectos Secundarios (Side Effects)](#14-efectos-secundarios-side-effects)
15. [Testing](#15-testing)
16. [Referencia de API](#16-referencia-de-api)
17. [Contribuir](#17-contribuir)
18. [Licencia y Versionado](#18-licencia-y-versionado)

---

## 1. ¿Qué es sinpapel?

`sinpapel` es un paquete Django que proporciona cuatro capacidades reutilizables para sistemas de procesamiento de trámites:

- **Motor de Workflow**: Máquina de estados versionada con transiciones configurables desde el admin de Django o migraciones de datos — sin lógica de estados hardcodeada. El decorador `@workflow_enabled` marca tu modelo de dominio (Solicitud, Permiso, Ticket, etc.) como capaz de workflow. El motor consulta `ConfiguracionTransicion` desde la base de datos en runtime.
- **Auditoría Inmutable**: Historial de cada cambio sobre modelos clave vía [django-simple-history](https://django-simple-history.readthedocs.io/), con `history_user` poblado por middleware durante requests reales.
- **Firmas Digitales**: Patrón Port + Adapter con tres backends incluidos:
  - `FielBackend` — FIEL/RSA-SHA256 + X.509 del SAT México
  - `ManualBackend` — Universal con imagen escaneada + testigo + timestamp (sin criptografía)
  - `FakeBackend` — Determinístico para tests/CI
- **Captura de Metadatos Estructurados**: Mixin `MetadatosCapturables` con campos declarados por schema, acceso proxy type-safe (`instance.meta.campo`), validación automática, y serialización JSON.

Las transiciones, requisitos documentales, auditoría, firmas y metadatos son **datos, no código**. Tu aplicación puede mutar los flujos de negocio sin redeployment.

---

## 2. Características

| Característica | Descripción |
|----------------|-------------|
| Decorador `@workflow_enabled` | Inyecta `available_transitions()`, `can_transition_to()`, `transition()` en tu modelo |
| `VersionFlujo` | Definiciones de workflow versionadas; banderas activo/inactivo para rollout A/B |
| `ConfiguracionTransicion` | Aristas dirigidas entre estados con permisos basados en grupos |
| `SeguimientoWorkflow` | Log de auditoría inmutable de cada transición con timestamp, IP, comentarios |
| `MetadatosCapturables` | Captura de metadatos basada en schema con validación de tipos y acceso proxy |
| `MetaFormFactory` | Generación dinámica de Django Forms / DRF Serializers desde `SCHEMA_METADATOS` |
| `CondicionTransicion` | Predicados configurables por transición con backends plugables (Python, JSON Logic, ORM) |
| `PredicateEngine` | Motor extensible para evaluar reglas de negocio antes de transiciones de estado |
| `Trazable` / `Catalogo` | Mixins reutilizables para tracking de creación/actualización y modelos catálogo |
| `RegistroFirma` | Registros de firma criptográfica con verificación agnóstica al backend |
| `ExpedienteAdjunto` | Adjuntos de archivos genéricos con vinculación por content-type |
| Integración con `django-simple-history` | Tablas históricas automáticas para 5+ modelos |
| Efectos secundarios | Handlers basados en decorador ejecutados atómicamente dentro de transiciones |
| Listo para i18n | Todo el metadata de modelos envuelto en `gettext_lazy` |
| Type hints | Marcador `py.typed` incluido para cumplimiento PEP 561 |

---

## 3. Instalación

`sinpapel` aún no está en PyPI. Instala directamente desde Git mientras la API se estabiliza:

```bash
pip install "git+ssh://git@github.com/aprendomx/sinpapel.git@develop"

# O con tag fijo:
pip install "git+ssh://git@github.com/aprendomx/sinpapel.git@v0.2.0"
```

**Requisitos:**
- Python `>=3.10`
- Django `>=5.0`

Verificación post-instalación:

```python
>>> import sinpapel
>>> sinpapel.__version__
'0.2.0'
>>> from sinpapel import workflow_enabled, WorkflowRegistry
>>> from sinpapel.signing.backends.fiel import FielBackend
```

---

## 4. Configuración

Agrega `sinpapel` (y dependencias) a `INSTALLED_APPS` **antes de tu app de dominio**:

```python
# settings.py
INSTALLED_APPS = [
    # ... django.contrib.* ...
    "simple_history",   # requerido por HistoricalRecords
    "sinpapel",         # antes de tu app de dominio para resolución de FK string
    "tu_app",           # ej. "creditos", "sep", "fondeso"
]
```

Activa el middleware de usuario de auditoría (después de `AuthenticationMiddleware`):

```python
MIDDLEWARE = [
    # ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",  # popula history_user
    # ...
]
```

Configura el backend de firma (sobrescribible via variable de entorno):

```python
import os

SINPAPEL_SIGNATURE_BACKEND = os.environ.get(
    "SINPAPEL_SIGNATURE_BACKEND",
    "sinpapel.signing.backends.fiel.FielBackend",
)
```

> **Tip para CI:** Usa `SINPAPEL_SIGNATURE_BACKEND=sinpapel.signing.backends.fake.FakeBackend` en pipelines de test para evitar generar keypairs reales.

---

## 5. Migraciones

Ejecuta las migraciones de sinpapel para crear todas las tablas de workflow, documentos, firma y auditoría:

```bash
python manage.py migrate sinpapel
```

Migraciones incluidas:

- `0001_initial` — Crea todos los modelos: `Etapa`, `Estado`, `VersionFlujo`, `ConfiguracionTransicion`, `SeguimientoWorkflow`, `RequisitoEstadoDocumento`, `TipoDocumento`, `Documento`, `InstanciaDocumento`, `RazonRechazoDocumento`, `ExpedienteAdjunto`, `RegistroFirma`, más tablas `historical_*`.

> **Breaking change en v0.2.0:** El historial de migraciones fue squasheado en una sola `0001_initial`. Despliegues existentes deben ejecutar `migrate --fake` o recrear la base de datos.

---

## 6. Inicio Rápido

Aplica `@workflow_enabled` al modelo que avanza entre estados:

```python
# tu_app/models.py
from django.db import models
from sinpapel import workflow_enabled
from sinpapel.mixins import CampoMetadato, MetadatosCapturables, Trazable
from decimal import Decimal


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
        """Hook polimórfico para resolver el VersionFlujo activo de esta instancia.

        El motor llama a este método cuando necesita validar una transición.
        Debe retornar un VersionFlujo (o None para fallback global).
        """
        from sinpapel.models import VersionFlujo
        return VersionFlujo.objects.filter(activo=True, nombre=self.tipo_tramite).first()
```

El decorador inyecta tres métodos:

- `solicitud.available_transitions(user)` → lista de `Estado` permitidos para este usuario en el estado actual.
- `solicitud.can_transition_to(nombre_estado_destino, user)` → tupla `(bool, str | None)`.
- `solicitud.transition(nombre_estado_destino, user, **kwargs)` → ejecuta transición + auditoría + efectos secundarios.

`state_field` debe ser un ForeignKey a `sinpapel.Estado`. `workflow_key` identifica el flujo en el registro.

---

## 7. Configuración del Workflow

Crea `Etapa`, `Estado`, `VersionFlujo` y `ConfiguracionTransicion` desde el admin o via migración de datos:

```python
# tu_app/migrations/0002_seed_workflow.py
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
    dependencies = [("sinpapel", "0001_initial"), ("tu_app", "0001_initial")]
    operations = [migrations.RunPython(seed, reverse_code=migrations.RunPython.noop)]
```

Para restringir transiciones por grupo Django, agrega miembros a `ConfiguracionTransicion.grupos_permitidos`.

---

## 8. Transiciones de Estado

Con el workflow configurado, ejecutar una transición es directo:

```python
# tu_app/views.py o capa de servicios
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
    return JsonResponse({
        "seguimiento_id": seguimiento.pk,
        "nuevo_estado": seguimiento.estado_nuevo.nombre,
    })
```

`transition()` valida (estado origen, permisos del usuario, gates documentales) y persiste un `SeguimientoWorkflow` con timestamp, IP, comentarios + dispatch de efectos secundarios registrados.

Errores comunes:

- `WorkflowConfigurationError` — El modelo no está decorado con `@workflow_enabled` o falta `resolve_workflow_version()`.
- `PermissionError` — El usuario no pertenece a un grupo permitido para esta transición.
- `ValueError` — El `target_state_name` no existe o no es un destino válido desde el estado actual.

---

## 9. Predicados de Transición

Adjunta reglas de negocio configurables a cualquier `ConfiguracionTransicion` via `CondicionTransicion`. El `WorkflowEngine` evalúa todas las condiciones activas (en `orden`) después de la validación de grupos y antes de permitir la transición.

**Backends:**

| Backend | `tipo` | Caso de uso |
|---------|--------|-------------|
| **Python Path** | `python_path` | Lógica compleja, validadores reutilizables, llamadas a APIs externas. Solo módulos en whitelist (`SINPAPEL_PREDICATE_MODULES`). |
| **JSON Logic** | `json_logic` | Reglas declarativas simples editables por no-desarrolladores via UI. Operadores seguros: `var`, `==`, `!=`, `<`, `>`, `<=`, `>=`, `and`, `or`, `!`, `in`. |
| **Django ORM** | `django_orm` | Condiciones sobre campos de modelos relacionados via lookups ORM. |

**Ejemplo — Python Path:**

```python
# tu_app/validators.py
def monto_minimo_100k(instance, user):
    if instance.meta.monto_solicitado >= 100_000:
        return True
    return False, "El monto debe ser al menos $100,000"
```

```python
# Admin o migración
from sinpapel.models.predicates import CondicionTransicion

CondicionTransicion.objects.create(
    transicion=transicion_aprobacion,
    tipo="python_path",
    configuracion={"path": "tu_app.validators.monto_minimo_100k"},
    mensaje_error="No cumple con las condiciones de monto",
    orden=1,
)
```

**Ejemplo — JSON Logic:**

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

**Seguridad:** El backend `python_path` solo importa desde módulos listados en `SINPAPEL_PREDICATE_MODULES` (setting de Django). Una whitelist vacía bloquea todas las importaciones por defecto.

---

## 10. Captura de Metadatos Estructurados

Los modelos que heredan de `MetadatosCapturables` declaran un schema de campos de metadatos capturables:

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

Uso en runtime:

```python
obj = MiModelo.objects.create(...)
obj.meta.rfc = "ABCD010101ABC"
obj.meta.monto = Decimal("500000")
obj.meta.tipo = "A"
obj.save()  # valida el schema automáticamente

# Serialización
obj.meta.to_dict()
# → {"rfc": "ABCD010101ABC", "monto": Decimal("500000"), "tipo": "A"}

obj.meta.to_dict(incluir_defaults=False)
# → solo campos explícitamente seteados
```

Validación:

- Campos desconocidos lanzan `AttributeError`
- Tipos incorrectos lanzan `TypeError`
- Choices inválidas lanzan `ValueError`
- Campos requeridos faltantes lanzan `ValidationError` en `save()`

Tipos soportados: `str`, `int`, `bool`, `Decimal`, `date`.

---

## 11. Factory de Forms/Serializers

Genera Django Forms y DRF Serializers dinámicamente desde `SCHEMA_METADATOS` — no necesitas escribir clases Form/Serializer manualmente.

### Django Forms

```python
from sinpapel.forms import MetaFormFactory

MetaForm = MetaFormFactory.build_form(
    Solicitud.SCHEMA_METADATOS,
    name="SolicitudMetaForm",
)

# En una vista
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

# En un viewset
serializer = MetaSerializer(data=request.data)
if serializer.is_valid():
    for key, value in serializer.validated_data.items():
        setattr(solicitud.meta, key, value)
    solicitud.save()
```

> **Nota:** DRF es una dependencia opcional. `build_serializer()` lanza `ImportError` con instrucciones de instalación si `djangorestframework` no está instalado.

### Mapeo de Campos

| `CampoMetadato.tipo` | Django Form Field | DRF Field |
|----------------------|-------------------|-----------|
| `str` (sin choices) | `CharField` | `CharField` |
| `str` (con choices) | `ChoiceField` | `ChoiceField` |
| `int` | `IntegerField` | `IntegerField` |
| `bool` | `BooleanField` | `BooleanField` |
| `Decimal` | `DecimalField(max_digits=15, decimal_places=2)` | `DecimalField(max_digits=15, decimal_places=2)` |
| `date` | `DateField` | `DateField` |

**Metadata mapeada:**
- `requerido` → `required`
- `default` → `initial` (Django) / `default` (DRF)
- `etiqueta` → `label`
- `ayuda` → `help_text`

---

## 12. Backends de Firma

`sinpapel.signing` define un Protocolo `SignatureBackend` con tres operaciones: `request_signature`, `verify`, `revoke`. Tres implementaciones incluidas:

| Backend | Identificador | Cuándo usar |
|---------|---------------|-------------|
| `FielBackend` | `fiel` | Producción México: firma RSA-SHA256 con certificado X.509 emitido por SAT (Servicio de Administración Tributaria). Verifica firma + extrae RFC del subject. |
| `ManualBackend` | `manual` | Universal: registro manual con imagen escaneada + nombre de testigo + timestamp. Sin criptografía. Ideal para flujos donde la firma es presencial / papel escaneado. |
| `FakeBackend` | `fake` | Tests / CI: determinístico (hash SHA-256 fijo). Nunca usar en producción. |

Selección del backend en runtime via setting `SINPAPEL_SIGNATURE_BACKEND` (ver §4) o instanciación directa:

```python
from sinpapel.signing.factory import get_signature_backend
from sinpapel.signing.backends.fiel import FielBackend

# Vía settings (recomendado)
backend = get_signature_backend()

# O instanciación directa
backend = FielBackend()

# Firmar (FIEL): contenido a firmar + firma RSA + certificado SAT
registro = backend.request_signature(
    content=b"contenido canónico a firmar",
    signer=request.user,                        # opcional, recomendado
    firma_b64=request_data["firma_b64"],        # firma generada client-side
    certificado_cer_b64=request_data["cer_b64"],
    is_required=True,
)
# → RegistroFirma persistido con verification_result="VALIDA" + backend_metadata FIEL

# Verificar
result = backend.verify(registro)
assert result.valid is True

# Revocar
backend.revoke(registro, reason="certificado comprometido")
# → verification_result="INVALIDA" + entrada de auditoría histórica
```

Para `ManualBackend`:

```python
backend = ManualBackend()
registro = backend.request_signature(
    content=b"documento firmado presencialmente",
    signer=request.user,
    scanned_image_path="/media/firmas/doc_42.jpg",
    witness_name="Mtra. Pérez",
)
```

---

## 11. Auditoría (Audit Trail)

Todos los cambios sobre 5 modelos clave (`RegistroFirma`, `InstanciaDocumento`, `ConfiguracionTransicion`, `VersionFlujo`, `RequisitoEstadoDocumento`) generan entradas automáticas en tablas `historical_*`.

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

`history_user` se popula automáticamente desde el request gracias a `HistoryRequestMiddleware` (§4). En contextos sin request (management commands, tareas Celery), `history_user` será `None` salvo que uses `bulk_create_with_history` o `update_change_reason` explícitamente.

> **Trazable vs simple-history:** Ambos coexisten sin redundancia. `Trazable` mantiene metadata de última escritura (`autor`, `modificador`) optimizada para queries rápidas. `simple-history` captura cada cambio como fila inmutable separada. Distintos consumidores.

---

## 12. Efectos Secundarios (Side Effects)

Asocia handlers a transiciones específicas via decorador. Los handlers se ejecutan **dentro** de la transacción atómica de `transition()`, después de persistir el `SeguimientoWorkflow`:

```python
# tu_app/services/side_effects.py
from sinpapel.services.side_effects import register_side_effect


@register_side_effect("APROBADA")
def generar_oficio_aprobacion(solicitud, usuario, **kwargs):
    """Efecto secundario ejecutado tras transición a estado APROBADA."""
    from tu_app.services.oficios import OficioService
    return {"oficio_id": OficioService.generar(solicitud=solicitud, autor=usuario)}


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

Para registrarlos al arranque de la app, importa el módulo en `tu_app/apps.py:ready()`:

```python
# tu_app/apps.py
from django.apps import AppConfig


class TuAppConfig(AppConfig):
    name = "tu_app"

    def ready(self):
        from tu_app.services import side_effects  # noqa — registra los handlers
```

---

## 13. Testing

### Ejecutar el test suite de sinpapel

```bash
pytest tests/ --ds=tests.settings
```

### Testing con FakeBackend

Para tests que necesitan que la firma "funcione" sin criptografía real:

```python
# settings_test.py
SINPAPEL_SIGNATURE_BACKEND = "sinpapel.signing.backends.fake.FakeBackend"
```

`FakeBackend` produce un `RegistroFirma` con hash determinístico, sin generar keypair real — mucho más rápido en suites grandes.

### Testing con RSA + cert auto-firmado real

Para tests que necesitan firmas reales (sin sandbox SAT):

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

### Testing de history_user

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
        # Tu mutación dentro del ciclo de vida del request
        ...

    HistoryRequestMiddleware(_do_mutation)(request)
    # Tus assertions sobre obj.history.first().history_user
```

---

## 14. Referencia de API

### `@workflow_enabled(state_field, workflow_key, expose_endpoints=False)`

Decorador de clase que registra el modelo en `WorkflowRegistry` e inyecta métodos de workflow.

**Parámetros:**
- `state_field` (str): Nombre del ForeignKey a `sinpapel.Estado`.
- `workflow_key` (str): Identificador único para este workflow en el registro.
- `expose_endpoints` (bool): Si auto-registra endpoints REST (feature futuro).

**Requiere:** Método `resolve_workflow_version()` en la clase decorada.

### `WorkflowEngine`

Servicio core para validación y ejecución de transiciones.

**Métodos:**
- `puede_cambiar_estado(instance, nombre_estado_destino, user) → (bool, str | None)`
- `cambiar_estado(instance, nombre_estado_destino, user, comentarios="", firma_payload=None) → dict`
- `available_transitions(instance, user) → list[Estado]`

### `CondicionTransicion`

Modelo que almacena un predicado configurable para una transición.

**Campos:**
- `transicion: ForeignKey[ConfiguracionTransicion]` — la transición a la que aplica esta condición
- `tipo: str` — tipo de backend: `python_path`, `json_logic`, `django_orm`
- `configuracion: JSONField` — parámetros específicos del backend
- `mensaje_error: str` — mensaje de error mostrado cuando la condición falla
- `orden: int` — orden de evaluación (menor primero)
- `activo: bool` — si esta condición es evaluada

### `PredicateEngine`

Motor extensible para evaluar condiciones de transición.

**Métodos de clase:**
- `registrar_backend(tipo: str, funcion: callable) → None` — registra un backend personalizado
- `evaluar(condicion, instance, user) → (bool, str | None)` — evalúa una condición individual

**Backends incluidos:**
- `python_path` — importa y llama una función Python desde un módulo en whitelist
- `json_logic` — evalúa una regla JSON Logic contra los metadatos de la instancia
- `django_orm` — evalúa un lookup de Django ORM contra la instancia

**Settings:**
- `SINPAPEL_PREDICATE_MODULES: list[str]` — whitelist de módulos para el backend `python_path`

### `MetaFormFactory`

Factory para generar Django Forms y DRF Serializers desde `SCHEMA_METADATOS`.

**Métodos de clase:**
- `build_form(schema, name=None, **kwargs) → type[forms.Form]` — genera un Django Form
- `build_serializer(schema, name=None, **kwargs) → type[serializers.Serializer]` — genera un DRF Serializer (lanza `ImportError` si DRF no está instalado)

### `MetadatosCapturables`

Mixin abstracto de modelo Django. Agrega a tu modelo junto con `Trazable`.

**Atributos de clase:**
- `SCHEMA_METADATOS: list[CampoMetadato]`

**Propiedades de instancia:**
- `meta: MetadatosProxy` — proxy de lectura/escritura type-safe

**Métodos:**
- `clean()` — valida campos requeridos
- `save()` — llama `clean()` antes de persistir

### `CampoMetadato`

Dataclass frozen que define el schema de un campo de metadato.

**Campos:**
- `nombre: str`
- `tipo: type` — `str`, `int`, `bool`, `Decimal`, `date`
- `requerido: bool = False`
- `default: Any = None`
- `choices: list[str] | None = None`
- `etiqueta: str = ""`
- `ayuda: str = ""`

### `MetadatosProxy`

Proxy en runtime adjunto a `instance.meta`.

**Métodos:**
- `errores() → dict[str, str]` — valida todos los campos requeridos
- `to_dict(incluir_defaults=True) → dict[str, Any]` — serializa todos los campos del schema

---

## 15. Contribuir

Las contribuciones son bienvenidas. Por favor abre un issue antes de cambios grandes.

1. Fork el repositorio
2. Crea una rama de feature (`git checkout -b feature/mi-feature`)
3. Realiza tus cambios con tests
4. Asegúrate de que el test suite pase: `pytest tests/ -q`
5. Commitea con mensajes claros
6. Push y abre un Pull Request

Setup de desarrollo:

```bash
git clone git@github.com:aprendomx/sinpapel.git
cd sinpapel
pip install -e ".[dev]"
pytest tests/ -q
```

---

## 16. Licencia y Versionado

**Licencia:** MIT (ver `LICENSE`). Uso comercial e institucional permitido. Sin garantía.

**Versionado:** [SemVer 2.0](https://semver.org). Pre-1.0 (`0.y.z`):

- Cambios de **`y` (minor)** pueden incluir breaking changes en API pública.
- Cambios de **`z` (patch)** son bug fixes / cambios internos sin breaking API.

Cuando la API se estabilice (v1.0.0), el contrato será:

- `MAJOR`: breaking changes.
- `MINOR`: features nuevas backwards-compatible.
- `PATCH`: bug fixes.

**Roadmap visible:**

- v0.2 — i18n vía `gettext_lazy`, `py.typed`, tablas `sinpapel_*`, modelo `Etapa`, tests standalone, mixin `MetadatosCapturables`. **(DONE)**
- v0.3 — Predicados de Transición (`CondicionTransicion` + `PredicateEngine`), Factory de Forms/Serializers (`MetaFormFactory`), evaluador JSON Logic, backends de predicados plugables. **(DONE)**
- v0.4 — Soporte para PAdES (firma PDF universal vía endesive) como adapter adicional.
- v1.0 — API estable + publicación a PyPI pública (decisión final de nombre + licencia).

**Reportar issues / proponer cambios:** [github.com/aprendomx/sinpapel/issues](https://github.com/aprendomx/sinpapel/issues)
