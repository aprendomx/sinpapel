"""Tests audit trail de RegistroFirma vía django-simple-history."""
from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from sinpapel.signing.backends.fiel import FielBackend
from sinpapel.tests.test_signing.test_fiel_backend import _make_keypair_and_cert


@pytest.mark.django_db
def test_registro_firma_create_appends_history_entry():
    """Crear un RegistroFirma deja 1 entrada history con history_type='+'."""
    private_key, cert_der = _make_keypair_and_cert()
    content = b"history smoke create"
    firma = private_key.sign(content, padding.PKCS1v15(), hashes.SHA256())
    rf = FielBackend().request_signature(
        content=content,
        signer=None,
        firma_b64=base64.b64encode(firma).decode(),
        certificado_cer_b64=base64.b64encode(cert_der).decode(),
    )
    assert rf.history.count() == 1
    entry = rf.history.first()
    assert entry.history_type == "+"
    assert entry.verification_result == "VALIDA"


@pytest.mark.django_db
def test_registro_firma_revoke_appends_update_entry():
    """revoke() produce 2 entradas: '+' (create) + '~' (update con verification_result='INVALIDA')."""
    private_key, cert_der = _make_keypair_and_cert()
    content = b"history smoke revoke"
    firma = private_key.sign(content, padding.PKCS1v15(), hashes.SHA256())
    rf = FielBackend().request_signature(
        content=content,
        signer=None,
        firma_b64=base64.b64encode(firma).decode(),
        certificado_cer_b64=base64.b64encode(cert_der).decode(),
    )
    FielBackend().revoke(rf, reason="cert comprometido")
    rf.refresh_from_db()

    assert rf.history.count() == 2
    latest = rf.history.first()
    earliest = rf.history.last()
    assert latest.history_type == "~"
    assert latest.verification_result == "INVALIDA"
    assert earliest.history_type == "+"
    assert earliest.verification_result == "VALIDA"


@pytest.mark.django_db
def test_registro_firma_history_diff_against_reports_changes():
    """diff_against() entre dos versiones reporta los campos cambiados."""
    private_key, cert_der = _make_keypair_and_cert()
    content = b"history smoke diff"
    firma = private_key.sign(content, padding.PKCS1v15(), hashes.SHA256())
    rf = FielBackend().request_signature(
        content=content,
        signer=None,
        firma_b64=base64.b64encode(firma).decode(),
        certificado_cer_b64=base64.b64encode(cert_der).decode(),
    )
    FielBackend().revoke(rf, reason="diff smoke")

    diff = rf.history.first().diff_against(rf.history.last())
    fields_changed = {c.field for c in diff.changes}
    assert "verification_result" in fields_changed
    # backend_metadata fue mutado por revoke (revoke_reason agregado)
    assert "backend_metadata" in fields_changed
