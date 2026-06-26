"""Mecanismo público WorkflowEngine.evaluar_requisitos_documentales.

Devuelve TODOS los requisitos documentales del estado (no solo faltantes), con
su estado de cumplimiento. Lo consumen el engine (_validar_documentos como
wrapper) y sinpapel-drf (GET /requisitos/), sin duplicar lógica.
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User

from sinpapel.services.workflow_engine import WorkflowEngine


@pytest.fixture
def flujo_con_requisito(db):
    from sinpapel.models import (
        ConfiguracionTransicion,
        Documento,
        Estado,
        RequisitoEstadoDocumento,
        TipoDocumento,
        VersionFlujo,
    )
    from tests.models import TestSolicitud

    origen = Estado.objects.create(nombre="EVR_ORIGEN", activo=True)
    destino = Estado.objects.create(nombre="EVR_DESTINO", activo=True)
    flujo = VersionFlujo.objects.create(nombre="EVR_FLUJO", activo=True)
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
    solicitud = TestSolicitud.objects.create(folio="EVR-001", estado=origen)
    return {
        "origen": origen, "tipo_ine": tipo_ine,
        "documento": documento, "requisito": requisito, "solicitud": solicitud,
    }


@pytest.mark.django_db
def test_typed_faltante_shape_completa(flujo_con_requisito):
    user = User.objects.create_superuser("evr1", password="x")
    items = WorkflowEngine().evaluar_requisitos_documentales(
        flujo_con_requisito["solicitud"]
    )
    ine = next(i for i in items if i.get("tipo_documento") == "INE")
    assert ine["nivel"] == "requisito_documento"
    assert ine["satisfecho"] is False
    assert ine["porcentaje_requerido"] == 100
    assert ine["porcentaje_actual"] == 0
    assert ine["auto_carga"] is False
    assert ine["tipo_documento_id"] == flujo_con_requisito["tipo_ine"].id
    assert ine["mensaje"]


@pytest.mark.django_db
def test_typed_satisfecho(flujo_con_requisito):
    from sinpapel.models import InstanciaDocumento

    InstanciaDocumento.objects.create(
        documento=flujo_con_requisito["documento"],
        target=flujo_con_requisito["solicitud"], porcentaje=100,
    )
    items = WorkflowEngine().evaluar_requisitos_documentales(
        flujo_con_requisito["solicitud"]
    )
    ine = next(i for i in items if i.get("tipo_documento") == "INE")
    assert ine["satisfecho"] is True
    assert ine["porcentaje_actual"] == 100


@pytest.mark.django_db
def test_typed_insuficiente(flujo_con_requisito):
    from sinpapel.models import InstanciaDocumento

    InstanciaDocumento.objects.create(
        documento=flujo_con_requisito["documento"],
        target=flujo_con_requisito["solicitud"], porcentaje=60,
    )
    items = WorkflowEngine().evaluar_requisitos_documentales(
        flujo_con_requisito["solicitud"]
    )
    ine = next(i for i in items if i.get("tipo_documento") == "INE")
    assert ine["satisfecho"] is False
    assert ine["porcentaje_actual"] == 60


@pytest.mark.django_db
def test_auto_carga_satisfecho(flujo_con_requisito):
    requisito = flujo_con_requisito["requisito"]
    requisito.auto_carga = True
    requisito.save()
    items = WorkflowEngine().evaluar_requisitos_documentales(
        flujo_con_requisito["solicitud"]
    )
    ine = next(i for i in items if i.get("tipo_documento") == "INE")
    assert ine["satisfecho"] is True
    assert ine["auto_carga"] is True


@pytest.mark.django_db
def test_coarse_expediente_obligatorio():
    from sinpapel.models import Estado
    from tests.models import TestSolicitud

    estado = Estado.objects.create(
        nombre="EVR_EXP", activo=True, expediente_obligatorio=True
    )
    sol = TestSolicitud.objects.create(folio="EVR-EXP", estado=estado)
    items = WorkflowEngine().evaluar_requisitos_documentales(sol)
    exp = next(i for i in items if i["nivel"] == "expediente")
    assert exp["satisfecho"] is False
    assert exp["mensaje"]


@pytest.mark.django_db
def test_estado_explicito(flujo_con_requisito):
    """Pasar estado explícito evalúa ese estado, no el actual."""
    items = WorkflowEngine().evaluar_requisitos_documentales(
        flujo_con_requisito["solicitud"], estado=flujo_con_requisito["origen"]
    )
    assert any(i.get("tipo_documento") == "INE" for i in items)
