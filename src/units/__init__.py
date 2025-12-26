"""
Units module - klasy jednostek i ich komponentów.

Zawiera:
- UnitStats: Dataclass ze statystykami (HP, mana, crit, etc.)
- UnitState: Enum stanów jednostki (IDLE, MOVING, etc.)
- Unit: Główna klasa jednostki łącząca wszystko
- ChampionClass: System klas modyfikujących zachowanie
"""

from .stats import UnitStats
from .state_machine import UnitState, UnitStateMachine
from .unit import Unit
from .champion_class import ChampionClass, ChampionClassLoader, DEFAULT_CLASS

__all__ = [
    "UnitStats", "UnitState", "UnitStateMachine", "Unit",
    "ChampionClass", "ChampionClassLoader", "DEFAULT_CLASS",
]

