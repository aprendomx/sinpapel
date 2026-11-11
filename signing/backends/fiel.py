"""Sinpapel — FielBackend (México SAT eFirma).

Modos soportados (ADR-012, S13.6):
- request_signature (modo A, client-side default): cliente firma localmente,
  envía firma_b64 + certificado_cer_b64. Backend solo verifica RSA-SHA256.
  La clave privada NUNCA cruza la red en modo A.
- sign_server_side (modo B, server-side opt-in): cliente sube cer_file +
  key_file + password. Backend descifra .key con password (in-memory), firma
  RSA-SHA256, descarta key vía del + gc.collect() en finally (security
  cleanup wrapper _with_secure_key_buffer). Gated por
  SINPAPEL_ALLOW_SERVER_SIGNING=True (default False).

ADVERTENCIA SEGURIDAD modo A: La clave privada NUNCA debe llegar a este backend.
ADVERTENCIA SEGURIDAD modo B: La clave existe en memoria del proceso solo
durante el firmado; descartada inmediatamente. Tests verifican cleanup vía
caplog (no leak en logs) y mock gc.collect.
"""
from __future__ import annotations

import base64
import contextlib
import datetime
import gc
import hashlib
import logging
from typing import TYPE_CHECKING, ClassVar

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509.oid import NameOID

from sinpapel.models import RegistroFirma
from sinpapel.signing.certificados import (
    CertificadoLeido,
    cargar_bundle_confianza,
    emitido_por,
    leer_certificado,
)
from sinpapel.signing.dto import VerificationResult
from sinpapel.signing.exceptions import (
    SignatureBackendNotConfiguredError,
    SignatureValidationError,
)


@contextlib.contextmanager
def _with_secure_key_buffer(key_bytes: bytes, password: bytes):
    """Garantiza descarte de key_bytes + password post-uso (D-cleanup S13.6).

    Yields el tuple original; en finally (siempre, incluso si raisea):
    - del key_bytes
    - del password
    - gc.collect() — fuerza ciclo de garbage collection.

    Aplicar wrapping cualquier código que use private key bytes en memoria.
    """
    try:
        yield key_bytes, password
    finally:
        del key_bytes
        del password
        gc.collect()


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from django.contrib.auth.models import User


class FielBackend:
    """Backend para firma electrónica avanzada (FIEL/eFirma SAT México).

    Verifica RSA-SHA256 contra certificado X.509 y persiste RegistroFirma con
    backend_metadata FIEL (firma_pkcs7_b64, certificado_cer_b64, rfc_firmante,
    curp_firmante, rfc_representante —solo persona moral—, numero_serie_cer).
    """

    name: ClassVar[str] = "fiel"

    def request_signature(
        self,
        content: bytes,
        signer: "User | None",
        firma_b64: str = "",
        certificado_cer_b64: str = "",
        is_required: bool = False,
        **kwargs: object,
    ) -> RegistroFirma:
        """Verifica firma + persiste RegistroFirma.

        Args:
            content: bytes del contenido canónico firmado.
            signer: User opcional (firmas externas pueden tener signer=None).
            firma_b64: firma RSA-SHA256 codificada en base64.
            certificado_cer_b64: certificado X.509 DER codificado en base64.
            is_required: si la firma era requerida por la transición.

        Returns:
            RegistroFirma persistido con backend_name='fiel'.

        Raises:
            SignatureValidationError: cert inválido/expirado o firma inválida.
        """
        if not firma_b64 or not certificado_cer_b64:
            raise SignatureValidationError(
                "FielBackend requires firma_b64 and certificado_cer_b64"
            )

        leido = self._load_cert_leido(certificado_cer_b64)
        cert = leido.cert
        self._validate_cert_validity(cert)
        self._verify_signature(cert, content, firma_b64)

        # Cadena de confianza (0.8.0): si hay bundle de ACs configurado
        # (SINPAPEL_FIEL_TRUSTED_CA_BUNDLE), el cert DEBE estar emitido por
        # una de ellas — un cert autofirmado se rechaza. Sin bundle, la firma
        # se acepta pero se marca VALIDA_SIN_CADENA: criptográficamente
        # íntegra, identidad del emisor NO verificada contra el SAT.
        trusted_cas = self._load_trusted_cas()
        if trusted_cas:
            self._verify_issuer_chain(cert, trusted_cas, tbs=leido.tbs_original)
            resultado = "VALIDA"
            cadena_verificada = True
        else:
            resultado = "VALIDA_SIN_CADENA"
            cadena_verificada = False

        # e.firma SAT (issue #5): el RFC vive en x500UniqueIdentifier
        # (2.5.4.45) y serialNumber (2.5.4.5) trae la CURP. Persona moral:
        # "RFC empresa / RFC representante" y " / CURP representante".
        # Siempre del SUJETO: el emisor trae su propio 2.5.4.45 (RFC del SAT).
        rfcs = self._split_sat_attr(
            self._extract_subject_attr(cert, NameOID.X500_UNIQUE_IDENTIFIER)
        )
        curps = self._split_sat_attr(
            self._extract_subject_attr(cert, NameOID.SERIAL_NUMBER)
        )
        rfc = rfcs[0] if rfcs else ""
        rfc_representante = rfcs[1] if len(rfcs) > 1 else ""
        curp = curps[-1] if curps else ""
        nombre = self._extract_subject_attr(cert, NameOID.COMMON_NAME) or ""
        serie = format(cert.serial_number, "x")
        now = datetime.datetime.now(datetime.timezone.utc)

        metadata = {
            "firma_pkcs7_b64": firma_b64,
            "certificado_cer_b64": certificado_cer_b64,
            "rfc_firmante": rfc,
            "curp_firmante": curp,
            "numero_serie_cer": serie,
            "cadena_verificada": cadena_verificada,
            "emisor": cert.issuer.rfc4514_string(),
        }
        if rfc_representante:
            metadata["rfc_representante"] = rfc_representante

        return RegistroFirma.objects.create(
            backend_name=self.name,
            backend_metadata=metadata,
            content_hash="sha256:" + hashlib.sha256(content).hexdigest(),
            signer=signer,
            signer_display_name=nombre,
            is_required=is_required,
            verification_result=resultado,
            signed_at=now,
        )

    def sign_server_side(
        self,
        content: bytes,
        signer: "User | None",
        cer_bytes: bytes,
        key_bytes: bytes,
        password: bytes,
        is_required: bool = False,
    ) -> RegistroFirma:
        """Modo B server-side — descifra .key, firma in-memory, descarta key.

        Gated por settings.SINPAPEL_ALLOW_SERVER_SIGNING=True (ADR-012).
        SAT FIEL .key es PKCS#8 DER cifrado; fallback a PEM si DER falla.

        Args:
            content: bytes canónicos a firmar.
            signer: User opcional.
            cer_bytes: bytes del .cer X.509 DER.
            key_bytes: bytes del .key PKCS#8 DER cifrado (o PEM).
            password: bytes del password (encoded utf-8 desde caller).
            is_required: si la firma era requerida por la transición.

        Returns:
            RegistroFirma persistido con backend_metadata.mode="server-side".

        Raises:
            SignatureBackendNotConfiguredError: si SINPAPEL_ALLOW_SERVER_SIGNING != True.
            SignatureValidationError: si key/password/cert inválido. Mensaje
                genérico (no leak which field falló — D-log-filter).
        """
        from django.conf import settings

        if not getattr(settings, "SINPAPEL_ALLOW_SERVER_SIGNING", False):
            raise SignatureBackendNotConfiguredError(
                "Server-side signing is disabled. "
                "Set SINPAPEL_ALLOW_SERVER_SIGNING=True (with legal review)."
            )

        from cryptography.hazmat.primitives.serialization import (
            load_der_private_key,
            load_pem_private_key,
        )

        firma_b64 = ""
        with _with_secure_key_buffer(key_bytes, password) as (kb, pw):
            try:
                # SAT FIEL es PKCS#8 DER cifrado
                try:
                    private_key = load_der_private_key(kb, password=pw)
                except Exception:
                    private_key = load_pem_private_key(kb, password=pw)
                firma_bytes = private_key.sign(
                    content, padding.PKCS1v15(), hashes.SHA256()
                )
                firma_b64 = base64.b64encode(firma_bytes).decode("ascii")
                # Discard private_key reference inmediato post-firma
                del private_key
            except Exception as exc:
                # Mensaje genérico — no leak which field falló (security)
                raise SignatureValidationError(
                    "Server-side signing failed (invalid cer/key/password)"
                ) from exc

        # Verify + persist via request_signature (modo A path) para consistency
        cer_b64 = base64.b64encode(cer_bytes).decode("ascii")
        rf = self.request_signature(
            content=content,
            signer=signer,
            firma_b64=firma_b64,
            certificado_cer_b64=cer_b64,
            is_required=is_required,
        )
        # Audit metadata: marca modo B para reporting (security checklist item 6)
        rf.backend_metadata = {**(rf.backend_metadata or {}), "mode": "server-side"}
        rf.save(update_fields=["backend_metadata"])
        return rf

    def verify(self, registro: RegistroFirma) -> VerificationResult:
        """Re-verifica firma persistida (cert load + integridad de metadata).

        No re-verifica RSA contra content original porque ese content no se
        almacena (solo content_hash). Verifica que el cert siga siendo
        cargable.
        """
        meta = registro.backend_metadata or {}
        firma_b64 = meta.get("firma_pkcs7_b64", "")
        cert_b64 = meta.get("certificado_cer_b64", "")
        if not firma_b64 or not cert_b64:
            return VerificationResult(valid=False, reason="missing FIEL metadata")
        try:
            self._load_cert(cert_b64)
            return VerificationResult(valid=True)
        except SignatureValidationError as e:
            return VerificationResult(valid=False, reason=str(e))

    def revoke(self, registro: RegistroFirma, reason: str) -> None:
        registro.verification_result = "INVALIDA"
        registro.backend_metadata = {
            **(registro.backend_metadata or {}),
            "revoke_reason": reason,
        }
        registro.save(update_fields=["verification_result", "backend_metadata"])

    # ─── helpers privados ──────────────────────────────────────────────

    def _load_trusted_cas(self) -> list[x509.Certificate]:
        """Carga el bundle de ACs de confianza (SAT) desde settings.

        SINPAPEL_FIEL_TRUSTED_CA_BUNDLE: path (str) o lista de paths a
        archivos PEM (uno o varios certificados por archivo) o DER con las
        AC **emisoras** vigentes del SAT. Sin setting → lista vacía (modo
        VALIDA_SIN_CADENA).

        Delega en ``sinpapel.signing.cargar_bundle_confianza`` (API pública
        desde 0.8.7, issue #7): cada certificado se carga por separado, los
        ilegibles se omiten con un WARNING que nombra archivo e índice, y
        solo si no queda NINGUNO se lanza SignatureBackendNotConfiguredError.
        Los nombres con PrintableString no conforme (AC6 del SAT) se leen
        con la ruta tolerante.
        """
        from django.conf import settings

        bundle = getattr(settings, "SINPAPEL_FIEL_TRUSTED_CA_BUNDLE", None)
        if not bundle:
            return []
        try:
            cargado = cargar_bundle_confianza(bundle)
        except SignatureBackendNotConfiguredError as exc:
            raise SignatureBackendNotConfiguredError(
                f"SINPAPEL_FIEL_TRUSTED_CA_BUNDLE: {exc}"
            ) from exc
        for clave in cargado.omitidos:
            logger.warning(
                "SINPAPEL_FIEL_TRUSTED_CA_BUNDLE: certificado %s no se pudo "
                "leer (%s); se omite.", clave, cargado.motivos.get(clave, ""),
            )
        for clave in cargado.normalizados:
            logger.info(
                "SINPAPEL_FIEL_TRUSTED_CA_BUNDLE: certificado %s tiene atributos "
                "PrintableString no conformes; se leyó con la ruta tolerante.",
                clave,
            )
        return cargado.cas

    def _verify_issuer_chain(
        self,
        cert: x509.Certificate,
        trusted_cas: list[x509.Certificate],
        tbs: bytes | None = None,
    ) -> None:
        """Verifica que cert esté emitido (firmado) por una AC del bundle.

        Emparejamiento por subject == issuer + verificación criptográfica de
        la firma del certificado con la llave pública de la AC. La AC además
        debe estar vigente.

        Valida **un solo nivel**: el bundle debe contener las AC que emiten
        directamente los certificados de los firmantes (en producción SAT:
        AC5, AC6 y AC7), no solo la raíz.

        ``tbs``: bytes tbsCertificate originales. Obligatorio si el cert se
        leyó con la ruta tolerante (``CertificadoLeido.tbs_original``); por
        defecto ``cert.tbs_certificate_bytes``.
        """
        leido = CertificadoLeido(
            cert, tbs if tbs is not None else cert.tbs_certificate_bytes, tbs is not None
        )
        if emitido_por(leido, trusted_cas) is not None:
            return
        raise SignatureValidationError(
            "El certificado no está emitido por ninguna AC del bundle de "
            "confianza (SINPAPEL_FIEL_TRUSTED_CA_BUNDLE)."
        )

    def _load_cert(self, cert_b64: str) -> x509.Certificate:
        return self._load_cert_leido(cert_b64).cert

    def _load_cert_leido(self, cert_b64: str) -> CertificadoLeido:
        """Carga el .cer del firmante, tolerando PrintableString no conformes
        (e.firma emitidas por la AC6 del SAT, issue #6)."""
        try:
            der = base64.b64decode(cert_b64)
        except Exception as exc:
            raise SignatureValidationError(
                "certificado_cer_b64 inválido: no es base64"
            ) from exc
        try:
            return leer_certificado(der)
        except ValueError as exc:
            raise SignatureValidationError(
                f"certificado_cer_b64 no es un certificado X.509 DER legible: {exc}"
            ) from exc

    def _validate_cert_validity(self, cert: x509.Certificate) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        if now < cert.not_valid_before_utc or now > cert.not_valid_after_utc:
            raise SignatureValidationError("Certificado expirado o aún no vigente")

    def _verify_signature(
        self, cert: x509.Certificate, content: bytes, firma_b64: str
    ) -> None:
        try:
            firma_raw = base64.b64decode(firma_b64)
        except Exception as exc:
            raise SignatureValidationError(
                "firma_b64 inválido: padding base64 incorrecto"
            ) from exc
        try:
            cert.public_key().verify(
                firma_raw, content, padding.PKCS1v15(), hashes.SHA256()
            )
        except InvalidSignature as exc:
            raise SignatureValidationError(
                "Firma inválida: el contenido no corresponde a esta firma"
            ) from exc

    @staticmethod
    def _split_sat_attr(value: str | None) -> list[str]:
        """Parte un atributo SAT 'A / B' en sus componentes no vacíos."""
        if not value:
            return []
        return [p.strip() for p in value.split("/") if p.strip()]

    def _extract_subject_attr(self, cert: x509.Certificate, oid) -> str | None:
        try:
            return cert.subject.get_attributes_for_oid(oid)[0].value  # type: ignore[return-value]
        except IndexError:
            return None
