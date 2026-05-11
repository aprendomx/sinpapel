"""S13.1 — Tests integración cache + WorkflowEngine.

Verifica que la migration de T2 produce cache effectivos en runtime — no
solo en tests aislados de helpers (T1). Ejecuta 2 invocaciones consecutivas
del engine sobre la misma solicitud y mide queries SQL diff.
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test import override_settings


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_workflow_engine_uses_cache_in_consecutive_transitions():
    """S13.1 AC2 E2E: 2da llamada a available_transitions usa cache."""
    from creditos.models import (
        ProductoCreditoFOVISSSTE,
        ProductoVersionFlujo,
        Solicitud,
    )
    from sinpapel.cache import clear_all
    from sinpapel.models import (
        ConfiguracionTransicion,
        Estado,
        VersionFlujo,
    )
    from sinpapel.services.workflow_engine import WorkflowEngine

    # Setup mínimo (similar a setup_engine_basico fixture)
    estado_origen, _ = Estado.objects.get_or_create(nombre="CACHE_INT_ORIGEN")
    estado_destino, _ = Estado.objects.get_or_create(nombre="CACHE_INT_DESTINO")
    flujo = VersionFlujo.objects.create(nombre="CACHE_INT_FLUJO", activo=True)
    ConfiguracionTransicion.objects.create(
        flujo=flujo,
        estado_origen=estado_origen,
        estado_destino=estado_destino,
    )
    producto = ProductoCreditoFOVISSSTE.objects.create(
        nombre="CACHE_INT_P",
        clave="CACHE-INT-P",
        identificador="C",
        marca="C",
        monto_minimo=0,
        monto_maximo=0,
        tasa_interes=0,
        tasa_interes_moratorio=0,
    )
    ProductoVersionFlujo.objects.create(producto=producto, flujo=flujo)
    solicitud = Solicitud.objects.create(estado=estado_origen, producto=producto)
    user = User.objects.create_user("cache_int_user", password="x")

    engine = WorkflowEngine()

    # Clear cache para garantizar 1ra llamada hit DB
    clear_all()

    # 1ra llamada — debería ejecutar queries SQL para flujo + transitions
    n0 = len(connection.queries)
    states_first = engine.available_transitions(solicitud, user)
    queries_first = len(connection.queries) - n0
    assert states_first == [estado_destino]
    assert queries_first > 0, "First call should hit DB"

    # 2da llamada — debería ser cache hit (0 queries para transitions)
    # Nota: solicitud.estado access puede generar 1 query si no está cached;
    # por eso usamos la fixture solicitud reusada (estado ya cargado).
    n1 = len(connection.queries)
    states_second = engine.available_transitions(solicitud, user)
    queries_second = len(connection.queries) - n1

    # 2da llamada debe ser ESTRICTAMENTE menos queries que la 1ra
    assert queries_second < queries_first, (
        f"Cache should reduce queries: 1st={queries_first}, 2nd={queries_second}"
    )
    assert states_second == states_first
