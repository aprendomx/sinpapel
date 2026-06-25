# Enforce de requisitos documentales + inyección de `preview_transition`

**Fecha:** 2026-06-25
**Estado:** Propuesto
**Versión objetivo:** 0.6.0 (cambio de comportamiento potencialmente breaking)

## Problema

Dos defectos detectados verificando `sinpapel-drf` contra `sinpapel==0.5.1`:

- **Defecto A** — El motor sólo evalúa el flag coarse `Estado.expediente_obligatorio`.
  Las reglas finas de `RequisitoEstadoDocumento` (tipo_documento + porcentaje mínimo)
  se configuran y se exportan/importan, pero **nunca se evalúan en la transición**.
  `cache.get_requisitos_for(estado_id)` existe pero sólo lo invoca el signal de
  invalidación, nunca el motor.
- **Defecto B** — `@workflow_enabled` inyecta `available_transitions`, `can_transition_to`
  y `transition`, pero **no** `preview_transition`, aunque el motor sí lo expone.
  `instance.preview_transition(...)` → `AttributeError` → HTTP 500 en el consumidor.

## Decisiones de diseño (Defecto A)

### D1 — Fuente de "documento de tipo T presente"

`InstanciaDocumento` es el **único** modelo que liga un `tipo_documento`
(vía `documento.tipo_documento`) con la instancia workflow (vía la GFK `target`).
`ExpedienteAdjunto` no tiene `tipo_documento`, así que no puede satisfacer un
requisito por tipo y se sigue usando **sólo** para el flag coarse
`expediente_obligatorio` (sin cambios).

### D2 — Origen del porcentaje actual

Se agrega un campo nuevo **`porcentaje`** (`IntegerField`, `default=100`,
validators 0–100) a `InstanciaDocumento`, con migración reversible.

- `default=100` ⇒ filas existentes cuentan como 100% ⇒ **backward-compatible**.
- Hace que `RequisitoEstadoDocumento.porcentaje` sea significativo: un documento
  puede estar parcialmente completo (p.ej. 60%) y bloquear un requisito de 100%.

`porcentaje_actual` de un tipo = `max(porcentaje)` entre las `InstanciaDocumento`
de ese tipo asociadas a la instancia (0 si no hay ninguna). Se compara
`porcentaje_actual >= requisito.porcentaje`.

### D3 — Semántica de `auto_carga`

`auto_carga=True` ⇒ documento generado por el sistema (no subido por el usuario)
⇒ **no bloquea** la transición del usuario. El motor enforce **sólo** los
requisitos con `auto_carga=False`.

## Implementación

### Defecto A — `_validar_documentos(instance, estado_actual)`

Se extiende el método existente (sin cambiar su firma). Además del flag coarse
actual (sin tocar), recorre `cache.get_requisitos_for(estado_actual.id)`:

```python
faltantes = []
# (1) flag coarse expediente_obligatorio — comportamiento intacto
...
# (2) requisitos finos por tipo/porcentaje
ct = ContentType.objects.get_for_model(type(instance))
for req in get_requisitos_for(estado_actual.id):
    if req.auto_carga:            # D3: system-generated no bloquea
        continue
    actual = max(
        InstanciaDocumento.objects.filter(
            target_content_type=ct,
            target_object_id=instance.pk,
            documento__tipo_documento_id=req.tipo_documento_id,
        ).values_list("porcentaje", flat=True),
        default=0,
    )
    if actual < req.porcentaje:
        faltantes.append({
            "tipo": "requisito_documento",
            "tipo_documento": req.tipo_documento.nombre,
            "porcentaje_requerido": req.porcentaje,
            "porcentaje_actual": actual,
            "mensaje": (
                f"Falta el documento '{req.tipo_documento.nombre}' "
                f"(requerido {req.porcentaje}%, actual {actual}%)."
            ),
        })
return faltantes
```

El enforce vive **sólo** en `_validar_documentos`; se propaga automáticamente a:

- `preview_transition()` → `documentos_faltantes` + `razones_bloqueo` (tipo `documento`).
- `puede_cambiar_estado()` → `(False, mensaje)`.
- `cambiar_estado()` → `PermissionError` (vía `puede_cambiar_estado`).

Usa el cache (`get_requisitos_for`) y respeta su invalidación por signal. La cuenta
de `InstanciaDocumento` es dato de instancia (cambia seguido) → no se cachea.

### Defecto B — inyección de `preview_transition`

- `injection.py`: nueva función `preview_transition(self, target_state_name, user)`
  que delega a `WorkflowEngine().preview_transition(self, target_state_name, user)`,
  con el mismo patrón de import local que las otras.
- `decorators.py`: `setattr(model_class, "preview_transition", preview_transition)`
  junto a las demás.

Firma consistente con `transition`/`can_transition_to`: `instance.preview_transition(target, user)`.

## Backward-compat / contrato

- Flujos sin `RequisitoEstadoDocumento` se comportan idénticamente a hoy.
- `expediente_obligatorio` sigue funcionando igual.
- El JSON v0.2 de export/import **no cambia**: serializa `RequisitoEstadoDocumento`
  (porcentaje, auto_carga ya existían), no `InstanciaDocumento`.
- Contrato público del motor intacto (sólo se añade comportamiento al validar).

## Testing (pytest-django, sin depender de `creditos`)

- Requisito por tipo/porcentaje: bloquea cuando falta; permite cuando se satisface
  (`InstanciaDocumento` del tipo con `porcentaje >= requerido`); aparece en
  `preview_transition()["documentos_faltantes"]`; provoca `PermissionError` en
  `cambiar_estado`.
- `auto_carga=True` no bloquea (regresión inversa).
- Caso coarse `expediente_obligatorio` sigue pasando igual (regresión).
- `instance.preview_transition(target, user)` existe y devuelve el mismo dict que
  `WorkflowEngine().preview_transition`.

## Entregables adicionales

- Migración reversible para `InstanciaDocumento.porcentaje` (`makemigrations` +
  `migrate` + prueba de reverse).
- Bump `0.5.2 → 0.6.0` + entrada en CHANGELOG (nuevo enforce, campo/migración,
  y nota para el mantenedor de `sinpapel-drf` sobre el workaround).
