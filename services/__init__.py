"""Sinpapel services — workflow engine + side_effects dispatch."""
from sinpapel.services.side_effects import (
    SIDE_EFFECTS,
    ejecutar_side_effects,
    register_side_effect,
)

__all__ = [
    "SIDE_EFFECTS",
    "ejecutar_side_effects",
    "register_side_effect",
]
