# Guía de upgrade / Upgrade guide

Cada sección lista lo que puede romperte al subir de versión y qué hacer.
*Each section lists what may break when upgrading and what to do.*

---

## 0.7.x → 0.8.0

**Corre `python manage.py migrate sinpapel`** (migraciones 0007–0009) y
regenera migraciones de tus apps si tus modelos heredan `Trazable`
(cambia `on_delete` de `autor`/`modificador`).

### Cambios de esquema y datos / Schema & data changes

- **`Estado.nombre` ahora es único** (`sin_estado_nombre_uniq`). Si tu BD
  tiene Estados duplicados, la migración fallará: consolida los duplicados
  ANTES de migrar (reapunta FKs al sobreviviente y borra el resto).
  *`Estado.nombre` is now unique — deduplicate before migrating.*
- **Solo una `VersionFlujo` activa por nombre**
  (`sin_versionflujo_activa_uniq`). Desactiva versiones redundantes antes de
  migrar. *Only one active `VersionFlujo` per name.*
- **`Trazable.autor`/`modificador`: CASCADE → SET_NULL.** Borrar un User ya
  no borra en cascada lo que autoró. Tus modelos que hereden `Trazable`
  necesitan `makemigrations`. *User deletion no longer cascades.*
- **PROTECT en la cadena documental y la firma:**
  `Documento.tipo_documento`, `InstanciaDocumento.documento` y
  `SeguimientoWorkflow.firma_registro` ahora protegen contra borrado del
  padre. Flujos de limpieza que borraban catálogos con hijos recibirán
  `ProtectedError`. *Catalog deletion with children now raises.*

### Cambios de comportamiento / Behavior changes

- **Las acciones SLA ahora ACTÚAN.** `escalar`/`rechazar` ejecutan la
  transición automática (configura `SINPAPEL_SLA_SYSTEM_USER` con un username
  con permisos), `alertar` persiste la bandera, `notificar` despacha al
  handler de `SINPAPEL_SLA_NOTIFY_HANDLER`. Además el plazo ahora mide
  **tiempo en el estado actual** (última transición), no edad de la
  instancia. Si dependías del comportamiento stub 0.7.x (no-op), revisa tus
  `SLAConfiguracion` antes de correr el cron. *SLA actions now execute for
  real, and measure time-in-state.*
- **`transition()` exige firma cuando la transición la requiere.** Nuevo
  campo `ConfiguracionTransicion.requiere_firma` (default `False` — sin
  cambio si no lo activas). *New opt-in `requiere_firma` flag.*
- **La firma modo A usa el backend configurado** (`SINPAPEL_SIGNATURE_BACKEND`
  vía factory), ya no `FielBackend` hardcodeado. Si dependías del bypass,
  configura el backend explícitamente. *Mode A now honors the configured
  backend.*
- **Modo B valida el `registro_firma_id`:** debe pertenecer al usuario que
  transiciona, estar en estado válido y no estar vinculado ya. *Mode B now
  validates ownership, validity and reuse.*
- **FIEL sin bundle de ACs produce `VALIDA_SIN_CADENA`** (antes `VALIDA`).
  Con `SINPAPEL_FIEL_TRUSTED_CA_BUNDLE` configurado (paths PEM de las AC del
  SAT), un cert no emitido por el bundle se **rechaza** y el emitido produce
  `VALIDA`. Si comparabas `verification_result == "VALIDA"`, usa
  `RegistroFirma.RESULTADOS_VALIDOS`. *New chain-of-trust semantics.*
- **`SeguimientoWorkflow` y `RegistroFirma` son inmutables a nivel ORM:**
  `save()` sobre un registro existente y `delete()` lanzan `ValueError`
  (los `queryset.update/delete` masivos no pasan por estos hooks — evítalos).
  *Audit rows are now append-only at the ORM level.*
- **`instance.available_transitions()` filtra por el flujo resuelto** (fix
  0.7.1, reforzado aquí): ya no devuelve transiciones de otros flujos.
- **`@workflow_enabled` valida el contrato `Trazable`** en tiempo de
  decoración: un modelo sin campo `actualizado` falla al importar, no en la
  primera transición.
- **Predicados mal configurados bloquean con mensaje** en lugar de lanzar
  excepción (antes: 500 en cada preview/transition con la condición rota).

### Settings nuevos / New settings

| Setting | Default | Uso |
|---|---|---|
| `SINPAPEL_SLA_SYSTEM_USER` | `None` | Username para transiciones automáticas de SLA |
| `SINPAPEL_SLA_NOTIFY_HANDLER` | `None` | Dotted path del handler de notificación SLA |
| `SINPAPEL_FIEL_TRUSTED_CA_BUNDLE` | `None` | Path(s) PEM de ACs de confianza (SAT) |

---

## 0.6.x → 0.7.x

- **0.7.0 eliminó `monto_aprobado`** de `SeguimientoWorkflow` y del parámetro
  de `transition()` / `cambiar_estado()` (migración 0006). Usa metadatos
  (`MetadatosCapturables`) o `condiciones`/`comentarios`. *`monto_aprobado`
  removed; use metadata.*
- **0.7.1** corrigió `historial_reciente` (antes siempre `[]`), el filtro por
  flujo de `available_transitions`, la carrera de transiciones concurrentes y
  declaró `Pillow` como dependencia.

---

## 0.5.x → 0.6.0

- **Las transiciones enforzan `RequisitoEstadoDocumento`.** Reglas que
  existían en BD pero nunca se evaluaban ahora bloquean
  (`PermissionError` / `documentos_faltantes` en preview). Antes de
  actualizar, revisa qué requisitos tienes configurados
  (`RequisitoEstadoDocumento.objects.all()`) y si tus expedientes los
  satisfacen (`InstanciaDocumento.porcentaje`, default 100 = completo).
  *Previously-dormant document requirements are now enforced — audit your
  configured rules before upgrading.*
