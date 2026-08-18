"""Tests de regresión — fixes de auditoría 0.7.1.

Cubre:
1. historial_reciente con contenido real (bug GFK filter → siempre []).
2. Revalidación bajo lock: una copia stale no puede duplicar la transición.
3. instance.available_transitions respeta el VersionFlujo resuelto.
4. Side effects se ejecutan post-commit (fuera de la transacción del motor).
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.db import transaction

from sinpapel.services.side_effects import SIDE_EFFECTS


@pytest.fixture
def setup_reg(db):
    """Estado ORIGEN→DESTINO en un flujo activo, con producto→flujo."""
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo
    from tests.models import TestProducto, TestSolicitud

    origen, _ = Estado.objects.get_or_create(nombre="REG_ORIGEN")
    destino, _ = Estado.objects.get_or_create(nombre="REG_DESTINO")
    flujo = VersionFlujo.objects.create(nombre="REG_FLUJO", activo=True)
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=origen, estado_destino=destino
    )
    # Regreso configurado para poder previsualizar desde REG_DESTINO
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=destino, estado_destino=origen
    )
    producto = TestProducto.objects.create(nombre="REG_P", flujo=flujo)
    solicitud = TestSolicitud.objects.create(
        estado=origen, producto=producto, folio="REG-001"
    )
    return {
        "solicitud": solicitud,
        "origen": origen,
        "destino": destino,
        "flujo": flujo,
    }


@pytest.mark.django_db
def test_historial_reciente_contiene_transiciones(setup_reg):
    """preview_transition debe reportar el historial real del target (no [])."""
    superuser = User.objects.create_superuser("reg_hist", password="x")
    solicitud = setup_reg["solicitud"]

    solicitud.transition("REG_DESTINO", superuser, comentarios="primera")

    preview = solicitud.preview_transition("REG_ORIGEN", superuser)
    historial = preview["historial_reciente"]
    assert len(historial) == 1
    assert historial[0]["transicion"] == "REG_ORIGEN → REG_DESTINO"
    assert historial[0]["usuario"] == "reg_hist"
    assert historial[0]["comentarios"] == "primera"


@pytest.mark.django_db
def test_historial_reciente_no_mezcla_targets(setup_reg):
    """El historial es del target consultado, no de otras instancias."""
    from tests.models import TestSolicitud

    superuser = User.objects.create_superuser("reg_hist2", password="x")
    setup_reg["solicitud"].transition("REG_DESTINO", superuser)

    otra = TestSolicitud.objects.create(
        estado=setup_reg["origen"],
        producto=setup_reg["solicitud"].producto,
        folio="REG-002",
    )
    preview = otra.preview_transition("REG_DESTINO", superuser)
    assert preview["historial_reciente"] == []


@pytest.mark.django_db
def test_copia_stale_no_puede_duplicar_transicion(setup_reg):
    """Dos copias en memoria: la segunda (stale) debe revalidar contra DB."""
    from sinpapel.models import SeguimientoWorkflow
    from tests.models import TestSolicitud

    superuser = User.objects.create_superuser("reg_stale", password="x")
    fresca = setup_reg["solicitud"]
    stale = TestSolicitud.objects.get(pk=fresca.pk)

    fresca.transition("REG_DESTINO", superuser)

    # La copia stale aún cree estar en REG_ORIGEN; el motor debe re-leer
    # el estado bajo lock y rechazar (DESTINO→DESTINO no está configurada).
    with pytest.raises(PermissionError):
        stale.transition("REG_DESTINO", superuser)

    assert (
        SeguimientoWorkflow.objects.filter(
            target_object_id=fresca.pk,
            estado_nuevo=setup_reg["destino"],
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_available_transitions_respeta_flujo(setup_reg):
    """instance.available_transitions filtra por el VersionFlujo resuelto."""
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo

    user = User.objects.create_user("reg_avail", password="x")
    otro_destino, _ = Estado.objects.get_or_create(nombre="REG_OTRO_DESTINO")
    otro_flujo = VersionFlujo.objects.create(nombre="REG_FLUJO_V2", activo=False)
    ConfiguracionTransicion.objects.create(
        flujo=otro_flujo,
        estado_origen=setup_reg["origen"],
        estado_destino=otro_destino,
    )

    destinos = setup_reg["solicitud"].available_transitions(user)
    assert setup_reg["destino"] in destinos
    assert otro_destino not in destinos, (
        "available_transitions no debe incluir transiciones de otros flujos"
    )


@pytest.mark.django_db(transaction=True)
def test_side_effects_corren_post_commit(setup_reg, sinpapel_migrated):
    """El handler de side effect debe ejecutarse fuera de la transacción."""
    superuser = User.objects.create_superuser("reg_se", password="x")
    observado: dict = {}

    def _handler(instance, usuario, **kwargs):
        observado["in_atomic_block"] = transaction.get_connection().in_atomic_block
        return {"observado": True}

    SIDE_EFFECTS["REG_DESTINO"] = _handler
    try:
        result = setup_reg["solicitud"].transition("REG_DESTINO", superuser)
    finally:
        SIDE_EFFECTS.pop("REG_DESTINO", None)

    assert result["observado"] is True
    assert observado["in_atomic_block"] is False, (
        "el side effect corrió dentro de la transacción del motor"
    )
