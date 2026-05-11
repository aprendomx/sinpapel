"""Sinpapel — FakeBackend (determinístico, para tests sin sandbox FIEL)."""
from __future__ import annotations

import datetime
import hashlib
from typing import TYPE_CHECKING, ClassVar

from sinpapel.models import RegistroFirma
from sinpapel.signing.dto import VerificationResult

if TYPE_CHECKING:
    from django.contrib.auth.models import User


class FakeBackend:
    """Backend no-crypto, determinístico, para tests.

    No requiere generar keypair RSA. content_hash via SHA-256 simple,
    verification_result siempre "VALIDA".
    """

    name: ClassVar[str] = "fake"

    def request_signature(
        self,
        content: bytes,
        signer: "User | None",
        is_required: bool = False,
        **kwargs: object,
    ) -> RegistroFirma:
        now = datetime.datetime.now(datetime.timezone.utc)
        return RegistroFirma.objects.create(
            backend_name=self.name,
            backend_metadata={"fake": True},
            content_hash="sha256:" + hashlib.sha256(content).hexdigest(),
            signer=signer,
            signer_display_name=(signer.username if signer else "fake_signer"),
            is_required=is_required,
            verification_result="VALIDA",
            signed_at=now,
        )

    def verify(self, registro: RegistroFirma) -> VerificationResult:
        return VerificationResult(valid=True)

    def revoke(self, registro: RegistroFirma, reason: str) -> None:
        # No-op — Fake nunca se considera revocado.
        return None
