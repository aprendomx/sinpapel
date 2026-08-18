"""Sinpapel — SLA Engine for evaluating and executing SLA actions.

Evaluates SLAConfiguracion rules against workflow-enabled instances and
dispatches configured actions when time limits are exceeded.

Semántica de tiempo (0.8.0): el plazo se mide como **tiempo en el estado
actual** — desde la fecha de la última transición registrada en
SeguimientoWorkflow para la instancia; si no hay historial, cae al campo
`creado` de la instancia.

Acciones (0.8.0 — ejecutan de verdad):
- notificar: construye el descriptor y lo despacha al handler configurado en
  ``SINPAPEL_SLA_NOTIFY_HANDLER`` (dotted path a un callable
  ``handler(instance, descriptor)``); sin handler, se loggea. La señal
  `sla_action_executed` se emite siempre.
- escalar / rechazar: ejecutan la transición automática al `estado_destino`
  configurado, vía WorkflowEngine, con el usuario de sistema
  ``SINPAPEL_SLA_SYSTEM_USER`` (username). Ese usuario debe tener permiso
  para la transición (superuser o miembro de los grupos permitidos).
- alertar: activa la bandera en la instancia y la persiste con
  ``save(update_fields=[campo])``.

Cron de producción: ``python manage.py sinpapel_verificar_slas`` (soporta
``--dry-run``: reporta vencidos sin ejecutar acciones ni emitir señales).
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib.auth.models import Group
from django.utils import timezone

from sinpapel.models.sla import SLAConfiguracion

if TYPE_CHECKING:
    from django.db import models

logger = logging.getLogger(__name__)


class SLAEngine:
    """Motor de evaluación y ejecución de SLAs."""

    @classmethod
    def verificar_todos(cls, dry_run: bool = False) -> dict[str, int]:
        """Evalúa todos los SLAs activos contra todas las instancias
        workflow-enabled registradas en WorkflowRegistry.

        Args:
            dry_run: si True, detecta vencidos sin ejecutar acciones ni
                emitir señales.

        Returns:
            dict con conteo por acción {accion: n} (en dry_run cuenta las
            acciones que SE EJECUTARÍAN).
        """
        from sinpapel.models import Estado
        from sinpapel.registry import WorkflowRegistry

        conteo: dict[str, int] = {}
        estados_con_sla = Estado.objects.filter(slas__activo=True).distinct()
        if not estados_con_sla.exists():
            return conteo

        for key in WorkflowRegistry.list_keys():
            config = WorkflowRegistry.get(key)
            model = config.model
            manager = getattr(model, "objects", None)
            if manager is None:  # mocks de tests sin manager
                continue
            qs = manager.filter(
                **{f"{config.state_field}__in": estados_con_sla}
            )
            for instance in qs.iterator():
                for accion in cls.evaluar_instancia(instance, dry_run=dry_run):
                    nombre = accion.get("accion", "?")
                    conteo[nombre] = conteo.get(nombre, 0) + 1
        return conteo

    @classmethod
    def evaluar_instancia(
        cls, instance: "models.Model", dry_run: bool = False
    ) -> list[dict[str, Any]]:
        """Evalúa SLAs para una instancia específica.

        Usa el `state_field` declarado en `_workflow_config` (fallback:
        atributo ``estado``).

        Returns:
            Lista de acciones ejecutadas (o por ejecutar, en dry_run).
        """
        state_field = getattr(
            getattr(type(instance), "_workflow_config", None),
            "state_field",
            "estado",
        )
        estado_actual = getattr(instance, state_field, None)
        if estado_actual is None:
            return []

        slas = SLAConfiguracion.objects.filter(
            estado=estado_actual,
            activo=True,
        )

        ejecutadas: list[dict[str, Any]] = []
        for sla in slas:
            if cls._sla_vencida(instance, sla, emitir_signal=not dry_run):
                if dry_run:
                    ejecutadas.append({
                        "accion": sla.accion_vencimiento,
                        "dry_run": True,
                    })
                    continue
                accion = cls._ejecutar_accion(instance, sla)
                if accion:
                    ejecutadas.append(accion)
        return ejecutadas

    # ─── Detección de vencimiento ──────────────────────────────────────────

    @classmethod
    def _fecha_referencia(cls, instance: "models.Model"):
        """Inicio del conteo: última transición registrada, o `creado`.

        El SLA mide tiempo EN EL ESTADO ACTUAL, no edad de la instancia:
        la referencia es la fecha del último SeguimientoWorkflow del target.
        Sin historial (instancia recién creada o mock de tests), cae a
        `creado`.
        """
        from django.db import models as django_models

        if isinstance(instance, django_models.Model) and instance.pk is not None:
            from django.contrib.contenttypes.models import ContentType

            from sinpapel.models import SeguimientoWorkflow

            content_type = ContentType.objects.get_for_model(type(instance))
            ultima = (
                SeguimientoWorkflow.objects.filter(
                    target_content_type=content_type,
                    target_object_id=instance.pk,
                )
                .order_by("-fecha_accion")
                .values_list("fecha_accion", flat=True)
                .first()
            )
            if ultima is not None:
                return ultima
        return getattr(instance, "creado", None)

    @classmethod
    def _sla_vencida(
        cls,
        instance: "models.Model",
        sla: SLAConfiguracion,
        emitir_signal: bool = True,
    ) -> bool:
        """Determina si el SLA está vencido para la instancia.

        Emite la señal `sinpapel.signals.sla_breached` cuando detecta una
        instancia vencida (antes de ejecutar la acción asociada), salvo que
        emitir_signal sea False (dry-run).
        """
        from sinpapel.signals import sla_breached

        referencia = cls._fecha_referencia(instance)
        if referencia is None:
            return False
        limite = referencia + timedelta(days=sla.dias_maximos)
        ahora = timezone.now()
        if ahora <= limite:
            return False
        dias_transcurridos = (ahora - referencia).days
        if emitir_signal:
            sla_breached.send_robust(
                sender=type(instance),
                target=instance,
                sla=sla,
                dias_transcurridos=dias_transcurridos,
            )
        return True

    # ─── Dispatch de acciones ──────────────────────────────────────────────

    @classmethod
    def _ejecutar_accion(
        cls, instance: "models.Model", sla: SLAConfiguracion
    ) -> dict[str, Any] | None:
        """Ejecuta la acción configurada del SLA.

        Emite la señal `sinpapel.signals.sla_action_executed` después de
        ejecutar un handler `_accion_*`.
        """
        from sinpapel.signals import sla_action_executed

        handler = getattr(cls, f"_accion_{sla.accion_vencimiento}", None)
        if handler is None:
            return None
        resultado = handler(instance, sla.configuracion_accion)
        if resultado is not None:
            sla_action_executed.send_robust(
                sender=type(instance),
                target=instance,
                sla=sla,
                accion=sla.accion_vencimiento,
                resultado=resultado,
            )
        return resultado

    @classmethod
    def _system_user(cls):
        """User de sistema para transiciones automáticas (escalar/rechazar).

        Configurable vía SINPAPEL_SLA_SYSTEM_USER (username). Debe tener
        permiso para las transiciones automáticas (superuser o grupos).
        """
        from django.contrib.auth import get_user_model

        username = getattr(settings, "SINPAPEL_SLA_SYSTEM_USER", None)
        if not username:
            return None
        return get_user_model().objects.filter(username=username).first()

    @classmethod
    def _accion_notificar(cls, instance: "models.Model", config: dict) -> dict[str, Any]:
        """Despacha la notificación al handler configurado.

        SINPAPEL_SLA_NOTIFY_HANDLER (dotted path, opcional): callable
        ``handler(instance, descriptor)`` que envía la notificación real
        (email, chat, webhook…). Sin handler, se loggea el vencimiento.
        """
        grupo_id = config.get("grupo_id")
        grupo = Group.objects.filter(id=grupo_id).first()
        descriptor: dict[str, Any] = {
            "accion": "notificar",
            "grupo": grupo.name if grupo else None,
            "template": config.get("template"),
        }

        handler_path = getattr(settings, "SINPAPEL_SLA_NOTIFY_HANDLER", None)
        if handler_path:
            from django.utils.module_loading import import_string

            try:
                import_string(handler_path)(instance, descriptor)
                descriptor["notificado"] = True
            except Exception:
                logger.exception(
                    "SLA notificar: handler '%s' falló para %s pk=%s",
                    handler_path,
                    type(instance).__name__,
                    getattr(instance, "pk", "?"),
                )
                descriptor["notificado"] = False
        else:
            logger.info(
                "SLA vencido (notificar) para %s pk=%s → grupo=%s "
                "(sin SINPAPEL_SLA_NOTIFY_HANDLER configurado)",
                type(instance).__name__,
                getattr(instance, "pk", "?"),
                descriptor["grupo"],
            )
            descriptor["notificado"] = False
        return descriptor

    @classmethod
    def _transicionar(
        cls, instance: "models.Model", config: dict, accion: str
    ) -> dict[str, Any]:
        """Común a escalar/rechazar: transición automática a estado_destino."""
        estado_destino = config.get("estado_destino")
        resultado: dict[str, Any] = {
            "accion": accion,
            "estado_destino": estado_destino,
            "ejecutado": False,
        }
        if not estado_destino:
            resultado["error"] = "configuracion_accion sin 'estado_destino'"
            return resultado

        user = cls._system_user()
        if user is None:
            resultado["error"] = (
                "SINPAPEL_SLA_SYSTEM_USER no configurado o el username no existe"
            )
            logger.warning(
                "SLA %s: no se puede transicionar %s pk=%s sin usuario de "
                "sistema (SINPAPEL_SLA_SYSTEM_USER).",
                accion,
                type(instance).__name__,
                getattr(instance, "pk", "?"),
            )
            return resultado

        from sinpapel.services.workflow_engine import WorkflowEngine

        try:
            WorkflowEngine().cambiar_estado(
                instance=instance,
                target_state_name=estado_destino,
                user=user,
                comentarios=(
                    f"Transición automática ({accion}) por vencimiento de SLA."
                ),
            )
            resultado["ejecutado"] = True
        except Exception as exc:
            logger.exception(
                "SLA %s: transición automática a '%s' falló para %s pk=%s",
                accion,
                estado_destino,
                type(instance).__name__,
                getattr(instance, "pk", "?"),
            )
            resultado["error"] = str(exc)
        return resultado

    @classmethod
    def _accion_escalar(cls, instance: "models.Model", config: dict) -> dict[str, Any]:
        """Ejecuta la transición automática de escalamiento."""
        return cls._transicionar(instance, config, "escalar")

    @classmethod
    def _accion_rechazar(cls, instance: "models.Model", config: dict) -> dict[str, Any]:
        """Ejecuta la transición automática de rechazo."""
        return cls._transicionar(instance, config, "rechazar")

    @classmethod
    def _accion_alertar(cls, instance: "models.Model", config: dict) -> dict[str, Any]:
        """Activa bandera en la instancia y la persiste."""
        from django.db import models as django_models

        campo = config.get("campo")
        valor = config.get("valor")
        persistido = False
        if campo and hasattr(instance, campo):
            setattr(instance, campo, valor)
            if (
                isinstance(instance, django_models.Model)
                and instance.pk is not None
            ):
                try:
                    instance.save(update_fields=[campo])
                    persistido = True
                except Exception:
                    logger.exception(
                        "SLA alertar: no se pudo persistir '%s' en %s pk=%s",
                        campo,
                        type(instance).__name__,
                        instance.pk,
                    )
        return {
            "accion": "alertar",
            "campo": campo,
            "valor": valor,
            "persistido": persistido,
        }
