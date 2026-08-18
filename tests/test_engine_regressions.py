"""Tests de regresión — fixes de auditoría 0.7.1.

Cubre:
1. historial_reciente con contenido real (bug GFK filter → siempre []).
2. Revalidación bajo lock: una copia stale no puede duplicar la transición.
3. instance.available_transitions respeta el VersionFlujo resuelto.
4. Side effects se ejecutan post-commit (fuera de la transacción del motor).
"""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.db import transaction

from sinpapel.services.side_effects import SIDE_EFFECTS


@pytest.fixture
def setup_reg(db):
    """Estado ORIGEN→DESTINO en un flujo activo, con producto→flujo."""
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo
    from tests.models import TestProducto, TestSolicitud

    origen, _ = Estado.objects.get_or_create(nombre="REG_ORIGEN")
    destino, _ = Estado.objects.get_or_create(nombre="REG_DESTINO")
    flujo = VersionFlujo.objects.create(nombre="REG_FLUJO", activo=True)
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=origen, estado_destino=destino
    )
    # Regreso configurado para poder previsualizar desde REG_DESTINO
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=destino, estado_destino=origen
    )
    producto = TestProducto.objects.create(nombre="REG_P", flujo=flujo)
    solicitud = TestSolicitud.objects.create(
        estado=origen, producto=producto, folio="REG-001"
    )
    return {
        "solicitud": solicitud,
        "origen": origen,
        "destino": destino,
        "flujo": flujo,
    }


@pytest.mark.django_db
def test_historial_reciente_contiene_transiciones(setup_reg):
    """preview_transition debe reportar el historial real del target (no [])."""
    superuser = User.objects.create_superuser("reg_hist", password="x")
    solicitud = setup_reg["solicitud"]

    solicitud.transition("REG_DESTINO", superuser, comentarios="primera")

    preview = solicitud.preview_transition("REG_ORIGEN", superuser)
    historial = preview["historial_reciente"]
    assert len(historial) == 1
    assert historial[0]["transicion"] == "REG_ORIGEN → REG_DESTINO"
    assert historial[0]["usuario"] == "reg_hist"
    assert historial[0]["comentarios"] == "primera"


@pytest.mark.django_db
def test_historial_reciente_no_mezcla_targets(setup_reg):
    """El historial es del target consultado, no de otras instancias."""
    from tests.models import TestSolicitud

    superuser = User.objects.create_superuser("reg_hist2", password="x")
    setup_reg["solicitud"].transition("REG_DESTINO", superuser)

    otra = TestSolicitud.objects.create(
        estado=setup_reg["origen"],
        producto=setup_reg["solicitud"].producto,
        folio="REG-002",
    )
    preview = otra.preview_transition("REG_DESTINO", superuser)
    assert preview["historial_reciente"] == []


@pytest.mark.django_db
def test_copia_stale_no_puede_duplicar_transicion(setup_reg):
    """Dos copias en memoria: la segunda (stale) debe revalidar contra DB."""
    from sinpapel.models import SeguimientoWorkflow
    from tests.models import TestSolicitud

    superuser = User.objects.create_superuser("reg_stale", password="x")
    fresca = setup_reg["solicitud"]
    stale = TestSolicitud.objects.get(pk=fresca.pk)

    fresca.transition("REG_DESTINO", superuser)

    # La copia stale aún cree estar en REG_ORIGEN; el motor debe re-leer
    # el estado bajo lock y rechazar (DESTINO→DESTINO no está configurada).
    with pytest.raises(PermissionError):
        stale.transition("REG_DESTINO", superuser)

    assert (
        SeguimientoWorkflow.objects.filter(
            target_object_id=fresca.pk,
            estado_nuevo=setup_reg["destino"],
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_available_transitions_respeta_flujo(setup_reg):
    """instance.available_transitions filtra por el VersionFlujo resuelto."""
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo

    user = User.objects.create_user("reg_avail", password="x")
    otro_destino, _ = Estado.objects.get_or_create(nombre="REG_OTRO_DESTINO")
    otro_flujo = VersionFlujo.objects.create(nombre="REG_FLUJO_V2", activo=False)
    ConfiguracionTransicion.objects.create(
        flujo=otro_flujo,
        estado_origen=setup_reg["origen"],
        estado_destino=otro_destino,
    )

    destinos = setup_reg["solicitud"].available_transitions(user)
    assert setup_reg["destino"] in destinos
    assert otro_destino not in destinos, (
        "available_transitions no debe incluir transiciones de otros flujos"
    )


@pytest.mark.django_db
def test_condicion_malconfigurada_bloquea_sin_reventar(setup_reg):
    """Config inválida de predicado = bloqueo controlado, no excepción 500."""
    from sinpapel.models import CondicionTransicion, ConfiguracionTransicion

    superuser = User.objects.create_superuser("reg_pred", password="x")
    transicion = ConfiguracionTransicion.objects.get(
        flujo=setup_reg["flujo"],
        estado_origen=setup_reg["origen"],
        estado_destino=setup_reg["destino"],
    )
    CondicionTransicion.objects.create(
        transicion=transicion,
        tipo="python_path",
        configuracion={},  # falta 'path' — config rota
        activo=True,
        orden=1,
    )

    # Lo importante: bloqueo controlado (tipo predicado), no una excepción.
    preview = setup_reg["solicitud"].preview_transition("REG_DESTINO", superuser)
    assert preview["permitido"] is False
    assert preview["predicados_fallidos"], "la condición rota debe reportarse"
    assert any(r["tipo"] == "predicado" for r in preview["razones_bloqueo"])
    with pytest.raises(PermissionError):
        setup_reg["solicitud"].transition("REG_DESTINO", superuser)


@pytest.mark.django_db(transaction=True)
def test_estado_rename_invalida_transitions_cacheadas(sinpapel_migrated):
    """Renombrar un Estado debe invalidar en cascada las transitions cacheadas."""
    from sinpapel.cache import get_transitions_for
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo

    origen = Estado.objects.create(nombre="CASC_ORIGEN")
    destino = Estado.objects.create(nombre="CASC_DESTINO")
    flujo = VersionFlujo.objects.create(nombre="CASC_FLUJO", activo=True)
    ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=origen, estado_destino=destino
    )

    cacheadas = get_transitions_for(flujo.id, origen.id)
    assert cacheadas[0].estado_destino.nombre == "CASC_DESTINO"

    destino.nombre = "CASC_RENOMBRADO"
    destino.save()  # transaction=True → on_commit corre y bumpea la versión

    frescas = get_transitions_for(flujo.id, origen.id)
    assert frescas[0].estado_destino.nombre == "CASC_RENOMBRADO", (
        "la cascada de invalidación no alcanzó las transitions cacheadas"
    )


@pytest.mark.django_db
def test_import_payload_malformado_da_valueerror():
    """deserialize_flujo con estructura inválida → ValueError, no KeyError."""
    from sinpapel.schemas.flujo_export import deserialize_flujo

    with pytest.raises(ValueError, match="flujo"):
        deserialize_flujo({"schema_version": "0.2", "flujo": {}}, dry_run=True)
    with pytest.raises(ValueError, match="transiciones"):
        deserialize_flujo(
            {"schema_version": "0.1", "flujo": {"nombre": "X"}}, dry_run=True
        )


@pytest.mark.django_db
def test_transicion_con_requiere_firma_exige_payload(setup_reg):
    """0.8.0: requiere_firma=True sin firma_payload → PermissionError."""
    from sinpapel.models import ConfiguracionTransicion

    superuser = User.objects.create_superuser("reg_reqfirma", password="x")
    ConfiguracionTransicion.objects.filter(
        flujo=setup_reg["flujo"],
        estado_origen=setup_reg["origen"],
        estado_destino=setup_reg["destino"],
    ).update(requiere_firma=True)

    preview = setup_reg["solicitud"].preview_transition("REG_DESTINO", superuser)
    assert preview["firma_requerida"] is True

    with pytest.raises(PermissionError, match="requiere firma"):
        setup_reg["solicitud"].transition("REG_DESTINO", superuser)


@pytest.mark.django_db
def test_transicion_firma_con_backend_configurado(setup_reg, settings):
    """0.8.0: modo A usa el backend de SINPAPEL_SIGNATURE_BACKEND (FakeBackend)."""
    from sinpapel.models import ConfiguracionTransicion, SeguimientoWorkflow
    from sinpapel.signing.factory import reset_backend_cache

    superuser = User.objects.create_superuser("reg_fake", password="x")
    ConfiguracionTransicion.objects.filter(
        flujo=setup_reg["flujo"],
        estado_origen=setup_reg["origen"],
        estado_destino=setup_reg["destino"],
    ).update(requiere_firma=True)

    settings.SINPAPEL_SIGNATURE_BACKEND = (
        "sinpapel.signing.backends.fake.FakeBackend"
    )
    reset_backend_cache()
    try:
        result = setup_reg["solicitud"].transition(
            "REG_DESTINO", superuser, firma_payload={"contenido": b"canonico"}
        )
    finally:
        reset_backend_cache()

    seg = SeguimientoWorkflow.objects.get(pk=result["seguimiento_id"])
    assert seg.firma_registro is not None
    assert seg.firma_registro.backend_name == "fake"
    assert seg.firma_registro.is_required is True


@pytest.mark.django_db
def test_modo_b_rechaza_firma_ajena_y_reuso(setup_reg):
    """0.8.0: registro_firma_id de otro usuario o ya vinculado → PermissionError."""
    import datetime

    from sinpapel.models import RegistroFirma

    ejecutor = User.objects.create_superuser("reg_ejecutor", password="x")
    otro = User.objects.create_user("reg_otro", password="x")
    ajena = RegistroFirma.objects.create(
        backend_name="fake",
        signer=otro,
        signer_display_name="Otro",
        content_hash="sha256:x",
        verification_result="VALIDA",
        signed_at=datetime.datetime.now(datetime.timezone.utc),
    )

    with pytest.raises(PermissionError, match="otro firmante"):
        setup_reg["solicitud"].transition(
            "REG_DESTINO", ejecutor,
            firma_payload={"registro_firma_id": ajena.pk},
        )

    propia_invalida = RegistroFirma.objects.create(
        backend_name="fake",
        signer=ejecutor,
        signer_display_name="Ejecutor",
        content_hash="sha256:y",
        verification_result="INVALIDA",
        signed_at=datetime.datetime.now(datetime.timezone.utc),
    )
    with pytest.raises(PermissionError, match="VALIDA"):
        setup_reg["solicitud"].transition(
            "REG_DESTINO", ejecutor,
            firma_payload={"registro_firma_id": propia_invalida.pk},
        )


@pytest.mark.django_db
def test_side_effects_scoped_por_workflow_key(setup_reg):
    """0.8.1: un handler scoped a otro flujo NO se ejecuta; el del flujo sí,
    con precedencia sobre el global."""
    from sinpapel.services.side_effects import (
        SIDE_EFFECTS,
        SIDE_EFFECTS_SCOPED,
        register_side_effect,
    )

    superuser = User.objects.create_superuser("reg_scope", password="x")
    llamadas: list[str] = []

    @register_side_effect("REG_DESTINO")
    def _global(instance, usuario, **kwargs):
        llamadas.append("global")
        return {"scope": "global"}

    @register_side_effect("REG_DESTINO", workflow_key="test_solicitud")
    def _scoped(instance, usuario, **kwargs):
        llamadas.append("scoped")
        return {"scope": "scoped"}

    @register_side_effect("REG_DESTINO", workflow_key="otro_flujo")
    def _ajeno(instance, usuario, **kwargs):
        llamadas.append("ajeno")
        return {"scope": "ajeno"}

    try:
        # TestSolicitud tiene workflow_key="test_solicitud"
        result = setup_reg["solicitud"].transition("REG_DESTINO", superuser)
    finally:
        SIDE_EFFECTS.pop("REG_DESTINO", None)
        SIDE_EFFECTS_SCOPED.pop(("test_solicitud", "REG_DESTINO"), None)
        SIDE_EFFECTS_SCOPED.pop(("otro_flujo", "REG_DESTINO"), None)

    assert llamadas == ["scoped"], (
        "debe correr SOLO el handler scoped del flujo de la instancia"
    )
    assert result["scope"] == "scoped"


@pytest.mark.django_db
def test_estado_inactivo_bloqueado_con_enforce(setup_reg, settings):
    """0.8.1: con SINPAPEL_ENFORCE_ESTADO_ACTIVO, destinos inactivos se
    bloquean y desaparecen de available_transitions."""
    superuser = User.objects.create_superuser("reg_activo", password="x")

    # Default (flag off): Estado.activo=False no bloquea (compat)
    assert setup_reg["destino"].activo is False
    preview = setup_reg["solicitud"].preview_transition("REG_DESTINO", superuser)
    assert preview["permitido"] is True

    settings.SINPAPEL_ENFORCE_ESTADO_ACTIVO = True
    preview = setup_reg["solicitud"].preview_transition("REG_DESTINO", superuser)
    assert preview["permitido"] is False
    assert any("inactivo" in r["mensaje"] for r in preview["razones_bloqueo"])
    assert setup_reg["solicitud"].available_transitions(superuser) == []

    # Activarlo lo rehabilita. (La invalidación por signal corre en
    # on_commit — no dispara en tests no-transaccionales; limpiamos a mano.)
    setup_reg["destino"].activo = True
    setup_reg["destino"].save()
    from sinpapel.cache import clear_all

    clear_all()
    destinos = setup_reg["solicitud"].available_transitions(superuser)
    assert setup_reg["destino"] in destinos


@pytest.mark.django_db
def test_requisitos_documentales_una_sola_query(setup_reg, django_assert_num_queries):
    """0.8.1: evaluar_requisitos_documentales agrega en una query, no N+1."""
    from sinpapel.models import RequisitoEstadoDocumento, TipoDocumento
    from sinpapel.services.workflow_engine import WorkflowEngine

    for i in range(3):
        tipo = TipoDocumento.objects.create(nombre=f"REG_TIPO_{i}")
        RequisitoEstadoDocumento.objects.create(
            estado=setup_reg["origen"], tipo_documento=tipo, porcentaje=100
        )

    engine = WorkflowEngine()
    engine.evaluar_requisitos_documentales(setup_reg["solicitud"])  # calienta cache
    # 2 queries: ContentType (cacheado por Django, puede ser 0) + agregada.
    with django_assert_num_queries(1):
        resultado = engine.evaluar_requisitos_documentales(setup_reg["solicitud"])
    assert len(resultado) == 3
    assert all(r["porcentaje_actual"] == 0 for r in resultado)


@pytest.mark.django_db(transaction=True)
def test_side_effects_corren_post_commit(setup_reg, sinpapel_migrated):
    """El handler de side effect debe ejecutarse fuera de la transacción."""
    superuser = User.objects.create_superuser("reg_se", password="x")
    observado: dict = {}

    def _handler(instance, usuario, **kwargs):
        observado["in_atomic_block"] = transaction.get_connection().in_atomic_block
        return {"observado": True}

    SIDE_EFFECTS["REG_DESTINO"] = _handler
    try:
        result = setup_reg["solicitud"].transition("REG_DESTINO", superuser)
    finally:
        SIDE_EFFECTS.pop("REG_DESTINO", None)

    assert result["observado"] is True
    assert observado["in_atomic_block"] is False, (
        "el side effect corrió dentro de la transacción del motor"
    )
