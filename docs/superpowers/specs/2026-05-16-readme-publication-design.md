# Public README + Publication Materials — Design Spec

**Date:** 2026-05-16
**Topic:** Rewrite README + add publication-ready materials for sinpapel v0.5.0
**Status:** Approved (pending user review)

---

## 1. Goals

Produce a public-facing, de-institutionalized identity for **sinpapel** that is ready to publish on PyPI and GitHub under **GPL-3.0-or-later**.

Specifically:

1. Replace MIT license with GPL-3.0-or-later end-to-end (LICENSE, `pyproject.toml`, README footer, classifier).
2. Rewrite both READMEs (EN + ES) with a concise structure (~350 lines each) and move the existing 900-line manual to `docs/USAGE.md` (+ `docs/USAGE.es.md`).
3. Strip all institutional references (SEP, FONDESO, aprendomx, "creditos/E12", `aprendomx/sinpapel-designer`, references that imply a specific public-sector target).
4. Add publication materials: `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`.
5. Make `pyproject.toml` PyPI-ready (correct license metadata, valid classifiers, project URLs left empty/placeholder until a public repo URL is decided, build/distribution metadata).
6. Do **not** introduce a public repository URL anywhere. Where a URL is required by tooling, leave the field empty or use a clearly marked placeholder (`https://example.com/sinpapel`) the user can swap before the first publish.

Non-goals (out of scope for this spec):

- Renaming any code, removing the `FielBackend` implementation, or changing supported signing backends. `FielBackend` stays as a reference backend; its docs describe it generically ("RSA-SHA256 + X.509 backend, reference implementation included") without anchoring it to a specific country/issuer in the README.
- Adding new features.
- Publishing to PyPI (the spec leaves the package ready; the actual `twine upload` is the user's call).

---

## 2. Tagline & Positioning

**Tagline (EN):** Versioned state machines, immutable audit trail, and pluggable electronic signatures for Django.

**Tagline (ES):** Máquinas de estado versionadas, auditoría inmutable y firmas electrónicas plugables para Django.

**Why sinpapel? (1-paragraph pitch):**

> Building paperless processes in Django usually means stitching together a state-machine library, an audit framework, a signing layer, and a forms toolkit. sinpapel ships them as one coherent package: declarative versioned workflows, immutable history, pluggable e-signature backends, schema-based metadata capture, transition predicates, SLA timers, and custom domain signals — designed to be adopted incrementally in any Django 5+ project.

---

## 3. File Plan

| File | Action | Notes |
|---|---|---|
| `LICENSE` | Replace | Full GPL-3.0 text from gnu.org canonical version. Copyright line: `Copyright (C) 2024-2026 Julio Adrián <jadrian.s@gmail.com>`. |
| `README.md` | Rewrite | ~350 lines, EN, concise structure (see §4). |
| `README.es.md` | Rewrite | Mirror of README.md in ES. Same anchors. |
| `CHANGELOG.md` | Create | Keep a Changelog 1.1.0 format. Entries reconstructed from `git log` (v0.1.0 → v0.5.0). One file (EN headings, content bilingual is over-engineering for a CHANGELOG). |
| `CONTRIBUTING.md` | Create | EN. Setup, tests, conventional commits, PR flow, DCO (no CLA). |
| `CODE_OF_CONDUCT.md` | Create | Contributor Covenant 2.1, EN, contact = `jadrian.s@gmail.com`. |
| `docs/USAGE.md` | Create | Manual extenso movido desde README actual (EN). |
| `docs/USAGE.es.md` | Create | Mirror in ES (from README.es.md). |
| `pyproject.toml` | Edit | License → GPL-3.0-or-later (SPDX), classifier swap, description update, keywords genericized, URLs cleared/placeheld. |
| `__init__.py` | Verify | `__version__` already `0.5.0`. No change. |

---

## 4. README Structure (both EN and ES, mirrored)

Section headings & target line budget:

```
1. Tagline + 5 badges + 2-sentence intro                            (~15 lines)
2. Why sinpapel?                                                    (~10 lines)
3. Features                                                         (~30 lines)
4. Installation                                                     (~15 lines)
5. Quick Start (one end-to-end example, <50 lines of code)          (~70 lines)
6. What's inside (subsystem map → links to docs/USAGE.md anchors)   (~40 lines)
7. Configuration (essential settings only)                          (~25 lines)
8. Compatibility (Python × Django matrix)                           (~15 lines)
9. Documentation (links to USAGE, CHANGELOG, CONTRIBUTING)          (~10 lines)
10. Versioning & Stability (SemVer, current alpha/beta/stable)      (~15 lines)
11. Contributing                                                    (~10 lines)
12. License (GPL-3.0-or-later notice + disclaimer)                  (~15 lines)
                                                                     ─────────
                                                              total ~270 lines
```

Total budget includes blank lines, headings, code fences. Target ~350 lines max.

**Subsystems listed in §3 Features** (with one-liner each):

- **Workflow Engine** — versioned state machines via `VersionFlujo` + `ConfiguracionTransicion`
- **Transition Predicates** — Python paths, JSON Logic, and Django-ORM predicates per transition
- **Structured Metadata** — `MetadatosCapturables` mixin with schema-declared `CampoMetadato` fields
- **Dynamic Forms & Serializers** — `MetaFormFactory` generates Django forms from metadata schema
- **Pluggable Signing Backends** — strategy interface + reference backends (`SimuladoBackend`, `RSAFileBackend`, `FielBackend`)
- **Immutable Audit Trail** — `Trazable` mixin + `SeguimientoWorkflow` + `RegistroFirma` + `django-simple-history`
- **SLA Timers & Preview Transitions** — `SLAEngine` with 4 action dispatchers; `WorkflowEngine.preview_transition()`
- **Custom Domain Signals** — `predicate_failed`, `sla_breached`, `sla_action_executed`, `transition_preview_requested`

**Badges (top of README):**

```markdown
[![PyPI](https://img.shields.io/pypi/v/sinpapel.svg)](https://pypi.org/project/sinpapel/)
[![Python](https://img.shields.io/pypi/pyversions/sinpapel.svg)](https://pypi.org/project/sinpapel/)
[![Django](https://img.shields.io/badge/django-5.0%20%7C%205.1-blue)](https://www.djangoproject.com/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-272%20passing-brightgreen)](#)
```

Badges that depend on a public repo URL (CI, Codecov) are intentionally omitted until that URL exists.

---

## 5. De-institutionalization Rules

**Remove or rewrite every occurrence of:**

| Reference | Action |
|---|---|
| SEP, FONDESO, "instituciones gubernamentales" | Remove |
| "Extracted from creditos (E12)" / "Extraído desde creditos" | Remove |
| `github.com/aprendomx/sinpapel` URLs (clone, install, issues) | Replace with placeholder or generic `pip install sinpapel` |
| `aprendomx/sinpapel-designer` companion app callouts | Remove from README; can stay in `docs/USAGE.md` as a one-line "Optional visual designer (external tool)" without URL |
| "Mexico SAT FIEL" specifics in the README | In README: rephrase to "`FielBackend` — RSA-SHA256 + X.509 reference backend"; full SAT/FIEL technical detail stays in `docs/USAGE.md` (it's accurate documentation, not institutional positioning) |
| Spanish institutional examples (`"sep"`, `"fondeso"` in code samples) | Replace with neutral names (`"my_app"`, `"requests"`) |

**Keep:**

- Author name and email (Julio Adrián).
- `FielBackend` code and its technical documentation (this is a feature, not branding).
- Spanish translations of error messages / model verbose names (this is i18n, not institutional anchoring).

---

## 6. `pyproject.toml` Changes

```toml
[project]
name = "sinpapel"
version = "0.5.0"
description = "Versioned workflows, immutable audit, and pluggable e-signatures for Django."
readme = "README.md"
requires-python = ">=3.10"
license = "GPL-3.0-or-later"           # PEP 639 SPDX expression
license-files = ["LICENSE"]
authors = [
    { name = "Julio Adrián", email = "jadrian.s@gmail.com" },
]
keywords = [
    "django", "workflow", "state-machine", "audit-trail",
    "electronic-signature", "compliance", "paperless",
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

[project.optional-dependencies]
dev = ["pytest>=9.0", "pytest-django>=4.12", "build>=1.2", "twine>=5.0"]

# URLs intentionally omitted until a public repo URL is decided.
# Before the first PyPI publish, add:
# [project.urls]
# Homepage = "https://<your-org>.example/sinpapel"
# Source   = "https://github.com/<your-org>/sinpapel"
# Issues   = "https://github.com/<your-org>/sinpapel/issues"
# Changelog = "https://github.com/<your-org>/sinpapel/blob/main/CHANGELOG.md"
```

Changes vs current:

- `license` → SPDX expression `GPL-3.0-or-later` (PEP 639); old `{ text = "MIT" }` removed.
- `license-files` added (PEP 639) so `LICENSE` ships in the sdist + wheel.
- `description` rewritten (no "extraído desde creditos").
- `classifiers`: MIT → GPLv3+; status bumped 3-Alpha → 4-Beta; added Django 5.1, Groupware topic.
- `keywords`: removed `fiel`, `tramites` (institutional); added neutral terms.
- `[project.urls]` removed entirely; restored as commented-out template.
- `dev` extras include `build` + `twine` so a contributor can produce dist artifacts.

`[tool.setuptools]` block stays as-is (flat layout works).

---

## 7. CHANGELOG Reconstruction Strategy

`CHANGELOG.md` will follow Keep a Changelog 1.1.0:

```
## [Unreleased]

## [0.5.0] — 2026-05-14
### Added
- ...

## [0.4.2] — ...
...
```

Tags present in repo: `v0.1.1`, `v0.4.0`, `v0.4.1`, `v0.4.2`, `v0.5.0`. Plus pre-tag history (s27.2-complete, s27.3-complete) which gets a single "Initial Releases" entry under `[0.1.0]` or `[0.1.1]`.

Reconstruction approach: read `git log <prev-tag>..<tag>` for each pair, classify commits by Conventional Commit prefix (`feat:` → Added, `fix:` → Fixed, `refactor:` → Changed, `docs:` → not included unless major, `test:`/`chore:`/`ci:` → omitted). One bullet per commit, grouped, summarized in English. Total CHANGELOG target: 150–250 lines.

---

## 8. CONTRIBUTING.md Outline

```
# Contributing to sinpapel

## Code of Conduct
## Development Setup
  - Clone, venv, editable install with dev extras
  - Run tests: pytest tests/ -q
## Development Workflow
  - Branch naming
  - Conventional Commits (feat, fix, refactor, docs, test, chore, ci)
  - Run linters / tests before pushing
## Pull Request Process
  - Open against main
  - Pass CI
  - At least one review
## Signing your work (DCO)
  - git commit -s
  - https://developercertificate.org/
## Reporting Bugs
  - Use GitHub issues (link omitted until repo URL exists)
## Reporting Security Vulnerabilities
  - Email jadrian.s@gmail.com privately; do not file a public issue
```

Target ~100 lines.

---

## 9. CODE_OF_CONDUCT.md

Verbatim **Contributor Covenant v2.1** (https://www.contributor-covenant.org/version/2/1/code_of_conduct/). Contact = `jadrian.s@gmail.com`. ~130 lines.

---

## 10. Verification

After all files are written:

1. `python -m pytest tests/ -q` — still 272 passing.
2. `python -m build` — builds wheel + sdist without errors (requires `build` from dev extras).
3. `python -m twine check dist/*` — passes metadata check.
4. `grep -nri -E "sep|fondeso|aprendomx|creditos|E12" README.md README.es.md` — zero matches except in `docs/USAGE.md` (technical context allowed) and CHANGELOG (historical commit titles).
5. `head -1 LICENSE` — reads `GNU GENERAL PUBLIC LICENSE`.

---

## 11. Open Risks

- **PEP 639 license-files**: Requires `setuptools>=77` to be reliably honored. Current build-system requires `setuptools>=68`. Bump to `setuptools>=77` in `[build-system]` to be safe.
- **`Development Status` bump to Beta**: v0.5.0 has 272 passing tests and stable signals API, so Beta is justified. If the user prefers to stay Alpha until the first PyPI release lands, easy to revert.
- **No repo URL** means PyPI listing will show no project URLs initially. PyPI accepts this, but the listing is less useful for adopters. The user must edit `[project.urls]` before first publish.
