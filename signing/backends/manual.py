"""Sinpapel — ManualBackend (escaneo + sello de tiempo).

No requiere criptografía. backend_metadata almacena ruta del escaneo +
nombre del testigo + timestamp. Útil para procesos donde la firma se
captura en papel y se digitaliza posteriormente.
"""
from __future__ import annotations

import datetime
import hashlib
from typing import TYPE_CHECKING, ClassVar

from sinpapel.models import RegistroFirma
from sinpapel.signing.dto import VerificationResult

if TYPE_CHECKING:
    from django.contrib.auth.models import User


class ManualBackend:
    """Backend para firmas manuales (escaneo + sello de tiempo)."""

    name: ClassVar[str] = "manual"

    def request_signature(
        self,
        content: bytes,
        signer: "User | None",
        scanned_image_path: str = "",
        witness_name: str = "",
        is_required: bool = False,
        **kwargs: object,
    ) -> RegistroFirma:
        now = datetime.datetime.now(datetime.timezone.utc)
        return RegistroFirma.objects.create(
            backend_name=self.name,
            backend_metadata={
                "scanned_image_path": scanned_image_path,
                "witness_name": witness_name,
                "timestamp": now.isoformat(),
            },
            content_hash="sha256:" + hashlib.sha256(content).hexdigest(),
            signer=signer,
            signer_display_name=(signer.get_full_name() if signer else witness_name),
            is_required=is_required,
            verification_result="VALIDA",
            signed_at=now,
        )

    def verify(self, registro: RegistroFirma) -> VerificationResult:
        # Manual no se invalida criptográficamente — confiar en el escaneo.
        return VerificationResult(valid=True)

    def revoke(self, registro: RegistroFirma, reason: str) -> None:
        registro.verification_result = "INVALIDA"
        registro.backend_metadata = {
            **(registro.backend_metadata or {}),
            "revoke_reason": reason,
        }
        registro.save(update_fields=["verification_result", "backend_metadata"])
