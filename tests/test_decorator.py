"""Tests para @workflow_enabled decorator + métodos inyectados."""
from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.db import models

from sinpapel import (
    WorkflowConfigurationError,
    WorkflowDuplicateKeyError,
    WorkflowRegistry,
    workflow_enabled,
)


# ──────────────────────────────────────────────────────────────────────────────
# Mock models — usados en tests unitarios sin tocar DB
# ──────────────────────────────────────────────────────────────────────────────


class _MockModelMeta:
    """Mimick Django _meta.get_field for testing decorator validation."""

    def __init__(self, fields: list[str]) -> None:
        self._fields = fields

    def get_field(self, name: str):
        if name not in self._fields:
            from django.core.exceptions import FieldDoesNotExist
            raise FieldDoesNotExist(f"no field {name}")
        return object()  # placeholder field


def _make_mock_model_class(name: str, fields: list[str]):
    """Construye una clase mock con _meta.get_field para tests del decorator."""
    cls = type(name, (), {"_meta": _MockModelMeta(fields)})
    return cls


# ──────────────────────────────────────────────────────────────────────────────
# Decorator validation tests — unit, no DB
# ──────────────────────────────────────────────────────────────────────────────


def test_decorator_validates_state_field_exists():
    """AC1: state_field inexistente raises WorkflowConfigurationError."""
    BadModel = _make_mock_model_class("BadModel", fields=["folio"])  # no 'estado'
    with pytest.raises(WorkflowConfigurationError, match="has no field 'estado'"):
        workflow_enabled(state_field="estado", workflow_key="bad_state_field_test")(BadModel)


def test_decorator_validates_version_field_when_provided():
    """AC1: version_field inexistente raises WorkflowConfigurationError."""
    Model = _make_mock_model_class("ModelMissingVersion", fields=["estado"])  # has estado, no version
    with pytest.raises(WorkflowConfigurationError, match="has no field 'version_flujo'"):
        workflow_enabled(
            state_field="estado",
            workflow_key="bad_version_field_test",
            version_field="version_flujo",
        )(Model)


def test_decorator_accepts_valid_config():
    """Decorator con campos válidos no levanta excepción."""
    GoodModel = _make_mock_model_class("GoodModel", fields=["estado"])
    decorated = workflow_enabled(
        state_field="estado",
        workflow_key="good_decorator_test",
    )(GoodModel)
    assert decorated is GoodModel  # no envuelve, retorna la misma clase
    # Cleanup
    WorkflowRegistry.unregister("good_decorator_test")


def test_duplicate_workflow_key_with_different_models_raises():
    """AC2: dos modelos distintos con la misma key levantan WorkflowDuplicateKeyError."""
    A = _make_mock_model_class("ModelA_dupe", fields=["estado"])
    B = _make_mock_model_class("ModelB_dupe", fields=["estado"])
    workflow_enabled(state_field="estado", workflow_key="dupe_decor_key")(A)
    with pytest.raises(WorkflowDuplicateKeyError, match="dupe_decor_key"):
        workflow_enabled(state_field="estado", workflow_key="dupe_decor_key")(B)
    WorkflowRegistry.unregister("dupe_decor_key")


def test_decorator_injects_methods():
    """AC3: decorator inyecta available_transitions, can_transition_to, transition."""
    Model = _make_mock_model_class("InjectedModel", fields=["estado"])
    decorated = workflow_enabled(
        state_field="estado",
        workflow_key="inject_test",
    )(Model)
    assert callable(getattr(decorated, "available_transitions", None))
    assert callable(getattr(decorated, "can_transition_to", None))
    assert callable(getattr(decorated, "transition", None))
    assert hasattr(decorated, "_workflow_config")
    WorkflowRegistry.unregister("inject_test")


def test_decorator_expose_endpoints_flag():
    """S13.4: expose_endpoints=True se refleja en WorkflowConfig."""
    Model = _make_mock_model_class("ExposeModel", fields=["estado"])
    decorated = workflow_enabled(
        state_field="estado",
        workflow_key="expose_test",
        expose_endpoints=True,
    )(Model)
    config = decorated._workflow_config
    assert config.expose_endpoints is True
    WorkflowRegistry.unregister("expose_test")


def test_decorator_endpoint_slug_validates_pattern():
    """S13.4 (D9): endpoint_slug inválido raises en factory time."""
    Model = _make_mock_model_class("SlugModel", fields=["estado"])
    with pytest.raises(WorkflowConfigurationError, match="endpoint_slug"):
        workflow_enabled(
            state_field="estado",
            workflow_key="slug_test",
            expose_endpoints=True,
            endpoint_slug="invalid_slug_!",
        )(Model)


def test_workflow_config_effective_slug_default():
    """S13.4: effective_slug default = workflow_key + 's'."""
    Model = _make_mock_model_class("SlugDefaultModel", fields=["estado"])
    decorated = workflow_enabled(
        state_field="estado",
        workflow_key="my_workflow",
        expose_endpoints=True,
    )(Model)
    assert decorated._workflow_config.effective_slug == "my_workflows"
    WorkflowRegistry.unregister("my_workflow")


def test_registry_list_exposed_filters_correctly():
    """S13.4: list_exposed() retorna solo configs con expose_endpoints=True."""
    M1 = _make_mock_model_class("M1", fields=["estado"])
    M2 = _make_mock_model_class("M2", fields=["estado"])
    workflow_enabled(state_field="estado", workflow_key="zzz_le_yes_a", expose_endpoints=True)(M1)
    workflow_enabled(state_field="estado", workflow_key="aaa_le_yes_b", expose_endpoints=True)(M2)
    exposed = WorkflowRegistry.list_exposed()
    assert len(exposed) == 2
    assert exposed[0].workflow_key == "aaa_le_yes_b"  # sorted
    assert exposed[1].workflow_key == "zzz_le_yes_a"
    WorkflowRegistry.unregister("zzz_le_yes_a")
    WorkflowRegistry.unregister("aaa_le_yes_b")


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — TestSolicitud real con DB
# ──────────────────────────────────────────────────────────────────────────────


def test_solicitud_registered_in_registry():
    """AC2: TestSolicitud aparece en WorkflowRegistry tras importar models."""
    from tests.models import TestSolicitud

    config = WorkflowRegistry.get("test_solicitud")
    assert config.model is TestSolicitud
    assert config.state_field == "estado"
    assert config.workflow_key == "test_solicitud"
    assert config.version_field is None


def test_solicitud_has_injected_methods():
    """AC3: TestSolicitud tiene los 3 métodos inyectados (no instanciado, solo class-level)."""
    from tests.models import TestSolicitud

    assert callable(getattr(TestSolicitud, "available_transitions", None))
    assert callable(getattr(TestSolicitud, "can_transition_to", None))
    assert callable(getattr(TestSolicitud, "transition", None))
    assert hasattr(TestSolicitud, "_workflow_config")


@pytest.mark.django_db
def test_available_transitions_with_no_estado_returns_empty():
    """AC4: solicitud sin estado retorna lista vacía."""
    from tests.models import TestSolicitud

    user = User.objects.create_user("test_avail_no_estado", password="x")
    solicitud = TestSolicitud.objects.create()  # estado=None
    transitions = solicitud.available_transitions(user)
    assert transitions == []


@pytest.mark.django_db
def test_available_transitions_queries_db():
    """AC4: con ConfiguracionTransicion configurada, retorna estados destino."""
    from tests.models import TestSolicitud
    from sinpapel.models import (
        ConfiguracionTransicion,
        Estado,
        VersionFlujo,
    )

    user = User.objects.create_user("test_avail_db", password="x")
    estado_origen, _ = Estado.objects.get_or_create(nombre="ORIGEN_AVAIL")
    estado_destino, _ = Estado.objects.get_or_create(nombre="DESTINO_AVAIL")
    flujo = VersionFlujo.objects.create(nombre="FLUJO_AVAIL_TEST", activo=True)
    ConfiguracionTransicion.objects.create(
        flujo=flujo,
        estado_origen=estado_origen,
        estado_destino=estado_destino,
    )

    solicitud = TestSolicitud.objects.create(estado=estado_origen)
    transitions = solicitud.available_transitions(user)
    assert estado_destino in transitions


@pytest.mark.django_db
def test_can_transition_to_returns_tuple():
    """AC5: can_transition_to retorna (bool, str | None)."""
    from tests.models import TestSolicitud
    from sinpapel.models import Estado

    user = User.objects.create_user("test_can_trans", password="x")
    estado_origen, _ = Estado.objects.get_or_create(nombre="CAPTURA")
    solicitud = TestSolicitud.objects.create(estado=estado_origen)

    result = solicitud.can_transition_to("ESTADO_INEXISTENTE_TEST", user)
    assert isinstance(result, tuple)
    assert len(result) == 2
    puede, mensaje = result
    assert isinstance(puede, bool)
    assert mensaje is None or isinstance(mensaje, str)


@pytest.mark.django_db
def test_transition_delegates_to_workflow_service():
    """AC6: transition() delega a WorkflowEngine y crea SeguimientoWorkflow."""
    from tests.models import TestSolicitud, TestProducto, TestProductoVersionFlujo
    from sinpapel.models import (
        ConfiguracionTransicion,
        Estado,
        SeguimientoWorkflow,
        VersionFlujo,
    )

    superuser = User.objects.create_superuser("test_trans_super", password="x")
    estado_origen, _ = Estado.objects.get_or_create(nombre="CAPTURA")
    estado_destino, _ = Estado.objects.get_or_create(nombre="EN_JEFATURA")
    flujo = VersionFlujo.objects.create(nombre="FLUJO_TRANS_TEST", activo=True)
    ConfiguracionTransicion.objects.create(
        flujo=flujo,
        estado_origen=estado_origen,
        estado_destino=estado_destino,
    )
    producto = TestProducto.objects.create(nombre="P_TEST")
    TestProductoVersionFlujo.objects.create(producto=producto, flujo=flujo)
    solicitud = TestSolicitud.objects.create(estado=estado_origen, producto=producto)

    seguimientos_antes = SeguimientoWorkflow.objects.count()
    solicitud.transition("EN_JEFATURA", superuser, comentarios="test transition")

    solicitud.refresh_from_db()
    assert solicitud.estado.nombre == "EN_JEFATURA"
    assert SeguimientoWorkflow.objects.count() == seguimientos_antes + 1
