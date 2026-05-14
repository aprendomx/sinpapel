"""Sinpapel — Restricted JSON Logic evaluator.

Supports safe operations only: var, ==, !=, <, >, <=, >=, and, or, !, in.
No arbitrary function calls. No access to Python builtins.
"""
from typing import Any


def evaluar(rule: Any, data: dict[str, Any]) -> Any:
    """Evalúa una regla JSON Logic contra un contexto de datos.

    Args:
        rule: dict con operador JSON Logic o valor literal
        data: dict con variables accesibles via {"var": "nombre"}

    Returns:
        Resultado de la evaluación
    """
    if not isinstance(rule, dict):
        return rule

    if len(rule) != 1:
        raise ValueError(f"Regla JSON Logic debe tener exactamente una clave, recibió: {list(rule.keys())}")

    op, args = next(iter(rule.items()))

    if op == "var":
        return data.get(args)

    if op == "==":
        left, right = _eval_args(args, data)
        return left == right

    if op == "!=":
        left, right = _eval_args(args, data)
        return left != right

    if op == ">":
        left, right = _eval_args(args, data)
        try:
            return left > right
        except TypeError:
            return False

    if op == ">=":
        left, right = _eval_args(args, data)
        try:
            return left >= right
        except TypeError:
            return False

    if op == "<":
        left, right = _eval_args(args, data)
        try:
            return left < right
        except TypeError:
            return False

    if op == "<=":
        left, right = _eval_args(args, data)
        try:
            return left <= right
        except TypeError:
            return False

    if op == "and":
        if not isinstance(args, list):
            raise ValueError(f"Operador 'and' requiere una lista de argumentos, recibió: {args}")
        return all(evaluar(subrule, data) for subrule in args)

    if op == "or":
        if not isinstance(args, list):
            raise ValueError(f"Operador 'or' requiere una lista de argumentos, recibió: {args}")
        return any(evaluar(subrule, data) for subrule in args)

    if op == "!":
        return not evaluar(args, data)

    if op == "in":
        left, right = _eval_args(args, data)
        return left in right

    raise ValueError(f"Operador JSON Logic no soportado: '{op}'")


def _eval_args(args: Any, data: dict[str, Any]) -> tuple[Any, Any]:
    """Evalúa una lista de 2 argumentos contra el contexto."""
    if not isinstance(args, list) or len(args) != 2:
        raise ValueError(f"Operador binario requiere lista de 2 argumentos, recibió: {args}")
    return evaluar(args[0], data), evaluar(args[1], data)
