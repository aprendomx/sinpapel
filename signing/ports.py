"""Sinpapel — SignatureBackend Protocol (ADR-008).

Contrato uniforme para backends de firma digital. Implementaciones concretas
viven en sinpapel/signing/backends/. Selección runtime via
settings.SINPAPEL_SIGNATURE_BACKEND.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

if TYPE_CHECKING:
    from django.contrib.auth.models import User

    from sinpapel.models import RegistroFirma
    from sinpapel.signing.dto import VerificationResult


@runtime_checkable
class SignatureBackend(Protocol):
    """Contrato uniforme para backends de firma digital (ADR-008).

    Implementaciones concretas:
    - sinpapel.signing.backends.fiel.FielBackend (México SAT eFirma)
    - sinpapel.signing.backends.manual.ManualBackend (escaneo + sello)
    - sinpapel.signing.backends.fake.FakeBackend (determinístico, tests)

    Cada backend persiste RegistroFirma con backend_name = self.name y
    backend_metadata específico al backend.
    """

    name: ClassVar[str]
    """Identificador del backend (ej. "fiel", "manual", "fake")."""

    def request_signature(
        self,
        content: bytes,
        signer: "User | None",
        **kwargs: object,
    ) -> "RegistroFirma":
        """Solicita firma; persiste RegistroFirma; retorna instance.

        Args:
            content: bytes del contenido canónico a firmar.
            signer: User que firma (puede ser None para firmas externas legacy).
            **kwargs: parámetros backend-specific (FIEL: firma_b64, certificado_cer_b64;
                Manual: scanned_image_path, witness_name; Fake: ninguno).

        Returns:
            RegistroFirma persistido con backend_name = self.name.

        Raises:
            SignatureValidationError: firma inválida (backend específico).
        """
        ...

    def verify(self, registro: "RegistroFirma") -> "VerificationResult":
        """Re-verifica una firma persistida (idempotente).

        Args:
            registro: RegistroFirma previamente persistido por este backend.

        Returns:
            VerificationResult con valid=True/False y reason si inválida.
        """
        ...

    def revoke(self, registro: "RegistroFirma", reason: str) -> None:
        """Revoca una firma (default no-op si backend no soporta revocación).

        Args:
            registro: RegistroFirma a revocar.
            reason: razón humana-legible para audit.
        """
        ...
