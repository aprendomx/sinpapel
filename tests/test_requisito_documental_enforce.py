"""Defecto A — RequisitoEstadoDocumento se enforce en la transición.

El motor debe evaluar las reglas finas (tipo_documento + porcentaje mínimo)
de RequisitoEstadoDocumento, además del flag coarse expediente_obligatorio.

Fuente de "documento presente por tipo": InstanciaDocumento (liga tipo vía
documento.tipo_documento y la instancia vía la GFK target). El porcentaje
actual sale del nuevo campo InstanciaDocumento.porcentaje (default 100).
auto_carga=True ⇒ no bloquea (documento generado por el sistema).
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User

from sinpapel.services.workflow_engine import WorkflowEngine


@pytest.fixture
def flujo_con_requisito(db):
    """Estado origen→destino con un RequisitoEstadoDocumento(INE, 100%) en origen."""
    from sinpapel.models import (
        ConfiguracionTransicion,
        Documento,
        Estado,
        RequisitoEstadoDocumento,
        TipoDocumento,
        VersionFlujo,
    )
    from tests.models import TestSolicitud

    origen = Estado.objects.create(nombre="REQ_ORIGEN", activo=True)
    destino = Estado.objects.create(nombre="REQ_DESTINO", activo=True)
    flujo = VersionFlujo.objects.create(nombre="REQ_FLUJO", activo=True)
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=origen, estado_destino=destino
    )
    tipo_ine = TipoDocumento.objects.create(nombre="INE", activo=True)
    documento = Documento.objects.create(
        nombre="INE", tipo_documento=tipo_ine, valor="INE"
    )
    requisito = RequisitoEstadoDocumento.objects.create(
        estado=origen, tipo_documento=tipo_ine, porcentaje=100
    )
    solicitud = TestSolicitud.objects.create(folio="REQ-001", estado=origen)
    return {
        "origen": origen,
        "destino": destino,
        "flujo": flujo,
        "tipo_ine": tipo_ine,
        "documento": documento,
        "requisito": requisito,
        "solicitud": solicitud,
    }


@pytest.mark.django_db
def test_requisito_faltante_bloquea_preview(flujo_con_requisito):
    """Sin el documento, preview reporta el requisito como faltante y bloquea."""
    user = User.objects.create_superuser("req_super1", password="x")
    preview = WorkflowEngine().preview_transition(
        flujo_con_requisito["solicitud"], "REQ_DESTINO", user
    )

    assert preview["permitido"] is False
    faltantes = preview["documentos_faltantes"]
    assert any(
        f.get("tipo") == "requisito_documento"
        and f.get("tipo_documento") == "INE"
        and f.get("porcentaje_requerido") == 100
        and f.get("porcentaje_actual") == 0
        for f in faltantes
    ), faltantes


@pytest.mark.django_db
def test_requisito_faltante_raises_permission_error(flujo_con_requisito):
    """cambiar_estado lanza PermissionError cuando falta el requisito documental."""
    user = User.objects.create_superuser("req_super2", password="x")
    with pytest.raises(PermissionError):
        WorkflowEngine().cambiar_estado(
            instance=flujo_con_requisito["solicitud"],
            target_state_name="REQ_DESTINO",
            user=user,
            comentarios="x",
        )


@pytest.mark.django_db
def test_requisito_satisfecho_permite(flujo_con_requisito):
    """Con InstanciaDocumento del tipo al 100%, la transición se permite."""
    from sinpapel.models import InstanciaDocumento

    InstanciaDocumento.objects.create(
        documento=flujo_con_requisito["documento"],
        target=flujo_con_requisito["solicitud"],
        porcentaje=100,
    )
    user = User.objects.create_superuser("req_super3", password="x")
    preview = WorkflowEngine().preview_transition(
        flujo_con_requisito["solicitud"], "REQ_DESTINO", user
    )
    assert preview["permitido"] is True
    assert preview["documentos_faltantes"] == []


@pytest.mark.django_db
def test_requisito_porcentaje_insuficiente_bloquea(flujo_con_requisito):
    """Un documento presente pero por debajo del porcentaje requerido bloquea."""
    from sinpapel.models import InstanciaDocumento

    InstanciaDocumento.objects.create(
        documento=flujo_con_requisito["documento"],
        target=flujo_con_requisito["solicitud"],
        porcentaje=60,
    )
    user = User.objects.create_superuser("req_super4", password="x")
    preview = WorkflowEngine().preview_transition(
        flujo_con_requisito["solicitud"], "REQ_DESTINO", user
    )
    assert preview["permitido"] is False
    faltante = next(
        f for f in preview["documentos_faltantes"]
        if f.get("tipo") == "requisito_documento"
    )
    assert faltante["porcentaje_actual"] == 60
    assert faltante["porcentaje_requerido"] == 100


@pytest.mark.django_db
def test_requisito_auto_carga_no_bloquea(flujo_con_requisito):
    """auto_carga=True ⇒ el requisito no bloquea (lo genera el sistema)."""
    requisito = flujo_con_requisito["requisito"]
    requisito.auto_carga = True
    requisito.save()

    user = User.objects.create_superuser("req_super5", password="x")
    preview = WorkflowEngine().preview_transition(
        flujo_con_requisito["solicitud"], "REQ_DESTINO", user
    )
    assert preview["permitido"] is True
    assert preview["documentos_faltantes"] == []


@pytest.mark.django_db
def test_default_porcentaje_es_100_backward_compat(flujo_con_requisito):
    """InstanciaDocumento sin porcentaje explícito cuenta como 100% (backward-compat)."""
    from sinpapel.models import InstanciaDocumento

    inst = InstanciaDocumento.objects.create(
        documento=flujo_con_requisito["documento"],
        target=flujo_con_requisito["solicitud"],
    )
    assert inst.porcentaje == 100

    user = User.objects.create_superuser("req_super6", password="x")
    preview = WorkflowEngine().preview_transition(
        flujo_con_requisito["solicitud"], "REQ_DESTINO", user
    )
    assert preview["permitido"] is True


@pytest.mark.django_db
def test_sin_requisitos_se_comporta_igual(flujo_con_requisito):
    """Regresión: sin requisitos documentales, la transición no se bloquea por docs."""
    flujo_con_requisito["requisito"].delete()
    user = User.objects.create_superuser("req_super7", password="x")
    preview = WorkflowEngine().preview_transition(
        flujo_con_requisito["solicitud"], "REQ_DESTINO", user
    )
    assert preview["permitido"] is True
    assert preview["documentos_faltantes"] == []


@pytest.mark.django_db
def test_expediente_obligatorio_coarse_sigue_funcionando():
    """Regresión: el flag coarse expediente_obligatorio sigue bloqueando."""
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo
    from tests.models import TestSolicitud

    origen = Estado.objects.create(
        nombre="EXP_ORIGEN", activo=True, expediente_obligatorio=True
    )
    destino = Estado.objects.create(nombre="EXP_DESTINO", activo=True)
    flujo = VersionFlujo.objects.create(nombre="EXP_FLUJO", activo=True)
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=origen, estado_destino=destino
    )
    solicitud = TestSolicitud.objects.create(folio="EXP-001", estado=origen)
    user = User.objects.create_superuser("exp_super", password="x")

    preview = WorkflowEngine().preview_transition(solicitud, "EXP_DESTINO", user)
    assert preview["permitido"] is False
    assert any(f.get("tipo") == "expediente" for f in preview["documentos_faltantes"])
