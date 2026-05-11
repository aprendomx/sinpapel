"""sinpapel.cache — helpers para cachear catálogos workflow.

S13.1 (E13a): cache layer transparente al motor (WorkflowEngine).
S13.2 agregará invalidación signal-based (post_save/post_delete).

Behavior:
- Cache miss → DB query → cache populate → return
- Cache hit → return desde memoria (0 SQL queries)
- DB miss (lookup no existe) → return None / [] (NO cachea — D1: no negative caching)
- Cache backend down → degrada a "siempre miss" (raise nunca)

Settings:
- SINPAPEL_CACHE_ALIAS: backend name (default 'default')
- SINPAPEL_CACHE_TIMEOUT: TTL en segundos (default 3600 = 1h)

Usage:
    from sinpapel.cache import (
        get_estado_by_name,
        get_active_version_flujo,
        get_transitions_for,
        get_requisitos_for,
    )

    estado = get_estado_by_name("EN_REVISION")
    flujo = get_active_version_flujo("solicitud")
    transitions = get_transitions_for(flujo.id, estado.id)

CAVEAT: Sin S13.2 (signal invalidation), mutaciones admin de Estado/
VersionFlujo/ConfiguracionTransicion NO invalidan cache automáticamente.
TTL 1h limita stale data al peor escenario. S13.2 resuelve con signals.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import caches

if TYPE_CHECKING:
    from sinpapel.models import (
        ConfiguracionTransicion,
        Estado,
        RequisitoEstadoDocumento,
        VersionFlujo,
    )


# Cache key namespace. Hardcoded (D3) — no configurable; sirve como
# namespace contra otros cache users del consumer (creditos cache, etc.)
_KEY_PREFIX = "sinpapel"


# ─────────────────────────────────────────────────────────────────────────────
# Settings readers (D9: lazy lookup en cada llamada — override_settings safe)
# ─────────────────────────────────────────────────────────────────────────────


def _cache_alias() -> str:
    """Backend cache alias. Configurable via SINPAPEL_CACHE_ALIAS."""
    return getattr(settings, "SINPAPEL_CACHE_ALIAS", "default")


def _cache_timeout() -> int:
    """TTL en segundos. Configurable via SINPAPEL_CACHE_TIMEOUT."""
    return getattr(settings, "SINPAPEL_CACHE_TIMEOUT", 3600)


def _cache():
    """Retorna el cache backend configurado."""
    return caches[_cache_alias()]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers (D2: local imports lazy anti-circular con sinpapel.models)
# ─────────────────────────────────────────────────────────────────────────────


def get_estado_by_name(nombre: str) -> "Estado | None":
    """Get Estado por nombre con cache.

    Returns None si no existe (defensive — D6 reemplaza DoesNotExist).
    NO cachea None (D1: no negative caching).
    """
    key = f"{_KEY_PREFIX}:estado:nombre:{nombre}"
    cache = _cache()
    obj = cache.get(key)
    if obj is None:
        from sinpapel.models import Estado

        obj = Estado.objects.filter(nombre=nombre).first()
        if obj is not None:
            cache.set(key, obj, _cache_timeout())
    return obj


def get_active_version_flujo(workflow_key: str) -> "VersionFlujo | None":
    """Get VersionFlujo activo (activo=True) por nombre/workflow_key con cache."""
    key = f"{_KEY_PREFIX}:flujo:active:{workflow_key}"
    cache = _cache()
    obj = cache.get(key)
    if obj is None:
        from sinpapel.models import VersionFlujo

        obj = VersionFlujo.objects.filter(activo=True, nombre=workflow_key).first()
        if obj is not None:
            cache.set(key, obj, _cache_timeout())
    return obj


def get_transitions_for(
    flujo_id: int,
    estado_origen_id: int,
) -> "list[ConfiguracionTransicion]":
    """Get ConfiguracionTransicion list desde estado_origen en un flujo.

    Lista pre-evaluada con select_related("estado_destino") +
    prefetch_related("grupos_permitidos") para evitar N+1 queries en callers
    (engine, permissions S13.6).
    """
    key = f"{_KEY_PREFIX}:transitions:{flujo_id}:{estado_origen_id}"
    cache = _cache()
    items = cache.get(key)
    if items is None:
        from sinpapel.models import ConfiguracionTransicion

        items = list(
            ConfiguracionTransicion.objects.filter(
                flujo_id=flujo_id,
                estado_origen_id=estado_origen_id,
            )
            .select_related("estado_destino")
            .prefetch_related("grupos_permitidos")
        )
        cache.set(key, items, _cache_timeout())
    return items


def get_requisitos_for(estado_id: int) -> "list[RequisitoEstadoDocumento]":
    """Get RequisitoEstadoDocumento list por estado con select_related."""
    key = f"{_KEY_PREFIX}:requisitos:{estado_id}"
    cache = _cache()
    items = cache.get(key)
    if items is None:
        from sinpapel.models import RequisitoEstadoDocumento

        items = list(
            RequisitoEstadoDocumento.objects.filter(estado_id=estado_id)
            .select_related("tipo_documento")
        )
        cache.set(key, items, _cache_timeout())
    return items


# ─────────────────────────────────────────────────────────────────────────────
# Test/admin helper
# ─────────────────────────────────────────────────────────────────────────────


def clear_all() -> None:
    """Borra TODO el cache backend (NO solo entries sinpapel:).

    SOLO usar en tests + management commands. NO en producción —
    invalidación granular llega en S13.2 (signal-based).

    Razón pattern delete: cache.delete_pattern("sinpapel:*") solo soportado
    por django-redis, no por LocMemCache/Memcached default. cache.clear()
    es portable (D4). Tests-only scope acepta el blast.
    """
    _cache().clear()
