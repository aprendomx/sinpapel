"""S13.1 — Tests para sinpapel.cache helpers + clear_all."""
from __future__ import annotations

import pytest
from django.core.cache import caches
from django.db import connection
from django.test import override_settings


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_cache_each_test():
    """Cache LocMemCache es process-wide; clear_all() entre tests evita
    interferencia entre suites."""
    from sinpapel.cache import clear_all
    clear_all()
    yield
    clear_all()


# ─────────────────────────────────────────────────────────────────────────────
# Tests: cache hit ratio (D7 TTL + connection.queries via DEBUG=True)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_estado_by_name_caches_after_first_call():
    """AC2: 2da llamada al mismo helper NO ejecuta query SQL (cache hit)."""
    from sinpapel.cache import get_estado_by_name
    from sinpapel.models import Estado

    Estado.objects.create(nombre="CACHE_FIRST_CALL_TEST")

    n0 = len(connection.queries)
    s1 = get_estado_by_name("CACHE_FIRST_CALL_TEST")
    n1 = len(connection.queries)
    assert n1 > n0, f"First call should hit DB; queries: {n1 - n0}"
    assert s1 is not None
    assert s1.nombre == "CACHE_FIRST_CALL_TEST"

    # 2da llamada: cache hit, 0 queries
    n_before = len(connection.queries)
    s2 = get_estado_by_name("CACHE_FIRST_CALL_TEST")
    n_after = len(connection.queries)
    assert n_after == n_before, (
        f"Second call should be cache hit (0 queries); was {n_after - n_before}"
    )
    assert s2 is not None
    assert s1.id == s2.id


@pytest.mark.django_db
def test_get_estado_by_name_returns_none_for_missing():
    """AC3: Estado inexistente retorna None sin raise (D1: no negative caching)."""
    from sinpapel.cache import get_estado_by_name

    result = get_estado_by_name("DEFINITELY_DOES_NOT_EXIST_XYZ_S13_1")
    assert result is None


@pytest.mark.django_db
def test_get_active_version_flujo_filters_by_active():
    """AC2+filter: get_active_version_flujo retorna solo activo=True."""
    from sinpapel.cache import get_active_version_flujo
    from sinpapel.models import VersionFlujo

    VersionFlujo.objects.create(nombre="cache_test_flujo_inactive", activo=False)
    active = VersionFlujo.objects.create(nombre="cache_test_flujo_active", activo=True)

    # Active retorna instancia
    result_active = get_active_version_flujo("cache_test_flujo_active")
    assert result_active is not None
    assert result_active.id == active.id

    # Inactive retorna None (filter activo=True)
    result_inactive = get_active_version_flujo("cache_test_flujo_inactive")
    assert result_inactive is None


@pytest.mark.django_db
def test_get_transitions_for_returns_prefetched_list():
    """AC2+prefetch: get_transitions_for retorna list con select_related (no N+1)."""
    from sinpapel.cache import get_transitions_for
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo

    flujo = VersionFlujo.objects.create(nombre="transitions_cache_test", activo=True)
    estado_origen = Estado.objects.create(nombre="ORIG_TRANS_CACHE")
    destino_a = Estado.objects.create(nombre="DEST_A_TRANS_CACHE")
    destino_b = Estado.objects.create(nombre="DEST_B_TRANS_CACHE")

    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=destino_a
    )
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=destino_b
    )

    transitions = get_transitions_for(flujo.id, estado_origen.id)
    assert isinstance(transitions, list)
    assert len(transitions) == 2

    # estado_destino accessible sin extra query (select_related)
    destino_names = sorted(t.estado_destino.nombre for t in transitions)
    assert destino_names == ["DEST_A_TRANS_CACHE", "DEST_B_TRANS_CACHE"]


@pytest.mark.django_db
def test_get_requisitos_for_filters_by_estado():
    """AC2+filter: get_requisitos_for filtra correctamente por estado."""
    from sinpapel.cache import get_requisitos_for
    from sinpapel.models import Estado, RequisitoEstadoDocumento, TipoDocumento

    estado_a = Estado.objects.create(nombre="REQ_TEST_A_CACHE")
    estado_b = Estado.objects.create(nombre="REQ_TEST_B_CACHE")
    tipo_doc = TipoDocumento.objects.create(nombre="REQ_DOC_TEST_CACHE", activo=True)

    RequisitoEstadoDocumento.objects.create(
        estado=estado_a, tipo_documento=tipo_doc, porcentaje=100
    )

    # estado_a tiene 1 requisito
    reqs_a = get_requisitos_for(estado_a.id)
    assert len(reqs_a) == 1
    assert reqs_a[0].tipo_documento.nombre == "REQ_DOC_TEST_CACHE"

    # estado_b no tiene requisitos
    reqs_b = get_requisitos_for(estado_b.id)
    assert reqs_b == []


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_clear_all_evicts_cache():
    """AC: clear_all() borra cache; subsequent calls re-hit DB."""
    from sinpapel.cache import clear_all, get_estado_by_name
    from sinpapel.models import Estado

    Estado.objects.create(nombre="CLEAR_ALL_TEST_STATE")

    # Populate cache
    get_estado_by_name("CLEAR_ALL_TEST_STATE")

    # 2da llamada: cache hit
    n_before = len(connection.queries)
    get_estado_by_name("CLEAR_ALL_TEST_STATE")
    n_after = len(connection.queries)
    assert n_after == n_before, "Should be cache hit before clear_all"

    # Clear cache
    clear_all()

    # 3ra llamada: cache miss → DB query
    n_before = len(connection.queries)
    s3 = get_estado_by_name("CLEAR_ALL_TEST_STATE")
    n_after = len(connection.queries)
    assert n_after > n_before, (
        f"After clear_all, next call should hit DB; queries: {n_after - n_before}"
    )
    assert s3 is not None
