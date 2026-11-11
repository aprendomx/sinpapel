"""Issue #6 — certificados del SAT con PrintableString no conforme (AC6).

Fixtures en ``fixtures/sat/``: certificados PÚBLICOS de producción del SAT
(Cert_Prod.zip). AC6_SAT.crt y OCSP.AC6_SAT.cer (emitido por AC6) traen un
``unstructuredName`` PrintableString con «ó» en UTF-8, que ``cryptography``
rechaza con su parser estricto.
"""
from __future__ import annotations

import base64
import datetime as _dt
import logging
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.name import _ASN1Type
from cryptography.x509.oid import NameOID

from sinpapel.signing._x509_tolerante import cargar_der
from sinpapel.signing.backends.fiel import FielBackend
from sinpapel.signing.exceptions import (
    SignatureBackendNotConfiguredError,
    SignatureValidationError,
)

SAT = Path(__file__).parent / "fixtures" / "sat"


def _der_de_pem(path: Path) -> bytes:
    """DER de un PEM sin pasar por cryptography (AC6 no se puede parsear)."""
    cuerpo = path.read_bytes().split(b"-----")[2]
    return base64.b64decode(b"".join(cuerpo.split()))


# ─── certificados reales del SAT ──────────────────────────────────────────


def test_parser_estricto_rechaza_ac6():
    """Precondición: sin la ruta tolerante, cryptography no lee AC6."""
    with pytest.raises(ValueError):
        x509.load_pem_x509_certificate((SAT / "AC6_SAT.crt").read_bytes())


def test_cargar_der_lee_ac6_y_su_ocsp():
    ac6 = cargar_der(_der_de_pem(SAT / "AC6_SAT.crt"))
    ocsp = cargar_der((SAT / "OCSP.AC6_SAT.cer").read_bytes())

    assert ac6.normalizado and ocsp.normalizado
    nombre = ac6.cert.subject.get_attributes_for_oid(NameOID.UNSTRUCTURED_NAME)[0]
    assert nombre.value == (
        "responsable: Administración Central de Servicios Tributarios al Contribuyente"
    )
    assert ocsp.cert.issuer == ac6.cert.subject


def test_cargar_der_no_toca_certificados_conformes():
    der = _der_de_pem(SAT / "AC7.crt")
    leido = cargar_der(der)
    assert not leido.normalizado
    assert leido.tbs_original == leido.cert.tbs_certificate_bytes


def test_cadena_ocsp_ac6_verifica_contra_tbs_original():
    """La firma de AC6 cubre los bytes ORIGINALES: verifica con tbs_original
    y NO con el tbs re-etiquetado (la tolerancia no relaja la verificación)."""
    ac6 = cargar_der(_der_de_pem(SAT / "AC6_SAT.crt")).cert
    ocsp = cargar_der((SAT / "OCSP.AC6_SAT.cer").read_bytes())

    FielBackend()._verify_issuer_chain(ocsp.cert, [ac6], tbs=ocsp.tbs_original)
    with pytest.raises(SignatureValidationError):
        FielBackend()._verify_issuer_chain(ocsp.cert, [ac6])


def test_bundle_con_ac5_ac6_ac7_carga_las_tres(settings, tmp_path):
    bundle = tmp_path / "sat.pem"
    bundle.write_bytes(b"".join(
        (SAT / n).read_bytes() for n in ("AC5_SAT.crt", "AC6_SAT.crt", "AC7.crt")
    ))
    settings.SINPAPEL_FIEL_TRUSTED_CA_BUNDLE = str(bundle)

    cas = FielBackend()._load_trusted_cas()
    assert len(cas) == 3


def test_bundle_omite_certificado_ilegible_con_warning(settings, tmp_path, caplog):
    roto = b"-----BEGIN CERTIFICATE-----\nTk9FU1VOQ0VSVA==\n-----END CERTIFICATE-----\n"
    bundle = tmp_path / "sat.pem"
    bundle.write_bytes((SAT / "AC5_SAT.crt").read_bytes() + roto + (SAT / "AC7.crt").read_bytes())
    settings.SINPAPEL_FIEL_TRUSTED_CA_BUNDLE = str(bundle)

    with caplog.at_level(logging.WARNING, logger="sinpapel.signing.backends.fiel"):
        cas = FielBackend()._load_trusted_cas()

    assert len(cas) == 2
    assert any("#1" in r.getMessage() and "sat.pem" in r.getMessage() for r in caplog.records)


def test_bundle_sin_ningun_certificado_legible_falla(settings, tmp_path):
    bundle = tmp_path / "basura.pem"
    bundle.write_bytes(b"no es un certificado")
    settings.SINPAPEL_FIEL_TRUSTED_CA_BUNDLE = str(bundle)

    with pytest.raises(SignatureBackendNotConfiguredError, match="basura.pem"):
        FielBackend()._load_trusted_cas()


def test_bundle_der_individual(settings, tmp_path):
    ac = tmp_path / "ac7.cer"
    ac.write_bytes(_der_de_pem(SAT / "AC7.crt"))
    settings.SINPAPEL_FIEL_TRUSTED_CA_BUNDLE = [str(ac)]
    assert len(FielBackend()._load_trusted_cas()) == 1


# ─── extremo a extremo con una AC sintética «estilo AC6» ──────────────────

_RESPONSABLE = "responsable: Administración Tributaria"


def _retag_y_refirmar(cert: x509.Certificate, firmante: rsa.RSAPrivateKey) -> bytes:
    """Convierte el UTF8String de _RESPONSABLE en PrintableString (como hace el
    SAT) y vuelve a firmar el tbs resultante, de modo que el certificado sea
    criptográficamente válido pero no conforme."""
    valor = _RESPONSABLE.encode()
    utf8 = bytes([0x0C, len(valor)]) + valor
    printable = bytes([0x13, len(valor)]) + valor
    der = cert.public_bytes(serialization.Encoding.DER).replace(utf8, printable)
    tbs = cert.tbs_certificate_bytes.replace(utf8, printable)
    firma = firmante.sign(tbs, padding.PKCS1v15(), hashes.SHA256())
    assert len(firma) == 256  # mismo largo: se reemplaza en sitio
    return der[:-256] + firma


def _nombre(cn: str) -> x509.Name:
    return x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
        x509.NameAttribute(
            NameOID.UNSTRUCTURED_NAME, _RESPONSABLE, _type=_ASN1Type.UTF8String
        ),
    ])


def _builder(subject, issuer, public_key):
    now = _dt.datetime.now(_dt.timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=1))
        .not_valid_after(now + _dt.timedelta(days=365))
    )


@pytest.fixture
def ac_estilo_ac6():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = _nombre("AC ESTILO AC6")
    cert = (
        _builder(nombre, nombre, key.public_key())
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    der = _retag_y_refirmar(cert, key)
    with pytest.raises(ValueError):
        x509.load_der_x509_certificate(der)  # de verdad no conforme
    return key, nombre, der


def _firmante(ac_key, ac_nombre):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "FIRMANTE"),
        x509.NameAttribute(NameOID.X500_UNIQUE_IDENTIFIER, "XAXX010101000"),
    ])
    cert = _builder(subject, ac_nombre, key.public_key()).sign(ac_key, hashes.SHA256())
    return key, _retag_y_refirmar(cert, ac_key)


@pytest.mark.django_db
def test_firma_emitida_por_ac_no_conforme_es_valida(settings, tmp_path, ac_estilo_ac6):
    ac_key, ac_nombre, ac_der = ac_estilo_ac6
    bundle = tmp_path / "ac.cer"
    bundle.write_bytes(ac_der)
    settings.SINPAPEL_FIEL_TRUSTED_CA_BUNDLE = str(bundle)

    key, cer = _firmante(ac_key, ac_nombre)
    contenido = b"contenido"
    rf = FielBackend().request_signature(
        content=contenido,
        signer=None,
        firma_b64=base64.b64encode(
            key.sign(contenido, padding.PKCS1v15(), hashes.SHA256())
        ).decode(),
        certificado_cer_b64=base64.b64encode(cer).decode(),
    )
    assert rf.verification_result == "VALIDA"
    assert rf.backend_metadata["rfc_firmante"] == "XAXX010101000"
    assert rf.backend_metadata["certificado_cer_b64"] == base64.b64encode(cer).decode()


@pytest.mark.django_db
def test_cert_no_conforme_de_otra_ac_se_rechaza(settings, tmp_path, ac_estilo_ac6):
    """Mismo nombre de emisor pero firmado por otra llave: la cadena falla."""
    _, ac_nombre, ac_der = ac_estilo_ac6
    bundle = tmp_path / "ac.cer"
    bundle.write_bytes(ac_der)
    settings.SINPAPEL_FIEL_TRUSTED_CA_BUNDLE = str(bundle)

    impostor = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key, cer = _firmante(impostor, ac_nombre)
    contenido = b"contenido"
    with pytest.raises(SignatureValidationError, match="bundle de"):
        FielBackend().request_signature(
            content=contenido,
            signer=None,
            firma_b64=base64.b64encode(
                key.sign(contenido, padding.PKCS1v15(), hashes.SHA256())
            ).decode(),
            certificado_cer_b64=base64.b64encode(cer).decode(),
        )


def test_printable_no_utf8_se_lee_como_t61():
    """Contenido que ni siquiera es UTF-8 (Latin-1) cae a T61String."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(
        NameOID.COMMON_NAME, "AXAA", _type=_ASN1Type.PrintableString
    )])
    cert = _builder(nombre, nombre, key.public_key()).sign(key, hashes.SHA256())
    der = cert.public_bytes(serialization.Encoding.DER).replace(b"AXAA", b"A\xf3AA")

    leido = cargar_der(der)
    assert leido.normalizado
    assert leido.tbs_original != leido.cert.tbs_certificate_bytes
    assert len(leido.tbs_original) == len(leido.cert.tbs_certificate_bytes)


def test_der_basura_conserva_error_original():
    with pytest.raises(ValueError):
        cargar_der(b"\x30\x03\x02\x01")


def test_der_anidado_hostil_no_revienta_la_pila():
    """Miles de SEQUENCE anidados: ValueError, nunca RecursionError."""
    der = b"\x13\x01\xff"  # PrintableString no conforme en el fondo
    for _ in range(5000):
        der = b"\x30" + (
            bytes([len(der)]) if len(der) < 128
            else bytes([0x84]) + len(der).to_bytes(4, "big")
        ) + der
    with pytest.raises(ValueError):
        cargar_der(der)
