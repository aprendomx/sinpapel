"""Sinpapel — Signing exceptions."""
from sinpapel.exceptions import SinpapelError


class SignatureError(SinpapelError):
    """Base para errores de firma digital."""


class SignatureValidationError(SignatureError):
    """Firma inválida (RSA falla, certificado expirado, kwargs faltantes, etc.)."""


class SignatureBackendNotConfiguredError(SignatureError):
    """settings.SINPAPEL_SIGNATURE_BACKEND mal configurado o backend no importable."""
