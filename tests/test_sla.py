"""Tests for SLA (State Timers)."""
from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.utils import timezone

from sinpapel.models import Estado, VersionFlujo
from sinpapel.models.sla import SLAConfiguracion
from sinpapel.services.sla_engine import SLAEngine


@pytest.mark.django_db
def test_sla_model_creation():
    """SLAConfiguracion can be created and linked to Estado."""
    estado = Estado.objects.create(nombre="SLA_TEST", activo=True)
    sla = SLAConfiguracion.objects.create(
        estado=estado,
        dias_maximos=5,
        accion_vencimiento="notificar",
        configuracion_accion={"grupo_id": 1},
    )
    assert sla.estado == estado
    assert sla.dias_maximos == 5
    assert sla.accion_vencimiento == "notificar"
    assert sla.activo is True
    assert str(sla) == "SLA_TEST: 5d → notificar"


def _crear_instancia_workflow(estado):
    """Helper: crea una instancia fake workflow-enabled en el estado dado."""
    class _FakeInstance:
        _workflow_config = type("Config", (), {"state_field": "estado"})()
        alerta_sla = False
        creado = timezone.now() - timedelta(days=1)

        def resolve_workflow_version(self):
            return None

    instance = _FakeInstance()
    instance.estado = estado
    return instance


@pytest.mark.django_db
def test_sla_engine_evaluar_instancia_sin_sla():
    """Instance without SLA configs returns empty list."""
    estado = Estado.objects.create(nombre="NO_SLA", activo=True)
    instance = _crear_instancia_workflow(estado)
    result = SLAEngine.evaluar_instancia(instance)
    assert result == []


@pytest.mark.django_db
def test_sla_engine_accion_notificar():
    """Notify action sends notification to group."""
    estado = Estado.objects.create(nombre="NOTIF", activo=True)
    grupo = Group.objects.create(name="test_group")
    SLAConfiguracion.objects.create(
        estado=estado,
        dias_maximos=0,  # vencido inmediatamente
        accion_vencimiento="notificar",
        configuracion_accion={"grupo_id": grupo.id, "template": "sla_vencido"},
    )
    instance = _crear_instancia_workflow(estado)
    result = SLAEngine.evaluar_instancia(instance)
    assert len(result) == 1
    assert result[0]["accion"] == "notificar"
    assert result[0]["grupo"] == "test_group"


@pytest.mark.django_db
def test_sla_engine_accion_alertar():
    """Flag action sets boolean field on instance."""
    estado = Estado.objects.create(nombre="ALERT", activo=True)
    SLAConfiguracion.objects.create(
        estado=estado,
        dias_maximos=0,
        accion_vencimiento="alertar",
        configuracion_accion={"campo": "alerta_sla", "valor": True},
    )
    instance = _crear_instancia_workflow(estado)
    result = SLAEngine.evaluar_instancia(instance)
    assert len(result) == 1
    assert result[0]["accion"] == "alertar"
    assert instance.alerta_sla is True


@pytest.mark.django_db
def test_sla_engine_inactive_ignored():
    """Inactive SLAs are skipped."""
    estado = Estado.objects.create(nombre="INACT", activo=True)
    SLAConfiguracion.objects.create(
        estado=estado,
        dias_maximos=0,
        accion_vencimiento="alertar",
        configuracion_accion={"campo": "alerta_sla", "valor": True},
        activo=False,
    )
    instance = _crear_instancia_workflow(estado)
    result = SLAEngine.evaluar_instancia(instance)
    assert result == []


@pytest.mark.django_db
def test_management_command_verificar_slas():
    """Command runs without errors and reports counts."""
    estado = Estado.objects.create(nombre="CMD", activo=True)
    SLAConfiguracion.objects.create(
        estado=estado,
        dias_maximos=0,
        accion_vencimiento="alertar",
        configuracion_accion={"campo": "alerta_sla", "valor": True},
    )
    out = StringIO()
    call_command("sinpapel_verificar_slas", stdout=out)
    output = out.getvalue()
    assert "SLAs verificados" in output


@pytest.mark.django_db
def test_management_command_dry_run():
    """Dry run reports but does not execute actions."""
    estado = Estado.objects.create(nombre="DRY", activo=True)
    SLAConfiguracion.objects.create(
        estado=estado,
        dias_maximos=0,
        accion_vencimiento="alertar",
        configuracion_accion={"campo": "alerta_sla", "valor": True},
    )
    out = StringIO()
    call_command("sinpapel_verificar_slas", "--dry-run", stdout=out)
    output = out.getvalue()
    assert "DRY RUN" in output


@pytest.mark.django_db
def test_sla_breach_fires_sla_breached_signal():
    """SLA vencida → sinpapel.signals.sla_breached is sent before action."""
    from sinpapel.signals import sla_breached
    from tests.models import TestSolicitud

    captured = []

    def receiver(sender, **kwargs):
        captured.append(kwargs)

    sla_breached.connect(receiver, weak=False)
    try:
        estado = Estado.objects.create(nombre="SLA_EN_REVISION", activo=True)
        sla = SLAConfiguracion.objects.create(
            estado=estado,
            dias_maximos=1,
            accion_vencimiento="alertar",
            configuracion_accion={"campo": "alerta", "valor": True},
            activo=True,
        )
        instance = TestSolicitud.objects.create(folio="SLA-B1", estado=estado)
        # Force creado backwards in time so SLA evaluates as vencida.
        TestSolicitud.objects.filter(pk=instance.pk).update(
            creado=timezone.now() - timedelta(days=5)
        )
        instance.refresh_from_db()
        SLAEngine.evaluar_instancia(instance)
    finally:
        sla_breached.disconnect(receiver)

    assert len(captured) == 1
    assert captured[0]["sla"].pk == sla.pk
    assert captured[0]["dias_transcurridos"] >= 5


@pytest.mark.django_db
def test_sla_action_dispatch_fires_sla_action_executed_signal():
    """SLAEngine._ejecutar_accion → sinpapel.signals.sla_action_executed is sent."""
    from sinpapel.signals import sla_action_executed
    from tests.models import TestSolicitud

    captured = []

    def receiver(sender, **kwargs):
        captured.append(kwargs)

    sla_action_executed.connect(receiver, weak=False)
    try:
        estado = Estado.objects.create(nombre="SLA_EN_REVISION_2", activo=True)
        SLAConfiguracion.objects.create(
            estado=estado,
            dias_maximos=1,
            accion_vencimiento="alertar",
            configuracion_accion={"campo": "alerta", "valor": True},
            activo=True,
        )
        instance = TestSolicitud.objects.create(folio="SLA-A1", estado=estado)
        TestSolicitud.objects.filter(pk=instance.pk).update(
            creado=timezone.now() - timedelta(days=5)
        )
        instance.refresh_from_db()
        SLAEngine.evaluar_instancia(instance)
    finally:
        sla_action_executed.disconnect(receiver)

    assert len(captured) == 1
    assert captured[0]["accion"] == "alertar"
    assert captured[0]["resultado"]["accion"] == "alertar"
