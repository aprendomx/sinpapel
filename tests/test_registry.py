"""Tests para WorkflowRegistry singleton."""
from __future__ import annotations

import pytest

from sinpapel.exceptions import WorkflowDuplicateKeyError
from sinpapel.registry import WorkflowConfig, WorkflowRegistry, _RegistryImpl


@pytest.fixture
def fresh_registry():
    """Yields a fresh registry instance, isolated from the singleton."""
    return _RegistryImpl()


class _FakeModelA:
    """Mock model class para tests — no es un Django model real."""


class _FakeModelB:
    """Otro mock model class para tests de duplicate detection."""


def test_registry_starts_empty(fresh_registry):
    """Registry recién creado no tiene entradas."""
    assert fresh_registry.list_keys() == []


def test_register_adds_config(fresh_registry):
    """register() agrega una entrada recuperable por get()."""
    config = WorkflowConfig(
        model=_FakeModelA,  # type: ignore[arg-type]
        state_field="state",
        workflow_key="test_a",
    )
    fresh_registry.register("test_a", config)
    assert fresh_registry.get("test_a") is config


def test_get_raises_keyerror_for_unknown(fresh_registry):
    """get() con workflow_key no registrado levanta KeyError."""
    with pytest.raises(KeyError):
        fresh_registry.get("nonexistent")


def test_duplicate_key_with_same_model_is_idempotent(fresh_registry):
    """Re-registrar la misma model con la misma key es no-op."""
    config_a = WorkflowConfig(
        model=_FakeModelA,  # type: ignore[arg-type]
        state_field="state",
        workflow_key="test_idem",
    )
    fresh_registry.register("test_idem", config_a)
    # Re-registrar el mismo modelo con la misma key — debe ser idempotente
    config_a_again = WorkflowConfig(
        model=_FakeModelA,  # type: ignore[arg-type]
        state_field="state",
        workflow_key="test_idem",
    )
    fresh_registry.register("test_idem", config_a_again)  # no raise
    assert fresh_registry.get("test_idem").model is _FakeModelA


def test_duplicate_key_with_different_model_raises(fresh_registry):
    """Registrar dos modelos distintos con la misma key levanta WorkflowDuplicateKeyError."""
    config_a = WorkflowConfig(
        model=_FakeModelA,  # type: ignore[arg-type]
        state_field="state",
        workflow_key="test_dupe",
    )
    config_b = WorkflowConfig(
        model=_FakeModelB,  # type: ignore[arg-type]
        state_field="state",
        workflow_key="test_dupe",
    )
    fresh_registry.register("test_dupe", config_a)
    with pytest.raises(WorkflowDuplicateKeyError, match="test_dupe"):
        fresh_registry.register("test_dupe", config_b)


def test_unregister_removes_entry(fresh_registry):
    """unregister() elimina entrada; idempotente con keys no existentes."""
    config = WorkflowConfig(
        model=_FakeModelA,  # type: ignore[arg-type]
        state_field="state",
        workflow_key="test_remove",
    )
    fresh_registry.register("test_remove", config)
    fresh_registry.unregister("test_remove")
    assert "test_remove" not in fresh_registry.list_keys()
    # No-op para keys no existentes
    fresh_registry.unregister("never_registered")  # no raise


def test_list_keys_returns_registered(fresh_registry):
    """list_keys() retorna todas las keys registradas."""
    fresh_registry.register(
        "key1",
        WorkflowConfig(model=_FakeModelA, state_field="s", workflow_key="key1"),  # type: ignore[arg-type]
    )
    fresh_registry.register(
        "key2",
        WorkflowConfig(model=_FakeModelB, state_field="s", workflow_key="key2"),  # type: ignore[arg-type]
    )
    keys = fresh_registry.list_keys()
    assert sorted(keys) == ["key1", "key2"]


def test_workflow_config_is_frozen():
    """WorkflowConfig es inmutable (frozen dataclass)."""
    config = WorkflowConfig(
        model=_FakeModelA,  # type: ignore[arg-type]
        state_field="state",
        workflow_key="frozen_test",
    )
    with pytest.raises((AttributeError, TypeError)):
        config.state_field = "modified"  # type: ignore[misc]


def test_workflow_config_version_field_optional():
    """version_field es opcional (None por default)."""
    config = WorkflowConfig(
        model=_FakeModelA,  # type: ignore[arg-type]
        state_field="state",
        workflow_key="opt_version",
    )
    assert config.version_field is None

    config_with_version = WorkflowConfig(
        model=_FakeModelA,  # type: ignore[arg-type]
        state_field="state",
        workflow_key="with_version",
        version_field="version_flujo",
    )
    assert config_with_version.version_field == "version_flujo"


def test_singleton_instance_exists():
    """WorkflowRegistry es accesible como singleton del módulo."""
    assert isinstance(WorkflowRegistry, _RegistryImpl)
