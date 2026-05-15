"""Sinpapel — PredicateEngine for evaluating transition conditions.

Pluggable engine that evaluates CondicionTransicion rules by dispatching
to registered backends based on the 'tipo' field.
"""
from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any, Callable

from django.conf import settings

from sinpapel.json_logic import evaluar as evaluar_json_logic

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django.db import models

    from sinpapel.models.predicates import CondicionTransicion


# Whitelist of allowed modules for python_path backend
_PREDICATE_MODULE_WHITELIST: set[str] = set()


def _get_predicate_whitelist() -> set[str]:
    """Lazy lookup — override_settings safe."""
    modules = getattr(settings, "SINPAPEL_PREDICATE_MODULES", None)
    if modules is not None:
        return set(modules)
    return _PREDICATE_MODULE_WHITELIST


def _build_data_context(instance: "models.Model | None", user: "User | None") -> dict[str, Any]:
    """Construye el contexto de datos para evaluación JSON Logic.

    Incluye:
    - meta.*: valores de MetadatosCapturables.to_dict()
    - user.id, user.username: datos del usuario (si hay user)
    - instance.pk: ID de la instancia (si hay instance)
    """
    data: dict[str, Any] = {}
    if instance is not None:
        data["instance.pk"] = instance.pk
        if hasattr(instance, "meta"):
            meta_dict = instance.meta.to_dict()
            for key, value in meta_dict.items():
                data[f"meta.{key}"] = value
    if user is not None:
        data["user.id"] = user.id
        data["user.username"] = user.username
    return data


def _backend_python_path(config: dict, instance: "models.Model | None", user: "User | None") -> tuple[bool, str | None]:
    """Backend: importa función vía importlib y la llama.

    Args:
        config: {"path": "module.submodule.function_name"}

    Returns:
        (pasa: bool, mensaje_error: str | None)
    """
    path = config["path"]
    if "." not in path:
        raise ValueError(f"python_path debe incluir módulo: {path}")

    module_path, func_name = path.rsplit(".", 1)

    if module_path not in _get_predicate_whitelist():
        raise ValueError(
            f"Módulo '{module_path}' no está en la whitelist de predicados. "
            f"Configura SINPAPEL_PREDICATE_MODULES o usa un módulo permitido."
        )

    module = import_module(module_path)
    func = getattr(module, func_name, None)
    if func is None:
        raise ValueError(f"Función '{func_name}' no encontrada en módulo '{module_path}'")
    if not callable(func):
        raise ValueError(f"'{func_name}' en módulo '{module_path}' no es callable")

    result = func(instance, user)
    if isinstance(result, bool):
        return result, None
    if isinstance(result, tuple) and len(result) == 2:
        return bool(result[0]), result[1] if result[1] else None
    raise ValueError(f"Función de predicado debe retornar bool o tuple[bool, str], recibió: {type(result)}")


def _backend_json_logic(config: dict, instance: "models.Model | None", user: "User | None") -> tuple[bool, str | None]:
    """Backend: evalúa regla JSON Logic contra el contexto de datos.

    Args:
        config: {"rule": {...}}

    Returns:
        (pasa: bool, mensaje_error: None)
    """
    data = _build_data_context(instance, user)
    result = evaluar_json_logic(config["rule"], data)
    return bool(result), None


def _backend_django_orm(config: dict, instance: "models.Model | None", user: "User | None") -> tuple[bool, str | None]:
    """Backend: evalúa lookup de Django ORM contra la instancia.

    Args:
        config: {"lookup": {"field__gte": value}}

    Returns:
        (pasa: bool, mensaje_error: None)
    """
    if instance is None:
        return False, "No hay instancia para evaluar lookup ORM"

    lookup = config["lookup"]
    qs = type(instance).objects.filter(pk=instance.pk, **lookup)
    return qs.exists(), None


class PredicateEngine:
    """Motor extensible de evaluación de condiciones de transición."""

    _backends: dict[str, Callable] = {
        "python_path": _backend_python_path,
        "json_logic": _backend_json_logic,
        "django_orm": _backend_django_orm,
    }

    @classmethod
    def registrar_backend(cls, tipo: str, funcion: Callable) -> None:
        """Registra un nuevo backend de evaluación."""
        cls._backends[tipo] = funcion

    @classmethod
    def evaluar(
        cls,
        condicion: "CondicionTransicion",
        instance: "models.Model | None",
        user: "User | None",
    ) -> tuple[bool, str | None]:
        """Evalúa una condición individual.

        Returns:
            (pasa: bool, mensaje_error: str | None)
        """
        backend = cls._backends.get(condicion.tipo)
        if backend is None:
            raise ValueError(f"Backend '{condicion.tipo}' no registrado")
        return backend(condicion.configuracion, instance, user)
