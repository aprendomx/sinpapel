"""Sinpapel — Signing DTOs."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationResult:
    """Resultado de SignatureBackend.verify().

    Attributes:
        valid: True si la firma es criptográficamente válida.
        reason: mensaje cuando valid=False (None si válida).
    """

    valid: bool
    reason: str | None = None
