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
    """AC3: los 3 métodos quedan accesibles en la clase decorada."""
    Model = _make_mock_model_class("MethodInjectModel", fields=["estado"])
    decorated = workflow_enabled(
        state_field="estado",
        workflow_key="method_inject_test",
    )(Model)
    assert callable(getattr(decorated, "available_transitions", None))
    assert callable(getattr(decorated, "can_transition_to", None))
    assert callable(getattr(decorated, "transition", None))
    assert decorated._workflow_config.workflow_key == "method_inject_test"
    WorkflowRegistry.unregister("method_inject_test")


# ──────────────────────────────────────────────────────────────────────────────
# S13.4 — expose_endpoints + endpoint_slug extensions
# ──────────────────────────────────────────────────────────────────────────────


def test_decorator_expose_endpoints_flag():
    """S13.4 AC1: expose_endpoints kwarg se persiste en WorkflowConfig.

    Default False preserva backward compat (S12.3 existing decoration).
    """
    M1 = _make_mock_model_class("M1_default", fields=["estado"])
    workflow_enabled(state_field="estado", workflow_key="exp_default_test")(M1)
    assert WorkflowRegistry.get("exp_default_test").expose_endpoints is False
    WorkflowRegistry.unregister("exp_default_test")

    M2 = _make_mock_model_class("M2_exposed", fields=["estado"])
    workflow_enabled(
        state_field="estado",
        workflow_key="exp_true_test",
        expose_endpoints=True,
        endpoint_slug="m2-exposed",
    )(M2)
    config = WorkflowRegistry.get("exp_true_test")
    assert config.expose_endpoints is True
    assert config.endpoint_slug == "m2-exposed"
    WorkflowRegistry.unregister("exp_true_test")


def test_decorator_endpoint_slug_validates_pattern():
    """S13.4 AC3: endpoint_slug debe ser URL-safe [a-z0-9-]+ — regex factory time."""
    M = _make_mock_model_class("M_slug_invalid", fields=["estado"])

    # Mayúsculas no permitidas
    with pytest.raises(WorkflowConfigurationError, match=r"endpoint_slug 'BadSlug'"):
        workflow_enabled(
            state_field="estado",
            workflow_key="slug_uppercase_test",
            expose_endpoints=True,
            endpoint_slug="BadSlug",
        )(M)

    # Underscore no permitido (kebab-case only)
    with pytest.raises(WorkflowConfigurationError, match=r"endpoint_slug 'with_underscore'"):
        workflow_enabled(
            state_field="estado",
            workflow_key="slug_underscore_test",
            expose_endpoints=True,
            endpoint_slug="with_underscore",
        )(M)

    # Espacios no permitidos
    with pytest.raises(WorkflowConfigurationError, match=r"endpoint_slug 'has spaces'"):
        workflow_enabled(
            state_field="estado",
            workflow_key="slug_spaces_test",
            expose_endpoints=True,
            endpoint_slug="has spaces",
        )(M)

    # Slug válido (lowercase + digits + hyphens) NO raises
    workflow_enabled(
        state_field="estado",
        workflow_key="slug_valid_test",
        expose_endpoints=True,
        endpoint_slug="valid-slug-123",
    )(M)
    WorkflowRegistry.unregister("slug_valid_test")


def test_workflow_config_effective_slug_default():
    """S13.4 AC1: effective_slug = workflow_key + 's' cuando endpoint_slug=None."""
    from sinpapel.registry import WorkflowConfig

    # Default: workflow_key + "s"
    config = WorkflowConfig(
        model=type("M", (), {}),
        state_field="estado",
        workflow_key="solicitud",
        expose_endpoints=True,
    )
    assert config.effective_slug == "solicituds"  # default pluralization

    # Explícito override
    config_override = WorkflowConfig(
        model=type("M", (), {}),
        state_field="estado",
        workflow_key="solicitud",
        expose_endpoints=True,
        endpoint_slug="solicitudes",
    )
    assert config_override.effective_slug == "solicitudes"


def test_registry_list_exposed_filters_correctly():
    """S13.4 AC4: list_exposed() retorna solo expose=True, sorted by workflow_key."""
    M_yes_a = _make_mock_model_class("YesA", fields=["estado"])
    M_yes_b = _make_mock_model_class("YesB", fields=["estado"])
    M_no = _make_mock_model_class("NoModel", fields=["estado"])

    workflow_enabled(state_field="estado", workflow_key="zzz_le_yes_a", expose_endpoints=True)(M_yes_a)
    workflow_enabled(state_field="estado", workflow_key="aaa_le_yes_b", expose_endpoints=True)(M_yes_b)
    workflow_enabled(state_field="estado", workflow_key="le_no", expose_endpoints=False)(M_no)

    exposed = WorkflowRegistry.list_exposed()
    exposed_keys = [c.workflow_key for c in exposed]

    # Solo expose=True
    assert "zzz_le_yes_a" in exposed_keys
    assert "aaa_le_yes_b" in exposed_keys
    assert "le_no" not in exposed_keys

    # Sorted by workflow_key
    relevant = [k for k in exposed_keys if k.startswith(("zzz_le_", "aaa_le_"))]
    assert relevant == sorted(relevant), f"list_exposed not sorted: {relevant}"

    # Cleanup
    for key in ("zzz_le_yes_a", "aaa_le_yes_b", "le_no"):
        WorkflowRegistry.unregister(key)


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests — Solicitud real con DB
# ──────────────────────────────────────────────────────────────────────────────


def test_solicitud_registered_in_registry():
    """AC2: Solicitud aparece en WorkflowRegistry tras importar models."""
    from creditos.models import Solicitud

    config = WorkflowRegistry.get("solicitud")
    assert config.model is Solicitud
    assert config.state_field == "estado"
    assert config.workflow_key == "solicitud"
    assert config.version_field is None


def test_solicitud_has_injected_methods():
    """AC3: Solicitud tiene los 3 métodos inyectados (no instanciado, solo class-level)."""
    from creditos.models import Solicitud

    assert callable(getattr(Solicitud, "available_transitions", None))
    assert callable(getattr(Solicitud, "can_transition_to", None))
    assert callable(getattr(Solicitud, "transition", None))
    assert hasattr(Solicitud, "_workflow_config")


@pytest.mark.django_db
def test_available_transitions_with_no_estado_returns_empty():
    """AC4: solicitud sin estado retorna lista vacía."""
    from creditos.models import Solicitud

    user = User.objects.create_user("test_avail_no_estado", password="x")
    solicitud = Solicitud.objects.create()  # estado=None
    transitions = solicitud.available_transitions(user)
    assert transitions == []


@pytest.mark.django_db
def test_available_transitions_queries_db():
    """AC4: con ConfiguracionTransicion configurada, retorna estados destino."""
    from creditos.models import Solicitud
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

    solicitud = Solicitud.objects.create(estado=estado_origen)
    transitions = solicitud.available_transitions(user)
    assert estado_destino in transitions


@pytest.mark.django_db
def test_can_transition_to_returns_tuple():
    """AC5: can_transition_to retorna (bool, str | None)."""
    from creditos.models import Solicitud
    from sinpapel.models import Estado

    user = User.objects.create_user("test_can_trans", password="x")
    estado_origen, _ = Estado.objects.get_or_create(nombre="CAPTURA")
    solicitud = Solicitud.objects.create(estado=estado_origen)

    result = solicitud.can_transition_to("ESTADO_INEXISTENTE_TEST", user)
    assert isinstance(result, tuple)
    assert len(result) == 2
    puede, mensaje = result
    assert isinstance(puede, bool)
    assert mensaje is None or isinstance(mensaje, str)


@pytest.mark.django_db
def test_transition_delegates_to_workflow_service():
    """AC6: transition() delega a WorkflowService y crea SeguimientoWorkflow."""
    from creditos.models import Solicitud, ProductoCreditoFOVISSSTE, ProductoVersionFlujo
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
    producto = ProductoCreditoFOVISSSTE.objects.create(
        nombre="P_TEST", clave="P-TEST-TRANS", identificador="TEST",
        marca="TEST", monto_minimo=0, monto_maximo=0,
        tasa_interes=0, tasa_interes_moratorio=0,
    )
    ProductoVersionFlujo.objects.create(producto=producto, flujo=flujo)
    solicitud = Solicitud.objects.create(estado=estado_origen, producto=producto)

    seguimientos_antes = SeguimientoWorkflow.objects.count()
    solicitud.transition("EN_JEFATURA", superuser, comentarios="test transition")

    solicitud.refresh_from_db()
    assert solicitud.estado.nombre == "EN_JEFATURA"
    assert SeguimientoWorkflow.objects.count() == seguimientos_antes + 1
