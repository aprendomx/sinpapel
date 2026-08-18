"""Tests 0.8.0 — SLA con acciones reales y tiempo-en-estado.

Cubre lo que la auditoría encontró como stub:
- escalar/rechazar ejecutan la transición automática (usuario de sistema),
- alertar persiste la bandera con save(update_fields),
- verificar_todos escanea el WorkflowRegistry de verdad,
- el plazo se mide como tiempo EN EL ESTADO, no edad de la instancia,
- --dry-run no ejecuta acciones.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from sinpapel.services.sla_engine import SLAEngine


@pytest.fixture
def setup_sla(db, settings):
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo
    from sinpapel.models.sla import SLAConfiguracion
    from tests.models import TestProducto, TestSolicitud

    origen = Estado.objects.create(nombre="SLAR_ORIGEN")
    escalado = Estado.objects.create(nombre="SLAR_ESCALADO")
    flujo = VersionFlujo.objects.create(nombre="SLAR_FLUJO", activo=True)
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=origen, estado_destino=escalado
    )
    producto = TestProducto.objects.create(nombre="SLAR_P", flujo=flujo)
    solicitud = TestSolicitud.objects.create(
        estado=origen, producto=producto, folio="SLAR-001"
    )
    # Instancia "vieja": 3 días en el estado inicial
    TestSolicitud.objects.filter(pk=solicitud.pk).update(
        creado=timezone.now() - timedelta(days=3)
    )
    solicitud.refresh_from_db()

    User.objects.create_superuser("sla_bot", password="x")
    settings.SINPAPEL_SLA_SYSTEM_USER = "sla_bot"

    sla = SLAConfiguracion.objects.create(
        estado=origen,
        dias_maximos=1,
        accion_vencimiento="escalar",
        configuracion_accion={"estado_destino": "SLAR_ESCALADO"},
    )
    return {
        "solicitud": solicitud,
        "origen": origen,
        "escalado": escalado,
        "sla": sla,
    }


@pytest.mark.django_db
def test_escalar_ejecuta_transicion_automatica(setup_sla):
    from sinpapel.models import SeguimientoWorkflow

    conteo = SLAEngine.verificar_todos()
    assert conteo.get("escalar") == 1

    solicitud = setup_sla["solicitud"]
    solicitud.refresh_from_db()
    assert solicitud.estado == setup_sla["escalado"], (
        "escalar debe ejecutar la transición, no solo describirla"
    )
    seg = SeguimientoWorkflow.objects.get(
        target_object_id=solicitud.pk,
        estado_nuevo=setup_sla["escalado"],
    )
    assert "automática" in seg.comentarios
    assert seg.usuario_accion.username == "sla_bot"


@pytest.mark.django_db
def test_escalar_sin_system_user_no_transiciona(setup_sla, settings):
    settings.SINPAPEL_SLA_SYSTEM_USER = None
    resultado = SLAEngine.evaluar_instancia(setup_sla["solicitud"])
    assert resultado[0]["ejecutado"] is False
    assert "SINPAPEL_SLA_SYSTEM_USER" in resultado[0]["error"]
    setup_sla["solicitud"].refresh_from_db()
    assert setup_sla["solicitud"].estado == setup_sla["origen"]


@pytest.mark.django_db
def test_dry_run_no_ejecuta_ni_emite(setup_sla):
    from sinpapel.signals import sla_breached

    señales = []

    def _receiver(**kwargs):
        señales.append(kwargs)

    sla_breached.connect(_receiver)
    try:
        conteo = SLAEngine.verificar_todos(dry_run=True)
    finally:
        sla_breached.disconnect(_receiver)

    assert conteo.get("escalar") == 1
    setup_sla["solicitud"].refresh_from_db()
    assert setup_sla["solicitud"].estado == setup_sla["origen"], (
        "dry_run no debe transicionar"
    )
    assert señales == [], "dry_run no debe emitir sla_breached"


@pytest.mark.django_db
def test_plazo_mide_tiempo_en_estado_no_edad(setup_sla):
    """Instancia vieja pero recién transicionada: NO vencida."""
    from sinpapel.models import SeguimientoWorkflow
    from sinpapel.models.sla import SLAConfiguracion

    solicitud = setup_sla["solicitud"]
    bot = User.objects.get(username="sla_bot")

    # Transiciona hoy → el reloj del SLA del estado nuevo arranca hoy
    solicitud.transition("SLAR_ESCALADO", bot)
    SLAConfiguracion.objects.create(
        estado=setup_sla["escalado"],
        dias_maximos=1,
        accion_vencimiento="alertar",
        configuracion_accion={"campo": "alerta_sla", "valor": True},
    )

    # Edad de la instancia: 3 días. Tiempo en SLAR_ESCALADO: segundos.
    assert SLAEngine.evaluar_instancia(solicitud) == [], (
        "el SLA debe medir tiempo-en-estado (desde la última transición), "
        "no la edad de la instancia"
    )

    # Envejecer la transición 2 días → ahora sí vence
    SeguimientoWorkflow.objects.filter(target_object_id=solicitud.pk).update(
        fecha_accion=timezone.now() - timedelta(days=2)
    )
    acciones = SLAEngine.evaluar_instancia(solicitud)
    assert acciones and acciones[0]["accion"] == "alertar"


@pytest.mark.django_db
def test_alertar_persiste_bandera(setup_sla):
    from sinpapel.models.sla import SLAConfiguracion

    setup_sla["sla"].delete()
    SLAConfiguracion.objects.create(
        estado=setup_sla["origen"],
        dias_maximos=1,
        accion_vencimiento="alertar",
        configuracion_accion={"campo": "alerta_sla", "valor": True},
    )

    resultado = SLAEngine.evaluar_instancia(setup_sla["solicitud"])
    assert resultado[0]["persistido"] is True

    recargada = type(setup_sla["solicitud"]).objects.get(
        pk=setup_sla["solicitud"].pk
    )
    assert recargada.alerta_sla is True, "la bandera debe persistir en BD"
