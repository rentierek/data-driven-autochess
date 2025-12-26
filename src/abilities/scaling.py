"""
System skalowania wartości dla umiejętności.

Prosty wzór: final = value × (stat / 100)

TYPY SKALOWANIA:
═══════════════════════════════════════════════════════════════════

    ad          - Attack Damage castera
    ap          - Ability Power castera
    armor       - Armor castera
    mr          - Magic Resist castera
    max_hp      - Max HP CELU (dla % HP damage)
    missing_hp  - Brakujące HP celu (dla execute/heal)
    caster_hp   - Max HP castera (dla tank skilli)
    caster_missing_hp - Brakujące HP castera

UŻYCIE:
═══════════════════════════════════════════════════════════════════

    # Prosty damage skalowany z AP
    effect:
      type: "damage"
      value: [200, 350, 600]
      scaling: "ap"
    
    # Caster ma 150 AP
    final = 200 * (150 / 100) = 300 damage

WARTOŚCI GWIAZDKOWE:
═══════════════════════════════════════════════════════════════════

    value: [100, 200, 400]   # per star level
    value: 100               # ta sama dla wszystkich

    get_star_value([100, 200, 400], star=2) → 200
    get_star_value(100, star=2) → 100
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Union, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..units.unit import Unit


# Typy wartości - może być lista lub pojedyncza wartość
StarValue = Union[float, int, List[float], List[int]]


def get_star_value(value: StarValue, star_level: int = 1) -> float:
    """
    Pobiera wartość dla danego poziomu gwiazdek.
    
    Args:
        value: Wartość lub lista [1★, 2★, 3★]
        star_level: Poziom gwiazdek (1-3)
        
    Returns:
        float: Wartość dla tego poziomu
        
    Example:
        >>> get_star_value([100, 200, 400], 2)
        200.0
        >>> get_star_value(150, 3)
        150.0
    """
    if isinstance(value, (list, tuple)):
        # Indeks 0 = 1★, 1 = 2★, 2 = 3★
        index = max(0, min(star_level - 1, len(value) - 1))
        return float(value[index])
    return float(value)


def get_stat_for_scaling(
    scaling_type: str,
    caster: "Unit",
    target: Optional["Unit"] = None,
) -> float:
    """
    Pobiera wartość statystyki do skalowania.
    
    Args:
        scaling_type: Typ skalowania (ad, ap, mr, etc.)
        caster: Jednostka castująca
        target: Cel (opcjonalny, dla max_hp/missing_hp celu)
        
    Returns:
        float: Wartość statystyki
    """
    stats = caster.stats
    
    scaling_map = {
        "ad": lambda: stats.get_attack_damage(),
        "ap": lambda: stats.get_ability_power(),
        "armor": lambda: stats.get_armor(),
        "mr": lambda: stats.get_magic_resist(),
        "caster_hp": lambda: stats.get_max_hp(),
        "caster_max_hp": lambda: stats.get_max_hp(),
        "caster_missing_hp": lambda: stats.get_max_hp() - stats.current_hp,
    }
    
    # Statystyki celu
    if target is not None:
        target_stats = target.stats
        scaling_map.update({
            "max_hp": lambda: target_stats.get_max_hp(),
            "target_max_hp": lambda: target_stats.get_max_hp(),
            "missing_hp": lambda: target_stats.get_max_hp() - target_stats.current_hp,
            "target_missing_hp": lambda: target_stats.get_max_hp() - target_stats.current_hp,
            "target_hp": lambda: target_stats.current_hp,
        })
    
    getter = scaling_map.get(scaling_type.lower())
    if getter:
        return getter()
    
    # Fallback - 100 (brak skalowania)
    return 100.0


def calculate_scaled_value(
    base_value: StarValue,
    scaling_type: Optional[str],
    star_level: int,
    caster: "Unit",
    target: Optional["Unit"] = None,
) -> float:
    """
    Oblicza przeskalowaną wartość efektu.
    
    Wzór: final = value[star] × (stat / 100)
    
    Args:
        base_value: Bazowa wartość lub lista per star
        scaling_type: Typ skalowania (None = brak skalowania)
        star_level: Poziom gwiazdek (1-3)
        caster: Jednostka castująca
        target: Cel (opcjonalny)
        
    Returns:
        float: Finalna wartość
        
    Example:
        >>> # 200 base, AP scaling, caster has 150 AP, 2★
        >>> calculate_scaled_value([200, 350, 600], "ap", 2, caster)
        525.0  # 350 * 1.5
    """
    value = get_star_value(base_value, star_level)
    
    if scaling_type is None or scaling_type == "none":
        return value
    
    stat = get_stat_for_scaling(scaling_type, caster, target)
    
    # Wzór: value × (stat / 100)
    return value * (stat / 100.0)


@dataclass
class ScalingConfig:
    """
    Konfiguracja skalowania dla efektu.
    
    Attributes:
        value: Bazowa wartość lub lista [1★, 2★, 3★]
        scaling: Typ skalowania (ad, ap, mr, etc.)
    """
    value: StarValue
    scaling: Optional[str] = None
    
    def calculate(
        self, 
        star_level: int, 
        caster: "Unit", 
        target: Optional["Unit"] = None
    ) -> float:
        """Oblicza przeskalowaną wartość."""
        return calculate_scaled_value(
            self.value, 
            self.scaling, 
            star_level, 
            caster, 
            target
        )
    
    @classmethod
    def from_dict(cls, data: dict) -> "ScalingConfig":
        """Tworzy z YAML dict."""
        return cls(
            value=data.get("value", 0),
            scaling=data.get("scaling"),
        )
