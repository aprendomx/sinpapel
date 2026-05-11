"""Tests para FakeBackend."""
from __future__ import annotations

import hashlib

import pytest
from django.contrib.auth.models import User

from sinpapel.signing import SignatureBackend
from sinpapel.signing.backends.fake import FakeBackend


def test_fake_backend_satisfies_protocol():
    """FakeBackend cumple SignatureBackend Protocol."""
    assert isinstance(FakeBackend(), SignatureBackend)


def test_fake_backend_name():
    """name ClassVar = 'fake'."""
    assert FakeBackend.name == "fake"


@pytest.mark.django_db
def test_fake_backend_creates_registro_deterministic():
    """request_signature genera content_hash determinístico via SHA-256."""
    user = User.objects.create_user("fake_test_create", password="x")
    content = b"contenido deterministico"
    rf = FakeBackend().request_signature(content=content, signer=user)

    expected_hash = "sha256:" + hashlib.sha256(content).hexdigest()
    assert rf.backend_name == "fake"
    assert rf.content_hash == expected_hash
    assert rf.backend_metadata == {"fake": True}
    assert rf.verification_result == "VALIDA"


@pytest.mark.django_db
def test_fake_backend_signer_optional():
    """signer=None acepta — display_name default 'fake_signer'."""
    rf = FakeBackend().request_signature(content=b"x", signer=None)
    assert rf.signer is None
    assert rf.signer_display_name == "fake_signer"


@pytest.mark.django_db
def test_fake_backend_verify_always_valid():
    """verify() siempre VerificationResult(valid=True)."""
    user = User.objects.create_user("fake_verify_test", password="x")
    rf = FakeBackend().request_signature(content=b"x", signer=user)
    result = FakeBackend().verify(rf)
    assert result.valid is True


@pytest.mark.django_db
def test_fake_backend_revoke_is_noop():
    """revoke() es no-op (Fake nunca se considera revocado)."""
    user = User.objects.create_user("fake_revoke_test", password="x")
    rf = FakeBackend().request_signature(content=b"x", signer=user)
    initial_result = rf.verification_result
    FakeBackend().revoke(rf, reason="ignored")
    rf.refresh_from_db()
    assert rf.verification_result == initial_result
