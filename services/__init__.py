"""Sinpapel services — workflow engine + side_effects dispatch."""
from sinpapel.services.predicate_engine import PredicateEngine
from sinpapel.services.side_effects import (
    SIDE_EFFECTS,
    ejecutar_side_effects,
    register_side_effect,
)

__all__ = [
    "PredicateEngine",
    "SIDE_EFFECTS",
    "ejecutar_side_effects",
    "register_side_effect",
]
