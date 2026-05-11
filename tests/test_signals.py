"""S13.2 — Tests para signal-based cache invalidation.

Usa @pytest.mark.django_db(transaction=True) (D4) para que on_commit
callbacks ejecuten (no en savepoints).
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.db import connection, transaction
from django.test import override_settings


# ─────────────────────────────────────────────────────────────────────────────
# T1 — Happy-path tests (post_save + post_delete)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_post_save_estado_invalidates_cache():
    """S13.2 AC1+AC2: post_save Estado invalida sinpapel:estado:nombre:<X>."""
    from sinpapel.cache import clear_all, get_estado_by_name
    from sinpapel.models import Estado

    clear_all()

    # Setup: crear Estado + cache populate
    estado = Estado.objects.create(nombre="SIG_EST_INV_TEST")

    # Cache populate
    s1 = get_estado_by_name("SIG_EST_INV_TEST")
    assert s1 is not None
    assert s1.id == estado.id

    # 2da llamada: cache hit
    n0 = len(connection.queries)
    s2 = get_estado_by_name("SIG_EST_INV_TEST")
    assert len(connection.queries) == n0  # cache hit confirmed

    # Mutate: post_save signal fire → on_commit invalida
    with transaction.atomic():
        estado.nombre = "SIG_EST_INV_RENAMED"
        estado.save()

    # Lookup nombre antiguo: debería ser miss (cache invalidada Y DB no tiene este nombre)
    result_old = get_estado_by_name("SIG_EST_INV_TEST")
    assert result_old is None, "Cache should be invalidated; DB has no 'SIG_EST_INV_TEST'"

    # Lookup nombre nuevo: hit DB fresh
    result_new = get_estado_by_name("SIG_EST_INV_RENAMED")
    assert result_new is not None
    assert result_new.id == estado.id


@pytest.mark.django_db(transaction=True)
def test_post_save_flujo_invalidates_cache():
    """S13.2 AC1+AC2: post_save VersionFlujo invalida sinpapel:flujo:active:<X>."""
    from sinpapel.cache import clear_all, get_active_version_flujo
    from sinpapel.models import VersionFlujo

    clear_all()

    flujo = VersionFlujo.objects.create(nombre="SIG_FLUJO_TEST", activo=True)

    # Cache populate
    f1 = get_active_version_flujo("SIG_FLUJO_TEST")
    assert f1 is not None

    # Mutate: deactivate
    with transaction.atomic():
        flujo.activo = False
        flujo.save()

    # Post-save: cache invalidada → próximo lookup ve activo=False, retorna None
    f2 = get_active_version_flujo("SIG_FLUJO_TEST")
    assert f2 is None, "Cache invalidated; flujo inactivo no debe retornar"


@pytest.mark.django_db(transaction=True)
def test_post_save_configuracion_transicion_invalidates_cache():
    """S13.2 AC1+AC2: post_save ConfiguracionTransicion invalida sinpapel:transitions:<flujo>:<estado>."""
    from sinpapel.cache import clear_all, get_transitions_for
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo

    clear_all()

    flujo = VersionFlujo.objects.create(nombre="SIG_CT_FLUJO", activo=True)
    estado_origen = Estado.objects.create(nombre="SIG_CT_ORIGEN")
    estado_destino_a = Estado.objects.create(nombre="SIG_CT_DEST_A")
    estado_destino_b = Estado.objects.create(nombre="SIG_CT_DEST_B")

    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino_a
    )

    # Populate cache: 1 transition
    t1 = get_transitions_for(flujo.id, estado_origen.id)
    assert len(t1) == 1

    # Add another transition: signal fire → on_commit invalida
    with transaction.atomic():
        ConfiguracionTransicion.objects.create(
            flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino_b
        )

    # Próximo lookup: hit DB fresh, ahora retorna 2
    t2 = get_transitions_for(flujo.id, estado_origen.id)
    assert len(t2) == 2, f"Expected 2 transitions post-add, got {len(t2)}"


@pytest.mark.django_db(transaction=True)
def test_post_save_requisito_invalidates_cache():
    """S13.2 AC1+AC2: post_save RequisitoEstadoDocumento invalida sinpapel:requisitos:<estado_id>."""
    from sinpapel.cache import clear_all, get_requisitos_for
    from sinpapel.models import (
        Estado,
        RequisitoEstadoDocumento,
        TipoDocumento,
    )

    clear_all()

    estado = Estado.objects.create(nombre="SIG_REQ_EST")
    tipo_a = TipoDocumento.objects.create(nombre="SIG_REQ_TIPO_A", activo=True)
    tipo_b = TipoDocumento.objects.create(nombre="SIG_REQ_TIPO_B", activo=True)

    RequisitoEstadoDocumento.objects.create(
        estado=estado, tipo_documento=tipo_a, porcentaje=100
    )

    # Cache populate
    r1 = get_requisitos_for(estado.id)
    assert len(r1) == 1

    # Add another requisito
    with transaction.atomic():
        RequisitoEstadoDocumento.objects.create(
            estado=estado, tipo_documento=tipo_b, porcentaje=80
        )

    # Próximo lookup: hit DB fresh, retorna 2
    r2 = get_requisitos_for(estado.id)
    assert len(r2) == 2


# ─────────────────────────────────────────────────────────────────────────────
# T2 — Advanced tests: rollback + m2m + cascada Estado→transitions
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_transaction_rollback_does_not_invalidate_cache():
    """S13.2 AC6 (D2 + D8): on_commit NO ejecuta si transacción rolls back.

    Cache stale-pero-válida sigue sirviendo si la mutación nunca persistió.
    """
    from sinpapel.cache import clear_all, get_estado_by_name
    from sinpapel.models import Estado

    clear_all()

    # Create + populate cache
    estado = Estado.objects.create(nombre="ROLLBACK_TEST_ESTADO")
    s1 = get_estado_by_name("ROLLBACK_TEST_ESTADO")
    assert s1 is not None

    # 2da llamada confirma cache hit pre-rollback
    n0 = len(connection.queries)
    s_pre = get_estado_by_name("ROLLBACK_TEST_ESTADO")
    assert len(connection.queries) == n0  # cache hit

    # Forzar rollback dentro de atomic block
    with pytest.raises(RuntimeError, match="forced rollback"):
        with transaction.atomic():
            estado.nombre = "ROLLBACK_TEST_RENAMED"
            estado.save()
            raise RuntimeError("forced rollback")

    # Refresh from DB: rollback ocurrió, nombre original preservado
    estado.refresh_from_db()
    assert estado.nombre == "ROLLBACK_TEST_ESTADO"

    # Cache test: lookup nombre original sigue retornando objeto
    # (NO fue invalidada porque on_commit nunca ejecutó)
    n0 = len(connection.queries)
    s_post = get_estado_by_name("ROLLBACK_TEST_ESTADO")
    assert len(connection.queries) == n0, (
        "Cache should still hit (on_commit never fired due to rollback)"
    )
    assert s_post is not None


@pytest.mark.django_db(transaction=True)
def test_m2m_grupos_permitidos_invalidates_transitions_cache():
    """S13.2 AC1 (D3): m2m_changed via through accessor invalida transitions.

    Cubre actions: post_add, post_remove, post_clear.
    """
    from sinpapel.cache import clear_all, get_transitions_for
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo

    clear_all()

    flujo = VersionFlujo.objects.create(nombre="M2M_FLUJO", activo=True)
    estado_origen = Estado.objects.create(nombre="M2M_ORIGEN")
    estado_destino = Estado.objects.create(nombre="M2M_DESTINO")
    transicion = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino
    )

    grupo_a = Group.objects.create(name="M2M_GRUPO_A")
    grupo_b = Group.objects.create(name="M2M_GRUPO_B")

    # Populate cache: 0 grupos asociados al inicio
    t1 = get_transitions_for(flujo.id, estado_origen.id)
    assert len(t1) == 1
    assert list(t1[0].grupos_permitidos.values_list("name", flat=True)) == []

    # Action: post_add
    with transaction.atomic():
        transicion.grupos_permitidos.add(grupo_a)

    # Cache invalidada → fresh DB query muestra grupo_a
    t2 = get_transitions_for(flujo.id, estado_origen.id)
    grupo_names = list(t2[0].grupos_permitidos.values_list("name", flat=True))
    assert "M2M_GRUPO_A" in grupo_names, f"Expected M2M_GRUPO_A in {grupo_names}"

    # Action: post_add (otro grupo)
    with transaction.atomic():
        transicion.grupos_permitidos.add(grupo_b)

    t3 = get_transitions_for(flujo.id, estado_origen.id)
    grupo_names = list(t3[0].grupos_permitidos.values_list("name", flat=True))
    assert set(grupo_names) == {"M2M_GRUPO_A", "M2M_GRUPO_B"}

    # Action: post_remove
    with transaction.atomic():
        transicion.grupos_permitidos.remove(grupo_a)

    t4 = get_transitions_for(flujo.id, estado_origen.id)
    grupo_names = list(t4[0].grupos_permitidos.values_list("name", flat=True))
    assert grupo_names == ["M2M_GRUPO_B"]

    # Action: post_clear
    with transaction.atomic():
        transicion.grupos_permitidos.clear()

    t5 = get_transitions_for(flujo.id, estado_origen.id)
    grupo_names = list(t5[0].grupos_permitidos.values_list("name", flat=True))
    assert grupo_names == []


@pytest.mark.django_db(transaction=True)
def test_estado_save_bumps_version_invalidating_transitions_cascade():
    """S13.2 D1: cascada Estado→transitions vía version bump.

    Mutar Estado dispara incr 'sinpapel:cache_version', que efectivamente
    invalida transitions cache (over-invalidation aceptado por simplicidad).
    """
    from django.core.cache import caches
    from sinpapel.cache import _cache_alias, clear_all

    clear_all()

    cache = caches[_cache_alias()]

    # Pre-condition: version key no existe o = 0
    initial_version = cache.get("sinpapel:cache_version")

    # Crear Estado y mutarlo dispara signal handler
    from sinpapel.models import Estado

    with transaction.atomic():
        estado = Estado.objects.create(nombre="CASCADE_VERSION_TEST")

    # post_save signal ejecutó on_commit → cascade incr/init cache_version
    version_after_create = cache.get("sinpapel:cache_version")
    assert version_after_create is not None, (
        "cache_version should be initialized after Estado save"
    )

    # 2da mutación: incr la version
    with transaction.atomic():
        estado.descripcion = "modified"
        estado.save()

    version_after_save = cache.get("sinpapel:cache_version")
    assert version_after_save > version_after_create, (
        f"version should bump: was {version_after_create}, now {version_after_save}"
    )
