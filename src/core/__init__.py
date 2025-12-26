"""
Core module - podstawowe komponenty silnika.

Zawiera:
- HexCoord: System współrzędnych hexagonalnych
- HexGrid: Siatka hexagonalna z obsługą zajętości
- pathfinding: Algorytm A* dla hex grid
- GameRNG: Deterministyczny generator losowości
- ConfigLoader: Wczytywanie konfiguracji z defaults
- targeting: Zaawansowany system targetingu
"""

from .hex_coord import HexCoord
from .hex_grid import HexGrid
from .pathfinding import find_path
from .rng import GameRNG
from .config_loader import ConfigLoader
from .targeting import (
    TargetSelector,
    get_selector,
    parse_target_type,
    SELECTOR_REGISTRY,
)

__all__ = [
    "HexCoord", "HexGrid", "find_path", "GameRNG", "ConfigLoader",
    "TargetSelector", "get_selector", "parse_target_type", "SELECTOR_REGISTRY",
]

