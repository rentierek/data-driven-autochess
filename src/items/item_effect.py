"""
ItemEffect i ConditionalEffect - efekty przedmiotów.

TYPY EFEKTÓW:
═══════════════════════════════════════════════════════════════════════════

    stat_bonus      - Dodaje statystykę (używa tego samego systemu co traits)
    damage_amp      - Zwiększa zadawane obrażenia %
    damage_reduction- Zmniejsza otrzymywane obrażenia %
    shield          - Daje tarczę
    heal            - Leczy
    mana_grant      - Daje manę
    slow            - Spowalnia wroga
    stun            - Ogłusza wroga
    stacking_stat   - Stackujące się bonusy (Titan's Resolve)

CONDITIONAL EFFECTS:
═══════════════════════════════════════════════════════════════════════════

    Sprawdzane podczas damage calculation.
    
    Giant Slayer: Jeśli cel ma >1600 HP -> +20% dmg
    
    condition:
      type: "target_max_hp"
      operator: ">"
      value: 1600
    effect:
      type: "damage_amp"
      value: 0.2
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum, auto

if TYPE_CHECKING:
    from ..units.unit import Unit
    from .item import ItemTrigger


# ═══════════════════════════════════════════════════════════════════════════
# EFFECT TARGET
# ═══════════════════════════════════════════════════════════════════════════

class EffectTarget(Enum):
    """Cel efektu itema."""
    
    SELF = "self"                      # Właściciel itema
    TARGET = "target"                   # Cel ataku/ability
    ENEMIES = "enemies"                 # Wszyscy wrogowie
    ALLIES = "allies"                   # Wszyscy sojusznicy
    ENEMIES_IN_RANGE = "enemies_in_range"  # Wrogowie w zasięgu
    ALLIES_IN_RANGE = "allies_in_range"    # Sojusznicy w zasięgu
    ALLIES_IN_ROW = "allies_in_row"        # Sojusznicy w tym samym rzędzie
    ADJACENT = "adjacent"                   # Jednostki obok
    
    @classmethod
    def from_string(cls, s: str) -> "EffectTarget":
        """Konwertuje string na EffectTarget."""
        for member in cls:
            if member.value == s:
                return member
        return cls.SELF


# ═══════════════════════════════════════════════════════════════════════════
# ITEM EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ItemEffect:
    """
    Efekt triggerowalny przedmiotu.
    
    Używa tego samego systemu co TraitEffect i AbilityEffect.
    
    Attributes:
        effect_type: Typ efektu (stat_bonus, damage_amp, etc.)
        target: Cel efektu
        value: Wartość efektu
        params: Dodatkowe parametry
        trigger: Kiedy efekt się aktywuje
    """
    
    effect_type: str
    target: EffectTarget
    value: float = 0
    params: Dict[str, Any] = field(default_factory=dict)
    trigger: Optional["ItemTrigger"] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], trigger: Optional["ItemTrigger"] = None) -> "ItemEffect":
        """Tworzy ItemEffect z danych YAML."""
        target_str = data.get("target", "self")
        
        # Zbierz wszystkie parametry oprócz type, target, value
        params = {k: v for k, v in data.items() if k not in ("type", "target", "value")}
        
        return cls(
            effect_type=data.get("type", "stat_bonus"),
            target=EffectTarget.from_string(target_str),
            value=data.get("value", 0),
            params=params,
            trigger=trigger,
        )


# ═══════════════════════════════════════════════════════════════════════════
# EFFECT CONDITION
# ═══════════════════════════════════════════════════════════════════════════

class ConditionOperator(Enum):
    """Operator porównania dla warunków."""
    
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "=="
    NEQ = "!="
    
    def check(self, a: float, b: float) -> bool:
        """Sprawdza warunek."""
        ops = {
            self.GT: lambda x, y: x > y,
            self.LT: lambda x, y: x < y,
            self.GTE: lambda x, y: x >= y,
            self.LTE: lambda x, y: x <= y,
            self.EQ: lambda x, y: x == y,
            self.NEQ: lambda x, y: x != y,
        }
        return ops[self](a, b)
    
    @classmethod
    def from_string(cls, s: str) -> "ConditionOperator":
        """Konwertuje string na operator."""
        for member in cls:
            if member.value == s:
                return member
        return cls.GT


@dataclass
class EffectCondition:
    """
    Warunek dla efektu warunkowego.
    
    Typy warunków:
        target_max_hp: Maksymalne HP celu
        target_hp_percent: Procent HP celu
        target_has_shield: Czy cel ma tarczę
        self_hp_percent: Procent HP właściciela
        self_max_hp: Maksymalne HP właściciela
        target_has_trait: Czy cel ma trait
        target_has_debuff: Czy cel ma debuff
    
    Attributes:
        condition_type: Typ warunku
        operator: Operator porównania (>, <, etc.)
        value: Wartość do porównania
        trait: Nazwa traitu (dla target_has_trait)
        debuff: Nazwa debuffa (dla target_has_debuff)
    """
    
    condition_type: str
    operator: ConditionOperator
    value: float = 0
    trait: Optional[str] = None
    debuff: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EffectCondition":
        """Tworzy EffectCondition z danych YAML."""
        return cls(
            condition_type=data.get("type", "target_max_hp"),
            operator=ConditionOperator.from_string(data.get("operator", ">")),
            value=data.get("value", 0),
            trait=data.get("trait"),
            debuff=data.get("debuff"),
        )
    
    def check(self, attacker: "Unit", defender: "Unit") -> bool:
        """
        Sprawdza czy warunek jest spełniony.
        
        Args:
            attacker: Jednostka z itemem
            defender: Cel ataku/ability
            
        Returns:
            True jeśli warunek spełniony
        """
        cond_type = self.condition_type
        
        if cond_type == "target_max_hp":
            val = defender.stats.base_hp
        elif cond_type == "target_hp_percent":
            val = defender.stats.hp_percent()
        elif cond_type == "target_current_hp":
            val = defender.stats.current_hp
        elif cond_type == "self_max_hp":
            val = attacker.stats.base_hp
        elif cond_type == "self_hp_percent":
            val = attacker.stats.hp_percent()
        elif cond_type == "self_current_hp":
            val = attacker.stats.current_hp
        elif cond_type == "target_has_shield":
            # Check if defender has shield
            shield = getattr(defender.stats, 'current_shield', 0)
            return self.operator.check(shield, self.value)
        elif cond_type == "target_has_trait":
            # Check if defender has specific trait
            return self.trait in defender.traits
        elif cond_type == "target_has_debuff":
            # Check if defender has specific debuff
            return any(d.id == self.debuff for d in defender.debuffs)
        else:
            return False
        
        return self.operator.check(val, self.value)


# ═══════════════════════════════════════════════════════════════════════════
# CONDITIONAL EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ConditionalEffect:
    """
    Efekt warunkowy sprawdzany podczas damage calculation.
    
    Przykład (Giant Slayer):
        condition:
          type: "target_max_hp"
          operator: ">"
          value: 1600
        effect:
          type: "damage_amp"
          value: 0.2
    
    Attributes:
        condition: Warunek do spełnienia
        effect: Efekt do zastosowania
    """
    
    condition: EffectCondition
    effect: ItemEffect
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConditionalEffect":
        """Tworzy ConditionalEffect z danych YAML."""
        condition_data = data.get("condition", {})
        effect_data = data.get("effect", {})
        
        return cls(
            condition=EffectCondition.from_dict(condition_data),
            effect=ItemEffect.from_dict(effect_data),
        )
    
    def check_and_get_modifier(
        self, 
        attacker: "Unit", 
        defender: "Unit"
    ) -> Optional[Dict[str, float]]:
        """
        Sprawdza warunek i zwraca modyfikatory.
        
        Returns:
            Dict z modyfikatorami jeśli warunek spełniony, None otherwise
        """
        if not self.condition.check(attacker, defender):
            return None
        
        effect = self.effect
        
        if effect.effect_type == "damage_amp":
            return {"damage_amp": effect.value}
        elif effect.effect_type == "damage_reduction":
            return {"damage_reduction": effect.value}
        elif effect.effect_type == "armor_pen":
            return {"armor_pen": effect.value}
        elif effect.effect_type == "magic_pen":
            return {"magic_pen": effect.value}
        
        return None
