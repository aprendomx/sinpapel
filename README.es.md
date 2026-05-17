# sinpapel

> **v0.5.0** — Máquinas de estado versionadas, auditoría inmutable y firmas electrónicas plugables para Django.

[![PyPI](https://img.shields.io/pypi/v/sinpapel.svg)](https://pypi.org/project/sinpapel/)
[![Python](https://img.shields.io/pypi/pyversions/sinpapel.svg)](https://pypi.org/project/sinpapel/)
[![Django](https://img.shields.io/badge/django-5.0%20%7C%205.1-blue)](https://www.djangoproject.com/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-272%20passing-brightgreen)](#)

🇺🇸 [Read in English](README.md)

---

## ¿Por qué sinpapel?

Construir procesos sin papel en Django suele significar pegar una librería de máquina de estados, un framework de auditoría, una capa de firma y un toolkit de formularios. **sinpapel** los entrega como un único paquete coherente: flujos versionados declarativos, historial inmutable, backends de firma plugables, captura de metadatos basada en schema, predicados de transición, timers SLA y signals de dominio personalizados — diseñado para adoptarse incrementalmente en cualquier proyecto Django 5+.

## Características

- **Motor de Workflow** — máquinas de estado versionadas vía `VersionFlujo` + `ConfiguracionTransicion`, con grupos de permisos, gates de documentos obligatorios y un servicio `WorkflowEngine`.
- **Predicados de Transición** — paths Python, JSON Logic restringido y predicados con backend ORM de Django, ordenados por transición.
- **Captura Estructurada de Metadatos** — mixin `MetadatosCapturables` con campos declarados por schema vía `CampoMetadato`, validados al guardar.
- **Formularios y Serializers Dinámicos** — `MetaFormFactory` construye Django Forms desde el schema de metadatos; modo DRF Serializer también soportado.
- **Backends de Firma Plugables** — interfaz strategy más backends de referencia: `SimuladoBackend`, `RSAFileBackend` y `FielBackend` (RSA-SHA256 + X.509).
- **Pista de Auditoría Inmutable** — mixin `Trazable`, historial `SeguimientoWorkflow`, `RegistroFirma`, más integración con `django-simple-history`.
- **Timers SLA y Preview de Transiciones** — `SLAEngine` con acciones notificar / escalar / rechazar / alertar; `WorkflowEngine.preview_transition()` retorna un reporte de impacto sin mutar el estado.
- **Signals de Dominio Personalizados** — `predicate_failed`, `sla_breached`, `sla_action_executed`, `transition_preview_requested` para observabilidad y cableado de side-effects.

## Instalación

```bash
pip install sinpapel
```

Requiere Python 3.10+ y Django 5.0+.

Agregar a `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "simple_history",
    "sinpapel",
    "mi_app",  # tu app que define modelos workflow-enabled
]
```

Correr migraciones:

```bash
python manage.py migrate sinpapel
```

## Quick Start

Declarar un modelo workflow-enabled:

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

    def resolve_workflow_version(self):
        from sinpapel.models import VersionFlujo
        return VersionFlujo.objects.get(nombre="solicitudes", activo=True)
```

Ejecutar una transición de estado a través del motor:

```python
from sinpapel.services.workflow_engine import WorkflowEngine

engine = WorkflowEngine()

# Preview antes de commitear (no muta, retorna reporte de impacto)
preview = engine.preview_transition(solicitud, "APROBADA", user=request.user)
if not preview["permitido"]:
    raise ValueError(preview["razones_bloqueo"][0]["mensaje"])

# Ejecutar la transición (crea row de auditoría + dispara signals)
engine.cambiar_estado(solicitud, "APROBADA", user=request.user, comentarios="Cumple requisitos")
```

Suscribirse a un signal personalizado:

```python
from django.dispatch import receiver
from sinpapel.signals import sla_breached

@receiver(sla_breached)
def on_sla_breach(sender, instance, sla, **kwargs):
    notify_team(instance, sla)
```

Ejemplos end-to-end completos, seeding de schema, cookbook de predicados, setup de backends de firma e integración con admin viven en [`docs/usage/es.md`](docs/usage/es.md).

## Qué Incluye

| Subsistema | Módulo | Docs |
|---|---|---|
| Motor de Workflow | `sinpapel.services.workflow_engine` | [USAGE §Transiciones](docs/usage/es.md#8-transiciones-de-estado) |
| Predicados | `sinpapel.services.predicate_engine` | [USAGE §Predicados](docs/usage/es.md#9-predicados-de-transición) |
| Metadatos | `sinpapel.mixins` | [USAGE §Metadatos](docs/usage/es.md#10-captura-estructurada-de-metadatos) |
| Forms Factory | `sinpapel.forms` | [USAGE §Forms](docs/usage/es.md#11-formserializer-factory) |
| Firmas | `sinpapel.signing` | [USAGE §Firmas](docs/usage/es.md#12-backends-de-firma) |
| Auditoría | `sinpapel.models` + `sinpapel.mixins.Trazable` | [USAGE §Auditoría](docs/usage/es.md#13-pista-de-auditoría) |
| Motor SLA | `sinpapel.services.sla_engine` | [USAGE §SLA](docs/usage/es.md) |
| Signals Personalizados | `sinpapel.signals` | [USAGE §Signals](docs/usage/es.md) |
| Export/Import de Schema | `sinpapel.schemas` + management commands | [USAGE §Schema](docs/usage/es.md) |

## Configuración

Settings opcionales de Django:

```python
# settings.py
SINPAPEL_DEFAULT_SIGNATURE_BACKEND = "rsa_file"
SINPAPEL_RSA_PRIVATE_KEY_PATH = "/run/secrets/sinpapel.key"
SINPAPEL_RSA_PUBLIC_KEY_PATH = "/run/secrets/sinpapel.pub"
SINPAPEL_EMIT_PREVIEW_EVENTS = False  # poner True para disparar el signal transition_preview_requested
```

Ver [USAGE §Settings](docs/usage/es.md#4-settings) para la referencia completa.

## Compatibilidad

| Python | Django |
|---|---|
| 3.10, 3.11, 3.12, 3.13 | 5.0, 5.1 |

CI corre el suite de tests contra la matriz completa.

## Documentación

- [Guía de Uso](docs/usage/es.md) — referencia completa (ES)
- [Usage Guide](docs/usage/en.md) — referencia completa (EN)
- [Changelog](docs/development/changelog.md)
- [Contributing](docs/development/contributing.md)
- [Código de Conducta](CODE_OF_CONDUCT.md)

## Versionado y Estabilidad

sinpapel sigue [Semantic Versioning](https://semver.org/). La release actual es **v0.5.0 (Beta)**. Las APIs públicas (`WorkflowEngine`, `PredicateEngine`, `SLAEngine`, signals, campos de modelos, schema JSON v0.2) son estables en la serie 0.x; los breaking changes incrementarán el minor y serán marcados en `docs/development/changelog.md` hasta 1.0.0.

## Contribuir

Los pull requests son bienvenidos. Por favor lee [docs/development/contributing.md](docs/development/contributing.md) para setup de desarrollo, convenciones de commits y el requisito de sign-off DCO (Developer Certificate of Origin).

## Licencia

Copyright (C) 2024-2026 Julio Adrián.

sinpapel es software libre: puedes redistribuirlo y/o modificarlo bajo los términos de la GNU General Public License publicada por la Free Software Foundation, ya sea la versión 3 de la Licencia, o (a tu elección) cualquier versión posterior.

sinpapel se distribuye con la esperanza de ser útil, pero **SIN NINGUNA GARANTÍA**; sin siquiera la garantía implícita de COMERCIABILIDAD o IDONEIDAD PARA UN PROPÓSITO PARTICULAR. Ver la [GNU General Public License](LICENSE) para más detalles.
