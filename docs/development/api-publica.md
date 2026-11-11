# API pública y política de estabilidad

Este documento define QUÉ es API pública de sinpapel (lo que el contrato de
versionado protege) y la política de nomenclatura del proyecto. Es la
referencia canónica; el README la resume.

## Superficie pública estable

Todo lo listado aquí está cubierto por el contrato de versionado (ver
"Contrato" abajo). Lo que NO está listado es interno: puede cambiar en
cualquier release sin aviso, aunque no tenga guion bajo.

### API de instancia (inyectada por `@workflow_enabled`)

- `instance.transition(target_state_name, user, **kwargs)`
- `instance.available_transitions(user)`
- `instance.can_transition_to(target_state_name, user)`
- `instance.preview_transition(target_state_name, user)`

Esta es la API recomendada para aplicaciones.

### Decorador y registro

- `sinpapel.workflow_enabled` (kwargs: `state_field`, `workflow_key`,
  `version_field`, `expose_endpoints`, `endpoint_slug`)
- `sinpapel.WorkflowRegistry` (`get`, `list_keys`, `list_exposed`,
  `unregister`)
- `sinpapel.WorkflowConfig`
- Excepciones: `SinpapelError`, `WorkflowConfigurationError`,
  `WorkflowDuplicateKeyError`

### Motor (para consumidores framework-level, p. ej. sinpapel-drf)

- `WorkflowEngine.cambiar_estado(...)` / `.puede_cambiar_estado(...)` /
  `.preview_transition(...)` / `.available_transitions(...)`
- `WorkflowEngine.evaluar_requisitos_documentales(instance, estado=None)`
- Las **formas de los dicts** que retornan `preview_transition`
  (`permitido`, `razones_bloqueo`, `documentos_faltantes`,
  `predicados_fallidos`, `firma_requerida`, `historial_reciente`, …) y
  `cambiar_estado` (`success`, `estado_anterior`, `estado_nuevo`,
  `seguimiento_id`, …). Agregar keys es no-breaking; quitar o renombrar keys
  es breaking.
- Métodos `_privados` del motor (`_validar_*`, `_resolver_*`): **internos**,
  aunque el changelog los mencione.

### Modelos y campos

Los modelos `Estado`, `Etapa`, `VersionFlujo`, `ConfiguracionTransicion`,
`SeguimientoWorkflow`, `RequisitoEstadoDocumento`, `TipoDocumento`,
`Documento`, `InstanciaDocumento`, `ExpedienteAdjunto`, `RegistroFirma`,
`SLAConfiguracion`, `CondicionTransicion` y sus campos documentados son API
pública (los consumen migraciones y paquetes downstream). Quitar o renombrar
un campo es breaking.

### Mixins, forms, firma, señales, predicados, SLA, portabilidad

- `sinpapel.mixins`: `Trazable`, `Catalogo`, `MetadatosCapturables`,
  `CampoMetadato`, `MetadatosProxy` (su comportamiento documentado)
- `sinpapel.forms.MetaFormFactory`
- `sinpapel.signing`: `SignatureBackend` (Protocol), `get_signature_backend`,
  `reset_backend_cache`, backends `FielBackend` / `ManualBackend` /
  `FakeBackend`, `VerificationResult`, excepciones de `signing.exceptions`
- `sinpapel.signing` — lectura de certificados (0.8.7): `leer_certificado`,
  `cargar_bundle_confianza`, `emitido_por`, `CertificadoLeido`,
  `BundleCargado`. Ver la sección siguiente.
- `sinpapel.signals`: `predicate_failed`, `sla_breached`,
  `sla_action_executed`, `transition_preview_requested` (y sus kwargs)
- `PredicateEngine.evaluar` / `PredicateEngine.registrar_backend` y los tres
  backends (`python_path`, `json_logic`, `django_orm`) con sus formas de
  `configuracion`
- `SLAEngine.verificar_todos` / `SLAEngine.evaluar_instancia`
- `sinpapel.schemas.flujo_export`: `serialize_flujo`, `deserialize_flujo`,
  `validate_schema_version`, `find_missing_entities`; el **schema JSON**
  (versiones soportadas: 0.1 y 0.2)
- Management commands: `sinpapel_export_flujo`, `sinpapel_import_flujo`,
  `sinpapel_verificar_slas`
- Settings `SINPAPEL_*` documentados en la guía de uso

### Lectura de certificados FIEL (0.8.7)

Para validar o armar `SINPAPEL_FIEL_TRUSTED_CA_BUNDLE` fuera del flujo de
firma, con **la misma implementación** que usa `FielBackend` (incluida la
ruta tolerante para la AC6 del SAT). Se importan desde `sinpapel.signing` y
no requieren settings de Django.

| Nombre | Contrato |
|---|---|
| `leer_certificado(datos: bytes) -> CertificadoLeido` | UN certificado DER o PEM. `ValueError` si es ilegible o si el PEM trae varios. |
| `cargar_bundle_confianza(rutas) -> BundleCargado` | Un path o lista de paths (PEM con uno o varios certificados, o DER). Omite los ilegibles. `SignatureBackendNotConfiguredError` si no queda ninguno; `OSError` si falta un archivo. |
| `emitido_por(cert, cas, *, en=None) -> x509.Certificate \| None` | Verificación de **un nivel**: sujeto de la AC == emisor, AC vigente en `en` (default: ahora) y firma sobre el `tbsCertificate` original. No valida la vigencia del propio `cert`. |
| `CertificadoLeido` | Dataclass frozen: `cert` (`x509.Certificate`, solo para leer campos), `tbs_original` (`bytes`), `normalizado` (`bool`). |
| `BundleCargado` | Dataclass: `cas`, `omitidos` (`"archivo#índice"`), `motivos` (`{clave: motivo}`), `normalizados`. |

Si `normalizado` es `True`, `cert.tbs_certificate_bytes` **no** es lo que
firmó la AC: para verificar usa `tbs_original` o pasa el `CertificadoLeido`
completo a `emitido_por`. Agregar campos a las dataclasses es no-breaking.

```python
from pathlib import Path
from sinpapel.signing import cargar_bundle_confianza, emitido_por, leer_certificado

bundle = cargar_bundle_confianza("/etc/siaf/sat-ac-bundle.pem")
assert not bundle.omitidos, bundle.motivos

efirma = leer_certificado(Path("persona.cer").read_bytes())
ac = emitido_por(efirma, bundle.cas)
assert ac is not None, "el bundle no cubre a la AC emisora de esta e.firma"
```

### Interno (NO API pública)

- `sinpapel.signing._x509_tolerante` (usa la API de arriba),
  `FielBackend._load_trusted_cas` / `_verify_issuer_chain` / `_load_cert*`.
- `sinpapel.cache` (helpers y keys), `sinpapel.injection`,
  `sinpapel.json_logic`, `sinpapel.apps`, todo `_prefijado`, y los receivers
  de invalidación en `sinpapel.signals`.

## Contrato de versionado (pre-1.0)

sinpapel sigue [SemVer](https://semver.org). En la serie `0.y.z`:

- **`y` (minor) PUEDE incluir breaking changes** en la superficie pública.
  Cada breaking change se documenta en el changelog y en la
  [guía de upgrade](upgrading.md).
- **`z` (patch)** solo contiene fixes y cambios internos, sin romper la
  superficie pública.
- Recomendación para consumidores 0.x: pinear minor (`sinpapel~=0.8.0`).

A partir de **1.0.0**: `MAJOR` = breaking, `MINOR` = features compatibles,
`PATCH` = fixes.

## Política de nomenclatura (decisión, no accidente)

sinpapel es deliberadamente bilingüe, con una regla fija:

- **El dominio habla español.** Modelos, campos, señales de negocio y
  mensajes (`Estado`, `VersionFlujo`, `SeguimientoWorkflow`,
  `requiere_firma`, `razones_bloqueo`…) están y permanecerán en español: es
  el lenguaje ubicuo del dominio (trámites, normativa mexicana) y renombrar
  el esquema rompería a todos los consumidores sin beneficio.
- **La API de instancia habla inglés.** Los verbos que una aplicación llama
  (`transition`, `available_transitions`, `can_transition_to`,
  `preview_transition`) son ingleses y son la superficie recomendada.
- Los métodos españoles del motor (`cambiar_estado`, `puede_cambiar_estado`)
  son la implementación a la que la API de instancia delega; son públicos
  para consumidores framework-level y no se planea renombrarlos.

No habrá renombrado masivo español→inglés antes de 1.0.
