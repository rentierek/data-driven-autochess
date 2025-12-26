"""
System Area of Effect (AoE) dla umiejętności.

Obsługuje różne kształty efektów obszarowych:
- Circle: okrąg o danym promieniu
- Cone: stożek w kierunku celu
- Line: linia o określonej szerokości

UŻYCIE:
═══════════════════════════════════════════════════════════════════

    aoe:
      type: "circle"
      radius: 2           # hexy
      includes_target: true

    aoe:
      type: "cone"
      angle: 60          # stopnie
      range: 3           # zasięg

    aoe:
      type: "line"
      width: 1           # szerokość
      range: 5           # długość
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, TYPE_CHECKING
import math

if TYPE_CHECKING:
    from ..units.unit import Unit
    from ..core.hex_coord import HexCoord


def get_units_in_circle(
    center: "HexCoord",
    radius: int,
    units: List["Unit"],
    include_center: bool = True,
) -> List["Unit"]:
    """
    Zwraca jednostki w okręgu o danym promieniu.
    
    Args:
        center: Środek okręgu
        radius: Promień w hexach
        units: Lista jednostek do sprawdzenia
        include_center: Czy uwzględnić jednostkę w centrum
        
    Returns:
        List[Unit]: Jednostki w zasięgu
    """
    result = []
    
    for unit in units:
        if not unit.is_alive():
            continue
            
        distance = center.distance(unit.position)
        
        if distance == 0:
            if include_center:
                result.append(unit)
        elif distance <= radius:
            result.append(unit)
    
    return result


def get_units_in_cone(
    origin: "HexCoord",
    target: "HexCoord", 
    angle: float,
    range_: int,
    units: List["Unit"],
) -> List["Unit"]:
    """
    Zwraca jednostki w stożku w kierunku celu.
    
    Args:
        origin: Punkt początkowy stożka
        target: Punkt wskazujący kierunek
        angle: Kąt stożka w stopniach
        range_: Maksymalny zasięg
        units: Lista jednostek do sprawdzenia
        
    Returns:
        List[Unit]: Jednostki w stożku
    """
    result = []
    
    # Oblicz kierunek do celu
    dir_q = target.q - origin.q
    dir_r = target.r - origin.r
    
    # Kąt bazowy (w radianach)
    if dir_q == 0 and dir_r == 0:
        return result
    
    base_angle = math.atan2(dir_r, dir_q)
    half_cone = math.radians(angle / 2)
    
    for unit in units:
        if not unit.is_alive():
            continue
        
        # Dystans od origin
        distance = origin.distance(unit.position)
        if distance == 0 or distance > range_:
            continue
        
        # Kąt do jednostki
        unit_q = unit.position.q - origin.q
        unit_r = unit.position.r - origin.r
        unit_angle = math.atan2(unit_r, unit_q)
        
        # Różnica kątów (normalized)
        angle_diff = abs(unit_angle - base_angle)
        if angle_diff > math.pi:
            angle_diff = 2 * math.pi - angle_diff
        
        # Sprawdź czy w stożku
        if angle_diff <= half_cone:
            result.append(unit)
    
    return result


def get_units_in_line(
    origin: "HexCoord",
    target: "HexCoord",
    width: int,
    units: List["Unit"],
) -> List["Unit"]:
    """
    Zwraca jednostki na linii między origin a target.
    
    Args:
        origin: Punkt początkowy
        target: Punkt końcowy
        width: Szerokość linii (0 = tylko dokładnie na linii)
        units: Lista jednostek do sprawdzenia
        
    Returns:
        List[Unit]: Jednostki na linii
    """
    result = []
    
    # Get all hexes on the line
    line_hexes = origin.line_to(target)
    line_set = set((h.q, h.r) for h in line_hexes)
    
    # Add adjacent hexes for width
    if width > 0:
        expanded = set()
        for hex_pos in line_hexes:
            expanded.add((hex_pos.q, hex_pos.r))
            for neighbor in hex_pos.neighbors():
                if origin.distance(neighbor) <= origin.distance(target) + 1:
                    expanded.add((neighbor.q, neighbor.r))
        line_set = expanded
    
    for unit in units:
        if not unit.is_alive():
            continue
        
        unit_pos = (unit.position.q, unit.position.r)
        if unit_pos in line_set:
            result.append(unit)
    
    return result


@dataclass
class AoECalculator:
    """
    Klasa pomocnicza do obliczania AoE.
    """
    
    @staticmethod
    def get_targets(
        aoe_type: str,
        origin: "HexCoord",
        target: "HexCoord",
        radius: int,
        angle: float,
        width: int,
        candidates: List["Unit"],
        include_primary: bool = True,
        primary_target: "Unit" = None,
    ) -> List["Unit"]:
        """
        Uniwersalna metoda do pobierania celów w AoE.
        
        Args:
            aoe_type: "circle", "cone", "line"
            origin: Pozycja castera
            target: Pozycja celu
            radius: Promień (dla circle)
            angle: Kąt (dla cone)
            width: Szerokość (dla line)
            candidates: Jednostki do sprawdzenia
            include_primary: Czy uwzględnić primary target
            primary_target: Główny cel (opcjonalny)
            
        Returns:
            List[Unit]: Lista celów w AoE
        """
        result = []
        
        if aoe_type == "circle":
            result = get_units_in_circle(target, radius, candidates)
        
        elif aoe_type == "cone":
            result = get_units_in_cone(origin, target, angle, radius, candidates)
        
        elif aoe_type == "line":
            result = get_units_in_line(origin, target, width, candidates)
        
        else:
            # Fallback: single target
            if primary_target and primary_target.is_alive():
                result = [primary_target]
        
        # Ensure primary target is included if requested
        if include_primary and primary_target:
            if primary_target not in result and primary_target.is_alive():
                result.insert(0, primary_target)
        
        return result
