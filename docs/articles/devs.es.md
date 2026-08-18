# sinpapel: deja de reprogramar el mismo trámite

Si has construido software para gobierno o para cualquier organización con procesos formales, ya escribiste este sistema: una solicitud entra, pasa por revisión, alguien la aprueba o la rechaza, todo debe quedar registrado, algunas decisiones requieren firma, hay plazos legales que se vencen y reglas que cambian cada año fiscal.

Y lo escribiste a mano. La máquina de estados como `if`s dispersos en las vistas, la auditoría como un modelo `Log` que alguien olvida poblar, la firma como una integración frágil, los plazos como un cron que nadie monitorea. Seis meses después, el área normativa cambia el proceso y el cambio requiere un deploy.

**sinpapel** es un framework Django (GPL-3.0, Python ≥3.10, Django ≥5.0) que resuelve ese problema una sola vez, con una idea central: **el workflow son datos, no código**.

## El flujo vive en la base de datos

En sinpapel, los estados, las transiciones permitidas, quién puede ejecutarlas, qué reglas las bloquean y qué plazos las gobiernan son registros en la base de datos — versionados. Tu modelo de dominio solo se decora:

```python
from django.db import models
from sinpapel.decorators import workflow_enabled
from sinpapel.mixins import Trazable

@workflow_enabled(
    state_field="estado",
    workflow_key="permiso_construccion",
    expose_endpoints=True,
)
class Solicitud(Trazable):
    estado = models.ForeignKey("sinpapel.Estado", on_delete=models.PROTECT)
    folio = models.CharField(max_length=20)
```

El decorador inyecta la API de workflow en el modelo:

```python
solicitud.available_transitions(user)      # ¿a dónde puede ir este usuario?
solicitud.can_transition_to("Aprobada", user)
solicitud.preview_transition("Aprobada", user)  # simula sin ejecutar
solicitud.transition("Aprobada", user, comentarios="Cumple normativa vigente")
```

Cada `transition()` es atómica: valida permisos por grupo, evalúa predicados, exige los documentos requeridos, ejecuta la firma si el estado la pide, dispara side effects y escribe el registro de auditoría. Todo o nada.

Cuando el proceso cambia, publicas una nueva `VersionFlujo`. Los expedientes viejos siguen gobernados por la versión con la que nacieron — que es exactamente lo que un auditor va a preguntar.

## Los cinco pilares

1. **Workflow versionado** — `Estado`, `VersionFlujo`, `ConfiguracionTransicion`. El grafo de transición es configurable por instancia de flujo, con grupos de Django como control de acceso por arista.
2. **Audit trail inmutable** — cada transición genera un `SeguimientoWorkflow` (quién, cuándo, desde dónde, con qué firma), y el mixin `Trazable` (sobre `django-simple-history`) versiona los cambios de campo del modelo.
3. **Firma electrónica pluggable** — patrón Port/Adapter. Incluye `FielBackend` para la FIEL del SAT (México), con modo client-side y server-side, más backends manual y fake para desarrollo y tests. Implementar el tuyo es cumplir un `Protocol`.
4. **Predicados de transición** — reglas de negocio que bloquean una transición: funciones Python whitelisteadas, JSON Logic restringido o consultas ORM declarativas. Se configuran por transición, en datos.
5. **SLA vigilados** — plazos máximos por estado; al vencer, el motor lo detecta y dispara el signal `sla_breached` con toda la información del caso, sobre el que cuelgas tus acciones (notificar, escalar, rechazar). Un management command en cron como punto de entrada. La ejecución integrada de acciones llega en 1.0 — hoy el patrón es suscribirse a la señal.

Además: captura de metadatos estructurados por instancia sin migraciones (`MetadatosCapturables`), signals de dominio, y export/import de flujos completos en JSON portable.

## Un ecosistema que se compone, no un monolito

El núcleo no sabe de HTTP. Cada capa es un paquete opcional:

| Paquete | Qué añade |
|---|---|
| [`sinpapel`](https://pypi.org/project/sinpapel/) | El motor: workflow, auditoría, firma, predicados, SLA, metadatos. |
| [`sinpapel-drf`](https://pypi.org/project/sinpapel-drf/) | API REST auto-generada por modelo: transiciones, historial, preview, documentos, requisitos, más CRUD administrativo y portabilidad de flujos. |
| [`sinpapel-webhooks`](https://pypi.org/project/sinpapel-webhooks/) | Webhooks salientes firmados con HMAC (patrón outbox, compatible con el estilo Stripe) y framework de receptores entrantes. |
| [`sinpapel-reports`](https://pypi.org/project/sinpapel-reports/) | Generación de oficios y acuses por plantilla: overlay sobre PDF y DOCX con datos del expediente. |
| [`sinpapel-designer`](https://github.com/aprendomx/sinpapel-designer) | SPA (Vue 3 + Quasar) para diseñar flujos visualmente; exporta el JSON que el backend importa. |
| [`@aprendomx/sinpapel-vue`](https://github.com/aprendomx/sinpapel-vue) | Widgets Vue 3 listos: timeline de historial, diálogo de transición con firma, panel de documentos, estado de SLA. |

El flujo de trabajo completo: dibujas el proceso en el designer, importas el JSON con un management command, decoras tu modelo, montas el router de DRF y sueltas los widgets Vue en tu frontend. Del diagrama al API funcionando, en una tarde.

## Lo que debes saber antes de adoptarlo

Honestidad primero:

- **Es 0.x.** La API pública es estable en la práctica pero sigue en beta; pinea versiones exactas (`sinpapel==0.7.1`).
- **i18n:** los mensajes y verbose_names del framework están en español. Si tu producto es en otro idioma, harás overrides en forms/serializers.
- **GPL-3.0.** Copyleft real. Perfecto para gobierno y software público; evalúalo si tu modelo de negocio es SaaS cerrado.
- **La firma FIEL es específica de México** (SAT). Para otros esquemas, el contrato `SignatureBackend` es pequeño y está documentado.

## Pruébalo

Los cuatro paquetes de backend ya están en PyPI:

```bash
pip install sinpapel sinpapel-drf sinpapel-webhooks sinpapel-reports
```

El código, la documentación bilingüe y los issues viven en [github.com/aprendomx/sinpapel](https://github.com/aprendomx/sinpapel). Si construyes sistemas de trámites en Django, la próxima máquina de estados no la escribas a mano.
