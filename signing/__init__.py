"""Sinpapel signing — Port + adapters para firma digital pluggable.

Public API:
    SignatureBackend (Protocol)
    VerificationResult (dataclass)
    SignatureError, SignatureValidationError, SignatureBackendNotConfiguredError
"""
from sinpapel.signing.dto import VerificationResult
from sinpapel.signing.exceptions import (
    SignatureBackendNotConfiguredError,
    SignatureError,
    SignatureValidationError,
)
from sinpapel.signing.ports import SignatureBackend

__all__ = [
    "SignatureBackend",
    "VerificationResult",
    "SignatureError",
    "SignatureValidationError",
    "SignatureBackendNotConfiguredError",
]
