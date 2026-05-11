"""Tests para ManualBackend."""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User

from sinpapel.signing import SignatureBackend, VerificationResult
from sinpapel.signing.backends.manual import ManualBackend


def test_manual_backend_satisfies_protocol():
    """ManualBackend cumple SignatureBackend Protocol."""
    assert isinstance(ManualBackend(), SignatureBackend)


def test_manual_backend_name():
    """name ClassVar = 'manual'."""
    assert ManualBackend.name == "manual"


@pytest.mark.django_db
def test_manual_backend_creates_registro_with_backend_name_manual():
    """request_signature persiste RegistroFirma con backend_name='manual'."""
    user = User.objects.create_user("manual_test_create", password="x")
    rf = ManualBackend().request_signature(
        content=b"contenido test",
        signer=user,
        scanned_image_path="/tmp/scan.png",
        witness_name="Testigo X",
    )
    assert rf.backend_name == "manual"
    assert rf.backend_metadata["scanned_image_path"] == "/tmp/scan.png"
    assert rf.backend_metadata["witness_name"] == "Testigo X"
    assert "timestamp" in rf.backend_metadata
    assert rf.signer == user
    assert rf.verification_result == "VALIDA"
    assert rf.content_hash.startswith("sha256:")


@pytest.mark.django_db
def test_manual_backend_signer_optional():
    """signer=None acepta firma con sólo witness_name."""
    rf = ManualBackend().request_signature(
        content=b"x",
        signer=None,
        witness_name="Solo Testigo",
    )
    assert rf.signer is None
    assert rf.signer_display_name == "Solo Testigo"


@pytest.mark.django_db
def test_manual_backend_verify_always_valid():
    """Manual no se invalida criptográficamente."""
    user = User.objects.create_user("manual_verify_test", password="x")
    rf = ManualBackend().request_signature(content=b"x", signer=user)
    result = ManualBackend().verify(rf)
    assert result.valid is True
    assert result.reason is None


@pytest.mark.django_db
def test_manual_backend_revoke_marks_invalida():
    """revoke() marca verification_result='INVALIDA' y guarda reason."""
    user = User.objects.create_user("manual_revoke_test", password="x")
    rf = ManualBackend().request_signature(content=b"x", signer=user)
    ManualBackend().revoke(rf, reason="firma sospechosa")
    rf.refresh_from_db()
    assert rf.verification_result == "INVALIDA"
    assert rf.backend_metadata["revoke_reason"] == "firma sospechosa"
