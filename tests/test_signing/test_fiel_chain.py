"""Tests 0.8.0 — cadena de confianza FIEL (SINPAPEL_FIEL_TRUSTED_CA_BUNDLE)."""
from __future__ import annotations

import base64
import datetime as _dt

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from sinpapel.signing.backends.fiel import FielBackend
from sinpapel.signing.exceptions import SignatureValidationError


def _name(cn: str, serial: str | None = None) -> x509.Name:
    attrs = [x509.NameAttribute(NameOID.COMMON_NAME, cn)]
    if serial:
        attrs.append(x509.NameAttribute(NameOID.SERIAL_NUMBER, serial))
    return x509.Name(attrs)


def _make_ca() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    """AC autofirmada (simula una AC del SAT)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = _dt.datetime.now(_dt.timezone.utc)
    name = _name("AC PRUEBAS SAT")
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=1))
        .not_valid_after(now + _dt.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _make_leaf(
    ca_key: rsa.RSAPrivateKey, ca_cert: x509.Certificate, rfc: str = "LEAFRFC000"
) -> tuple[rsa.RSAPrivateKey, bytes]:
    """Cert de firmante emitido por la AC."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name("FIRMANTE EMITIDO", rfc))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=1))
        .not_valid_after(now + _dt.timedelta(days=365))
        .sign(ca_key, hashes.SHA256())
    )
    return key, cert.public_bytes(serialization.Encoding.DER)


def _self_signed(days_valid: int = 365) -> tuple[rsa.RSAPrivateKey, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = _dt.datetime.now(_dt.timezone.utc)
    name = _name("AUTOFIRMADO", "FAKERFC000")
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=2))
        .not_valid_after(now + _dt.timedelta(days=days_valid))
        .sign(key, hashes.SHA256())
    )
    return key, cert.public_bytes(serialization.Encoding.DER)


def _sign(key: rsa.RSAPrivateKey, content: bytes) -> str:
    return base64.b64encode(
        key.sign(content, padding.PKCS1v15(), hashes.SHA256())
    ).decode("ascii")


@pytest.fixture
def ca_bundle(tmp_path):
    ca_key, ca_cert = _make_ca()
    bundle_path = tmp_path / "sat_cas.pem"
    bundle_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    return {"key": ca_key, "cert": ca_cert, "path": str(bundle_path)}


@pytest.mark.django_db
def test_cert_emitido_por_ca_del_bundle_es_valida(ca_bundle, settings):
    settings.SINPAPEL_FIEL_TRUSTED_CA_BUNDLE = ca_bundle["path"]
    leaf_key, leaf_der = _make_leaf(ca_bundle["key"], ca_bundle["cert"])
    content = b"contenido con cadena"

    rf = FielBackend().request_signature(
        content=content,
        signer=None,
        firma_b64=_sign(leaf_key, content),
        certificado_cer_b64=base64.b64encode(leaf_der).decode("ascii"),
    )
    assert rf.verification_result == "VALIDA"
    assert rf.backend_metadata["cadena_verificada"] is True


@pytest.mark.django_db
def test_autofirmado_con_bundle_se_rechaza(ca_bundle, settings):
    settings.SINPAPEL_FIEL_TRUSTED_CA_BUNDLE = ca_bundle["path"]
    key, der = _self_signed()
    content = b"contenido autofirmado"

    with pytest.raises(SignatureValidationError, match="AC del bundle"):
        FielBackend().request_signature(
            content=content,
            signer=None,
            firma_b64=_sign(key, content),
            certificado_cer_b64=base64.b64encode(der).decode("ascii"),
        )


@pytest.mark.django_db
def test_sin_bundle_marca_valida_sin_cadena(settings):
    settings.SINPAPEL_FIEL_TRUSTED_CA_BUNDLE = None
    key, der = _self_signed()
    content = b"sin bundle"

    rf = FielBackend().request_signature(
        content=content,
        signer=None,
        firma_b64=_sign(key, content),
        certificado_cer_b64=base64.b64encode(der).decode("ascii"),
    )
    assert rf.verification_result == "VALIDA_SIN_CADENA"
    assert rf.backend_metadata["cadena_verificada"] is False


@pytest.mark.django_db
def test_cert_expirado_se_rechaza():
    """Cubre la rama de vigencia que la auditoría señaló sin test."""
    key, der = _self_signed(days_valid=-1)  # ya expirado
    content = b"contenido expirado"

    with pytest.raises(SignatureValidationError, match="expirado"):
        FielBackend().request_signature(
            content=content,
            signer=None,
            firma_b64=_sign(key, content),
            certificado_cer_b64=base64.b64encode(der).decode("ascii"),
        )
