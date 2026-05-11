"""Tests para get_signature_backend() factory."""
from __future__ import annotations

import pytest
from django.test import override_settings

from sinpapel.signing import SignatureBackendNotConfiguredError
from sinpapel.signing.backends.fake import FakeBackend
from sinpapel.signing.backends.manual import ManualBackend
from sinpapel.signing.factory import (
    DEFAULT_BACKEND,
    get_signature_backend,
    reset_backend_cache,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Limpia cache antes/después de cada test (otherwise singleton lru_cache leaks)."""
    reset_backend_cache()
    yield
    reset_backend_cache()


def test_factory_default_constant_is_manual():
    """DEFAULT_BACKEND apunta a ManualBackend (sin crypto)."""
    assert DEFAULT_BACKEND == "sinpapel.signing.backends.manual.ManualBackend"


@override_settings(SINPAPEL_SIGNATURE_BACKEND=None)
def test_factory_returns_default_when_setting_missing():
    """Cuando settings no define SINPAPEL_SIGNATURE_BACKEND, default ManualBackend."""
    # override_settings con None remueve el setting; getattr default aplica
    backend = get_signature_backend()
    assert isinstance(backend, ManualBackend)


@override_settings(SINPAPEL_SIGNATURE_BACKEND="sinpapel.signing.backends.fake.FakeBackend")
def test_factory_reads_settings_fake():
    """Factory lee settings y retorna instance del backend configurado."""
    backend = get_signature_backend()
    assert isinstance(backend, FakeBackend)


@override_settings(SINPAPEL_SIGNATURE_BACKEND="sinpapel.signing.backends.manual.ManualBackend")
def test_factory_reads_settings_manual():
    """Factory funciona con ManualBackend explícito."""
    backend = get_signature_backend()
    assert isinstance(backend, ManualBackend)


@override_settings(SINPAPEL_SIGNATURE_BACKEND="nonexistent.module.Backend")
def test_factory_raises_on_invalid_path():
    """import_string fallido → SignatureBackendNotConfiguredError."""
    with pytest.raises(SignatureBackendNotConfiguredError, match="Cannot import"):
        get_signature_backend()


def test_reset_backend_cache_clears():
    """reset_backend_cache() permite re-leer settings tras cambio."""
    with override_settings(SINPAPEL_SIGNATURE_BACKEND="sinpapel.signing.backends.fake.FakeBackend"):
        b1 = get_signature_backend()
        assert isinstance(b1, FakeBackend)

    reset_backend_cache()

    with override_settings(SINPAPEL_SIGNATURE_BACKEND="sinpapel.signing.backends.manual.ManualBackend"):
        b2 = get_signature_backend()
        assert isinstance(b2, ManualBackend)
