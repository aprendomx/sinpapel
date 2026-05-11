"""Tests para FielBackend con RSA keypair generado in-memory."""
from __future__ import annotations

import base64
import datetime as _dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from sinpapel.signing import SignatureBackend, SignatureValidationError
from sinpapel.signing.backends.fiel import FielBackend


def _make_keypair_and_cert(
    common_name: str = "TEST FIRMANTE",
    serial_number_subject: str = "TESTRFC000",
    days_valid: int = 365,
) -> tuple[rsa.RSAPrivateKey, bytes]:
    """Genera RSA private key + self-signed cert DER. In-memory, no sandbox."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        x509.NameAttribute(NameOID.SERIAL_NUMBER, serial_number_subject),
    ])
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=1))
        .not_valid_after(now + _dt.timedelta(days=days_valid))
        .sign(private_key, hashes.SHA256())
    )
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    return private_key, cert_der


def test_fiel_backend_satisfies_protocol():
    """FielBackend cumple SignatureBackend Protocol."""
    assert isinstance(FielBackend(), SignatureBackend)


def test_fiel_backend_name():
    """name ClassVar = 'fiel'."""
    assert FielBackend.name == "fiel"


@pytest.mark.django_db
def test_fiel_backend_valid_signature():
    """Firma RSA-SHA256 válida persiste RegistroFirma con backend_name='fiel'."""
    private_key, cert_der = _make_keypair_and_cert()
    content = b"contenido a firmar"
    firma = private_key.sign(content, padding.PKCS1v15(), hashes.SHA256())

    rf = FielBackend().request_signature(
        content=content,
        signer=None,
        firma_b64=base64.b64encode(firma).decode(),
        certificado_cer_b64=base64.b64encode(cert_der).decode(),
    )
    assert rf.backend_name == "fiel"
    assert rf.verification_result == "VALIDA"
    assert "firma_pkcs7_b64" in rf.backend_metadata
    assert "certificado_cer_b64" in rf.backend_metadata


@pytest.mark.django_db
def test_fiel_backend_extracts_rfc_from_cert():
    """RFC del subject del cert se persiste en backend_metadata."""
    private_key, cert_der = _make_keypair_and_cert(serial_number_subject="XAXX010101000")
    content = b"contenido"
    firma = private_key.sign(content, padding.PKCS1v15(), hashes.SHA256())

    rf = FielBackend().request_signature(
        content=content,
        signer=None,
        firma_b64=base64.b64encode(firma).decode(),
        certificado_cer_b64=base64.b64encode(cert_der).decode(),
    )
    assert rf.backend_metadata["rfc_firmante"] == "XAXX010101000"
    assert "numero_serie_cer" in rf.backend_metadata


@pytest.mark.django_db
def test_fiel_backend_invalid_signature_raises():
    """Firma sobre content distinto raises SignatureValidationError."""
    private_key, cert_der = _make_keypair_and_cert()
    firma = private_key.sign(b"original", padding.PKCS1v15(), hashes.SHA256())

    with pytest.raises(SignatureValidationError, match="Firma inválida"):
        FielBackend().request_signature(
            content=b"OTRO_CONTENIDO",
            signer=None,
            firma_b64=base64.b64encode(firma).decode(),
            certificado_cer_b64=base64.b64encode(cert_der).decode(),
        )


def test_fiel_backend_missing_kwargs_raises():
    """Sin firma_b64 o certificado_cer_b64 raises."""
    with pytest.raises(SignatureValidationError, match="requires firma_b64"):
        FielBackend().request_signature(content=b"x", signer=None)


def test_fiel_backend_invalid_cert_b64_raises():
    """Cert b64 inválido raises."""
    with pytest.raises(SignatureValidationError, match="X.509 DER"):
        FielBackend().request_signature(
            content=b"x",
            signer=None,
            firma_b64="aGVsbG8=",  # b64 de 'hello' — no es firma RSA
            certificado_cer_b64="bm90X2NlcnQ=",  # b64 inválido como cert
        )


@pytest.mark.django_db
def test_fiel_backend_verify_persisted_registro():
    """verify() de un registro persistido valida cert internamente."""
    private_key, cert_der = _make_keypair_and_cert()
    content = b"contenido verify"
    firma = private_key.sign(content, padding.PKCS1v15(), hashes.SHA256())

    rf = FielBackend().request_signature(
        content=content,
        signer=None,
        firma_b64=base64.b64encode(firma).decode(),
        certificado_cer_b64=base64.b64encode(cert_der).decode(),
    )
    result = FielBackend().verify(rf)
    assert result.valid is True


@pytest.mark.django_db
def test_fiel_backend_revoke_marks_invalida():
    """revoke() marca verification_result='INVALIDA' + reason."""
    private_key, cert_der = _make_keypair_and_cert()
    content = b"x"
    firma = private_key.sign(content, padding.PKCS1v15(), hashes.SHA256())
    rf = FielBackend().request_signature(
        content=content,
        signer=None,
        firma_b64=base64.b64encode(firma).decode(),
        certificado_cer_b64=base64.b64encode(cert_der).decode(),
    )
    FielBackend().revoke(rf, reason="cert comprometido")
    rf.refresh_from_db()
    assert rf.verification_result == "INVALIDA"
    assert rf.backend_metadata["revoke_reason"] == "cert comprometido"


# ─────────────────────────────────────────────────────────────────────────────
# S13.6 T2 — sign_server_side + _with_secure_key_buffer cleanup
# ─────────────────────────────────────────────────────────────────────────────


def _make_pkcs8_der_encrypted_key(private_key: rsa.RSAPrivateKey, password: bytes) -> bytes:
    """Serializa private_key a PKCS#8 DER cifrado (formato SAT FIEL)."""
    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )


@pytest.fixture
def fiel_keypair_pem():
    """Genera keypair RSA + cert + DER PKCS#8 encrypted .key bytes (SAT FIEL format)."""
    private_key, cert_der = _make_keypair_and_cert()
    password = b"test-pass-2026"
    key_der_encrypted = _make_pkcs8_der_encrypted_key(private_key, password)
    return {
        "private_key": private_key,
        "cer_bytes": cert_der,
        "key_bytes": key_der_encrypted,
        "password": password,
    }


@pytest.mark.django_db
def test_sign_server_side_blocked_when_setting_false(fiel_keypair_pem, settings):
    """S13.6 T2 — modo B bloqueado cuando SINPAPEL_ALLOW_SERVER_SIGNING=False (default)."""
    from sinpapel.signing.exceptions import SignatureBackendNotConfiguredError

    settings.SINPAPEL_ALLOW_SERVER_SIGNING = False  # explicit
    with pytest.raises(SignatureBackendNotConfiguredError, match="Server-side signing"):
        FielBackend().sign_server_side(
            content=b"content",
            signer=None,
            cer_bytes=fiel_keypair_pem["cer_bytes"],
            key_bytes=fiel_keypair_pem["key_bytes"],
            password=fiel_keypair_pem["password"],
        )


@pytest.mark.django_db
def test_sign_server_side_persists_registro_firma(fiel_keypair_pem, settings):
    """S13.6 T2 — happy path con setting True → RegistroFirma persiste con metadata.mode."""
    settings.SINPAPEL_ALLOW_SERVER_SIGNING = True

    rf = FielBackend().sign_server_side(
        content=b"contenido server-side",
        signer=None,
        cer_bytes=fiel_keypair_pem["cer_bytes"],
        key_bytes=fiel_keypair_pem["key_bytes"],
        password=fiel_keypair_pem["password"],
        is_required=True,
    )
    assert rf.backend_name == "fiel"
    assert rf.verification_result == "VALIDA"
    assert rf.backend_metadata.get("mode") == "server-side"


@pytest.mark.django_db
def test_sign_server_side_invalid_password_raises(fiel_keypair_pem, settings):
    """S13.6 T2 — password incorrecta → SignatureValidationError con mensaje genérico."""
    settings.SINPAPEL_ALLOW_SERVER_SIGNING = True

    with pytest.raises(SignatureValidationError, match=r"Server-side signing failed"):
        FielBackend().sign_server_side(
            content=b"content",
            signer=None,
            cer_bytes=fiel_keypair_pem["cer_bytes"],
            key_bytes=fiel_keypair_pem["key_bytes"],
            password=b"WRONG_PASSWORD",
        )


def test_with_secure_key_buffer_cleanup_called_on_success(monkeypatch):
    """S13.6 T2 — _with_secure_key_buffer invoca gc.collect() en finally."""
    from sinpapel.signing.backends import fiel as fiel_module

    gc_calls = []
    monkeypatch.setattr(fiel_module.gc, "collect", lambda: gc_calls.append(1))

    with fiel_module._with_secure_key_buffer(b"keybytes", b"pwd"):
        pass

    assert len(gc_calls) == 1, "gc.collect() should be called exactly once on context exit"


def test_with_secure_key_buffer_cleanup_called_on_exception(monkeypatch):
    """S13.6 T2 — _with_secure_key_buffer invoca gc.collect() incluso si raisea."""
    from sinpapel.signing.backends import fiel as fiel_module

    gc_calls = []
    monkeypatch.setattr(fiel_module.gc, "collect", lambda: gc_calls.append(1))

    with pytest.raises(RuntimeError, match="signature failed"):
        with fiel_module._with_secure_key_buffer(b"keybytes", b"pwd"):
            raise RuntimeError("signature failed")

    assert len(gc_calls) == 1, "gc.collect() must run even if body raises (security)"


@pytest.mark.django_db
def test_sign_server_side_cleanup_runs_after_signing(fiel_keypair_pem, settings, monkeypatch):
    """S13.6 T2 — sign_server_side invoca gc.collect via wrapper post-firma."""
    from sinpapel.signing.backends import fiel as fiel_module
    settings.SINPAPEL_ALLOW_SERVER_SIGNING = True

    gc_calls = []
    monkeypatch.setattr(fiel_module.gc, "collect", lambda: gc_calls.append(1))

    FielBackend().sign_server_side(
        content=b"content",
        signer=None,
        cer_bytes=fiel_keypair_pem["cer_bytes"],
        key_bytes=fiel_keypair_pem["key_bytes"],
        password=fiel_keypair_pem["password"],
    )
    assert len(gc_calls) >= 1, "gc.collect() must run after sign_server_side"
