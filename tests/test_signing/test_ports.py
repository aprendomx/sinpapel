"""Tests para SignatureBackend Protocol + DTOs + exceptions."""
from __future__ import annotations

import pytest

from sinpapel.signing import (
    SignatureBackend,
    SignatureBackendNotConfiguredError,
    SignatureError,
    SignatureValidationError,
    VerificationResult,
)


def test_signature_backend_protocol_runtime_checkable():
    """SignatureBackend es @runtime_checkable — isinstance() funciona."""

    class _MockBackend:
        name = "mock"

        def request_signature(self, content, signer, **kwargs):
            return None  # no-op para test

        def verify(self, registro):
            return VerificationResult(valid=True)

        def revoke(self, registro, reason):
            pass

    assert isinstance(_MockBackend(), SignatureBackend)


def test_object_without_methods_not_signature_backend():
    """Un objeto sin los métodos del Protocol NO es SignatureBackend."""

    class _Empty:
        name = "empty"

    assert not isinstance(_Empty(), SignatureBackend)


def test_verification_result_frozen():
    """VerificationResult es frozen (inmutable)."""
    result = VerificationResult(valid=True)
    assert result.valid is True
    assert result.reason is None
    with pytest.raises((AttributeError, TypeError)):
        result.valid = False  # type: ignore[misc]


def test_verification_result_with_reason():
    """VerificationResult acepta reason cuando valid=False."""
    result = VerificationResult(valid=False, reason="cert expirado")
    assert result.valid is False
    assert result.reason == "cert expirado"


def test_signature_error_hierarchy():
    """Las excepciones específicas heredan de SignatureError y SinpapelError."""
    from sinpapel.exceptions import SinpapelError

    assert issubclass(SignatureError, SinpapelError)
    assert issubclass(SignatureValidationError, SignatureError)
    assert issubclass(SignatureBackendNotConfiguredError, SignatureError)


def test_signature_validation_error_can_be_raised():
    """SignatureValidationError es raisable con mensaje."""
    with pytest.raises(SignatureValidationError, match="test message"):
        raise SignatureValidationError("test message")
