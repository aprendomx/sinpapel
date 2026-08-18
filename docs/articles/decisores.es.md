# Digitalizar trámites sin quedar atrapado: la tercera vía

Cuando una institución decide digitalizar sus trámites, la conversación suele reducirse a dos opciones. La primera: comprar una suite BPM comercial — licencias costosas, consultores del proveedor para cada cambio, y una dependencia que crece con los años. La segunda: encargar un desarrollo a la medida — que resuelve el proceso de hoy, pero envejece mal, porque cada cambio normativo vuelve a requerir programadores tocando el corazón del sistema.

Existe una tercera vía: **sinpapel**, un conjunto de herramientas de código abierto, diseñado específicamente para sistemas de trámites, que separa lo que nunca cambia (el motor) de lo que cambia todo el tiempo (las reglas de cada proceso).

## Qué obtiene su institución

**Trazabilidad total.** Cada movimiento de cada expediente queda registrado de forma inmutable: quién lo hizo, cuándo, desde dónde, con qué justificación y — cuando aplica — con qué firma electrónica. No es un módulo opcional que alguien puede omitir: el propio motor escribe el registro en la misma operación. Ante una auditoría o una solicitud de transparencia, la evidencia ya existe.

**Firma electrónica con validez.** El sistema incluye soporte para la FIEL del SAT, de modo que las decisiones críticas — una aprobación, un rechazo — pueden exigir la firma electrónica del funcionario responsable, verificada criptográficamente y ligada al expediente. También admite otros esquemas de firma cuando el trámite lo requiera.

**Reglas que cambian sin reprogramar.** Los pasos del trámite, quién puede autorizar qué, los requisitos documentales de cada etapa y los montos o condiciones que bloquean una decisión no están escritos en el código: son configuración. Cuando el reglamento cambia, se publica una nueva versión del flujo. Y algo que los auditores agradecen: los expedientes iniciados bajo las reglas anteriores conservan sus reglas — el sistema sabe exactamente bajo qué normativa se tramitó cada caso.

**Plazos vigilados por el sistema.** A cada etapa se le asigna un tiempo máximo. Si se vence, el sistema lo detecta automáticamente y activa las respuestas que la institución configure: notificar al responsable, escalar al superior o alertar al área de control. Los tiempos de respuesta dejan de depender de que alguien revise una bandeja.

**Documentos que se generan solos.** Oficios, acuses y constancias se producen automáticamente a partir de plantillas institucionales, con los datos del expediente. Menos captura manual, menos errores, formato uniforme.

**Integración con lo que ya existe.** El sistema notifica en tiempo real a otros sistemas (pagos, notificaciones al ciudadano, archivos institucionales) mediante mecanismos estándar y seguros, en lugar de vivir aislado.

**Diseño visual de procesos.** Los flujos se dibujan en una herramienta visual — cajas y flechas que el área normativa puede leer y validar — y ese diagrama es lo que el sistema ejecuta. El proceso documentado y el proceso real son el mismo artefacto.

## Costo, control y permanencia

sinpapel es software libre (licencia GPL-3.0). Eso tiene tres consecuencias prácticas:

- **Sin costo de licenciamiento.** La inversión se concentra en la implementación y en su propio equipo, no en pagos recurrentes por usuario o por proceso.
- **Sin dependencia de un proveedor.** El código es público y auditable; cualquier equipo competente puede mantenerlo, extenderlo o auditarlo. Si cambia el proveedor de implementación, el sistema sigue siendo suyo.
- **Transparencia verificable.** Para una institución pública, poder demostrar cómo decide su software no es un lujo: es una obligación que el código abierto convierte en un hecho verificable.

## Qué se necesita para adoptarlo

Ser realistas es parte de la propuesta. sinpapel no es un producto "llave en mano" que se instala y funciona solo: es el cimiento profesional sobre el que un equipo de desarrollo construye el sistema de su institución, en semanas en lugar de años, y sin reinventar la parte difícil.

Se necesita un equipo (interno o contratado) con experiencia en Python/Django — una de las tecnologías con mayor disponibilidad de talento en el mercado — y un ejercicio serio de mapeo de sus procesos, que de cualquier forma es la parte más valiosa de cualquier digitalización.

## El siguiente paso

El proyecto, su documentación en español e inglés y sus componentes están públicamente disponibles en [github.com/aprendomx/sinpapel](https://github.com/aprendomx/sinpapel). Una prueba de concepto sobre un trámite real — uno de esos que hoy tarda semanas y nadie sabe dónde está — es la mejor manera de evaluar si esta tercera vía es la de su institución.
