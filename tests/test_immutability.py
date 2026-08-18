"""Tests 0.8.0 — inmutabilidad enforceada y políticas on_delete de auditoría."""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User


@pytest.fixture
def seguimiento(db):
    from sinpapel.models import Estado, SeguimientoWorkflow
    from tests.models import TestTrazableModel

    user = User.objects.create_user("imm_user", password="x")
    estado = Estado.objects.create(nombre="IMM_ESTADO")
    target = TestTrazableModel.objects.create(name="imm-target")
    seg = SeguimientoWorkflow.objects.create(
        target=target,
        estado_nuevo=estado,
        usuario_accion=user,
        comentarios="registro original",
    )
    return seg


@pytest.mark.django_db
def test_seguimiento_no_se_puede_modificar(seguimiento):
    seguimiento.comentarios = "editado a posteriori"
    with pytest.raises(ValueError, match="inmutable"):
        seguimiento.save()


@pytest.mark.django_db
def test_seguimiento_no_se_puede_borrar(seguimiento):
    with pytest.raises(ValueError, match="inmutable"):
        seguimiento.delete()


@pytest.mark.django_db
def test_registro_firma_no_se_puede_borrar(db):
    from sinpapel.models import RegistroFirma

    rf = RegistroFirma.objects.create(
        backend_name="fake",
        signer_display_name="Firmante",
        content_hash="sha256:abc",
        signed_at="2026-01-01T00:00:00Z",
    )
    with pytest.raises(ValueError, match="no se borra"):
        rf.delete()


@pytest.mark.django_db
def test_borrar_user_no_arrasa_registros_trazables(db):
    """Trazable.autor es SET_NULL: borrar el User preserva el registro."""
    from tests.models import TestTrazableModel

    autor = User.objects.create_user("imm_autor", password="x")
    obj = TestTrazableModel.objects.create(name="sobreviviente", autor=autor)

    autor.delete()

    obj.refresh_from_db()
    assert obj.autor is None
    assert obj.name == "sobreviviente"
