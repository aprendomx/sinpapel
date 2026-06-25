"""Defecto B — @workflow_enabled inyecta preview_transition en la instancia."""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User

from sinpapel.services.workflow_engine import WorkflowEngine


@pytest.mark.django_db
def test_instance_preview_transition_matches_engine():
    """instance.preview_transition(target, user) existe y devuelve el mismo dict
    que WorkflowEngine().preview_transition(instance, target, user)."""
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo
    from tests.models import TestSolicitud

    estado_origen = Estado.objects.create(nombre="INJ_ORIG", activo=True)
    estado_destino = Estado.objects.create(nombre="INJ_DEST", activo=True)
    flujo = VersionFlujo.objects.create(nombre="INJ_FLUJO", activo=True)
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino
    )
    solicitud = TestSolicitud.objects.create(folio="INJ-001", estado=estado_origen)
    user = User.objects.create_superuser("inj_super", password="x")

    assert hasattr(solicitud, "preview_transition")

    via_instance = solicitud.preview_transition("INJ_DEST", user)
    via_engine = WorkflowEngine().preview_transition(solicitud, "INJ_DEST", user)

    assert via_instance == via_engine
    assert via_instance["permitido"] is True
