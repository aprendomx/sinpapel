# Changelog

All notable changes to **sinpapel** are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] — 2026-06-25

### Added
- **Enforce de requisitos documentales finos en las transiciones.** El motor
  (`WorkflowEngine._validar_documentos`) ahora evalúa las reglas de
  `RequisitoEstadoDocumento` (tipo de documento + porcentaje mínimo) sobre el
  estado actual, además del flag coarse `Estado.expediente_obligatorio`. Un
  requisito no satisfecho bloquea `preview_transition()`
  (en `documentos_faltantes` / `razones_bloqueo`), `puede_cambiar_estado()` y
  `cambiar_estado()` (→ `PermissionError`). Las reglas se leen vía el cache
  `get_requisitos_for()` (invalidado por signal). Cada faltante se reporta como
  `{"tipo": "requisito_documento", "tipo_documento", "porcentaje_requerido",
  "porcentaje_actual", "mensaje"}`. La fuente de "documento presente por tipo"
  es `InstanciaDocumento` (liga el tipo vía `documento.tipo_documento` y la
  instancia vía la GFK `target`). Requisitos con `auto_carga=True` (documento
  generado por el sistema) **no** bloquean.
- Campo `InstanciaDocumento.porcentaje` (`IntegerField`, `0–100`, `default=100`)
  como origen del porcentaje real de completitud por documento. Migración
  reversible `0004_historicalinstanciadocumento_porcentaje_and_more`. El default
  100 hace que las filas existentes cuenten como documento completo
  (backward-compatible).
- `@workflow_enabled` ahora inyecta `instance.preview_transition(target, user)`,
  que delega a `WorkflowEngine().preview_transition(...)` (antes faltaba, aunque
  el motor sí lo exponía). **Nota para el consumidor `sinpapel-drf`:** el
  workaround que llama al motor directamente en el endpoint `preview-transition`
  ya no es necesario; puede volver opcionalmente a `instance.preview_transition(...)`.

### Changed
- **Comportamiento potencialmente breaking:** flujos que ya tenían
  `RequisitoEstadoDocumento` configurados (pero nunca se evaluaban) ahora los
  enforce. Flujos sin requisitos documentales se comportan idénticamente a 0.5.x;
  el flag `expediente_obligatorio` no cambia. El JSON v0.2 de export/import no se
  modifica (sigue serializando `RequisitoEstadoDocumento`, no `InstanciaDocumento`).

## [0.5.1] — 2026-05-17

### Fixed
- Packaging: drop the legacy `License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)` classifier. Per PEP 639, it cannot coexist with the SPDX `license = "GPL-3.0-or-later"` expression introduced in 0.5.0; `python -m build` failed with `InvalidConfigError` under `setuptools >= 77`.

### Changed
- Relicensed from MIT to **GPL-3.0-or-later** (SPDX, PEP 639). `LICENSE` now contains the canonical GPL-3.0 text prefixed with the project copyright notice.
- Public-facing materials rewritten and stripped of institutional references. `README.md` and `README.es.md` reduced to ~170 lines each; long-form manuals moved to `docs/USAGE.md` and `docs/USAGE.es.md`.

### Added
- `CHANGELOG.md` (Keep a Changelog 1.1.0) reconstructed back to v0.1.1.
- `CONTRIBUTING.md` with Conventional Commits guidance and DCO sign-off requirement.
- `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1).
- `build` and `twine` added to the `dev` extras so contributors can produce PyPI artifacts locally.

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

[Unreleased]: https://github.com/OWNER/REPO/compare/v0.5.1...HEAD
[0.5.1]: https://github.com/OWNER/REPO/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/OWNER/REPO/compare/v0.4.2...v0.5.0
[0.4.2]: https://github.com/OWNER/REPO/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/OWNER/REPO/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/OWNER/REPO/compare/v0.1.1...v0.4.0
[0.3.0]: https://github.com/OWNER/REPO/releases/tag/v0.3.0
[0.2.0]: https://github.com/OWNER/REPO/releases/tag/v0.2.0
[0.1.1]: https://github.com/OWNER/REPO/releases/tag/v0.1.1
