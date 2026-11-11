"""Sinpapel signing — Port + adapters para firma digital pluggable.

Public API:
    SignatureBackend (Protocol)
    VerificationResult (dataclass)
    SignatureError, SignatureValidationError, SignatureBackendNotConfiguredError
    leer_certificado, cargar_bundle_confianza, emitido_por,
    CertificadoLeido, BundleCargado  (0.8.7 — lectura de certificados como
    FielBackend, incluida la ruta tolerante para la AC6 del SAT)
"""
from sinpapel.signing.certificados import (
    BundleCargado,
    CertificadoLeido,
    cargar_bundle_confianza,
    emitido_por,
    leer_certificado,
)
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
    "BundleCargado",
    "CertificadoLeido",
    "cargar_bundle_confianza",
    "emitido_por",
    "leer_certificado",
]
