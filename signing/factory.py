"""Sinpapel — Backend factory.

Lee settings.SINPAPEL_SIGNATURE_BACKEND, retorna instance del backend
configurado. Cache lazy para evitar re-imports.
"""
from __future__ import annotations

from functools import lru_cache

from django.conf import settings
from django.utils.module_loading import import_string

from sinpapel.signing.exceptions import SignatureBackendNotConfiguredError
from sinpapel.signing.ports import SignatureBackend

DEFAULT_BACKEND = "sinpapel.signing.backends.manual.ManualBackend"


@lru_cache(maxsize=1)
def get_signature_backend() -> SignatureBackend:
    """Retorna instance del backend configurado en settings.

    settings.SINPAPEL_SIGNATURE_BACKEND debe ser un dotted path Python a
    una clase que implemente SignatureBackend Protocol. Si no está
    configurado, default a ManualBackend (sin crypto, sin requerir credenciales).

    Raises:
        SignatureBackendNotConfiguredError: si import_string falla.
    """
    dotted_path = getattr(settings, "SINPAPEL_SIGNATURE_BACKEND", DEFAULT_BACKEND) or DEFAULT_BACKEND
    try:
        backend_class = import_string(dotted_path)
    except ImportError as e:
        raise SignatureBackendNotConfiguredError(
            f"Cannot import signature backend '{dotted_path}': {e}"
        ) from e
    return backend_class()


def reset_backend_cache() -> None:
    """Útil para tests que cambian SINPAPEL_SIGNATURE_BACKEND en runtime."""
    get_signature_backend.cache_clear()
