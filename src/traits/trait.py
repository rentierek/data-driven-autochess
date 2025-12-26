"""
System Traitów/Synergii.

Traity to synergie między jednostkami. Aktywują się przy progach (2/4/6)
i mogą dawać bonusy dla posiadaczy traitu lub całego teamu.

KLUCZOWE ZASADY:
═══════════════════════════════════════════════════════════════════════════

1. UNIKALNE JEDNOSTKI
   Dwie takie same jednostki liczą się jako 1 do traitu.
   Przykład: 2x Warrior = 1 "knight" trait count

2. PROGI ZASTĘPUJĄ
   Wyższy próg zastępuje niższy, nie sumują się.
   Przykład: Knight 4 daje 40 armor, NIE 20+40=60

3. CELE EFEKTÓW
   - "holders": tylko jednostki z traitem
   - "team": cały team
   - "self": jednostka która triggered
   - "adjacent": sąsiedzi na hexach
   - "enemies": wrogowie

4. TRIGGERY
   - on_battle_start: start walki
   - on_hp_threshold: HP poniżej progu
   - on_time: po X tickach
   - on_death: po śmierci sojusznika
   - on_interval: co X ticków
   - on_first_cast: po pierwszym cascie
   - on_kill: po zabiciu wroga

PRZYKŁAD YAML:
═══════════════════════════════════════════════════════════════════════════

    knight:
      name: "Knight"
      description: "Knights gain bonus armor."
      thresholds:
        2:
          trigger: "on_battle_start"
          effects:
            - type: "stat_bonus"
              stat: "armor"
              value: 20
              target: "holders"
        4:
          trigger: "on_battle_start"
          effects:
            - type: "stat_bonus"
              stat: "armor"
              value: 40
              target: "holders"
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from enum import Enum, auto

if TYPE_CHECKING:
    from ..units.unit import Unit


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════

class TriggerType(Enum):
    """Typ triggera traitu."""
    ON_BATTLE_START = auto()
    ON_HP_THRESHOLD = auto()
    ON_TIME = auto()
    ON_DEATH = auto()
    ON_INTERVAL = auto()
    ON_FIRST_CAST = auto()
    ON_KILL = auto()


class EffectTarget(Enum):
    """Cel efektu traitu."""
    HOLDERS = "holders"       # Tylko jednostki z traitem
    TEAM = "team"             # Cały team
    SELF = "self"             # Jednostka która triggered
    ADJACENT = "adjacent"     # Sąsiedzi na hexach
    ENEMIES = "enemies"       # Wrogowie
    NEAREST_ALLY = "nearest_ally"


# ═══════════════════════════════════════════════════════════════════════════
# TRAIT TRIGGER
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TraitTrigger:
    """
    Określa kiedy trait się aktywuje.
    
    Attributes:
        trigger_type: Typ triggera
        params: Parametry triggera (np. threshold dla HP)
    
    Example:
        >>> trigger = TraitTrigger(TriggerType.ON_HP_THRESHOLD, {"threshold": 0.5})
    """
    trigger_type: TriggerType
    params: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraitTrigger":
        """Tworzy trigger z słownika YAML."""
        trigger_str = data.get("trigger", "on_battle_start")
        params = data.get("trigger_params", {})
        
        trigger_map = {
            "on_battle_start": TriggerType.ON_BATTLE_START,
            "on_hp_threshold": TriggerType.ON_HP_THRESHOLD,
            "on_time": TriggerType.ON_TIME,
            "on_death": TriggerType.ON_DEATH,
            "on_interval": TriggerType.ON_INTERVAL,
            "on_first_cast": TriggerType.ON_FIRST_CAST,
            "on_kill": TriggerType.ON_KILL,
        }
        
        trigger_type = trigger_map.get(trigger_str, TriggerType.ON_BATTLE_START)
        return cls(trigger_type=trigger_type, params=params)


# ═══════════════════════════════════════════════════════════════════════════
# TRAIT EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TraitEffect:
    """
    Pojedynczy efekt traitu.
    
    Attributes:
        effect_type: Typ efektu (stat_bonus, damage_amp, shield, etc.)
        target: Kto otrzymuje efekt
        value: Wartość efektu
        params: Dodatkowe parametry
    
    Example:
        >>> effect = TraitEffect("stat_bonus", EffectTarget.HOLDERS, 20, {"stat": "armor"})
    """
    effect_type: str
    target: EffectTarget
    value: float
    params: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraitEffect":
        """Tworzy efekt z słownika YAML."""
        effect_type = data.get("type", "stat_bonus")
        target_str = data.get("target", "holders")
        value = data.get("value", 0)
        
        # Convert target string to enum
        target_map = {
            "holders": EffectTarget.HOLDERS,
            "team": EffectTarget.TEAM,
            "self": EffectTarget.SELF,
            "adjacent": EffectTarget.ADJACENT,
            "enemies": EffectTarget.ENEMIES,
            "nearest_ally": EffectTarget.NEAREST_ALLY,
        }
        target = target_map.get(target_str, EffectTarget.HOLDERS)
        
        # Extract additional params
        params = {k: v for k, v in data.items() 
                  if k not in ("type", "target", "value")}
        
        return cls(
            effect_type=effect_type,
            target=target,
            value=value,
            params=params,
        )


# ═══════════════════════════════════════════════════════════════════════════
# TRAIT THRESHOLD
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TraitThreshold:
    """
    Próg aktywacji traitu.
    
    Attributes:
        count: Wymagana liczba jednostek (2, 4, 6...)
        trigger: Kiedy się aktywuje
        effects: Lista efektów do zastosowania
    
    Example:
        >>> threshold = TraitThreshold(
        ...     count=2,
        ...     trigger=TraitTrigger(TriggerType.ON_BATTLE_START),
        ...     effects=[TraitEffect("stat_bonus", EffectTarget.HOLDERS, 20, {"stat": "armor"})]
        ... )
    """
    count: int
    trigger: TraitTrigger
    effects: List[TraitEffect]
    
    @classmethod
    def from_dict(cls, count: int, data: Dict[str, Any]) -> "TraitThreshold":
        """Tworzy próg z słownika YAML."""
        trigger = TraitTrigger.from_dict(data)
        
        effects_data = data.get("effects", [])
        effects = [TraitEffect.from_dict(e) for e in effects_data]
        
        return cls(count=count, trigger=trigger, effects=effects)


# ═══════════════════════════════════════════════════════════════════════════
# TRAIT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Trait:
    """
    Definicja traitu/synergii.
    
    Attributes:
        id: Unikalne ID traitu
        name: Nazwa wyświetlana
        description: Opis działania
        thresholds: Mapa count -> TraitThreshold
    
    Example:
        >>> trait = Trait.from_dict("knight", {
        ...     "name": "Knight",
        ...     "description": "Knights gain bonus armor.",
        ...     "thresholds": {
        ...         2: {"effects": [{"type": "stat_bonus", "stat": "armor", "value": 20}]}
        ...     }
        ... })
    """
    id: str
    name: str
    description: str
    thresholds: Dict[int, TraitThreshold]
    
    def get_active_threshold(self, count: int) -> Optional[TraitThreshold]:
        """
        Zwraca najwyższy aktywowany próg dla danej liczby jednostek.
        
        Progi ZASTĘPUJĄ się (nie sumują).
        
        Args:
            count: Liczba unikalnych jednostek z traitem
            
        Returns:
            TraitThreshold lub None jeśli brak aktywnego progu
        
        Example:
            >>> trait.get_active_threshold(5)  # z progami 2, 4, 6
            TraitThreshold(count=4, ...)  # zwraca najwyższy <= 5
        """
        active = None
        for threshold_count, threshold in sorted(self.thresholds.items()):
            if count >= threshold_count:
                active = threshold
        return active
    
    def get_threshold_counts(self) -> List[int]:
        """Zwraca posortowaną listę progów [2, 4, 6]."""
        return sorted(self.thresholds.keys())
    
    @classmethod
    def from_dict(cls, trait_id: str, data: Dict[str, Any]) -> "Trait":
        """Tworzy trait z słownika YAML."""
        name = data.get("name", trait_id.title())
        description = data.get("description", "")
        
        thresholds = {}
        thresholds_data = data.get("thresholds", {})
        
        for count, threshold_data in thresholds_data.items():
            count_int = int(count)
            thresholds[count_int] = TraitThreshold.from_dict(count_int, threshold_data)
        
        return cls(
            id=trait_id,
            name=name,
            description=description,
            thresholds=thresholds,
        )


# ═══════════════════════════════════════════════════════════════════════════
# ACTIVE TRAIT EFFECT (Runtime)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ActiveTraitEffect:
    """
    Aktywny efekt traitu w trakcie walki.
    
    Używane do śledzenia efektów które zostały już zastosowane,
    szczególnie dla triggerów jednorazowych jak on_hp_threshold.
    
    Attributes:
        trait_id: ID traitu
        threshold_count: Który próg
        effect: Sam efekt
        applied_to: Lista unit IDs do których zastosowano
        triggered: Czy już triggered (dla one-time triggers)
    """
    trait_id: str
    threshold_count: int
    effect: TraitEffect
    applied_to: List[str] = field(default_factory=list)
    triggered: bool = False
