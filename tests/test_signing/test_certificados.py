"""Issue #7 — API pública de lectura de certificados (sinpapel.signing).

Usa los certificados públicos de producción del SAT de ``fixtures/sat/``.
"""
from __future__ import annotations

import datetime as _dt
import os
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

import sinpapel.signing as signing
from sinpapel.signing import (
    BundleCargado,
    CertificadoLeido,
    SignatureBackendNotConfiguredError,
    cargar_bundle_confianza,
    emitido_por,
    leer_certificado,
)
from sinpapel.signing.backends.fiel import FielBackend

SAT = Path(__file__).parent / "fixtures" / "sat"
AC5, AC6, AC7, OCSP_AC6 = (
    SAT / "AC5_SAT.crt", SAT / "AC6_SAT.crt", SAT / "AC7.crt", SAT / "OCSP.AC6_SAT.cer"
)
BASURA_PEM = b"-----BEGIN CERTIFICATE-----\nTk9FU1VOQ0VSVA==\n-----END CERTIFICATE-----\n"


def test_api_exportada_en_sinpapel_signing():
    for nombre in (
        "leer_certificado", "cargar_bundle_confianza", "emitido_por",
        "CertificadoLeido", "BundleCargado",
    ):
        assert nombre in signing.__all__


# ─── leer_certificado ─────────────────────────────────────────────────────


def test_leer_certificado_pem_ac6_con_ruta_tolerante():
    leido = leer_certificado(AC6.read_bytes())
    assert isinstance(leido, CertificadoLeido)
    assert leido.normalizado


def test_leer_certificado_der():
    leido = leer_certificado(OCSP_AC6.read_bytes())
    assert leido.normalizado
    bc = leido.cert.extensions.get_extension_for_class(x509.BasicConstraints)
    assert bc.value.ca is False  # entidad final emitida por AC6


def test_leer_certificado_conforme_no_se_normaliza():
    leido = leer_certificado(AC7.read_bytes())
    assert not leido.normalizado
    assert leido.tbs_original == leido.cert.tbs_certificate_bytes


def test_leer_certificado_pem_con_varios_rechaza():
    with pytest.raises(ValueError, match="cargar_bundle_confianza"):
        leer_certificado(AC5.read_bytes() + AC7.read_bytes())


def test_leer_certificado_basura_rechaza():
    with pytest.raises(ValueError):
        leer_certificado(b"no es un certificado")
    with pytest.raises(ValueError):
        leer_certificado(BASURA_PEM)


# ─── cargar_bundle_confianza ──────────────────────────────────────────────


def test_bundle_pem_con_ac5_ac6_ac7(tmp_path):
    bundle = tmp_path / "sat.pem"
    bundle.write_bytes(AC5.read_bytes() + AC6.read_bytes() + AC7.read_bytes())

    cargado = cargar_bundle_confianza(bundle)  # acepta Path

    assert isinstance(cargado, BundleCargado)
    assert len(cargado.cas) == 3
    assert cargado.omitidos == []
    assert cargado.normalizados == [f"{bundle}#1"]


def test_bundle_lista_de_rutas():
    cargado = cargar_bundle_confianza([str(AC5), str(AC7), OCSP_AC6])
    assert len(cargado.cas) == 3


def test_bundle_reporta_bloque_basura(tmp_path):
    bundle = tmp_path / "sat.pem"
    bundle.write_bytes(AC5.read_bytes() + BASURA_PEM + AC7.read_bytes())

    cargado = cargar_bundle_confianza(str(bundle))

    assert len(cargado.cas) == 2
    assert cargado.omitidos == [f"{bundle}#1"]
    assert cargado.motivos[f"{bundle}#1"]


def test_bundle_sin_ningun_legible_falla(tmp_path):
    basura = tmp_path / "basura.pem"
    basura.write_bytes(BASURA_PEM)
    with pytest.raises(SignatureBackendNotConfiguredError, match="basura.pem#0"):
        cargar_bundle_confianza(basura)
    with pytest.raises(SignatureBackendNotConfiguredError):
        cargar_bundle_confianza([])


def test_bundle_archivo_inexistente_propaga_oserror(tmp_path):
    with pytest.raises(OSError):
        cargar_bundle_confianza(tmp_path / "no-existe.pem")


# ─── emitido_por ──────────────────────────────────────────────────────────


@pytest.fixture
def cas_sat():
    return cargar_bundle_confianza([AC5, AC6, AC7]).cas


def test_emitido_por_ocsp_de_ac6_devuelve_ac6(cas_sat):
    ac6 = leer_certificado(AC6.read_bytes()).cert
    assert emitido_por(leer_certificado(OCSP_AC6.read_bytes()), cas_sat) == ac6


def test_emitido_por_exige_tbs_original(cas_sat):
    """Con el x509.Certificate re-etiquetado (sin tbs_original) la firma no
    verifica: hay que pasar el CertificadoLeido."""
    assert emitido_por(leer_certificado(OCSP_AC6.read_bytes()).cert, cas_sat) is None


def test_emitido_por_autofirmado_devuelve_none(cas_sat):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AUTOFIRMADO")])
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nombre).issuer_name(nombre)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(days=1))
        .not_valid_after(now + _dt.timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    der = cert.public_bytes(serialization.Encoding.DER)
    assert emitido_por(leer_certificado(der), cas_sat) is None
    assert emitido_por(cert, cas_sat) is None  # acepta x509.Certificate


def test_emitido_por_respeta_vigencia_de_la_ac(cas_sat):
    ocsp = leer_certificado(OCSP_AC6.read_bytes())
    despues_de_ac6 = _dt.datetime(2031, 6, 1, tzinfo=_dt.timezone.utc)
    assert emitido_por(ocsp, cas_sat, en=despues_de_ac6) is None


# ─── FielBackend usa la misma implementación ──────────────────────────────


def test_fiel_backend_carga_el_mismo_bundle(settings, tmp_path):
    bundle = tmp_path / "sat.pem"
    bundle.write_bytes(AC5.read_bytes() + AC6.read_bytes() + AC7.read_bytes())
    settings.SINPAPEL_FIEL_TRUSTED_CA_BUNDLE = str(bundle)

    assert FielBackend()._load_trusted_cas() == cargar_bundle_confianza(bundle).cas


def test_se_importa_sin_settings_de_django():
    """Para scripts de despliegue: sin DJANGO_SETTINGS_MODULE ni modelos."""
    env = {k: v for k, v in os.environ.items() if k != "DJANGO_SETTINGS_MODULE"}
    codigo = (
        "import sys\n"
        "from sinpapel.signing import cargar_bundle_confianza\n"
        f"print(len(cargar_bundle_confianza([{str(AC5)!r}, {str(AC6)!r}]).cas))\n"
        "assert 'sinpapel.models' not in sys.modules\n"
    )
    raiz = Path(__file__).resolve().parents[3]  # dir que contiene el paquete
    out = subprocess.run(
        [sys.executable, "-c", codigo], env=env, cwd=raiz,
        capture_output=True, text=True, check=True,
    )
    assert out.stdout.strip() == "2"
