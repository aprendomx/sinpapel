"""Tests integration para WorkflowEngine con modelos de prueba + DB."""
from __future__ import annotations

import pytest
from django.contrib.auth.models import Group, User

from sinpapel.services.workflow_engine import WorkflowEngine


@pytest.fixture
def setup_engine_basico(db):
    """Crea Estado, VersionFlujo, ConfiguracionTransicion, TestProducto, TestSolicitud."""
    from sinpapel.models import (
        ConfiguracionTransicion,
        Estado,
        VersionFlujo,
    )
    from tests.models import TestProducto, TestProductoVersionFlujo, TestSolicitud

    estado_origen, _ = Estado.objects.get_or_create(nombre="ENG_ORIGEN")
    estado_destino, _ = Estado.objects.get_or_create(nombre="ENG_DESTINO")
    flujo = VersionFlujo.objects.create(nombre="ENG_FLUJO", activo=True)
    transicion = ConfiguracionTransicion.objects.create(
        flujo=flujo,
        estado_origen=estado_origen,
        estado_destino=estado_destino,
    )
    producto = TestProducto.objects.create(nombre="ENG_P", flujo=flujo)
    TestProductoVersionFlujo.objects.create(producto=producto, flujo=flujo)
    solicitud = TestSolicitud.objects.create(estado=estado_origen, producto=producto, folio="ENG-001")
    return {
        "solicitud": solicitud,
        "estado_origen": estado_origen,
        "estado_destino": estado_destino,
        "flujo": flujo,
        "producto": producto,
        "transicion": transicion,
    }


@pytest.mark.django_db
def test_engine_puede_cambiar_estado_valid_transition(setup_engine_basico):
    superuser = User.objects.create_superuser("eng_super_valid", password="x")
    puede, msg = WorkflowEngine().puede_cambiar_estado(
        setup_engine_basico["solicitud"],
        "ENG_DESTINO",
        superuser,
    )
    assert puede is True
    assert msg == "OK"


@pytest.mark.django_db
def test_engine_puede_cambiar_estado_invalid_transition(setup_engine_basico):
    superuser = User.objects.create_superuser("eng_super_invalid", password="x")
    puede, msg = WorkflowEngine().puede_cambiar_estado(
        setup_engine_basico["solicitud"],
        "ESTADO_NUNCA_CONFIGURADO",
        superuser,
    )
    assert puede is False
    assert "no existe" in (msg or "")


@pytest.mark.django_db
def test_engine_cambiar_estado_creates_seguimiento(setup_engine_basico):
    from sinpapel.models import SeguimientoWorkflow

    superuser = User.objects.create_superuser("eng_super_change", password="x")
    seguimientos_antes = SeguimientoWorkflow.objects.count()

    result = WorkflowEngine().cambiar_estado(
        instance=setup_engine_basico["solicitud"],
        target_state_name="ENG_DESTINO",
        user=superuser,
        comentarios="test cambiar",
    )

    assert result["success"] is True
    assert result["estado_anterior"] == "ENG_ORIGEN"
    assert result["estado_nuevo"] == "ENG_DESTINO"
    assert SeguimientoWorkflow.objects.count() == seguimientos_antes + 1

    setup_engine_basico["solicitud"].refresh_from_db()
    assert setup_engine_basico["solicitud"].estado.nombre == "ENG_DESTINO"


@pytest.mark.django_db
def test_engine_available_transitions_returns_list(setup_engine_basico):
    user = User.objects.create_user("eng_avail", password="x")
    transitions = WorkflowEngine().available_transitions(
        setup_engine_basico["solicitud"],
        user,
    )
    assert setup_engine_basico["estado_destino"] in transitions


@pytest.mark.django_db
def test_engine_invalid_transition_raises_permission_error(setup_engine_basico):
    superuser = User.objects.create_superuser("eng_super_raise", password="x")
    with pytest.raises(PermissionError):
        WorkflowEngine().cambiar_estado(
            instance=setup_engine_basico["solicitud"],
            target_state_name="ESTADO_NUNCA_CONFIG",
            user=superuser,
            comentarios="x",
        )


@pytest.mark.django_db
def test_engine_resolves_flujo_via_resolve_workflow_version(setup_engine_basico):
    flujo = setup_engine_basico["solicitud"].resolve_workflow_version()
    assert flujo is not None
    assert flujo.nombre == "ENG_FLUJO"


@pytest.mark.django_db
def test_engine_validates_grupos_permitidos(setup_engine_basico):
    grupo_test = Group.objects.create(name="grupo_eng_test")
    setup_engine_basico["transicion"].grupos_permitidos.add(grupo_test)

    user_sin_grupo = User.objects.create_user("eng_no_group", password="x")
    puede, msg = WorkflowEngine().puede_cambiar_estado(
        setup_engine_basico["solicitud"],
        "ENG_DESTINO",
        user_sin_grupo,
    )
    assert puede is False
    assert "No tiene permisos" in (msg or "")


@pytest.mark.django_db
def test_engine_grupos_permitidos_user_in_group_passes(setup_engine_basico):
    grupo_ok = Group.objects.create(name="grupo_eng_ok")
    setup_engine_basico["transicion"].grupos_permitidos.add(grupo_ok)

    user = User.objects.create_user("eng_with_group", password="x")
    user.groups.add(grupo_ok)

    puede, msg = WorkflowEngine().puede_cambiar_estado(
        setup_engine_basico["solicitud"],
        "ENG_DESTINO",
        user,
    )
    assert puede is True


@pytest.mark.django_db
def test_engine_dispatches_side_effects(setup_engine_basico):
    from sinpapel.services.side_effects import SIDE_EFFECTS

    invocations: list[dict] = []

    def _test_handler(instance, user, **kwargs):
        invocations.append(
            {
                "instance_id": instance.id,
                "user_username": user.username,
                "kwargs": kwargs,
            }
        )
        return {"side_effect_ran": True}

    SIDE_EFFECTS["ENG_DESTINO"] = _test_handler
    try:
        superuser = User.objects.create_superuser("eng_se", password="x")
        result = WorkflowEngine().cambiar_estado(
            instance=setup_engine_basico["solicitud"],
            target_state_name="ENG_DESTINO",
            user=superuser,
            comentarios="se test",
        )
        assert result.get("side_effect_ran") is True
        assert len(invocations) == 1
        assert invocations[0]["instance_id"] == setup_engine_basico["solicitud"].id
    finally:
        del SIDE_EFFECTS["ENG_DESTINO"]


@pytest.mark.django_db
def test_engine_atomic_transaction(setup_engine_basico):
    from sinpapel.models import SeguimientoWorkflow
    from sinpapel.services.side_effects import SIDE_EFFECTS

    def _bad_handler(instance, user, **kwargs):
        raise RuntimeError("side effect failure")

    SIDE_EFFECTS["ENG_DESTINO"] = _bad_handler
    try:
        superuser = User.objects.create_superuser("eng_atom", password="x")
        seguimientos_antes = SeguimientoWorkflow.objects.count()

        result = WorkflowEngine().cambiar_estado(
            instance=setup_engine_basico["solicitud"],
            target_state_name="ENG_DESTINO",
            user=superuser,
            comentarios="atomic test",
        )

        setup_engine_basico["solicitud"].refresh_from_db()
        assert setup_engine_basico["solicitud"].estado.nombre == "ENG_DESTINO"
        assert SeguimientoWorkflow.objects.count() == seguimientos_antes + 1
        assert result.get("error") is True
    finally:
        del SIDE_EFFECTS["ENG_DESTINO"]


@pytest.mark.django_db
def test_engine_accepts_pre_created_registro_firma(setup_engine_basico):
    from sinpapel.models import RegistroFirma, SeguimientoWorkflow
    import datetime

    superuser = User.objects.create_superuser("eng_modo_b", password="x")
    rf = RegistroFirma.objects.create(
        backend_name="fiel",
        backend_metadata={"mode": "server-side", "rfc_firmante": "TEST"},
        content_hash="sha256:abc",
        signer=superuser,
        signer_display_name="TEST USER",
        is_required=True,
        verification_result="VALIDA",
        signed_at=datetime.datetime.now(datetime.timezone.utc),
    )

    seg_before = SeguimientoWorkflow.objects.count()
    result = WorkflowEngine().cambiar_estado(
        instance=setup_engine_basico["solicitud"],
        target_state_name="ENG_DESTINO",
        user=superuser,
        comentarios="test modo B",
        firma_payload={"registro_firma_id": rf.id},
    )
    assert result["success"] is True
    seg = SeguimientoWorkflow.objects.latest("id")
    assert seg.firma_registro_id == rf.id
    assert SeguimientoWorkflow.objects.count() == seg_before + 1


@pytest.mark.django_db
def test_engine_modo_a_verify_fields_uses_fiel_backend(setup_engine_basico, monkeypatch):
    from sinpapel.models import RegistroFirma
    from sinpapel.signing.backends import fiel as fiel_module

    captured = {}

    class _MockFielBackend:
        def request_signature(self, **kwargs):
            captured.update(kwargs)
            return RegistroFirma.objects.create(
                backend_name="fiel",
                backend_metadata={"mock": True},
                content_hash="sha256:mock",
                signer=kwargs.get("signer"),
                signer_display_name="MOCK",
                is_required=kwargs.get("is_required", False),
                verification_result="VALIDA",
                signed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )

    monkeypatch.setattr(fiel_module, "FielBackend", _MockFielBackend)

    superuser = User.objects.create_superuser("eng_modo_a", password="x")
    payload = {
        "contenido": b"canonical content",
        "firma_b64": "ZmFrZQ==",
        "certificado_cer_b64": "ZmFrZWNlcnQ=",
    }
    result = WorkflowEngine().cambiar_estado(
        instance=setup_engine_basico["solicitud"],
        target_state_name="ENG_DESTINO",
        user=superuser,
        comentarios="test modo A",
        firma_payload=payload,
    )
    assert result["success"] is True
    assert captured["firma_b64"] == "ZmFrZQ=="
    assert captured["certificado_cer_b64"] == "ZmFrZWNlcnQ="
    assert captured["content"] == b"canonical content"
    assert captured["signer"] == superuser
