# MkDocs Documentation Site — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up a MkDocs site with the Material theme to publish sinpapel documentation (README content, USAGE guides, API reference) and add a GitHub Action to deploy it automatically on every push to main.

**Architecture:** Add `mkdocs` and `mkdocs-material` as optional dev dependencies. Create a `mkdocs.yml` at repo root pointing to a `docs/` source directory. Restructure existing `docs/` to have a `docs/index.md` landing page and `docs/usage/` subfolder. Add a `docs/api/` section with module docstrings rendered via `mkdocstrings`. Add a GitHub Pages deploy workflow.

**Tech Stack:** MkDocs, Material for MkDocs, mkdocstrings (Python), GitHub Actions

---

## File Structure

| File | Action | Purpose |
|---|---|---|
| `pyproject.toml` | Modify | Add `[project.optional-dependencies] docs = ["mkdocs>=1.6", "mkdocs-material>=9.5", "mkdocstrings[python]>=0.25"]` |
| `mkdocs.yml` | Create | MkDocs configuration with Material theme, navigation, plugins |
| `docs/index.md` | Create | Landing page — sinpapel overview + quick start |
| `docs/usage/index.md` | Create | Table of contents for usage guides |
| `docs/usage/en.md` | Move + modify | Move `docs/USAGE.md` → `docs/usage/en.md`, fix internal links |
| `docs/usage/es.md` | Move + modify | Move `docs/USAGE.es.md` → `docs/usage/es.md`, fix internal links |
| `docs/api/index.md` | Create | API reference landing page |
| `docs/development/contributing.md` | Move + modify | Move `CONTRIBUTING.md` → `docs/development/contributing.md` |
| `docs/development/changelog.md` | Move + modify | Move `CHANGELOG.md` → `docs/development/changelog.md` |
| `docs/development/security.md` | Move + modify | Move `SECURITY.md` → `docs/development/security.md` |
| `.github/workflows/docs.yml` | Create | Build + deploy MkDocs to GitHub Pages on push to main |

---

### Task 1: Add MkDocs dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add docs optional dependencies**

Append a new section after `[project.optional-dependencies] dev`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=9.0",
    "pytest-django>=4.12",
    "build>=1.2",
    "twine>=5.0",
]
docs = [
    "mkdocs>=1.6",
    "mkdocs-material>=9.5",
    "mkdocstrings[python]>=0.25",
]
```

- [ ] **Step 2: Verify the file syntax**

Run: `python3 -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('TOML OK')"`
Expected: `TOML OK`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add mkdocs dependencies for documentation site"
```

---

### Task 2: Create MkDocs configuration file

**Files:**
- Create: `mkdocs.yml`

- [ ] **Step 1: Write mkdocs.yml**

```yaml
site_name: sinpapel
site_description: "Versioned workflows, immutable audit, and pluggable e-signatures for Django"
site_url: "https://jadrian.github.io/sinpapel"
repo_url: "https://github.com/jadrian/sinpapel"
repo_name: jadrian/sinpapel
edit_uri: edit/main/docs/

theme:
  name: material
  palette:
    - scheme: default
      primary: teal
      accent: teal
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: teal
      accent: teal
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - search.suggest
    - search.highlight
    - content.code.copy

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          paths: [.]
          options:
            docstring_style: google
            show_source: true
            show_root_heading: true

nav:
  - Home: index.md
  - Usage:
      - usage/index.md
      - English: usage/en.md
      - Español: usage/es.md
  - API Reference:
      - api/index.md
  - Development:
      - development/contributing.md
      - development/changelog.md
      - development/security.md

markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - pymdownx.superfences
  - admonition
  - pymdownx.details
  - pymdownx.tabbed:
      alternate_style: true
  - tables
  - toc:
      permalink: true

extra:
  version:
    provider: mike

watch:
  - sinpapel
```

- [ ] **Step 2: Verify YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('mkdocs.yml')); print('YAML OK')"`
Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add mkdocs.yml
git commit -m "docs: add mkdocs configuration with material theme"
```

---

### Task 3: Create landing page docs/index.md

**Files:**
- Create: `docs/index.md`

- [ ] **Step 1: Write docs/index.md**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/index.md
git commit -m "docs: add mkdocs landing page"
```

---

### Task 4: Move USAGE guides and create usage index

**Files:**
- Move: `docs/USAGE.md` → `docs/usage/en.md`
- Move: `docs/USAGE.es.md` → `docs/usage/es.md`
- Create: `docs/usage/index.md`

- [ ] **Step 1: Create docs/usage/index.md**

```markdown
# Usage Guides

Select your language:

- [English](en.md)
- [Español](es.md)
```

- [ ] **Step 2: Move existing USAGE files**

```bash
git mv docs/USAGE.md docs/usage/en.md
git mv docs/USAGE.es.md docs/usage/es.md
```

- [ ] **Step 3: Commit**

```bash
git add docs/usage/
git commit -m "docs: reorganize usage guides into docs/usage/"
```

---

### Task 5: Move development docs and create development section

**Files:**
- Move: `CONTRIBUTING.md` → `docs/development/contributing.md`
- Move: `CHANGELOG.md` → `docs/development/changelog.md`
- Move: `SECURITY.md` → `docs/development/security.md`
- Create: `docs/development/index.md`

- [ ] **Step 1: Create docs/development/index.md**

```markdown
# Development

- [Contributing](contributing.md)
- [Changelog](changelog.md)
- [Security Policy](security.md)
```

- [ ] **Step 2: Move existing files**

```bash
git mv CONTRIBUTING.md docs/development/contributing.md
git mv CHANGELOG.md docs/development/changelog.md
git mv SECURITY.md docs/development/security.md
```

- [ ] **Step 3: Commit**

```bash
git add docs/development/
git commit -m "docs: move contributing, changelog, and security into docs/development"
```

---

### Task 6: Create API reference landing page

**Files:**
- Create: `docs/api/index.md`

- [ ] **Step 1: Write docs/api/index.md**

```markdown
# API Reference

## sinpapel.decorators

::: sinpapel.decorators

## sinpapel.exceptions

::: sinpapel.exceptions

## sinpapel.registry

::: sinpapel.registry

## sinpapel.services.workflow_engine

::: sinpapel.services.workflow_engine

## sinpapel.services.predicate_engine

::: sinpapel.services.predicate_engine

## sinpapel.services.sla_engine

::: sinpapel.services.sla_engine

## sinpapel.mixins

::: sinpapel.mixins

## sinpapel.signing

::: sinpapel.signing
```

- [ ] **Step 2: Commit**

```bash
git add docs/api/
git commit -m "docs: add API reference landing page with mkdocstrings"
```

---

### Task 7: Create GitHub Action for MkDocs deploy

**Files:**
- Create: `.github/workflows/docs.yml`

- [ ] **Step 1: Write .github/workflows/docs.yml**

```yaml
name: Deploy Docs

on:
  push:
    branches: [main, master]
    paths:
      - "docs/**"
      - "mkdocs.yml"
      - "sinpapel/**"

permissions:
  contents: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[docs]"

      - name: Deploy to GitHub Pages
        run: mkdocs gh-deploy --force
```

- [ ] **Step 2: Verify YAML syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/docs.yml')); print('YAML OK')"`
Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/docs.yml
git commit -m "ci: add GitHub Action to deploy MkDocs to GitHub Pages"
```

---

### Task 8: Build docs locally and verify

**Files:**
- (No file changes)

- [ ] **Step 1: Install docs dependencies**

```bash
source .venv/bin/activate
pip install -e ".[docs]"
```

- [ ] **Step 2: Build the site locally**

```bash
mkdocs build
```

Expected: `site/` directory created with `index.html`, no errors.

- [ ] **Step 3: Serve locally (optional, smoke test)**

```bash
mkdocs serve &
# Wait 3 seconds, then kill the background job
sleep 3
kill %1 2>/dev/null || true
```

Expected: `INFO     -  [macros] - ...` and `Serving on http://127.0.0.1:8000/`

- [ ] **Step 4: Clean up build artifacts (do not commit site/)**

```bash
rm -rf site/
```

- [ ] **Step 5: No commit needed for this task (verification only)**

---

### Task 9: Update README links

**Files:**
- Modify: `README.md`
- Modify: `README.es.md`

- [ ] **Step 1: Fix links in README.md**

Replace references to `docs/USAGE.md` and `docs/USAGE.es.md` with the new paths, or remove them if they are now redundant with the docs site.

In `README.md`, change:
```
[`docs/USAGE.md`](docs/USAGE.md)
```
to:
```
[Usage Guide](https://jadrian.github.io/sinpapel/usage/en/)
```

And similarly for `README.es.md` pointing to the Spanish guide.

Also update the Documentation section to point to the live site instead of local paths:

```markdown
## Documentation

- [Documentation Site](https://jadrian.github.io/sinpapel/)
- [Usage Guide (EN)](https://jadrian.github.io/sinpapel/usage/en/)
- [Guía de Uso (ES)](https://jadrian.github.io/sinpapel/usage/es/)
- [Changelog](https://jadrian.github.io/sinpapel/development/changelog/)
- [Contributing](https://jadrian.github.io/sinpapel/development/contributing/)
- [Code of Conduct](CODE_OF_CONDUCT.md)
```

Do the equivalent in `README.es.md`.

- [ ] **Step 2: Commit**

```bash
git add README.md README.es.md
git commit -m "docs: update README links to point to MkDocs site"
```

---

## Self-Review Checklist

1. **Spec coverage:** All tasks map to adding MkDocs + Material theme, reorganizing docs, adding API reference, and deploying to GitHub Pages.
2. **Placeholder scan:** No TBDs, TODOs, or vague instructions. Every step has exact content.
3. **Type consistency:** No new code types introduced — this is purely documentation/tooling.
4. **No runtime code changes:** Tasks 1–9 touch only docs, CI, and README.
5. **Link integrity:** README links updated to point to GitHub Pages URLs. Internal mkdocs nav matches file paths.
6. **Backward compatibility:** Original `docs/USAGE.md` and `docs/USAGE.es.md` content is preserved (just moved). `CONTRIBUTING.md`, `CHANGELOG.md`, `SECURITY.md` are preserved (just moved).
