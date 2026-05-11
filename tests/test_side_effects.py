"""Tests para side_effects registry + dispatch (ADR-004)."""
from __future__ import annotations

import logging

import pytest

from sinpapel.services.side_effects import (
    SIDE_EFFECTS,
    ejecutar_side_effects,
    register_side_effect,
)


@pytest.fixture(autouse=True)
def cleanup_test_handlers():
    """Limpia handlers registrados en cada test bajo prefijo TEST_*."""
    yield
    keys_to_remove = [k for k in SIDE_EFFECTS if k.startswith("TEST_SE_")]
    for k in keys_to_remove:
        del SIDE_EFFECTS[k]


def test_register_side_effect_decorator_adds_handler():
    """register_side_effect agrega el handler al registry."""

    @register_side_effect("TEST_SE_REG")
    def _handler(instance, user, **kwargs):
        return {"called": True}

    assert "TEST_SE_REG" in SIDE_EFFECTS
    assert SIDE_EFFECTS["TEST_SE_REG"] is _handler


def test_dispatch_calls_registered_handler():
    """ejecutar_side_effects invoca el handler registrado."""

    @register_side_effect("TEST_SE_DISP")
    def _handler(instance, user, **kwargs):
        return {"handled": True, "instance_id": instance.id, "user_name": user.name}

    class FakeInst:
        id = 42

    class FakeUser:
        name = "alice"

    result = ejecutar_side_effects("TEST_SE_DISP", FakeInst(), FakeUser())
    assert result == {"handled": True, "instance_id": 42, "user_name": "alice"}


def test_dispatch_passes_kwargs_to_handler():
    """ejecutar_side_effects propaga **kwargs al handler."""

    @register_side_effect("TEST_SE_KWARGS")
    def _handler(instance, user, **kwargs):
        return {"kwargs": kwargs}

    class _F:
        id = 1

    result = ejecutar_side_effects(
        "TEST_SE_KWARGS",
        _F(),
        _F(),
        monto_aprobado=100,
        comentarios="x",
    )
    assert result["kwargs"] == {"monto_aprobado": 100, "comentarios": "x"}


def test_dispatch_returns_empty_dict_for_unknown_state():
    """Estado sin handler registrado retorna {}."""
    result = ejecutar_side_effects("UNKNOWN_STATE_NEVER_REG", object(), object())
    assert result == {}


def test_dispatch_logs_errors_does_not_raise(caplog):
    """ADR-004: errors loggeados, NO re-raised."""

    @register_side_effect("TEST_SE_FAILS")
    def _handler(instance, user, **kwargs):
        raise RuntimeError("intentional test failure")

    class _F:
        id = 99

    with caplog.at_level(logging.ERROR, logger="sinpapel.services.side_effects"):
        result = ejecutar_side_effects("TEST_SE_FAILS", _F(), _F())

    assert result == {"error": True, "estado": "TEST_SE_FAILS"}
    assert any(
        "Side-effect error for state TEST_SE_FAILS" in record.message
        for record in caplog.records
    )


def test_handler_returning_non_dict_falls_back_to_empty():
    """Si handler retorna no-dict (None, int, etc.), dispatch retorna {}."""

    @register_side_effect("TEST_SE_NONE")
    def _handler(instance, user, **kwargs):
        return None  # bug del handler

    @register_side_effect("TEST_SE_INT")
    def _handler_int(instance, user, **kwargs):
        return 42

    class _F:
        id = 1

    assert ejecutar_side_effects("TEST_SE_NONE", _F(), _F()) == {}
    assert ejecutar_side_effects("TEST_SE_INT", _F(), _F()) == {}


def test_register_returns_handler_unchanged():
    """register_side_effect decorator retorna la función original (callable normal)."""

    @register_side_effect("TEST_SE_UNCH")
    def my_handler(instance, user, **kwargs):
        return {"x": 1}

    # El handler decorado debe seguir siendo callable directo
    class _F:
        id = 1

    assert my_handler(_F(), _F()) == {"x": 1}


def test_module_level_singleton():
    """SIDE_EFFECTS es accesible como singleton del módulo."""
    from sinpapel.services import side_effects as se_mod

    assert se_mod.SIDE_EFFECTS is SIDE_EFFECTS
