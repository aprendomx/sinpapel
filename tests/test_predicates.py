"""Tests for Transition Predicates (CondicionTransicion + PredicateEngine)."""
from __future__ import annotations

import pytest
from django.db import models

from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo
from sinpapel.models.predicates import CondicionTransicion


@pytest.mark.django_db
def test_condicion_transicion_model_exists():
    """CondicionTransicion can be created and linked to ConfiguracionTransicion."""
    estado_origen = Estado.objects.create(nombre="ORIG", activo=True)
    estado_destino = Estado.objects.create(nombre="DEST", activo=True)
    flujo = VersionFlujo.objects.create(nombre="F1", activo=True)
    transicion = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino
    )
    cond = CondicionTransicion.objects.create(
        transicion=transicion,
        tipo="python_path",
        configuracion={"path": "tests.test_predicates._always_true"},
        mensaje_error="Falló validación",
        orden=1,
    )
    assert cond.tipo == "python_path"
    assert cond.activo is True
    assert str(cond) == "Condicion #1 (python_path)"


from sinpapel.json_logic import evaluar


def test_json_logic_var():
    """Access variable from data context."""
    assert evaluar({"var": "nombre"}, {"nombre": "Juan"}) == "Juan"


def test_json_logic_equal():
    """Equality comparison."""
    assert evaluar({"==": [{"var": "edad"}, 30]}, {"edad": 30}) is True
    assert evaluar({"==": [{"var": "edad"}, 30]}, {"edad": 25}) is False


def test_json_logic_and():
    """AND logical operator."""
    rule = {"and": [
        {">=": [{"var": "monto"}, 100000]},
        {"==": [{"var": "tipo"}, "FOVISSSTE"]}
    ]}
    assert evaluar(rule, {"monto": 150000, "tipo": "FOVISSSTE"}) is True
    assert evaluar(rule, {"monto": 50000, "tipo": "FOVISSSTE"}) is False


def test_json_logic_or():
    """OR logical operator."""
    rule = {"or": [
        {"==": [{"var": "estado"}, "URGENTE"]},
        {">=": [{"var": "monto"}, 1000000]}
    ]}
    assert evaluar(rule, {"estado": "NORMAL", "monto": 2000000}) is True
    assert evaluar(rule, {"estado": "NORMAL", "monto": 1000}) is False


def test_json_logic_gt_lt():
    """Greater than / less than."""
    assert evaluar({">": [{"var": "a"}, 5]}, {"a": 10}) is True
    assert evaluar({"<": [{"var": "a"}, 5]}, {"a": 3}) is True


def test_json_logic_gte_lte_ne():
    """Greater-or-equal, less-or-equal, not-equal."""
    assert evaluar({">=": [{"var": "a"}, 5]}, {"a": 5}) is True
    assert evaluar({">=": [{"var": "a"}, 5]}, {"a": 4}) is False
    assert evaluar({"<=": [{"var": "a"}, 5]}, {"a": 5}) is True
    assert evaluar({"<=": [{"var": "a"}, 5]}, {"a": 6}) is False
    assert evaluar({"!=": [{"var": "a"}, 5]}, {"a": 3}) is True
    assert evaluar({"!=": [{"var": "a"}, 5]}, {"a": 5}) is False


def test_json_logic_not():
    """NOT operator."""
    assert evaluar({"!": {"var": "inactivo"}}, {"inactivo": False}) is True


def test_json_logic_in():
    """Membership test."""
    assert evaluar({"in": [{"var": "tipo"}, ["A", "B", "C"]]}, {"tipo": "B"}) is True


def test_json_logic_missing_var_returns_none():
    """Missing variables return None (falsy)."""
    assert evaluar({"var": "inexistente"}, {}) is None
    assert evaluar({"==": [{"var": "inexistente"}, None]}, {}) is True


def test_json_logic_missing_var_comparisons():
    """Missing variables in numeric comparisons evaluate to False instead of crashing."""
    assert evaluar({">": [{"var": "edad"}, 30]}, {}) is False
    assert evaluar({">=": [{"var": "edad"}, 30]}, {}) is False
    assert evaluar({"<": [{"var": "edad"}, 30]}, {}) is False
    assert evaluar({"<=": [{"var": "edad"}, 30]}, {}) is False


def test_json_logic_invalid_operator():
    """Invalid operators raise ValueError."""
    with pytest.raises(ValueError, match="no soportado"):
        evaluar({"bad": 1}, {})


def test_json_logic_malformed_binary_args():
    """Binary operators with fewer than 2 args raise ValueError."""
    with pytest.raises(ValueError, match="requiere lista de 2 argumentos"):
        evaluar({"==": [{"var": "x"}]}, {})


def test_json_logic_empty_rule():
    """Empty rule dict raises ValueError."""
    with pytest.raises(ValueError, match="exactamente una clave"):
        evaluar({}, {})


from sinpapel.services.predicate_engine import PredicateEngine


def _always_true(instance, user):
    return True


def _always_false(instance, user):
    return False, "Condición rechazada"


def test_predicate_engine_python_path_pass():
    """Python path backend returns True when function returns True."""
    config = {"path": "tests.test_predicates._always_true"}
    result = PredicateEngine._backend_python_path(config, None, None)
    assert result == (True, None)


def test_predicate_engine_python_path_fail():
    """Python path backend returns False + message when function returns tuple."""
    config = {"path": "tests.test_predicates._always_false"}
    result = PredicateEngine._backend_python_path(config, None, None)
    assert result == (False, "Condición rechazada")


def test_predicate_engine_json_logic_pass():
    """JSON Logic backend evaluates rule against instance data."""
    from sinpapel.mixins import CampoMetadato, MetadatosCapturables

    class _FakeModel(MetadatosCapturables):
        SCHEMA_METADATOS = [CampoMetadato("monto", int)]
        class Meta:
            app_label = "tests"

    obj = _FakeModel()
    obj.meta.monto = 150000
    config = {"rule": {">=": [{"var": "meta.monto"}, 100000]}}
    result = PredicateEngine._backend_json_logic(config, obj, None)
    assert result == (True, None)


def test_predicate_engine_json_logic_fail():
    """JSON Logic backend returns False when rule does not match."""
    from sinpapel.mixins import CampoMetadato, MetadatosCapturables

    class _FakeModel(MetadatosCapturables):
        SCHEMA_METADATOS = [CampoMetadato("monto", int)]
        class Meta:
            app_label = "tests"

    obj = _FakeModel()
    obj.meta.monto = 50000
    config = {"rule": {">=": [{"var": "meta.monto"}, 100000]}}
    result = PredicateEngine._backend_json_logic(config, obj, None)
    assert result == (False, None)


@pytest.mark.django_db
def test_predicate_engine_evaluar_dispatches_by_tipo():
    """evaluar() dispatches to correct backend by tipo."""
    from sinpapel.models.predicates import CondicionTransicion
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo

    estado_origen = Estado.objects.create(nombre="ORIG2", activo=True)
    estado_destino = Estado.objects.create(nombre="DEST2", activo=True)
    flujo = VersionFlujo.objects.create(nombre="F2", activo=True)
    transicion = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino
    )
    cond = CondicionTransicion(
        transicion=transicion,
        tipo="python_path",
        configuracion={"path": "tests.test_predicates._always_true"},
    )
    result = PredicateEngine.evaluar(cond, None, None)
    assert result == (True, None)


@pytest.mark.django_db
def test_predicate_engine_evaluar_unknown_tipo_raises():
    """evaluar() raises ValueError for unregistered backend tipo."""
    from sinpapel.models.predicates import CondicionTransicion
    from sinpapel.models import ConfiguracionTransicion, Estado, VersionFlujo

    estado_origen = Estado.objects.create(nombre="ORIG3", activo=True)
    estado_destino = Estado.objects.create(nombre="DEST3", activo=True)
    flujo = VersionFlujo.objects.create(nombre="F3", activo=True)
    transicion = ConfiguracionTransicion.objects.create(
        flujo=flujo, estado_origen=estado_origen, estado_destino=estado_destino
    )
    cond = CondicionTransicion(
        transicion=transicion,
        tipo="unknown_type",
        configuracion={},
    )
    with pytest.raises(ValueError, match="no registrado"):
        PredicateEngine.evaluar(cond, None, None)
