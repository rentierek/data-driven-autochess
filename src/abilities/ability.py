"""
Ability - reprezentacja umiejętności.

Ability łączy:
- Targeting (kogo celujemy)
- Delivery (instant/projectile)
- Effects (co robimy)

YAML FORMAT:
═══════════════════════════════════════════════════════════════════

    fireball:
      name: "Fireball"
      mana_cost: 80
      cast_time: [20, 18, 15]    # per star
      
      target_type: "current_target"
      delivery: "projectile"
      projectile:
        speed: 3
        homing: true
      
      aoe:
        type: "circle"
        radius: [1, 1, 2]
      
      effects:
        - type: "damage"
          damage_type: "magical"
          value: [200, 350, 600]
          scaling: "ap"
        - type: "burn"
          value: [20, 35, 50]
          duration: 90
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from .scaling import get_star_value, StarValue
from .effect import Effect, parse_effects, EffectResult

if TYPE_CHECKING:
    from ..units.unit import Unit
    from ..simulation.simulation import Simulation


# ═══════════════════════════════════════════════════════════════════════════
# PROJECTILE CONFIG
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ProjectileConfig:
    """
    Konfiguracja pocisku.
    
    Attributes:
        speed: Prędkość w hexach per tick
        homing: Czy śledzi cel
        can_miss: Czy może pudłować (jeśli cel zginie/ucieknie)
    """
    speed: float = 2.0
    homing: bool = True
    can_miss: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectileConfig":
        return cls(
            speed=data.get("speed", 2.0),
            homing=data.get("homing", True),
            can_miss=data.get("can_miss", True),
        )


# ═══════════════════════════════════════════════════════════════════════════
# AOE CONFIG
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AoEConfig:
    """
    Konfiguracja Area of Effect.
    
    Attributes:
        aoe_type: circle, cone, line
        radius: Promień (dla circle)
        angle: Kąt (dla cone)
        width: Szerokość (dla line)
        includes_target: Czy primary target jest też trafiony
    """
    aoe_type: str = "circle"
    radius: StarValue = 1
    angle: int = 60  # dla cone
    width: int = 1   # dla line
    includes_target: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AoEConfig":
        return cls(
            aoe_type=data.get("type", "circle"),
            radius=data.get("radius", 1),
            angle=data.get("angle", 60),
            width=data.get("width", 1),
            includes_target=data.get("includes_target", True),
        )


# ═══════════════════════════════════════════════════════════════════════════
# ABILITY
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Ability:
    """
    Reprezentacja umiejętności.
    
    Attributes:
        id: Unikalny identyfikator (z YAML key)
        name: Nazwa wyświetlana
        mana_cost: Koszt many
        cast_time: Czas castowania w tickach per star
        
        target_type: Typ targetingu
        delivery: "instant" lub "projectile"
        projectile: Konfiguracja pocisku (jeśli projectile)
        aoe: Konfiguracja AoE (opcjonalne)
        
        effects: Lista efektów do zaaplikowania
    """
    id: str
    name: str
    mana_cost: int = 100
    cast_time: StarValue = 15
    effect_delay: StarValue = 0  # delay przed efektem
    
    # Targeting
    target_type: str = "current_target"
    
    # Delivery
    delivery: str = "instant"  # "instant" | "projectile"
    projectile: Optional[ProjectileConfig] = None
    
    # AoE
    aoe: Optional[AoEConfig] = None
    
    # Effects
    effects: List[Effect] = field(default_factory=list)
    
    def get_cast_time(self, star_level: int) -> int:
        """Zwraca czas castowania dla poziomu gwiazdek."""
        return int(get_star_value(self.cast_time, star_level))
    
    def get_effect_delay(self, star_level: int) -> int:
        """Zwraca opóźnienie efektu."""
        return int(get_star_value(self.effect_delay, star_level))
    
    def get_aoe_radius(self, star_level: int) -> int:
        """Zwraca promień AoE dla poziomu gwiazdek."""
        if self.aoe is None:
            return 0
        return int(get_star_value(self.aoe.radius, star_level))
    
    def execute(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> List[EffectResult]:
        """
        Wykonuje ability - aplikuje wszystkie efekty.
        
        Args:
            caster: Jednostka castująca
            target: Główny cel
            star_level: Poziom gwiazdek castera
            simulation: Referencja do symulacji
            
        Returns:
            List[EffectResult]: Wyniki wszystkich efektów
        """
        results = []
        
        # Znajdź wszystkie cele (z AoE jeśli jest)
        targets = self._get_all_targets(target, star_level, simulation)
        
        # Aplikuj każdy efekt na każdy cel
        for effect in self.effects:
            for t in targets:
                result = effect.apply(caster, t, star_level, simulation)
                results.append(result)
        
        return results
    
    def _get_all_targets(
        self,
        primary_target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> List["Unit"]:
        """
        Zwraca listę wszystkich celów (uwzględniając AoE).
        """
        if self.aoe is None:
            return [primary_target]
        
        targets = []
        radius = self.get_aoe_radius(star_level)
        
        if self.aoe.aoe_type == "circle":
            # Znajdź wszystkich wrogów w radius od primary_target
            for unit in simulation.get_living_units():
                if unit.team != primary_target.team:
                    continue  # tylko ten sam team co target (wrogowie castera)
                if unit.id == primary_target.id:
                    if self.aoe.includes_target:
                        targets.append(unit)
                    continue
                
                distance = primary_target.position.distance(unit.position)
                if distance <= radius:
                    targets.append(unit)
            
            # Zawsze dodaj primary target na początku
            if self.aoe.includes_target and primary_target not in targets:
                targets.insert(0, primary_target)
        
        elif self.aoe.aoe_type == "cone":
            # TODO: Implementacja cone
            targets = [primary_target]
        
        elif self.aoe.aoe_type == "line":
            # TODO: Implementacja line
            targets = [primary_target]
        
        return targets if targets else [primary_target]
    
    @classmethod
    def from_dict(cls, ability_id: str, data: Dict[str, Any]) -> "Ability":
        """
        Tworzy Ability z YAML dict.
        
        Args:
            ability_id: Klucz z YAML (np. "fireball")
            data: Dane ability
            
        Returns:
            Ability: Nowa instancja
        """
        # Parsuj projectile config
        projectile = None
        if "projectile" in data:
            projectile = ProjectileConfig.from_dict(data["projectile"])
        
        # Parsuj AoE config
        aoe = None
        if "aoe" in data:
            aoe = AoEConfig.from_dict(data["aoe"])
        
        # Parsuj effects
        effects = []
        if "effects" in data:
            effects = parse_effects(data["effects"])
        
        return cls(
            id=ability_id,
            name=data.get("name", ability_id),
            mana_cost=data.get("mana_cost", 100),
            cast_time=data.get("cast_time", data.get("cast_time_ticks", 15)),
            effect_delay=data.get("effect_delay", 0),
            target_type=data.get("target_type", "current_target"),
            delivery=data.get("delivery", "instant"),
            projectile=projectile,
            aoe=aoe,
            effects=effects,
        )
    
    def to_dict(self) -> dict:
        """Serializuje ability do dict."""
        result = {
            "id": self.id,
            "name": self.name,
            "mana_cost": self.mana_cost,
            "cast_time": self.cast_time,
            "target_type": self.target_type,
            "delivery": self.delivery,
            "effects_count": len(self.effects),
        }
        if self.aoe:
            result["aoe"] = self.aoe.aoe_type
        return result
