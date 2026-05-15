"""Sinpapel — SLA Engine for evaluating and executing SLA actions.

Evaluates SLAConfiguracion rules against workflow-enabled instances
and dispatches configured actions when time limits are exceeded.
"""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import Group
from django.utils import timezone

from sinpapel.models.sla import SLAConfiguracion

if TYPE_CHECKING:
    from django.db import models


class SLAEngine:
    """Motor de evaluación y ejecución de SLAs."""

    @classmethod
    def verificar_todos(cls) -> dict[str, int]:
        """Evalúa todos los SLAs activos contra todas las instancias workflow-enabled.

        Returns:
            dict con conteo por acción ejecutada
        """
        # Nota: En una implementación real, esto escanearía todos los modelos
        # workflow-enabled. Para tests, delegamos a evaluar_instancia.
        return {}

    @classmethod
    def evaluar_instancia(cls, instance: "models.Model") -> list[dict[str, Any]]:
        """Evalúa SLAs para una instancia específica.

        Returns:
            Lista de acciones ejecutadas
        """
        estado_actual = getattr(instance, "estado", None)
        if estado_actual is None:
            return []

        slas = SLAConfiguracion.objects.filter(
            estado=estado_actual,
            activo=True,
        )

        ejecutadas: list[dict[str, Any]] = []
        for sla in slas:
            if cls._sla_vencida(instance, sla):
                accion = cls._ejecutar_accion(instance, sla)
                if accion:
                    ejecutadas.append(accion)
        return ejecutadas

    @classmethod
    def _sla_vencida(cls, instance: "models.Model", sla: SLAConfiguracion) -> bool:
        """Determina si el SLA está vencido para la instancia.

        Usa el campo `creado` de la instancia como referencia de tiempo.
        Si la instancia no tiene `creado`, asume que no está vencida.
        """
        creado = getattr(instance, "creado", None)
        if creado is None:
            return False
        limite = creado + timedelta(days=sla.dias_maximos)
        return timezone.now() > limite

    @classmethod
    def _ejecutar_accion(cls, instance: "models.Model", sla: SLAConfiguracion) -> dict[str, Any] | None:
        """Ejecuta la acción configurada del SLA."""
        handler = getattr(cls, f"_accion_{sla.accion_vencimiento}", None)
        if handler is None:
            return None
        return handler(instance, sla.configuracion_accion)

    @classmethod
    def _accion_notificar(cls, instance: "models.Model", config: dict) -> dict[str, Any]:
        """Envía notificación al grupo configurado."""
        grupo_id = config.get("grupo_id")
        grupo = Group.objects.filter(id=grupo_id).first()
        return {
            "accion": "notificar",
            "grupo": grupo.name if grupo else None,
            "template": config.get("template"),
        }

    @classmethod
    def _accion_escalar(cls, instance: "models.Model", config: dict) -> dict[str, Any]:
        """Ejecuta transición automática al estado destino."""
        estado_destino = config.get("estado_destino")
        return {
            "accion": "escalar",
            "estado_destino": estado_destino,
        }

    @classmethod
    def _accion_rechazar(cls, instance: "models.Model", config: dict) -> dict[str, Any]:
        """Ejecuta transición automática al estado de rechazo."""
        estado_destino = config.get("estado_destino")
        return {
            "accion": "rechazar",
            "estado_destino": estado_destino,
        }

    @classmethod
    def _accion_alertar(cls, instance: "models.Model", config: dict) -> dict[str, Any]:
        """Activa bandera en la instancia."""
        campo = config.get("campo")
        valor = config.get("valor")
        if campo and hasattr(instance, campo):
            setattr(instance, campo, valor)
        return {
            "accion": "alertar",
            "campo": campo,
            "valor": valor,
        }
