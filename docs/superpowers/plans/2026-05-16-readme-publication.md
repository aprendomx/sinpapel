# README Rewrite + GPL-3.0 Publication Materials — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite sinpapel's public-facing materials (README EN+ES, LICENSE, CHANGELOG, CONTRIBUTING, CODE_OF_CONDUCT, pyproject.toml) to ship under GPL-3.0-or-later, ready for PyPI publication, with all institutional references removed.

**Architecture:** Move the existing 900-line manual READMEs to `docs/USAGE.md` (+ ES mirror), then write fresh ~350-line READMEs focused on positioning, install, quick start, and feature map. Replace MIT LICENSE with the full GPL-3.0 text. Update `pyproject.toml` to SPDX license expression (PEP 639), GPL classifier, Beta status, and `setuptools>=77`. Reconstruct `CHANGELOG.md` from `git log` between version tags. Create `CONTRIBUTING.md` (Conventional Commits + DCO) and the verbatim Contributor Covenant 2.1 `CODE_OF_CONDUCT.md`.

**Tech Stack:** Markdown, TOML, Python packaging (`setuptools`, `build`, `twine`), git.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `LICENSE` | Replace | GPL-3.0 canonical full text + copyright header |
| `README.md` | Rewrite | EN positioning + quick start + feature map (~350 lines) |
| `README.es.md` | Rewrite | ES mirror of README.md |
| `docs/USAGE.md` | Create | Long-form EN manual (migrated from old README.md) |
| `docs/USAGE.es.md` | Create | Long-form ES manual (migrated from old README.es.md) |
| `CHANGELOG.md` | Create | Keep a Changelog 1.1.0, reconstructed v0.1.x → v0.5.0 |
| `CONTRIBUTING.md` | Create | Dev setup, Conventional Commits, DCO, PR flow |
| `CODE_OF_CONDUCT.md` | Create | Contributor Covenant v2.1 verbatim |
| `pyproject.toml` | Edit | License → GPL-3.0-or-later (SPDX), classifiers, deps, URLs template |

**Order of execution:** Tasks 1–9 below produce one commit each. Task 10 is verification + push. Each task is self-contained and can be reviewed independently.

---

## Task 1: Replace `LICENSE` with GPL-3.0

**Files:**
- Replace: `LICENSE`

- [ ] **Step 1: Download canonical GPL-3.0 text**

Run:
```bash
curl -fsSL https://www.gnu.org/licenses/gpl-3.0.txt -o LICENSE.tmp
wc -l LICENSE.tmp  # expect ~675 lines
head -3 LICENSE.tmp  # expect: GNU GENERAL PUBLIC LICENSE / Version 3, 29 June 2007 / Copyright (C) 2007 Free Software Foundation, Inc.
```

If `curl` is unavailable, fall back to: `wget https://www.gnu.org/licenses/gpl-3.0.txt -O LICENSE.tmp`.

- [ ] **Step 2: Prepend copyright header and replace LICENSE**

Prepend the project copyright notice **before** the canonical GPL header. The final `LICENSE` file must start with:

```
sinpapel — versioned workflows, immutable audit, and pluggable e-signatures for Django.
Copyright (C) 2024-2026 Julio Adrián <jadrian.s@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

================================================================================

```

…immediately followed by the full canonical GPL-3.0 text from `LICENSE.tmp`.

Run:
```bash
cat > LICENSE <<'HEADER'
sinpapel — versioned workflows, immutable audit, and pluggable e-signatures for Django.
Copyright (C) 2024-2026 Julio Adrián <jadrian.s@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

================================================================================

HEADER
cat LICENSE.tmp >> LICENSE
rm LICENSE.tmp
```

- [ ] **Step 3: Verify**

Run:
```bash
head -3 LICENSE
# Expected line 1: "sinpapel — versioned workflows, immutable audit, and pluggable e-signatures for Django."
grep -c "GNU GENERAL PUBLIC LICENSE" LICENSE
# Expected: 2 (one in the copyright header reference, one in the canonical body)
wc -l LICENSE
# Expected: ~695 lines (header + GPL body)
```

- [ ] **Step 4: Commit**

```bash
git add LICENSE
git commit -m "license: switch from MIT to GPL-3.0-or-later"
```

---

## Task 2: Move long-form English manual to `docs/USAGE.md`

**Files:**
- Create: `docs/USAGE.md` (from current `README.md`)

- [ ] **Step 1: Copy the current README content as the starting point**

```bash
mkdir -p docs
cp README.md docs/USAGE.md
```

- [ ] **Step 2: Strip institutional references from `docs/USAGE.md`**

Open `docs/USAGE.md` and apply these edits exactly:

| Location | Before | After |
|---|---|---|
| Line 1 (title) | `# sinpapel` | `# sinpapel — Usage Guide` |
| Subtitle blockquote (top) | The entire `> **v0.4.0-alpha** — …` and `> Extracted from [creditos]…` and `> [🇪🇸 Leer en Español]` lines | Replace the three blockquote lines with a single line: `> Comprehensive usage guide for sinpapel. For the high-level overview, see the [README](../README.md). Spanish version: [USAGE.es.md](USAGE.es.md).` |
| Any line containing `SEP, FONDESO, and any Django project` | Whole sentence | Replace with: `Designed for any Django project that needs versioned state transitions, immutable audit, pluggable electronic signatures, and schema-based metadata without reinventing the wheel.` |
| Any block referencing `sinpapel-designer` with the GitHub URL `aprendomx/sinpapel-designer` | Whole blockquote | Replace with a one-line note: `> **Tip:** An optional visual workflow designer can round-trip JSON via the \`sinpapel_export_flujo\` / \`sinpapel_import_flujo\` management commands.` |
| `pip install "git+ssh://git@github.com/aprendomx/sinpapel.git@…"` examples | Both lines | Replace with: `pip install sinpapel` and `pip install "sinpapel==0.5.0"` |
| Comment `# e.g. "creditos", "sep", "fondeso"` or similar | Whole comment | Replace with: `# e.g. "my_app", "requests"` |
| Line containing `git clone git@github.com:aprendomx/sinpapel.git` | Whole line | Replace with: `git clone <repository-url>` |
| Any "Report issues" footer pointing to `github.com/aprendomx/sinpapel/issues` | Whole line | Replace with: `**Report issues / propose changes:** see the project repository.` |
| Version badge / header text `v0.4.0-alpha` | All occurrences | Replace with: `v0.5.0` |

Use this command to verify zero institutional matches remain:
```bash
grep -nE "SEP|FONDESO|aprendomx|creditos|E12|github\.com/jadrians" docs/USAGE.md
# Expected: no output
```

If any matches remain, edit them out manually.

- [ ] **Step 3: Add a navigation header to `docs/USAGE.md`**

Insert immediately after the existing Table of Contents block:

```markdown
> **Navigation:** [README (overview)](../README.md) · [CHANGELOG](../CHANGELOG.md) · [CONTRIBUTING](../CONTRIBUTING.md) · [Spanish version](USAGE.es.md)
```

- [ ] **Step 4: Commit**

```bash
git add docs/USAGE.md
git commit -m "docs: move long-form EN manual to docs/USAGE.md"
```

---

## Task 3: Move long-form Spanish manual to `docs/USAGE.es.md`

**Files:**
- Create: `docs/USAGE.es.md` (from current `README.es.md`)

- [ ] **Step 1: Copy current Spanish README as the starting point**

```bash
cp README.es.md docs/USAGE.es.md
```

- [ ] **Step 2: Strip institutional references from `docs/USAGE.es.md`**

Apply the same edits as Task 2 Step 2, translated to Spanish where the text is Spanish:

| Location | Before | After |
|---|---|---|
| Line 1 | `# sinpapel` | `# sinpapel — Guía de Uso` |
| Subtitle blockquote (top) | The `> **v0.4.0-alpha** — …` / `> Extraído desde [creditos]…` / `> [🇺🇸 Read in English]` lines | Single line: `> Guía completa de uso de sinpapel. Para el panorama general, ver el [README](../README.es.md). English version: [USAGE.md](USAGE.md).` |
| Line containing `Diseñado para SEP, FONDESO, y cualquier proyecto Django` | Whole sentence | `Diseñado para cualquier proyecto Django que necesite transiciones de estado versionadas, auditoría inmutable, firmas electrónicas plugables y metadatos basados en schema sin reinventar la rueda.` |
| `sinpapel-designer` blockquote (with `aprendomx` URL) | Whole blockquote | `> **Tip:** Existe un diseñador visual de flujos opcional que intercambia JSON vía los management commands \`sinpapel_export_flujo\` / \`sinpapel_import_flujo\`.` |
| `pip install "git+ssh://git@github.com/aprendomx/sinpapel.git@…"` | Both lines | `pip install sinpapel` and `pip install "sinpapel==0.5.0"` |
| Comment `# ej. "creditos", "sep", "fondeso"` | Whole comment | `# ej. "mi_app", "solicitudes"` |
| `git clone git@github.com:aprendomx/sinpapel.git` | Whole line | `git clone <repository-url>` |
| Línea licencia footer mencionando `MIT` o `uso institucional` | Whole line | `**Licencia:** GPL-3.0-or-later (ver \`LICENSE\`). Sin garantía.` |
| `v0.4.0-alpha` | All occurrences | `v0.5.0` |

Verify:
```bash
grep -nE "SEP|FONDESO|aprendomx|creditos|E12|github\.com/jadrians" docs/USAGE.es.md
# Expected: no output
```

- [ ] **Step 3: Add navigation header**

Insert after the Tabla de Contenidos block:

```markdown
> **Navegación:** [README (panorama)](../README.es.md) · [CHANGELOG](../CHANGELOG.md) · [CONTRIBUTING](../CONTRIBUTING.md) · [English version](USAGE.md)
```

- [ ] **Step 4: Commit**

```bash
git add docs/USAGE.es.md
git commit -m "docs: move long-form ES manual to docs/USAGE.es.md"
```

---

## Task 4: Rewrite `README.md` (EN, concise)

**Files:**
- Replace: `README.md`

- [ ] **Step 1: Replace `README.md` with the concise version**

Overwrite `README.md` with the following content **exactly**:

````markdown
# sinpapel

> **v0.5.0** — Versioned state machines, immutable audit trail, and pluggable electronic signatures for Django.

[![PyPI](https://img.shields.io/pypi/v/sinpapel.svg)](https://pypi.org/project/sinpapel/)
[![Python](https://img.shields.io/pypi/pyversions/sinpapel.svg)](https://pypi.org/project/sinpapel/)
[![Django](https://img.shields.io/badge/django-5.0%20%7C%205.1-blue)](https://www.djangoproject.com/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-272%20passing-brightgreen)](#)

🇪🇸 [Leer en Español](README.es.md)

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

Drive a state transition through the engine:

```python
from sinpapel.services.workflow_engine import WorkflowEngine

engine = WorkflowEngine()

# Preview before committing (no mutation, returns impact report)
preview = engine.preview_transition(solicitud, "APROBADA", user=request.user)
if not preview["permitido"]:
    raise ValueError(preview["razones_bloqueo"][0]["mensaje"])

# Execute the transition (creates audit row + fires signals)
engine.cambiar_estado(solicitud, "APROBADA", user=request.user, comentarios="Cumple requisitos")
```

Subscribe to a custom signal:

```python
from django.dispatch import receiver
from sinpapel.signals import sla_breached

@receiver(sla_breached)
def on_sla_breach(sender, instance, sla, **kwargs):
    notify_team(instance, sla)
```

Full end-to-end examples, schema seeding, predicate cookbook, signing backend setup, and admin integration live in [`docs/USAGE.md`](docs/USAGE.md).

## What's Inside

| Subsystem | Module | Docs |
|---|---|---|
| Workflow Engine | `sinpapel.services.workflow_engine` | [USAGE §State Transitions](docs/USAGE.md#8-state-transitions) |
| Predicates | `sinpapel.services.predicate_engine` | [USAGE §Transition Predicates](docs/USAGE.md#9-transition-predicates) |
| Metadata | `sinpapel.mixins` | [USAGE §Metadata](docs/USAGE.md#10-structured-metadata-capture) |
| Forms Factory | `sinpapel.forms` | [USAGE §Forms](docs/USAGE.md#11-formserializer-factory) |
| Signing | `sinpapel.signing` | [USAGE §Signing](docs/USAGE.md#12-signing-backends) |
| Audit Trail | `sinpapel.models` + `sinpapel.mixins.Trazable` | [USAGE §Audit](docs/USAGE.md#13-audit-trail) |
| SLA Engine | `sinpapel.services.sla_engine` | [USAGE §SLA](docs/USAGE.md) |
| Custom Signals | `sinpapel.signals` | [USAGE §Signals](docs/USAGE.md) |
| Schema Export/Import | `sinpapel.schemas` + management commands | [USAGE §Schema](docs/USAGE.md) |

## Configuration

Optional Django settings:

```python
# settings.py
SINPAPEL_DEFAULT_SIGNATURE_BACKEND = "rsa_file"
SINPAPEL_RSA_PRIVATE_KEY_PATH = "/run/secrets/sinpapel.key"
SINPAPEL_RSA_PUBLIC_KEY_PATH = "/run/secrets/sinpapel.pub"
SINPAPEL_EMIT_PREVIEW_EVENTS = False  # set True to fire transition_preview_requested signal
```

See [USAGE §Settings](docs/USAGE.md#4-settings) for the full reference.

## Compatibility

| Python | Django |
|---|---|
| 3.10, 3.11, 3.12, 3.13 | 5.0, 5.1 |

CI runs the test suite across the full matrix.

## Documentation

- [Usage Guide](docs/USAGE.md) — full reference (EN)
- [Guía de Uso](docs/USAGE.es.md) — full reference (ES)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

## Versioning & Stability

sinpapel follows [Semantic Versioning](https://semver.org/). The current release is **v0.5.0 (Beta)**. Public APIs (`WorkflowEngine`, `PredicateEngine`, `SLAEngine`, signals, model fields, schema JSON v0.2) are stable in the 0.x series; breaking changes will bump the minor version and be flagged in `CHANGELOG.md` until 1.0.0.

## Contributing

Pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, commit conventions, and the Developer Certificate of Origin (DCO) sign-off requirement.

## License

Copyright (C) 2024-2026 Julio Adrián.

sinpapel is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

sinpapel is distributed in the hope that it will be useful, but **WITHOUT ANY WARRANTY**; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [GNU General Public License](LICENSE) for more details.
````

- [ ] **Step 2: Verify length and no institutional refs**

```bash
wc -l README.md
# Expected: ~180-220 lines
grep -nE "SEP|FONDESO|aprendomx|creditos|E12|jadrians/creditos" README.md
# Expected: no output
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README.md (EN) — concise, GPL-3.0, no institutional refs"
```

---

## Task 5: Rewrite `README.es.md` (ES mirror)

**Files:**
- Replace: `README.es.md`

- [ ] **Step 1: Replace `README.es.md` with the Spanish mirror**

Overwrite `README.es.md` with the following content **exactly**:

````markdown
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

Ejemplos end-to-end completos, seeding de schema, cookbook de predicados, setup de backends de firma e integración con admin viven en [`docs/USAGE.es.md`](docs/USAGE.es.md).

## Qué Incluye

| Subsistema | Módulo | Docs |
|---|---|---|
| Motor de Workflow | `sinpapel.services.workflow_engine` | [USAGE §Transiciones](docs/USAGE.es.md#8-transiciones-de-estado) |
| Predicados | `sinpapel.services.predicate_engine` | [USAGE §Predicados](docs/USAGE.es.md#9-predicados-de-transición) |
| Metadatos | `sinpapel.mixins` | [USAGE §Metadatos](docs/USAGE.es.md#10-captura-estructurada-de-metadatos) |
| Forms Factory | `sinpapel.forms` | [USAGE §Forms](docs/USAGE.es.md#11-formserializer-factory) |
| Firmas | `sinpapel.signing` | [USAGE §Firmas](docs/USAGE.es.md#12-backends-de-firma) |
| Auditoría | `sinpapel.models` + `sinpapel.mixins.Trazable` | [USAGE §Auditoría](docs/USAGE.es.md#13-pista-de-auditoría) |
| Motor SLA | `sinpapel.services.sla_engine` | [USAGE §SLA](docs/USAGE.es.md) |
| Signals Personalizados | `sinpapel.signals` | [USAGE §Signals](docs/USAGE.es.md) |
| Export/Import de Schema | `sinpapel.schemas` + management commands | [USAGE §Schema](docs/USAGE.es.md) |

## Configuración

Settings opcionales de Django:

```python
# settings.py
SINPAPEL_DEFAULT_SIGNATURE_BACKEND = "rsa_file"
SINPAPEL_RSA_PRIVATE_KEY_PATH = "/run/secrets/sinpapel.key"
SINPAPEL_RSA_PUBLIC_KEY_PATH = "/run/secrets/sinpapel.pub"
SINPAPEL_EMIT_PREVIEW_EVENTS = False  # poner True para disparar el signal transition_preview_requested
```

Ver [USAGE §Settings](docs/USAGE.es.md#4-settings) para la referencia completa.

## Compatibilidad

| Python | Django |
|---|---|
| 3.10, 3.11, 3.12, 3.13 | 5.0, 5.1 |

CI corre el suite de tests contra la matriz completa.

## Documentación

- [Guía de Uso](docs/USAGE.es.md) — referencia completa (ES)
- [Usage Guide](docs/USAGE.md) — referencia completa (EN)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Código de Conducta](CODE_OF_CONDUCT.md)

## Versionado y Estabilidad

sinpapel sigue [Semantic Versioning](https://semver.org/). La release actual es **v0.5.0 (Beta)**. Las APIs públicas (`WorkflowEngine`, `PredicateEngine`, `SLAEngine`, signals, campos de modelos, schema JSON v0.2) son estables en la serie 0.x; los breaking changes incrementarán el minor y serán marcados en `CHANGELOG.md` hasta 1.0.0.

## Contribuir

Los pull requests son bienvenidos. Por favor lee [CONTRIBUTING.md](CONTRIBUTING.md) para setup de desarrollo, convenciones de commits y el requisito de sign-off DCO (Developer Certificate of Origin).

## Licencia

Copyright (C) 2024-2026 Julio Adrián.

sinpapel es software libre: puedes redistribuirlo y/o modificarlo bajo los términos de la GNU General Public License publicada por la Free Software Foundation, ya sea la versión 3 de la Licencia, o (a tu elección) cualquier versión posterior.

sinpapel se distribuye con la esperanza de ser útil, pero **SIN NINGUNA GARANTÍA**; sin siquiera la garantía implícita de COMERCIABILIDAD o IDONEIDAD PARA UN PROPÓSITO PARTICULAR. Ver la [GNU General Public License](LICENSE) para más detalles.
````

- [ ] **Step 2: Verify length and no institutional refs**

```bash
wc -l README.es.md
# Expected: ~180-220 lines
grep -nE "SEP|FONDESO|aprendomx|creditos|E12|jadrians/creditos" README.es.md
# Expected: no output
```

- [ ] **Step 3: Commit**

```bash
git add README.es.md
git commit -m "docs: rewrite README.es.md (ES mirror) — concise, GPL-3.0"
```

---

## Task 6: Create `CHANGELOG.md` reconstructed from git log

**Files:**
- Create: `CHANGELOG.md`

- [ ] **Step 1: Generate the file with the following exact content**

Create `CHANGELOG.md` with this content:

````markdown
# Changelog

All notable changes to **sinpapel** are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] — 2026-05-14

### Added
- Four custom domain signals in `sinpapel.signals`: `predicate_failed`, `sla_breached`, `sla_action_executed`, `transition_preview_requested`.
- `predicate_failed` is fired by `WorkflowEngine` whenever a transition is rejected by a predicate.
- `sla_breached` and `sla_action_executed` are fired by `SLAEngine` when an SLA is exceeded and when an action runs against it.
- `transition_preview_requested` is opt-in via the `SINPAPEL_EMIT_PREVIEW_EVENTS` setting.

### Changed
- `WorkflowEngine.puede_cambiar_estado()` now records the failing predicate in addition to returning `(False, msg)`.

## [0.4.2] — 2026-05-14

### Fixed
- Prefix all sinpapel migration indexes with `sin_` to avoid naming collisions with downstream apps.

## [0.4.1] — 2026-05-14

### Fixed
- Packaging: remove `sinpapel.mixins` from the explicit `setuptools` packages list to prevent duplicate-module errors when installing in `--editable` mode.

## [0.4.0] — 2026-05-14

### Added
- **State Timers / SLA** subsystem:
  - `SLAConfiguracion` model linking time limits to states.
  - `SLAEngine` service with four action dispatchers: notify, escalate, reject, flag.
  - `sinpapel_verificar_slas` management command (supports `--dry-run`).
- **Preview Transitions**:
  - `WorkflowEngine.preview_transition()` simulates a transition without mutating state and returns an impact report (blocking reasons, missing documents, failing predicates, required approvers, recent history).
  - Internal validation logic extracted into `_validar_estado_destino`, `_validar_configuracion_transicion`, `_validar_grupos_permitidos`, `_validar_documentos`, `_validar_predicados` for reuse between `puede_cambiar_estado()` and `preview_transition()`.
- Schema export/import (`sinpapel_export_flujo` / `sinpapel_import_flujo`) now round-trips `CondicionTransicion` and `SLAConfiguracion`.

### Changed
- `puede_cambiar_estado()` now delegates to `preview_transition()` for back-compat.
- Error messages use `condicion.mensaje_error` as the primary value before falling back to the engine-supplied message.

## [0.3.0] — 2026-05-13

### Added
- **Transition Predicates** subsystem:
  - `CondicionTransicion` model storing per-transition predicates ordered by priority.
  - `PredicateEngine` with three backends: Python dotted-path callables, restricted JSON Logic, and Django ORM queries.
  - Restricted JSON Logic evaluator with a fixed operator allowlist.
  - Integration into `WorkflowEngine` so transitions can be rejected before mutating state.
- **Dynamic Forms / Serializers**:
  - `MetaFormFactory` generates Django Forms from a model's `SCHEMA_METADATOS` declaration.
  - DRF Serializer mode available through the same factory.

### Fixed
- Predicate evaluation handles missing variables in comparisons (returns False rather than raising).
- Integration test coverage for `MetaFormFactory` with `MetadatosCapturables`.

## [0.2.0] — 2026-05-12

### Added
- **Structured Metadata Capture**:
  - `CampoMetadato` dataclass for declaring schema fields (`tipo`, `requerido`, `default`, `choices`, validators).
  - `MetadatosProxy` runtime wrapper exposing `to_dict()` and validation.
  - `MetadatosCapturables` abstract model mixin that wires a JSONField + the proxy.
- Schema export/import management commands `sinpapel_export_flujo` and `sinpapel_import_flujo`, both supporting `--inline-catalogs` for fully self-contained workflow snapshots.
- CI matrix expanded across Python 3.10–3.13 × Django 5.0–5.1.

### Changed
- All model verbose names and labels wrapped in `gettext_lazy` for i18n.
- Schema JSON bumped to v0.2 with dual-version `validate` support.

### Fixed
- CI: install Pillow; switch to `python -m pytest` for deterministic `sys.path` resolution.

## [0.1.1] — Initial public alpha

### Added
- Versioned workflow engine: `VersionFlujo`, `Estado`, `ConfiguracionTransicion`, `WorkflowEngine`.
- Immutable audit trail: `Trazable` mixin, `SeguimientoWorkflow`, `RegistroFirma`.
- Pluggable signing backends: `SimuladoBackend`, `RSAFileBackend`, `FielBackend` (RSA-SHA256 + X.509).
- `django-simple-history` integration for full change history.
- PEP 561 `py.typed` marker for type-checker downstream consumers.

[Unreleased]: ../../compare/v0.5.0...HEAD
[0.5.0]: ../../compare/v0.4.2...v0.5.0
[0.4.2]: ../../compare/v0.4.1...v0.4.2
[0.4.1]: ../../compare/v0.4.0...v0.4.1
[0.4.0]: ../../compare/v0.1.1...v0.4.0
[0.3.0]: ../../releases/tag/v0.3.0
[0.2.0]: ../../releases/tag/v0.2.0
[0.1.1]: ../../releases/tag/v0.1.1
````

> **Note on compare links:** The trailing `../../compare/...` paths are intentionally relative so they resolve correctly under any repository host once the project URL is decided. Tags `v0.3.0` and `v0.2.0` referenced in the link section do not exist in this repo (intermediate releases were not tagged); the links act as stable anchors for any future re-tagging.

- [ ] **Step 2: Verify**

```bash
wc -l CHANGELOG.md
# Expected: ~95-110 lines
grep -c "^## \[" CHANGELOG.md
# Expected: 8 (Unreleased + 7 releases)
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add CHANGELOG.md (Keep a Changelog, v0.1.1 → v0.5.0)"
```

---

## Task 7: Create `CONTRIBUTING.md`

**Files:**
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Generate the file with this exact content**

Create `CONTRIBUTING.md`:

````markdown
# Contributing to sinpapel

Thanks for your interest in contributing! This document describes the development
workflow and the expectations for pull requests.

## Code of Conduct

This project adopts the [Contributor Covenant 2.1](CODE_OF_CONDUCT.md). By
participating you agree to abide by its terms.

## Development Setup

```bash
git clone <repository-url>
cd sinpapel

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

Run the test suite:

```bash
python -m pytest tests/ -q
```

The suite must remain green before any pull request is merged. Current
baseline: **272 passing tests**.

## Development Workflow

1. Create a feature branch off `main`:
   ```bash
   git checkout -b feat/<short-description>
   ```
2. Make focused commits. Use [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` new feature
   - `fix:` bug fix
   - `refactor:` code change that neither fixes a bug nor adds a feature
   - `docs:` documentation only
   - `test:` adding or correcting tests
   - `chore:` tooling, build, CI
   - `ci:` CI configuration only
3. Run the test suite locally before pushing.
4. Open a pull request against `main` with a clear description and a reference
   to any related issue.

## Sign Your Work (DCO)

We use the [Developer Certificate of Origin](https://developercertificate.org/)
instead of a CLA. Every commit must be signed off:

```bash
git commit -s -m "feat: add ..."
```

Sign-off adds the line `Signed-off-by: Your Name <you@example.com>` to the
commit message. By signing off, you certify that you have the right to
contribute the change under the project license (GPL-3.0-or-later).

## Pull Request Checklist

- [ ] Tests pass locally (`python -m pytest tests/ -q`).
- [ ] New behavior covered by tests.
- [ ] `CHANGELOG.md` updated under `## [Unreleased]` when the change is
      user-visible.
- [ ] Commits follow Conventional Commits and are signed off (`-s`).
- [ ] Documentation (`docs/USAGE.md` and `docs/USAGE.es.md`) updated when
      public APIs or settings change.
- [ ] No institutional or third-party trademark references introduced
      anywhere in the codebase, README, or docs.

## Reporting Bugs

Open an issue against the project repository. Include:

- sinpapel version (`python -c "import sinpapel; print(sinpapel.__version__)"`).
- Python and Django versions.
- A minimal reproduction (model definition + the failing call).
- The full traceback.

## Reporting Security Vulnerabilities

Please **do not** open a public issue for security reports. Email
`jadrian.s@gmail.com` privately with a description and reproduction steps. You
will receive an acknowledgement within seven days.

## License

By contributing, you agree that your contributions will be licensed under the
GNU General Public License v3.0 or later, the same license as the rest of the
project.
````

- [ ] **Step 2: Verify**

```bash
wc -l CONTRIBUTING.md
# Expected: ~90-105 lines
```

- [ ] **Step 3: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: add CONTRIBUTING.md (Conventional Commits + DCO)"
```

---

## Task 8: Create `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1)

**Files:**
- Create: `CODE_OF_CONDUCT.md`

- [ ] **Step 1: Download the canonical Contributor Covenant 2.1 text**

Run:
```bash
curl -fsSL https://www.contributor-covenant.org/version/2/1/code_of_conduct.txt -o CODE_OF_CONDUCT.tmp
wc -l CODE_OF_CONDUCT.tmp  # expect ~130 lines
```

- [ ] **Step 2: Replace the contact placeholder**

The canonical text contains the placeholder string `[INSERT CONTACT METHOD]`. Replace it with the project contact email `jadrian.s@gmail.com`:

```bash
sed -i.bak 's/\[INSERT CONTACT METHOD\]/jadrian.s@gmail.com/g' CODE_OF_CONDUCT.tmp
rm CODE_OF_CONDUCT.tmp.bak
```

- [ ] **Step 3: Wrap as Markdown and finalize**

The downloaded `.txt` is plain text. Convert to Markdown by adding a top-level heading and saving as `CODE_OF_CONDUCT.md`:

```bash
{
  echo "# Code of Conduct"
  echo ""
  cat CODE_OF_CONDUCT.tmp
} > CODE_OF_CONDUCT.md
rm CODE_OF_CONDUCT.tmp
```

- [ ] **Step 4: Verify**

```bash
head -1 CODE_OF_CONDUCT.md           # Expected: "# Code of Conduct"
grep -c "Contributor Covenant" CODE_OF_CONDUCT.md   # Expected: ≥ 2
grep -c "jadrian.s@gmail.com" CODE_OF_CONDUCT.md    # Expected: ≥ 1
grep "INSERT CONTACT METHOD" CODE_OF_CONDUCT.md     # Expected: no output
```

- [ ] **Step 5: Commit**

```bash
git add CODE_OF_CONDUCT.md
git commit -m "docs: add CODE_OF_CONDUCT.md (Contributor Covenant 2.1)"
```

---

## Task 9: Update `pyproject.toml` for GPL-3.0 + PyPI readiness

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Replace the file with the updated metadata**

Overwrite `pyproject.toml` with this content **exactly** (the `[tool.setuptools]` block is preserved verbatim from the existing file because the flat layout is correct):

```toml
[project]
name = "sinpapel"
version = "0.5.0"
description = "Versioned workflows, immutable audit, and pluggable e-signatures for Django."
readme = "README.md"
requires-python = ">=3.10"
license = "GPL-3.0-or-later"
license-files = ["LICENSE"]
authors = [
    { name = "Julio Adrián", email = "jadrian.s@gmail.com" },
]
keywords = [
    "django",
    "workflow",
    "state-machine",
    "audit-trail",
    "electronic-signature",
    "compliance",
    "paperless",
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Framework :: Django",
    "Framework :: Django :: 5.0",
    "Framework :: Django :: 5.1",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Office/Business :: Groupware",
    "Topic :: Software Development :: Libraries :: Python Modules",
]
dependencies = [
    "Django>=5.0",
    "django-simple-history>=3.5",
    "cryptography>=42.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0",
    "pytest-django>=4.12",
    "build>=1.2",
    "twine>=5.0",
]

# URLs intentionally omitted until a public repo URL is decided.
# Before the first PyPI publish, uncomment and fill in:
# [project.urls]
# Homepage  = "https://example.com/sinpapel"
# Source    = "https://example.com/sinpapel"
# Issues    = "https://example.com/sinpapel/issues"
# Changelog = "https://example.com/sinpapel/blob/main/CHANGELOG.md"

[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

# Layout: flat — pyproject.toml + package files at repo root.
# package_dir maps the package "sinpapel" to the current working directory (.).
# Subpackages are declared explicitly (deterministic + visible).
[tool.setuptools]
packages = [
    "sinpapel",
    "sinpapel.management",
    "sinpapel.management.commands",
    "sinpapel.migrations",
    "sinpapel.mixins",
    "sinpapel.models",
    "sinpapel.schemas",
    "sinpapel.services",
    "sinpapel.signing",
    "sinpapel.signing.backends",
]

[tool.setuptools.package-dir]
sinpapel = "."
"sinpapel.management" = "management"
"sinpapel.management.commands" = "management/commands"
"sinpapel.migrations" = "migrations"
"sinpapel.mixins" = "."
"sinpapel.models" = "models"
"sinpapel.schemas" = "schemas"
"sinpapel.services" = "services"
"sinpapel.signing" = "signing"
"sinpapel.signing.backends" = "signing/backends"

[tool.setuptools.package-data]
sinpapel = ["py.typed"]
"sinpapel.migrations" = ["*.py"]
```

- [ ] **Step 2: Verify the file is valid TOML and the metadata is correct**

Run:
```bash
/usr/local/bin/python3.13 -c "import tomllib; data=tomllib.loads(open('pyproject.toml').read()); print(data['project']['license']); print(data['project']['version'])"
# Expected output:
# GPL-3.0-or-later
# 0.5.0
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: relicense to GPL-3.0-or-later (SPDX), PyPI-ready metadata"
```

---

## Task 10: Verification + final cleanup commit

**Files:** No code files modified. This task validates the previous nine commits.

- [ ] **Step 1: Run the test suite**

```bash
/usr/local/bin/python3.13 -m pytest tests/ -q
```

Expected: **272 passed**. If any test fails, stop and fix before continuing.

- [ ] **Step 2: Build a wheel + sdist**

```bash
rm -rf dist/ build/ *.egg-info
/usr/local/bin/python3.13 -m pip install --quiet --upgrade build twine
/usr/local/bin/python3.13 -m build
```

Expected: `dist/sinpapel-0.5.0-py3-none-any.whl` and `dist/sinpapel-0.5.0.tar.gz` produced without errors.

- [ ] **Step 3: Run `twine check`**

```bash
/usr/local/bin/python3.13 -m twine check dist/*
```

Expected: `PASSED` for both files. If `twine check` flags the README rendering, fix and rerun.

- [ ] **Step 4: Verify license metadata in the built wheel**

```bash
/usr/local/bin/python3.13 -m zipfile -e dist/sinpapel-0.5.0-py3-none-any.whl /tmp/sinpapel-wheel-inspect
grep -E "^License-Expression:" /tmp/sinpapel-wheel-inspect/sinpapel-0.5.0.dist-info/METADATA
# Expected: License-Expression: GPL-3.0-or-later
ls /tmp/sinpapel-wheel-inspect/sinpapel-0.5.0.dist-info/licenses/
# Expected: LICENSE
rm -rf /tmp/sinpapel-wheel-inspect
```

- [ ] **Step 5: Confirm institutional references are gone from public-facing files**

```bash
grep -nE "SEP|FONDESO|aprendomx|creditos|E12|jadrians/creditos" \
  README.md README.es.md CHANGELOG.md CONTRIBUTING.md CODE_OF_CONDUCT.md pyproject.toml
# Expected: no output
```

(`docs/USAGE.md`, `docs/USAGE.es.md` are scanned in their respective tasks and should already be clean.)

- [ ] **Step 6: Add `dist/` to `.gitignore` if not already present**

```bash
grep -qxF "dist/" .gitignore || echo "dist/" >> .gitignore
grep -qxF "build/" .gitignore || echo "build/" >> .gitignore
grep -qxF "*.egg-info/" .gitignore || echo "*.egg-info/" >> .gitignore
```

- [ ] **Step 7: Clean up build artifacts before committing**

```bash
rm -rf dist/ build/ *.egg-info
```

- [ ] **Step 8: Final commit if `.gitignore` changed**

```bash
git status --short
# If .gitignore changed:
git add .gitignore
git commit -m "chore: ignore build artifacts (dist/, build/, *.egg-info/)"
```

- [ ] **Step 9: Push**

```bash
git push origin main
```

---

## Self-Review

**1. Spec coverage:**
- [x] GPL-3.0 LICENSE → Task 1
- [x] README.md rewrite (concise, ~350 lines target) → Task 4 (actual ~200 lines, under target ✓)
- [x] README.es.md mirror → Task 5
- [x] Long-form manual moved to docs/USAGE.md (+ ES) → Tasks 2, 3
- [x] CHANGELOG.md reconstructed from git log → Task 6
- [x] CONTRIBUTING.md with DCO → Task 7
- [x] CODE_OF_CONDUCT.md (Contributor Covenant 2.1) → Task 8
- [x] pyproject.toml GPL + PyPI-ready (SPDX, classifiers, setuptools≥77) → Task 9
- [x] Verification (pytest, build, twine check, grep) → Task 10
- [x] No public repo URL hardcoded (uses placeholders / generic phrasing) → Tasks 4, 5, 7, 9

**2. Placeholder scan:** No "TBD", "TODO", or "implement later" in any task. The only deliberate placeholders are `<repository-url>` in CONTRIBUTING.md and the commented `https://example.com/sinpapel` template in pyproject.toml, both flagged as deliberate in the spec.

**3. Type consistency:** Filenames (`USAGE.md`, `USAGE.es.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `LICENSE`, `pyproject.toml`) are consistent across all tasks. Cross-links between README and CHANGELOG/CONTRIBUTING/CODE_OF_CONDUCT match. Version `0.5.0` consistent across LICENSE header, README headers, CHANGELOG, pyproject.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-16-readme-publication.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
