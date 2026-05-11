"""sinpapel.signals — invalidación signal-based del cache.

S13.2 (E13a): post_save/post_delete/m2m_changed handlers que invalidan
sinpapel.cache entries cuando admin muta Estado/VersionFlujo/ConfigT/
RequisitoEstadoDocumento.

transaction.on_commit() wrapping (D2) garantiza invalidación SOLO post-commit
— rollback NO invalida (race condition mitigation con datos no persistidos).

Cascada Estado→transitions vía versioning bump (D1):
incrementar 'sinpapel:cache_version' al mutar Estado fuerza próximo lookup
de transitions a hacer fresh DB query (over-invalidation aceptado por
simplicidad — vs cache.clear() blast radius alto).

Lambda capture en variable local (D5) — frozen values protegen contra
mutaciones post-handler que cambien instance state antes de on_commit.
"""
from __future__ import annotations

from django.core.cache import caches
from django.db import transaction
from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
    pre_save,
)
from django.dispatch import receiver

from sinpapel.cache import _KEY_PREFIX, _cache_alias


def _cache():
    """Cache backend configurado (lazy lookup, override_settings safe)."""
    return caches[_cache_alias()]


# ─────────────────────────────────────────────────────────────────────────────
# Estado handlers (S13.1 helper: get_estado_by_name → key sinpapel:estado:nombre:<X>)
# ─────────────────────────────────────────────────────────────────────────────


@receiver(pre_save, sender="sinpapel.Estado")
def _capture_old_estado_nombre(sender, instance, **kwargs):
    """Discovery T1: capturar nombre OLD pre-save para invalidar el cache key
    correspondiente cuando admin renombra el Estado.

    Sin esto, post_save solo invalidaría la key del NUEVO nombre y dejaría
    el cache stale en la key del nombre antiguo durante TTL 1h. Bug
    descubierto en T1 RED cycle.
    """
    if not instance.pk:
        instance._sinpapel_old_estado_nombre = None
        return
    try:
        old = type(instance).objects.get(pk=instance.pk)
        instance._sinpapel_old_estado_nombre = old.nombre
    except type(instance).DoesNotExist:
        instance._sinpapel_old_estado_nombre = None


@receiver([post_save, post_delete], sender="sinpapel.Estado")
def invalidate_estado_cache(sender, instance, **kwargs):
    """Invalida sinpapel:estado:nombre:<X> (NEW + OLD si rename) + cascada
    transitions via version bump."""
    nombre = instance.nombre  # D5: frozen value antes de on_commit
    old_nombre = getattr(instance, "_sinpapel_old_estado_nombre", None)

    def _invalidate():
        c = _cache()
        c.delete(f"{_KEY_PREFIX}:estado:nombre:{nombre}")
        if old_nombre is not None and old_nombre != nombre:
            # Rename: invalidar también la key antigua
            c.delete(f"{_KEY_PREFIX}:estado:nombre:{old_nombre}")
        # Cascada: bump version global invalida transitions+requisitos cached
        # que referencien este estado (D1 over-invalidation por simplicidad)
        try:
            c.incr(f"{_KEY_PREFIX}:cache_version")
        except ValueError:
            # Key no existe aún — initialize sin TTL
            c.set(f"{_KEY_PREFIX}:cache_version", 1, None)

    transaction.on_commit(_invalidate)


# ─────────────────────────────────────────────────────────────────────────────
# VersionFlujo (S13.1 helper: get_active_version_flujo → key sinpapel:flujo:active:<X>)
# ─────────────────────────────────────────────────────────────────────────────


@receiver(pre_save, sender="sinpapel.VersionFlujo")
def _capture_old_flujo_nombre(sender, instance, **kwargs):
    """Discovery T1: capturar nombre OLD para invalidar key cuando admin
    renombra el VersionFlujo (mismo razonamiento que _capture_old_estado_nombre)."""
    if not instance.pk:
        instance._sinpapel_old_flujo_nombre = None
        return
    try:
        old = type(instance).objects.get(pk=instance.pk)
        instance._sinpapel_old_flujo_nombre = old.nombre
    except type(instance).DoesNotExist:
        instance._sinpapel_old_flujo_nombre = None


@receiver([post_save, post_delete], sender="sinpapel.VersionFlujo")
def invalidate_flujo_cache(sender, instance, **kwargs):
    """Invalida sinpapel:flujo:active:<workflow_key> (NEW + OLD si rename)."""
    nombre = instance.nombre
    old_nombre = getattr(instance, "_sinpapel_old_flujo_nombre", None)

    def _invalidate():
        c = _cache()
        c.delete(f"{_KEY_PREFIX}:flujo:active:{nombre}")
        if old_nombre is not None and old_nombre != nombre:
            c.delete(f"{_KEY_PREFIX}:flujo:active:{old_nombre}")

    transaction.on_commit(_invalidate)


# ─────────────────────────────────────────────────────────────────────────────
# ConfiguracionTransicion (key sinpapel:transitions:<flujo_id>:<estado_origen_id>)
# ─────────────────────────────────────────────────────────────────────────────


@receiver([post_save, post_delete], sender="sinpapel.ConfiguracionTransicion")
def invalidate_transitions_cache(sender, instance, **kwargs):
    """Invalida sinpapel:transitions:<flujo_id>:<estado_origen_id>."""
    flujo_id = instance.flujo_id
    estado_origen_id = instance.estado_origen_id

    def _invalidate():
        c = _cache()
        c.delete(f"{_KEY_PREFIX}:transitions:{flujo_id}:{estado_origen_id}")

    transaction.on_commit(_invalidate)


# ─────────────────────────────────────────────────────────────────────────────
# RequisitoEstadoDocumento (key sinpapel:requisitos:<estado_id>)
# ─────────────────────────────────────────────────────────────────────────────


@receiver([post_save, post_delete], sender="sinpapel.RequisitoEstadoDocumento")
def invalidate_requisitos_cache(sender, instance, **kwargs):
    """Invalida sinpapel:requisitos:<estado_id>."""
    estado_id = instance.estado_id

    def _invalidate():
        c = _cache()
        c.delete(f"{_KEY_PREFIX}:requisitos:{estado_id}")

    transaction.on_commit(_invalidate)


# ─────────────────────────────────────────────────────────────────────────────
# m2m_changed: ConfiguracionTransicion.grupos_permitidos
# ─────────────────────────────────────────────────────────────────────────────


def _connect_m2m_handler():
    """Connect m2m_changed via through accessor (D3 robusto vs string form).

    Lazy — llamado al final del módulo cuando sinpapel.models ya importado.
    """
    from sinpapel.models import ConfiguracionTransicion

    @receiver(
        m2m_changed,
        sender=ConfiguracionTransicion.grupos_permitidos.through,
    )
    def invalidate_transitions_on_grupos_change(sender, instance, action, **kwargs):
        """Invalida transitions cache cuando grupos_permitidos M2M cambia."""
        if action not in ("post_add", "post_remove", "post_clear"):
            return
        flujo_id = instance.flujo_id
        estado_origen_id = instance.estado_origen_id

        def _invalidate():
            c = _cache()
            c.delete(
                f"{_KEY_PREFIX}:transitions:{flujo_id}:{estado_origen_id}"
            )

        transaction.on_commit(_invalidate)


_connect_m2m_handler()  # Conecta m2m post-import sinpapel.models
