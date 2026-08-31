# Changelog

All notable changes to **sinpapel** are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.4] — 2026-08-30

### Fixed
- **`MetaFormFactory.build_serializer` producía serializers inservibles en dos
  casos frecuentes**, y en ambos el síntoma era un 500 o un 400 en los
  endpoints `/metadatos/` de `sinpapel-drf`, no un error al declarar el schema.

  - Un `CampoMetadato(requerido=True, default=...)` emitía `required` y
    `default` a la vez y DRF aborta con `May not set both 'required' and
    'default'`. Ahora, en DRF, el default implica opcional y `required` se
    omite; en Django Forms —donde `default` es solo `initial`— se conserva el
    comportamiento anterior. La combinación era además redundante:
    `MetadatosProxy.errores()` nunca ve vacío un campo con default.
  - Un campo opcional sin default vale `None` en `meta.to_dict()`, que es lo
    que devuelve un cliente al reenviar los metadatos completos —como hace el
    formulario de `sinpapel-vue`—. Sin `allow_null` (y `allow_blank` en los de
    texto), DRF rechazaba tanto el `null` como la cadena vacía y el campo
    resultaba imposible de guardar por la API.

## [0.8.3] — 2026-08-28

### Fixed
- **`AUTH_USER_MODEL` custom ya no rompe el arranque.** `VersionFlujo.creado_por`,
  `SeguimientoWorkflow.usuario_accion` y `RegistroFirma.signer` declaraban el FK
  con el literal `"auth.User"`. En cualquier proyecto con usuario custom, Django
  abortaba el system check con cinco `fields.E301` (los tres campos más sus
  modelos `Historical*`) y `manage.py check` / `migrate` fallaban: el framework
  era inusable. Ahora usan `settings.AUTH_USER_MODEL`.

  **Sin migración:** las migraciones ya registraban `settings.AUTH_USER_MODEL`;
  el desajuste vivía solo en las definiciones de modelo. No hay cambio de
  esquema y no se requiere `migrate` al actualizar desde 0.8.2.

## [0.8.2] — 2026-08-18

### Fixed
- **`requiere_firma` sobrevive el round-trip export/import.** `serialize_flujo`
  no serializaba el campo nuevo de 0.8.0 y `deserialize_flujo` lo perdía
  (quedaba en False al importar). Key aditiva al schema v0.2 — JSONs viejos
  sin la key importan con default False; el número de schema no cambia.

## [0.8.1] — 2026-08-18

### Added
- **Side effects scoped por flujo:** `@register_side_effect("ESTADO",
  workflow_key="mi_flujo")` limita el handler a ese flujo (precedencia sobre
  el global). El registro global sigue funcionando igual (compat).
- **`SINPAPEL_ENFORCE_ESTADO_ACTIVO`** (default False, opt-in): con True, un
  `Estado` con `activo=False` deja de ser destino válido y desaparece de
  `available_transitions`.

### Changed
- `evaluar_requisitos_documentales` agrega los porcentajes por tipo en UNA
  query (antes: una por requisito — N+1 en previews).
- sdist limpio: MANIFEST.in con rutas reales del flat layout (`prune
  tests/docs/site`); el tarball baja a solo el paquete + metadata.
  `.coverage` deja de estar trackeado en git.
- CI: pyright corre contra un `.venv` real con `django-types` — de 8 falsos
  positivos sin stubs a **0 errors** con imports resueltos; los 13 tests del
  modo DRF corren también en local.

## [0.8.0] — 2026-08-18

Release de endurecimiento post-auditoría. **Contiene breaking changes** —
lee la [guía de upgrade](upgrading.md#07x--080) antes de actualizar.

### Added
- **Firma exigible por transición:** campo
  `ConfiguracionTransicion.requiere_firma` (default False, migración 0008).
  Con True, `transition()` sin `firma_payload` lanza `PermissionError`, y
  `preview_transition()` reporta `firma_requerida`.
- **Cadena de confianza FIEL:** setting `SINPAPEL_FIEL_TRUSTED_CA_BUNDLE`
  (paths PEM de ACs del SAT). Con bundle, un certificado no emitido por una
  AC de confianza se rechaza; sin bundle, la firma se persiste como
  `VALIDA_SIN_CADENA` (nuevo estado, migración 0009) — íntegra pero con
  identidad del emisor no verificada. `RegistroFirma.RESULTADOS_VALIDOS`
  agrupa los estados utilizables.
- **SLA real:** las acciones ejecutan — `escalar`/`rechazar` corren la
  transición automática como `SINPAPEL_SLA_SYSTEM_USER`, `alertar` persiste
  la bandera, `notificar` despacha a `SINPAPEL_SLA_NOTIFY_HANDLER`.
  `SLAEngine.verificar_todos()` escanea el `WorkflowRegistry` y el comando
  `sinpapel_verificar_slas` lo invoca (con `--dry-run` sin efectos). El plazo
  ahora mide **tiempo-en-estado** (última transición), no edad de la
  instancia.
- **API pública explícita** (`docs/development/api-publica.md`) con política
  de nomenclatura documentada, y **guía de upgrade**
  (`docs/development/upgrading.md`).

### Changed
- **Constraints de integridad (breaking, migración 0007):** `Estado.nombre`
  único; solo una `VersionFlujo` activa por nombre; `Trazable.autor` /
  `modificador` pasan de CASCADE a SET_NULL (borrar un User ya no arrasa sus
  registros); PROTECT en `Documento.tipo_documento`,
  `InstanciaDocumento.documento` y `SeguimientoWorkflow.firma_registro`.
- **Inmutabilidad enforceada:** `SeguimientoWorkflow` es append-only
  (`save()` de update y `delete()` lanzan) y `RegistroFirma.delete()` lanza
  (revocar vía `backend.revoke()`).
- **Modo A de firma usa el backend configurado** (`get_signature_backend()`)
  en lugar de `FielBackend` hardcodeado; **modo B valida** que el
  `registro_firma_id` pertenezca al usuario, esté en estado válido y no esté
  ya vinculado.
- **Predicados robustos:** una `CondicionTransicion` mal configurada bloquea
  la transición con mensaje controlado en lugar de lanzar excepción; los
  backends validan su `configuracion` con errores accionables.
- **Invalidación de cache real:** las keys de transitions/requisitos
  incorporan `sinpapel:cache_version`, así el bump por mutación de `Estado`
  sí invalida en cascada (antes el bump era un no-op).
- **`@workflow_enabled` valida el contrato `Trazable`** (campo
  `actualizado`) en tiempo de decoración.
- **Import de flujos:** payload estructuralmente inválido produce
  `ValueError` accionable (antes `KeyError` → 500 en los endpoints).
- CI: matriz Django 5.0 / 5.2 LTS / 6.0 (con exclusiones por versión de
  Python), DRF instalado (los 13 tests del modo serializer ya corren), job
  de ruff (config `[tool.ruff]` nueva), Postgres con Django 6. Classifiers
  de Django 5.2/6.0.

## [0.7.1] — 2026-08-18

### Fixed
- **`preview_transition()["historial_reciente"]` siempre regresaba `[]`.**
  `_obtener_historial_reciente` filtraba `target=instance` sobre una
  GenericForeignKey (FieldError silenciado por un `except` amplio). Ahora
  filtra por `(target_content_type, target_object_id)` con `select_related`,
  y los errores se loggean en vez de tragarse.
- **`instance.available_transitions()` ignoraba la versión del flujo.** El
  método inyectado consultaba `ConfiguracionTransicion` sin filtro de `flujo`
  y sin cache; ahora delega a `WorkflowEngine.available_transitions` (filtra
  por el `VersionFlujo` resuelto y usa el cache de transiciones). Si tu app
  dependía de ver transiciones de todos los flujos, usa una consulta ORM
  directa.
- **Carrera check-then-act en `cambiar_estado`.** La transición ahora re-lee
  el row con `SELECT ... FOR UPDATE` dentro de la transacción y revalida
  sobre el estado fresco: dos transiciones concurrentes (o una copia stale en
  memoria) ya no pueden ejecutarse ambas; la segunda recibe `PermissionError`.
- **Side effects post-commit.** `ejecutar_side_effects` corre ahora DESPUÉS
  de que la transacción del motor commiteó (antes corría dentro, y la
  justificación del ADR-004 era incorrecta): un side effect con efectos
  externos ya no puede dispararse para una transición que hace rollback.
- **Packaging: `Pillow` declarado como dependencia.** `Catalogo.imagen` es un
  `ImageField`; sin Pillow, `pip install sinpapel` en un proyecto limpio
  fallaba `manage.py check` con 4 × `fields.E210`.
- Docs: la guía de uso EN declaraba licencia **MIT** (es GPL-3.0-or-later
  desde 0.5.1); el Quick Start de la home de MkDocs no ejecutaba (decorador
  sin kwargs obligatorios, `CampoMetadato` con strings en vez de types) y
  anunciaba backends inexistentes; URL de Changelog en los metadatos de PyPI
  apuntaba a un archivo inexistente.

### Changed
- **Documentado el estado real del subsistema SLA en 0.7.x** (README, guías
  de uso, docstrings): las acciones integradas (`notificar` / `escalar` /
  `rechazar` / `alertar`) son stubs informativos — detectan el vencimiento y
  emiten `sla_breached` / `sla_action_executed`, pero no ejecutan la acción
  descrita. La ejecución real (basada en tiempo-en-estado) está planeada para
  1.0.

## [0.7.0] — 2026-06-28

### Removed
- **Campo residual `SeguimientoWorkflow.monto_aprobado`.** Era un concepto de
  dominio (montos de aprobación) filtrado en el framework genérico. Se elimina
  del modelo (migración `0006`), del parámetro `monto_aprobado` de
  `WorkflowEngine.cambiar_estado()` y de la propagación a side-effects.
  **Breaking:** `transition()` / `cambiar_estado()` ya no aceptan
  `monto_aprobado`; las apps que necesiten datos de dominio deben usar
  metadatos (`MetadatosCapturables`) o `condiciones` / `comentarios`.

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
- Campo `InstanciaDocumento.archivo` (`FileField`, `upload_to="instancias_documento/"`,
  `blank/null`) para el archivo que sube el usuario, distinto de `archivo_generado`
  (que produce el sistema). Migración reversible
  `0005_historicalinstanciadocumento_archivo_and_more`. Lo consume `sinpapel-drf`
  en el endpoint de carga `POST /<slug>/<pk>/documentos/`.
- Método público `WorkflowEngine.evaluar_requisitos_documentales(instance, estado=None)`
  que devuelve **todos** los requisitos documentales del estado (no solo los
  faltantes) con su cumplimiento por nivel (`expediente` / `requisito_documento`).
  `_validar_documentos` pasa a ser un wrapper sobre él (una sola fuente de verdad,
  preservando exacta la forma de `documentos_faltantes`). Lo consume `sinpapel-drf`
  en `GET /<slug>/<pk>/requisitos/`, evitando duplicar la lógica del motor.
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

[Unreleased]: https://github.com/aprendomx/sinpapel/compare/v0.8.2...HEAD
[0.8.2]: https://github.com/aprendomx/sinpapel/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/aprendomx/sinpapel/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/aprendomx/sinpapel/compare/v0.7.1...v0.8.0
[0.7.1]: https://github.com/aprendomx/sinpapel/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/aprendomx/sinpapel/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/aprendomx/sinpapel/compare/v0.5.1...v0.6.0
[0.5.1]: https://github.com/aprendomx/sinpapel/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/aprendomx/sinpapel/compare/v0.4.2...v0.5.0
[0.4.2]: https://github.com/aprendomx/sinpapel/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/aprendomx/sinpapel/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/aprendomx/sinpapel/compare/v0.1.1...v0.4.0
[0.3.0]: https://github.com/aprendomx/sinpapel/releases/tag/v0.3.0
[0.2.0]: https://github.com/aprendomx/sinpapel/releases/tag/v0.2.0
[0.1.1]: https://github.com/aprendomx/sinpapel/releases/tag/v0.1.1
