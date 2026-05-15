"""Tests for SLA (State Timers)."""
from __future__ import annotations

import pytest

from sinpapel.models import Estado
from sinpapel.models.sla import SLAConfiguracion


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
