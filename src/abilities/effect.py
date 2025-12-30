"""
System efektów dla umiejętności.

Każdy efekt to pojedynczy komponent ability - damage, heal, stun, etc.
Efekty mogą być łączone w łańcuchy (ability ma listę effects).

TYPY EFEKTÓW:
═══════════════════════════════════════════════════════════════════

    OFFENSIVE
    ─────────────────────────────────────────────────────────────
    damage      - Jednorazowe obrażenia (physical/magical/true)
    dot         - Damage Over Time
    burn        - True damage per second
    execute     - Zabija poniżej % HP
    sunder      - Redukuje Armor
    shred       - Redukuje Magic Resist

    CROWD CONTROL
    ─────────────────────────────────────────────────────────────
    stun        - Wyłącza jednostkę
    knockup     - Stun + nie można przerwać
    silence     - Blokada spelli
    disarm      - Blokada auto-ataków
    slow        - Spowolnienie Attack Speed
    mana_reave  - Zwiększa koszt many

    SUPPORT
    ─────────────────────────────────────────────────────────────
    heal        - Przywraca HP
    shield      - Tymczasowe HP
    cleanse     - Usuwa debuffs
    mana_grant  - Daje manę
    wound       - Redukuje leczenie

    DISPLACEMENT
    ─────────────────────────────────────────────────────────────
    knockback   - Odpycha cel
    pull        - Przyciąga cel
    dash        - Dash castera

    MODIFIERS
    ─────────────────────────────────────────────────────────────
    buff        - Tymczasowy bonus do statystyki

UŻYCIE W YAML:
═══════════════════════════════════════════════════════════════════

    effects:
      - type: "damage"
        damage_type: "magical"
        value: [200, 350, 600]
        scaling: "ap"
      - type: "stun"
        duration: [30, 45, 60]
      - type: "burn"
        value: [20, 35, 50]
        duration: 90
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from .scaling import get_star_value, calculate_scaled_value, StarValue

if TYPE_CHECKING:
    from ..units.unit import Unit
    from ..simulation.simulation import Simulation


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════

class EffectTarget(Enum):
    """Na kogo działa efekt."""
    ENEMY = auto()      # Wróg (cel ability)
    SELF = auto()       # Caster
    ALLY = auto()       # Sojusznik
    ALL_ENEMIES = auto()
    ALL_ALLIES = auto()
    AOE = auto()        # Obszar (używa AoE config)


class DamageType(Enum):
    """Typ obrażeń."""
    PHYSICAL = auto()
    MAGICAL = auto()
    TRUE = auto()


# ═══════════════════════════════════════════════════════════════════════════
# EFFECT RESULT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class EffectResult:
    """
    Wynik zastosowania efektu.
    
    Attributes:
        effect_type: Typ efektu
        success: Czy efekt zadziałał
        value: Wartość (damage dealt, HP healed, etc.)
        targets: Lista jednostek na które efekt zadziałał
        details: Dodatkowe szczegóły
    """
    effect_type: str
    success: bool = True
    value: float = 0.0
    targets: List[str] = field(default_factory=list)  # unit IDs
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "effect_type": self.effect_type,
            "success": self.success,
            "value": round(self.value, 1),
            "targets": self.targets,
            **self.details
        }


# ═══════════════════════════════════════════════════════════════════════════
# BASE EFFECT
# ═══════════════════════════════════════════════════════════════════════════

class Effect(ABC):
    """
    Bazowa klasa dla wszystkich efektów.
    """
    
    effect_type: str = "base"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    @abstractmethod
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        """
        Aplikuje efekt na cel.
        
        Args:
            caster: Jednostka castująca
            target: Cel efektu
            star_level: Poziom gwiazdek castera
            simulation: Referencja do symulacji
            
        Returns:
            EffectResult: Wynik efektu
        """
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Effect":
        """Tworzy efekt z YAML dict."""
        pass

    def _check_condition(self, caster: "Unit", target: "Unit", condition: str, simulation: "Simulation" = None) -> bool:
        """
        Sprawdza elastyczne warunki (zastępuje system z DamageEffect).
        Format: "scope_condition_value" lub "scope_condition"
        """
        if not condition:
            return True
            
        parts = condition.split("_")
        if len(parts) < 2:
            return False

        scope = parts[0]  # "target" | "caster" | "range"
        unit = target if scope == "target" else caster if scope == "caster" else None

        # Range-based conditions
        if scope == "range":
            distance = caster.position.distance(target.position)
            if len(parts) >= 3 and parts[1] == "above":
                threshold = int(parts[2])
                return distance > threshold
            elif len(parts) >= 3 and parts[1] == "below":
                threshold = int(parts[2])
                return distance < threshold
            return False

        if unit is None:
            return False

        cond = "_".join(parts[1:])

        # HP conditions
        if cond.startswith("below_hp_"):
            try:
                threshold = int(cond.split("_")[-1]) / 100.0
                return unit.stats.hp_percent() < threshold
            except:
                return False
        elif cond.startswith("above_hp_"):
            try:
                threshold = int(cond.split("_")[-1]) / 100.0
                return unit.stats.hp_percent() > threshold
            except:
                return False
                
        # Status conditions
        if cond == "has_chill":
            return getattr(unit, 'chill_remaining_ticks', 0) > 0
        elif cond == "hit_count_3":
            # Specyficzne dla Kennena/Ahri - może wymagać śledzenia w unit.state
            return getattr(unit, 'hit_by_ability_count', 0) >= 3

        return False


# ═══════════════════════════════════════════════════════════════════════════
# DAMAGE EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DamageEffect(Effect):
    """
    Efekt zadający obrażenia.
    
    Attributes:
        damage_type: physical/magical/true
        value: Wartość per star [1★, 2★, 3★]
        scaling: Typ skalowania (ad, ap, etc.)
        crit_condition: Warunek na crit (np. "target_has_chill")
    """
    effect_type: str = "damage"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    damage_type: DamageType = DamageType.MAGICAL
    value: StarValue = 100
    scaling: Optional[str] = None
    crit_condition: Optional[str] = None
    
    # New for 3-Cost
    falloff_percent: float = 0.0  # redukcja dmg za każdy kolejny cel
    execute_threshold: float = 0.0  # HP % poniżej którego zabija natychmiast
    target_count: int = 1  # liczba celów (np. Jinx rakiety)
    target_radius: int = 0  # jeśli > 0, szuka celów w radiusie głównego celu
    on_hit_ricochet: Optional[Dict] = None  # efekt odbicia (jak Lulu/LeBlanc)
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        # Oblicz damage podstawowy
        base_val = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, target
        )
        
        # Znajdź wszystkie cele
        targets = [target]
        if self.target_radius > 0:
            others = simulation.get_enemies_in_radius(target.position, self.target_radius, caster.team)
            for o in others:
                if o.id != target.id:
                    targets.append(o)
        elif self.target_count > 1:
            others = simulation.get_enemies(caster.team)
            others = sorted(others, key=lambda x: target.position.distance(x.position))
            for o in others:
                if o.id != target.id and len(targets) < self.target_count:
                    targets.append(o)

        results_value = 0
        hit_ids = []
        
        for i, t in enumerate(targets):
            # Aplikuj falloff
            current_dmg = base_val * (1.0 - (self.falloff_percent * i))
            if current_dmg <= 0:
                continue
                
            # Sprawdź execute threshold
            if self.execute_threshold > 0 and t.stats.hp_percent() < self.execute_threshold:
                actual = t.take_damage(t.stats.current_hp + 1000, 2, caster, simulation) # 2 = TRUE
                results_value += actual
            else:
                # Normalny damage
                is_crit = False
                if self.crit_condition:
                    is_crit = self._check_condition(caster, t, self.crit_condition, simulation)
                
                final_dmg = current_dmg * (caster.stats.get_crit_damage() if is_crit else 1.0)
                actual = t.take_damage(final_dmg, self.damage_type, caster, simulation)
                results_value += actual
            
            hit_ids.append(t.id)
            
            # On-hit effects (np. ricochet)
            if self.on_hit_ricochet:
                from .effect import create_effect
                eff_data = self.on_hit_ricochet.copy()
                eff_data.pop("on_hit_ricochet", None)
                eff = create_effect(eff_data.get("type", "damage"), eff_data)
                eff.apply(caster, t, star_level, simulation)

        return EffectResult(
            effect_type="damage",
            success=results_value > 0,
            value=results_value,
            targets=hit_ids,
            details={"crit": self.crit_condition is not None, "targets_hit": len(hit_ids)}
        )
    
    def _check_crit_condition(self, caster: "Unit", target: "Unit", condition: str, simulation: "Simulation") -> bool:
        """
        Sprawdza elastyczne warunki na crit.
        
        Format: "scope_condition_value" lub "scope_condition"
        Scopes: target, caster
        Conditions: has_chill, below_hp_X, above_hp_X, stunned, range_above_X, etc.
        
        Examples:
            - "target_has_chill" - target ma debuff chill
            - "target_below_hp_50" - target HP < 50%
            - "caster_above_hp_80" - caster HP > 80%
            - "range_above_4" - dystans > 4 hex
        """
        parts = condition.split("_")
        if len(parts) < 2:
            return False
        
        scope = parts[0]  # "target" | "caster" | "range"
        unit = target if scope == "target" else caster if scope == "caster" else None
        
        # Range-based conditions
        if scope == "range":
            distance = caster.position.distance(target.position)
            if len(parts) >= 3 and parts[1] == "above":
                threshold = int(parts[2])
                return distance > threshold
            elif len(parts) >= 3 and parts[1] == "below":
                threshold = int(parts[2])
                return distance < threshold
            return False
        
        if unit is None:
            return False
        
        cond = "_".join(parts[1:])  # Combine remaining parts
        
        # Debuff conditions
        if cond == "has_chill":
            return getattr(unit, 'chill_remaining_ticks', 0) > 0
        elif cond == "stunned":
            return unit.state.is_stunned() if hasattr(unit.state, 'is_stunned') else False
        elif cond == "silenced":
            return unit.is_silenced()
        elif cond == "slowed":
            return getattr(unit, 'slow_remaining_ticks', 0) > 0
        elif cond == "burned":
            return len(getattr(unit, 'burns', [])) > 0
        
        # HP conditions
        elif cond.startswith("below_hp_"):
            try:
                threshold = int(cond.split("_")[-1]) / 100.0
                return unit.stats.hp_percent() < threshold
            except:
                return False
        elif cond.startswith("above_hp_"):
            try:
                threshold = int(cond.split("_")[-1]) / 100.0
                return unit.stats.hp_percent() > threshold
            except:
                return False
        
        # Stat conditions
        elif cond.startswith("armor_above_"):
            try:
                threshold = int(cond.split("_")[-1])
                return unit.stats.get_armor() > threshold
            except:
                return False
        elif cond.startswith("mr_above_"):
            try:
                threshold = int(cond.split("_")[-1])
                return unit.stats.get_magic_resist() > threshold
            except:
                return False
        
        return False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DamageEffect":
        dt_str = data.get("damage_type", "magical").upper()
        return cls(
            damage_type=DamageType[dt_str],
            value=data.get("value", 100),
            scaling=data.get("scaling"),
            crit_condition=data.get("crit_condition"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# HEAL EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HealEffect(Effect):
    """
    Efekt leczący.
    
    Attributes:
        value: Wartość heala per star
        scaling: Typ skalowania
        target: "self" lub "ally"
    """
    effect_type: str = "heal"
    target_filter: EffectTarget = EffectTarget.ALLY
    
    value: StarValue = 100
    scaling: Optional[str] = None
    heal_target: str = "target"  # "self" | "target" | "ally"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        # Wybierz cel heala
        heal_target = caster if self.heal_target == "self" else target
        
        # Oblicz heal
        heal_amount = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, heal_target
        )
        
        # Sprawdź wound (redukcja leczenia)
        wound_reduction = getattr(heal_target, 'wound_percent', 0)
        if wound_reduction > 0:
            heal_amount *= (1 - wound_reduction / 100)
        
        # Aplikuj
        actual = heal_target.stats.heal(heal_amount)
        
        return EffectResult(
            effect_type="heal",
            success=True,
            value=actual,
            targets=[heal_target.id],
            details={"intended": round(heal_amount, 1)}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealEffect":
        return cls(
            value=data.get("value", 100),
            scaling=data.get("scaling"),
            heal_target=data.get("target", "target"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# SHIELD EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ShieldEffect(Effect):
    """
    Efekt dający tarczę (tymczasowe HP).
    
    Attributes:
        value: Wartość tarczy per star
        duration: Czas trwania w tickach
        scaling: Typ skalowania
    """
    effect_type: str = "shield"
    target_filter: EffectTarget = EffectTarget.ALLY
    
    value: StarValue = 100
    duration: StarValue = 90  # 3s @ 30 TPS
    scaling: Optional[str] = None
    shield_target: str = "target"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        shield_target = caster if self.shield_target == "self" else target
        
        shield_amount = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, shield_target
        )
        duration = int(get_star_value(self.duration, star_level))
        
        # Dodaj shield (implementacja w unit.py)
        shield_target.add_shield(shield_amount, duration)
        
        return EffectResult(
            effect_type="shield",
            success=True,
            value=shield_amount,
            targets=[shield_target.id],
            details={"duration_ticks": duration}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShieldEffect":
        return cls(
            value=data.get("value", 100),
            duration=data.get("duration", 90),
            scaling=data.get("scaling"),
            shield_target=data.get("target", "target"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# STUN EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class StunEffect(Effect):
    """
    Efekt ogłuszenia.
    
    Attributes:
        duration: Czas trwania w tickach per star
    """
    effect_type: str = "stun"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    duration: StarValue = 30  # 1s @ 30 TPS
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        duration = int(get_star_value(self.duration, star_level))
        
        target.state.apply_stun(duration)
        
        return EffectResult(
            effect_type="stun",
            success=True,
            value=duration,
            targets=[target.id],
            details={"duration_ticks": duration}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StunEffect":
        return cls(
            duration=data.get("duration", 30),
        )


# ═══════════════════════════════════════════════════════════════════════════
# BURN EFFECT (TRUE DAMAGE/S)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class BurnEffect(Effect):
    """
    Efekt podpalenia - TRUE damage per second.
    
    Attributes:
        value: Damage per second per star
        duration: Czas trwania w tickach
        scaling: Opcjonalne skalowanie
    """
    effect_type: str = "burn"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: StarValue = 20  # true damage per second
    duration: StarValue = 90  # 3s
    scaling: Optional[str] = None
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        dps = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, target
        )
        duration = int(get_star_value(self.duration, star_level))
        
        # Dodaj burn debuff (implementacja w unit.py)
        target.add_burn(dps, duration, caster.id)
        
        return EffectResult(
            effect_type="burn",
            success=True,
            value=dps,
            targets=[target.id],
            details={
                "dps": round(dps, 1),
                "duration_ticks": duration,
                "total_damage": round(dps * duration / 30, 1),  # 30 TPS
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BurnEffect":
        return cls(
            value=data.get("value", 20),
            duration=data.get("duration", 90),
            scaling=data.get("scaling"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# WOUND EFFECT (HEALING REDUCTION)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class WoundEffect(Effect):
    """
    Efekt rany - redukcja leczenia.
    
    Attributes:
        value: % redukcji leczenia per star
        duration: Czas trwania w tickach
    """
    effect_type: str = "wound"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: StarValue = 50  # 50% redukcji
    duration: StarValue = 150  # 5s
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        reduction = get_star_value(self.value, star_level)
        duration = int(get_star_value(self.duration, star_level))
        
        # Dodaj wound debuff
        target.add_wound(reduction, duration)
        
        return EffectResult(
            effect_type="wound",
            success=True,
            value=reduction,
            targets=[target.id],
            details={
                "heal_reduction_percent": reduction,
                "duration_ticks": duration,
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WoundEffect":
        return cls(
            value=data.get("value", 50),
            duration=data.get("duration", 150),
        )


# ═══════════════════════════════════════════════════════════════════════════
# DOT EFFECT (DAMAGE OVER TIME)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DoTEffect(Effect):
    """
    Damage Over Time (nie TRUE, używa damage_type).
    
    Attributes:
        damage_type: physical/magical
        value: Damage per tick per star
        duration: Czas trwania w tickach
        interval: Co ile ticków damage (default 30 = 1s)
    """
    effect_type: str = "dot"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    damage_type: DamageType = DamageType.MAGICAL
    value: StarValue = 30
    duration: StarValue = 90
    interval: int = 30  # damage co sekundę
    scaling: Optional[str] = None
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        dps = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, target
        )
        duration = int(get_star_value(self.duration, star_level))
        
        # Dodaj DoT (implementacja w unit.py)
        target.add_dot(
            damage=dps,
            damage_type=self.damage_type,
            duration=duration,
            interval=self.interval,
            source_id=caster.id,
        )
        
        return EffectResult(
            effect_type="dot",
            success=True,
            value=dps,
            targets=[target.id],
            details={
                "damage_type": self.damage_type.name,
                "damage_per_tick": round(dps, 1),
                "duration_ticks": duration,
                "interval": self.interval,
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DoTEffect":
        dt_str = data.get("damage_type", "magical").upper()
        return cls(
            damage_type=DamageType[dt_str],
            value=data.get("value", 30),
            duration=data.get("duration", 90),
            interval=data.get("interval", 30),
            scaling=data.get("scaling"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# SLOW EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SlowEffect(Effect):
    """
    Efekt spowolnienia Attack Speed.
    
    Attributes:
        value: % spowolnienia per star
        duration: Czas trwania
    """
    effect_type: str = "slow"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: StarValue = 30  # 30% slow
    duration: StarValue = 60  # 2s
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        slow_percent = get_star_value(self.value, star_level)
        duration = int(get_star_value(self.duration, star_level))
        
        target.add_slow(slow_percent, duration)
        
        return EffectResult(
            effect_type="slow",
            success=True,
            value=slow_percent,
            targets=[target.id],
            details={
                "slow_percent": slow_percent,
                "duration_ticks": duration,
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlowEffect":
        return cls(
            value=data.get("value", 30),
            duration=data.get("duration", 60),
        )


# ═══════════════════════════════════════════════════════════════════════════
# SUNDER EFFECT (ARMOR REDUCTION)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SunderEffect(Effect):
    """
    Redukcja Armor celu.
    """
    effect_type: str = "sunder"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: StarValue = 20  # redukcja armor
    duration: StarValue = 120
    is_percent: bool = False  # flat vs percent
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        reduction = get_star_value(self.value, star_level)
        duration = int(get_star_value(self.duration, star_level))
        
        target.add_armor_reduction(reduction, duration, self.is_percent)
        
        return EffectResult(
            effect_type="sunder",
            success=True,
            value=reduction,
            targets=[target.id],
            details={"duration_ticks": duration, "is_percent": self.is_percent}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SunderEffect":
        return cls(
            value=data.get("value", 20),
            duration=data.get("duration", 120),
            is_percent=data.get("is_percent", False),
        )


# ═══════════════════════════════════════════════════════════════════════════
# SHRED EFFECT (MR REDUCTION)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ShredEffect(Effect):
    """
    Redukcja Magic Resist celu.
    """
    effect_type: str = "shred"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: StarValue = 20
    duration: StarValue = 120
    is_percent: bool = False
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        reduction = get_star_value(self.value, star_level)
        duration = int(get_star_value(self.duration, star_level))
        
        target.add_mr_reduction(reduction, duration, self.is_percent)
        
        return EffectResult(
            effect_type="shred",
            success=True,
            value=reduction,
            targets=[target.id],
            details={"duration_ticks": duration}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShredEffect":
        return cls(
            value=data.get("value", 20),
            duration=data.get("duration", 120),
            is_percent=data.get("is_percent", False),
        )


# ═══════════════════════════════════════════════════════════════════════════
# HYBRID DAMAGE EFFECT (AD + AP scaling combined)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HybridDamageEffect(Effect):
    """
    Zadaje mieszane obrażenia (AD + AP).
    """
    effect_type: str = "hybrid_damage"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    ad_value: StarValue = 0
    ap_value: StarValue = 0
    ad_is_percent: bool = False  # jeśli true, ad_value to % AD
    damage_type: DamageType = DamageType.PHYSICAL
    
    # 3-Cost extensions
    target_count: int = 1
    target_radius: int = 0
    falloff_percent: float = 0.0
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        # Znajdź wszystkie cele
        targets = [target]
        if self.target_radius > 0:
            others = simulation.get_enemies_in_radius(target.position, self.target_radius, caster.team)
            for o in others:
                if o.id != target.id:
                    targets.append(o)
        elif self.target_count > 1:
            others = simulation.get_enemies(caster.team)
            others = sorted(others, key=lambda x: target.position.distance(x.position))
            for o in others:
                if o.id != target.id and len(targets) < self.target_count:
                    targets.append(o)

        total_actual = 0.0
        hit_ids = []
        
        for i, t in enumerate(targets):
            # Oblicz damage AD
            ad_val = get_star_value(self.ad_value, star_level)
            ad_dmg = ad_val * caster.stats.get_attack_damage() if self.ad_is_percent else ad_val
            
            # Oblicz damage AP
            ap_val = get_star_value(self.ap_value, star_level)
            ap_dmg = calculate_scaled_value(ap_val, "ap", star_level, caster, t)
            
            base_total = ad_dmg + ap_dmg
            current_dmg = base_total * (1.0 - (self.falloff_percent * i))
            
            if current_dmg <= 0:
                continue
                
            actual = t.take_damage(current_dmg, self.damage_type, caster, simulation)
            total_actual += actual
            hit_ids.append(t.id)
            
        return EffectResult(
            effect_type="hybrid_damage",
            success=total_actual > 0,
            value=total_actual,
            targets=hit_ids,
            details={"ad": ad_dmg, "ap": ap_dmg, "targets_hit": len(hit_ids)}
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HybridDamageEffect":
        dtype = data.get("damage_type", "physical")
        return cls(
            ad_value=data.get("ad_value", 0),
            ap_value=data.get("ap_value", 0),
            ad_is_percent=data.get("ad_is_percent", False),
            damage_type=DamageType[dtype.upper()] if isinstance(dtype, str) else dtype,
            target_count=data.get("target_count", 1),
            target_radius=data.get("target_radius", 0),
            falloff_percent=data.get("falloff_percent", 0.0)
        )


# ═══════════════════════════════════════════════════════════════════════════
# EXECUTE EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ExecuteEffect(Effect):
    """
    Zabija cel poniżej progu % HP.
    """
    effect_type: str = "execute"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    threshold: StarValue = 15  # % HP
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        threshold = get_star_value(self.threshold, star_level)
        hp_percent = target.stats.hp_percent() * 100
        
        executed = hp_percent <= threshold
        if executed:
            target.die()
        
        return EffectResult(
            effect_type="execute",
            success=executed,
            value=threshold,
            targets=[target.id] if executed else [],
            details={
                "threshold_percent": threshold,
                "target_hp_percent": round(hp_percent, 1),
                "executed": executed,
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecuteEffect":
        return cls(
            threshold=data.get("threshold", 15),
        )


# ═══════════════════════════════════════════════════════════════════════════
# BUFF EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class BuffEffect(Effect):
    """
    Tymczasowy bonus do statystyki.
    """
    effect_type: str = "buff"
    target_filter: EffectTarget = EffectTarget.ALLY
    
    stat: str = "attack_damage"  # która statystyka
    value: StarValue = 20
    duration: StarValue = 120
    is_percent: bool = False
    buff_target: str = "self"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        buff_target = caster if self.buff_target == "self" else target
        
        buff_value = get_star_value(self.value, star_level)
        duration = int(get_star_value(self.duration, star_level))
        
        # Aplikuj buff
        if self.is_percent:
            buff_target.stats.add_percent_modifier(self.stat, buff_value / 100)
        else:
            buff_target.stats.add_flat_modifier(self.stat, buff_value)
        
        # TODO: Track buff dla remove po duration
        
        return EffectResult(
            effect_type="buff",
            success=True,
            value=buff_value,
            targets=[buff_target.id],
            details={
                "stat": self.stat,
                "is_percent": self.is_percent,
                "duration_ticks": duration,
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BuffEffect":
        return cls(
            stat=data.get("stat", "attack_damage"),
            value=data.get("value", 20),
            duration=data.get("duration", 120),
            is_percent=data.get("is_percent", False),
            buff_target=data.get("target", "self"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# MANA GRANT EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ManaGrantEffect(Effect):
    """
    Daje manę celowi.
    """
    effect_type: str = "mana_grant"
    target_filter: EffectTarget = EffectTarget.ALLY
    
    value: StarValue = 20
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        mana_amount = get_star_value(self.value, star_level)
        
        target.stats.add_mana(mana_amount)
        
        return EffectResult(
            effect_type="mana_grant",
            success=True,
            value=mana_amount,
            targets=[target.id],
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManaGrantEffect":
        return cls(
            value=data.get("value", 20),
        )


# ═══════════════════════════════════════════════════════════════════════════
# SILENCE EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SilenceEffect(Effect):
    """
    Blokuje castowanie umiejętności.
    """
    effect_type: str = "silence"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    duration: StarValue = 60  # 2s
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        duration = int(get_star_value(self.duration, star_level))
        
        target.add_silence(duration)
        
        return EffectResult(
            effect_type="silence",
            success=True,
            value=duration,
            targets=[target.id],
            details={"duration_ticks": duration}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SilenceEffect":
        return cls(duration=data.get("duration", 60))


# ═══════════════════════════════════════════════════════════════════════════
# DISARM EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DisarmEffect(Effect):
    """
    Blokuje auto-ataki.
    """
    effect_type: str = "disarm"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    duration: StarValue = 60
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        duration = int(get_star_value(self.duration, star_level))
        
        target.add_disarm(duration)
        
        return EffectResult(
            effect_type="disarm",
            success=True,
            value=duration,
            targets=[target.id],
            details={"duration_ticks": duration}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DisarmEffect":
        return cls(duration=data.get("duration", 60))


# ═══════════════════════════════════════════════════════════════════════════
# KNOCKBACK EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class KnockbackEffect(Effect):
    """
    Odpycha cel o X hexów od castera.
    Opcjonalnie: tylko jeśli warunek (np. range_below_2) jest spełniony.
    """
    effect_type: str = "knockback"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    distance: StarValue = 2
    stun_duration: StarValue = 15  # krótki stun po knockback
    condition: str = ""  # np. "range_below_2" - tylko jeśli w zasięgu 2 hex
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        distance = int(get_star_value(self.distance, star_level))
        stun_dur = int(get_star_value(self.stun_duration, star_level))
        
        # Check condition if specified
        if self.condition:
            condition_met = self._check_condition(caster, target, self.condition)
            if not condition_met:
                return EffectResult(
                    effect_type="knockback",
                    success=False,
                    value=0,
                    targets=[target.id],
                    details={"reason": "condition_not_met", "condition": self.condition}
                )
        
        # Oblicz kierunek od castera
        dir_q = target.position.q - caster.position.q
        dir_r = target.position.r - caster.position.r
        
        # Normalizuj i przemnóż przez distance
        length = max(1, abs(dir_q) + abs(dir_r))
        new_q = target.position.q + int((dir_q / length) * distance)
        new_r = target.position.r + int((dir_r / length) * distance)
        
        # Sprawdź czy nowa pozycja jest ważna
        from ..core.hex_coord import HexCoord
        new_pos = HexCoord(new_q, new_r)
        
        moved = False
        if simulation.grid.is_valid(new_pos) and simulation.grid.is_walkable(new_pos):
            simulation.grid.move_unit(target, new_pos)
            target.position = new_pos
            moved = True
        
        # Aplikuj mini-stun
        if stun_dur > 0:
            target.state.apply_stun(stun_dur)
        
        return EffectResult(
            effect_type="knockback",
            success=moved,
            value=distance,
            targets=[target.id],
            details={
                "distance": distance,
                "moved": moved,
                "stun_duration": stun_dur,
            }
        )
    
    def _check_condition(self, caster: "Unit", target: "Unit", condition: str) -> bool:
        """Check knockback condition (range-based)."""
        parts = condition.split("_")
        if len(parts) >= 3 and parts[0] == "range":
            try:
                threshold = int(parts[2])
                actual_distance = caster.position.distance(target.position)
                if parts[1] == "below":
                    return actual_distance < threshold
                elif parts[1] == "above":
                    return actual_distance > threshold
            except:
                pass
        return True  # Default: condition met
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnockbackEffect":
        return cls(
            distance=data.get("distance", 2),
            stun_duration=data.get("stun_duration", 15),
            condition=data.get("condition", ""),
        )


# ═══════════════════════════════════════════════════════════════════════════
# PULL EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PullEffect(Effect):
    """
    Przyciąga cel o X hexów w kierunku castera.
    """
    effect_type: str = "pull"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    distance: StarValue = 2
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        distance = int(get_star_value(self.distance, star_level))
        
        # Kierunek DO castera
        dir_q = caster.position.q - target.position.q
        dir_r = caster.position.r - target.position.r
        
        length = max(1, abs(dir_q) + abs(dir_r))
        new_q = target.position.q + int((dir_q / length) * distance)
        new_r = target.position.r + int((dir_r / length) * distance)
        
        from ..core.hex_coord import HexCoord
        new_pos = HexCoord(new_q, new_r)
        
        moved = False
        if simulation.grid.is_valid(new_pos) and simulation.grid.is_walkable(new_pos):
            simulation.grid.move_unit(target, new_pos)
            target.position = new_pos
            moved = True
        
        return EffectResult(
            effect_type="pull",
            success=moved,
            value=distance,
            targets=[target.id],
            details={"distance": distance, "moved": moved}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PullEffect":
        return cls(distance=data.get("distance", 2))


# ═══════════════════════════════════════════════════════════════════════════
# DASH EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DashEffect(Effect):
    """
    Dash castera w kierunku celu lub od celu.
    
    Attributes:
        distance: Dystans w hexach
        direction: "to_target" | "away_from_target"
        target_type: "current" | "farthest" | "closest" | "lowest_hp"
    """
    effect_type: str = "dash"
    target_filter: EffectTarget = EffectTarget.SELF
    
    distance: StarValue = 2
    direction: str = "to_target"  # "to_target" | "away_from_target"
    target_type: str = "current"  # NEW: "current" | "farthest" | "closest" | "lowest_hp"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        distance = int(get_star_value(self.distance, star_level))
        
        # Select actual target based on target_type
        actual_target = self._select_target(caster, target, simulation)
        if actual_target is None:
            return EffectResult(
                effect_type="dash",
                success=False,
                value=0,
                targets=[],
                details={"reason": "no_valid_target"}
            )
        
        from ..core.hex_coord import HexCoord
        
        if self.direction == "to_target":
            # Calculate direction towards target
            dir_q = actual_target.position.q - caster.position.q
            dir_r = actual_target.position.r - caster.position.r
            
            length = max(1, abs(dir_q) + abs(dir_r))
            norm_q = dir_q / length
            norm_r = dir_r / length
            
            # Find best landing position (adjacent to target, not ON target)
            best_pos = None
            best_dist = float('inf')
            
            # Try positions from far to close, find closest walkable to target
            for d in range(distance, 0, -1):
                new_q = caster.position.q + int(norm_q * d)
                new_r = caster.position.r + int(norm_r * d)
                new_pos = HexCoord(new_q, new_r)
                
                # Check if valid and walkable (not occupied)
                if simulation.grid.is_valid(new_pos) and simulation.grid.is_walkable(new_pos):
                    dist_to_target = new_pos.distance(actual_target.position)
                    # Must be at least 1 hex away from target (adjacent, not on)
                    if dist_to_target >= 1 and dist_to_target < best_dist:
                        best_pos = new_pos
                        best_dist = dist_to_target
            
            # If no position found in direct path, try neighbors of target
            if best_pos is None:
                for neighbor in actual_target.position.neighbors():
                    if simulation.grid.is_valid(neighbor) and simulation.grid.is_walkable(neighbor):
                        best_pos = neighbor
                        break
            
            new_pos = best_pos
        else:  # away_from_target
            dir_q = caster.position.q - actual_target.position.q
            dir_r = caster.position.r - actual_target.position.r
            length = max(1, abs(dir_q) + abs(dir_r))
            new_q = caster.position.q + int((dir_q / length) * distance)
            new_r = caster.position.r + int((dir_r / length) * distance)
            new_pos = HexCoord(new_q, new_r)
        
        moved = False
        if new_pos and simulation.grid.is_valid(new_pos) and simulation.grid.is_walkable(new_pos):
            simulation.grid.move_unit(caster, new_pos)
            caster.position = new_pos
            moved = True
            # Set target for immediate attack
            caster.set_target(actual_target)
        
        return EffectResult(
            effect_type="dash",
            success=moved,
            value=distance,
            targets=[caster.id],
            details={
                "distance": distance,
                "direction": self.direction,
                "target_type": self.target_type,
                "moved": moved,
                "target_id": actual_target.id if actual_target else None,
            }
        )
    
    def _select_target(self, caster: "Unit", default_target: "Unit", simulation: "Simulation") -> Optional["Unit"]:
        """Select target based on target_type."""
        if self.target_type == "current":
            return default_target
        
        # Get enemy units
        enemies = [u for u in simulation.units if u.is_alive() and u.team != caster.team]
        if not enemies:
            return None
        
        if self.target_type == "farthest":
            return max(enemies, key=lambda u: caster.position.distance(u.position))
        elif self.target_type == "closest":
            return min(enemies, key=lambda u: caster.position.distance(u.position))
        elif self.target_type == "lowest_hp":
            return min(enemies, key=lambda u: u.stats.current_hp)
        elif self.target_type == "lowest_hp_percent":
            return min(enemies, key=lambda u: u.stats.hp_percent())
        
        return default_target
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DashEffect":
        return cls(
            distance=data.get("distance", 2),
            direction=data.get("direction", "to_target"),
            target_type=data.get("target_type", "current"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# CLEANSE EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CleanseEffect(Effect):
    """
    Usuwa wszystkie negatywne efekty z celu.
    """
    effect_type: str = "cleanse"
    target_filter: EffectTarget = EffectTarget.ALLY
    
    cleanse_target: str = "target"  # "self" | "target"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        cleanse_target = caster if self.cleanse_target == "self" else target
        
        # Clear all debuffs
        removed = 0
        
        if cleanse_target.wound_percent > 0:
            cleanse_target.wound_percent = 0
            cleanse_target.wound_remaining_ticks = 0
            removed += 1
        
        if cleanse_target.slow_percent > 0:
            cleanse_target.slow_percent = 0
            cleanse_target.slow_remaining_ticks = 0
            removed += 1
        
        if cleanse_target.armor_reduction > 0:
            cleanse_target.armor_reduction = 0
            cleanse_target.armor_reduction_ticks = 0
            removed += 1
        
        if cleanse_target.mr_reduction > 0:
            cleanse_target.mr_reduction = 0
            cleanse_target.mr_reduction_ticks = 0
            removed += 1
        
        if len(cleanse_target.burns) > 0:
            removed += len(cleanse_target.burns)
            cleanse_target.burns.clear()
        
        if len(cleanse_target.dots) > 0:
            removed += len(cleanse_target.dots)
            cleanse_target.dots.clear()
        
        # Clear silence/disarm if present
        if hasattr(cleanse_target, 'silence_remaining_ticks'):
            if cleanse_target.silence_remaining_ticks > 0:
                cleanse_target.silence_remaining_ticks = 0
                removed += 1
        
        if hasattr(cleanse_target, 'disarm_remaining_ticks'):
            if cleanse_target.disarm_remaining_ticks > 0:
                cleanse_target.disarm_remaining_ticks = 0
                removed += 1
        
        return EffectResult(
            effect_type="cleanse",
            success=removed > 0,
            value=removed,
            targets=[cleanse_target.id],
            details={"debuffs_removed": removed}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CleanseEffect":
        return cls(cleanse_target=data.get("target", "target"))


# ═══════════════════════════════════════════════════════════════════════════
# CHILL EFFECT (ATTACK SPEED REDUCTION)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ChillEffect(Effect):
    """
    Chill - redukcja Attack Speed (jak Slow ale nazwa TFT).
    
    Attributes:
        value: % redukcji AS per star (0.20 = 20%)
        duration: Czas trwania w tickach
    """
    effect_type: str = "chill"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: StarValue = 0.20  # 20% AS reduction
    duration: StarValue = 60  # 2s
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        slow_percent = get_star_value(self.value, star_level)
        duration = int(get_star_value(self.duration, star_level))
        
        target.add_slow(slow_percent, duration)
        
        return EffectResult(
            effect_type="chill",
            success=True,
            value=slow_percent,
            targets=[target.id],
            details={"as_reduction": slow_percent, "duration_ticks": duration}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChillEffect":
        return cls(
            value=data.get("value", 0.20),
            duration=data.get("duration", 60),
        )


# ═══════════════════════════════════════════════════════════════════════════
# SPLASH DAMAGE EFFECT (AOE REDUCTION)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SplashDamageEffect(Effect):
    """
    Damage z splash na adjacent units (jak "50% to adjacent").
    
    Attributes:
        value: Główne obrażenia per star
        splash_percent: % damage dla adjacent (0.5 = 50%)
        damage_type: Typ obrażeń
        scaling: Skalowanie (ap, ad)
    """
    effect_type: str = "splash_damage"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: StarValue = 100
    splash_percent: float = 0.5
    damage_type: DamageType = DamageType.MAGICAL
    scaling: Optional[str] = "ap"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        from ..combat.damage import calculate_damage
        
        main_damage = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, target
        )
        
        affected = [target.id]
        total_damage = 0.0
        
        # Main target damage
        result = calculate_damage(
            caster, target, main_damage, self.damage_type,
            simulation.rng, can_crit=False, can_dodge=False, is_ability=True
        )
        target.stats.take_damage(result.final_damage)
        total_damage += result.final_damage
        
        # Splash to adjacent
        splash_damage = main_damage * self.splash_percent
        for unit in simulation.units:
            if not unit.is_alive() or unit.team == caster.team:
                continue
            if unit.id == target.id:
                continue
            # Check if adjacent (distance == 1)
            if target.position.distance(unit.position) == 1:
                result = calculate_damage(
                    caster, unit, splash_damage, self.damage_type,
                    simulation.rng, can_crit=False, can_dodge=False, is_ability=True
                )
                unit.stats.take_damage(result.final_damage)
                total_damage += result.final_damage
                affected.append(unit.id)
        
        return EffectResult(
            effect_type="splash_damage",
            success=True,
            value=total_damage,
            targets=affected,
            details={"main_damage": main_damage, "splash_percent": self.splash_percent}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SplashDamageEffect":
        dtype = data.get("damage_type", "magical")
        return cls(
            value=data.get("value", 100),
            splash_percent=data.get("splash_percent", 0.5),
            damage_type=DamageType[dtype.upper()] if isinstance(dtype, str) else dtype,
            scaling=data.get("scaling", "ap"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# RICOCHET DAMAGE (BOUNCES ON KILL)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class RicochetDamageEffect(Effect):
    """
    Damage który odbija się do następnego celu jeśli zabije pierwszy.
    
    Attributes:
        value: Obrażenia per star
        damage_type: Typ
        max_bounces: Max odbić
        scaling: Skalowanie
    """
    effect_type: str = "ricochet"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: StarValue = 500
    damage_type: DamageType = DamageType.PHYSICAL
    max_bounces: int = 3
    scaling: Optional[str] = "ad"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        from ..combat.damage import calculate_damage
        
        damage = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, target
        )
        
        affected = []
        current_target = target
        remaining_damage = damage
        bounces = 0
        
        while current_target and bounces <= self.max_bounces and remaining_damage > 0:
            hp_before = current_target.stats.current_hp
            
            result = calculate_damage(
                caster, current_target, remaining_damage, self.damage_type,
                simulation.rng, can_crit=True, can_dodge=False, is_ability=True
            )
            actual_damage = current_target.stats.take_damage(result.final_damage)
            affected.append(current_target.id)
            
            if not current_target.is_alive():
                # Bounce with excess damage
                excess = remaining_damage - hp_before
                remaining_damage = max(0, excess)
                bounces += 1
                
                # Find next target (farthest enemy)
                enemies = [u for u in simulation.units 
                          if u.is_alive() and u.team != caster.team and u.id not in affected]
                if enemies:
                    current_target = max(enemies, key=lambda u: caster.position.distance(u.position))
                else:
                    current_target = None
            else:
                break
        
        return EffectResult(
            effect_type="ricochet",
            success=len(affected) > 0,
            value=damage,
            targets=affected,
            details={"bounces": bounces}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RicochetDamageEffect":
        dtype = data.get("damage_type", "physical")
        return cls(
            value=data.get("value", 500),
            damage_type=DamageType[dtype.upper()] if isinstance(dtype, str) else dtype,
            max_bounces=data.get("max_bounces", 3),
            scaling=data.get("scaling", "ad"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# MULTI HIT EFFECT (SLASH X TIMES)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MultiHitEffect(Effect):
    """
    Wielokrotne uderzenia (slash X razy).
    
    Attributes:
        value: Obrażenia per hit per star
        hits: Liczba uderzeń
        damage_type: Typ
        scaling: Skalowanie
    """
    effect_type: str = "multi_hit"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: StarValue = 50
    hits: StarValue = 4
    damage_type: DamageType = DamageType.PHYSICAL
    scaling: Optional[str] = "ad"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        from ..combat.damage import calculate_damage
        
        damage_per_hit = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, target
        )
        num_hits = int(get_star_value(self.hits, star_level))
        
        total_damage = 0.0
        hits_landed = 0
        
        for _ in range(num_hits):
            if not target.is_alive():
                break
            result = calculate_damage(
                caster, target, damage_per_hit, self.damage_type,
                simulation.rng, can_crit=True, can_dodge=True, is_ability=True
            )
            target.stats.take_damage(result.final_damage)
            total_damage += result.final_damage
            hits_landed += 1
        
        return EffectResult(
            effect_type="multi_hit",
            success=hits_landed > 0,
            value=total_damage,
            targets=[target.id],
            details={"hits": hits_landed, "damage_per_hit": damage_per_hit}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MultiHitEffect":
        dtype = data.get("damage_type", "physical")
        return cls(
            value=data.get("value", 50),
            hits=data.get("hits", 4),
            damage_type=DamageType[dtype.upper()] if isinstance(dtype, str) else dtype,
            scaling=data.get("scaling", "ad"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# BUFF TEAM EFFECT (GRANT STAT TO ALL ALLIES)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class BuffTeamEffect(Effect):
    """
    Daje buff całemu teamowi.
    
    Attributes:
        stat: Statystyka do buffowania
        value: Wartość per star
        duration: Czas trwania
        is_percent: Czy wartość jest procentowa
    """
    effect_type: str = "buff_team"
    target_filter: EffectTarget = EffectTarget.ALL_ALLIES
    
    stat: str = "attack_speed"
    value: StarValue = 0.20
    duration: StarValue = 120  # 4s
    is_percent: bool = True
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",  # ignored, affects all allies
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        buff_value = get_star_value(self.value, star_level)
        duration = int(get_star_value(self.duration, star_level))
        
        affected = []
        for unit in simulation.units:
            if unit.is_alive() and unit.team == caster.team:
                # Apply temporary stat buff
                if self.is_percent:
                    unit.stats.add_percent_modifier(self.stat, buff_value)
                else:
                    unit.stats.add_flat_modifier(self.stat, buff_value)
                affected.append(unit.id)
        
        return EffectResult(
            effect_type="buff_team",
            success=len(affected) > 0,
            value=buff_value,
            targets=affected,
            details={"stat": self.stat, "duration": duration, "is_percent": self.is_percent}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BuffTeamEffect":
        return cls(
            stat=data.get("stat", "attack_speed"),
            value=data.get("value", 0.20),
            duration=data.get("duration", 120),
            is_percent=data.get("is_percent", True),
        )


# ═══════════════════════════════════════════════════════════════════════════
# SHIELD SELF EFFECT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ShieldSelfEffect(Effect):
    """
    Daje tarczę casterowi.
    
    Attributes:
        value: Wartość tarczy per star
        duration: Czas trwania
        scaling: Skalowanie (ap)
    """
    effect_type: str = "shield_self"
    target_filter: EffectTarget = EffectTarget.SELF
    
    value: StarValue = 300
    duration: StarValue = 120  # 4s
    scaling: Optional[str] = "ap"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",  # ignored
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        shield_amount = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, caster
        )
        duration = int(get_star_value(self.duration, star_level))
        
        caster.add_shield(shield_amount, duration)
        
        return EffectResult(
            effect_type="shield_self",
            success=True,
            value=shield_amount,
            targets=[caster.id],
            details={"duration_ticks": duration}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShieldSelfEffect":
        return cls(
            value=data.get("value", 300),
            duration=data.get("duration", 120),
            scaling=data.get("scaling", "ap"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# DASH THROUGH EFFECT (DASH + DAMAGE ALL IN PATH)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DashThroughEffect(Effect):
    """
    Dash do celu, zadając obrażenia wszystkim po drodze.
    
    Attributes:
        value: Obrażenia per star
        damage_type: Typ obrażeń
        scaling: Skalowanie
    """
    effect_type: str = "dash_through"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: StarValue = 80
    damage_type: DamageType = DamageType.PHYSICAL
    scaling: Optional[str] = "ad"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        from ..combat.damage import calculate_damage
        
        damage = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, target
        )
        
        affected = []
        
        # Get all enemies in line between caster and target
        for unit in simulation.units:
            if not unit.is_alive() or unit.team == caster.team:
                continue
            
            # Simple check: unit is between caster and target
            dist_to_caster = caster.position.distance(unit.position)
            dist_to_target = caster.position.distance(target.position)
            dist_unit_to_target = unit.position.distance(target.position)
            
            # If unit is roughly on the path
            if dist_to_caster + dist_unit_to_target <= dist_to_target + 1:
                result = calculate_damage(
                    caster, unit, damage, self.damage_type,
                    simulation.rng, can_crit=True, can_dodge=True, is_ability=True
                )
                unit.stats.take_damage(result.final_damage)
                affected.append(unit.id)
        
        # Move caster to target position (if possible)
        # Note: actual movement would need grid update
        
        return EffectResult(
            effect_type="dash_through",
            success=len(affected) > 0,
            value=damage,
            targets=affected,
            details={"enemies_hit": len(affected)}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DashThroughEffect":
        dtype = data.get("damage_type", "physical")
        return cls(
            value=data.get("value", 80),
            damage_type=DamageType[dtype.upper()] if isinstance(dtype, str) else dtype,
            scaling=data.get("scaling", "ad"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# PERCENT HP DAMAGE
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PercentHPDamageEffect(Effect):
    """
    Obrażenia jako % Max HP celu.
    
    Attributes:
        value: % HP jako obrażenia per star (0.08 = 8%)
        damage_type: Typ obrażeń
        is_current: True = current HP, False = max HP
    """
    effect_type: str = "percent_hp_damage"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: StarValue = 0.08
    damage_type: DamageType = DamageType.MAGICAL
    is_current: bool = False  # max HP by default
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        from ..combat.damage import calculate_damage
        
        percent = get_star_value(self.value, star_level)
        
        if self.is_current:
            base_damage = target.stats.current_hp * percent
        else:
            base_damage = target.stats.get_max_hp() * percent
        
        result = calculate_damage(
            caster, target, base_damage, self.damage_type,
            simulation.rng, can_crit=False, can_dodge=False, is_ability=True
        )
        target.stats.take_damage(result.final_damage)
        
        return EffectResult(
            effect_type="percent_hp_damage",
            success=True,
            value=result.final_damage,
            targets=[target.id],
            details={"percent": percent, "is_current": self.is_current}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PercentHPDamageEffect":
        dtype = data.get("damage_type", "magical")
        return cls(
            value=data.get("value", 0.08),
            damage_type=DamageType[dtype.upper()] if isinstance(dtype, str) else dtype,
            is_current=data.get("is_current", False),
        )


# ═══════════════════════════════════════════════════════════════════════════
# REPLACE ATTACKS EFFECT (Jhin, Aphelios - przekształcenie ataków)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ReplaceAttacksEffect(Effect):
    """
    Zastępuje auto-ataki castera wzmocnionymi atakami na X ataków lub sekundy.
    
    Attributes:
        count: Liczba ataków do zastąpienia (lub None dla duration-based)
        duration: Czas trwania w tickach (lub None dla count-based)
        damage_type: Typ obrażeń wzmocnionych ataków
        ad_value: AD scaling per attack
        ap_value: AP scaling per attack (hybrid)
        bonus_multiplier: Mnożnik dla specjalnego ataku (np. 4th shot)
        bonus_on_attack: Który atak jest wzmocniony (np. 4 = czwarty)
        infinite_range: Czy ataki mają nieskończony zasięg
    """
    effect_type: str = "replace_attacks"
    target_filter: EffectTarget = EffectTarget.SELF
    
    count: Optional[int] = 4
    duration: Optional[StarValue] = None  # Alternative to count
    damage_type: DamageType = DamageType.PHYSICAL
    ad_value: StarValue = 125
    ap_value: StarValue = 15
    bonus_multiplier: float = 1.0  # For 4th shot bonus
    bonus_on_attack: Optional[int] = None  # Which attack gets bonus (e.g. 4)
    infinite_range: bool = False
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        count = self.count or 4
        duration = int(get_star_value(self.duration, star_level)) if self.duration else None
        
        ad_dmg = get_star_value(self.ad_value, star_level)
        ap_dmg = get_star_value(self.ap_value, star_level)
        
        # Calculate total empowered attack damage (AD scaling + AP scaling)
        ad_ratio = caster.stats.get_attack_damage() / 100.0
        ap_ratio = caster.stats.get_ability_power() / 100.0
        total_damage = (ad_dmg * ad_ratio) + (ap_dmg * ap_ratio)
        
        # Store replacement attack data on unit
        caster.empowered_attacks = {
            "remaining": count,
            "total": count,  # For tracking which attack number
            "damage": total_damage,  # Pre-calculated base damage
            "duration_ticks": duration,
            "damage_type": self.damage_type.name.lower(),
            "ad_value": ad_dmg,
            "ap_value": ap_dmg,
            "bonus_multiplier": self.bonus_multiplier,
            "bonus_on_attack": self.bonus_on_attack,
            "attack_count": 0,
            "infinite_range": self.infinite_range,
        }
        
        return EffectResult(
            effect_type="replace_attacks",
            success=True,
            value=count,
            targets=[caster.id],
            details={
                "count": count,
                "damage": round(total_damage, 1),
                "ad_value": ad_dmg,
                "ap_value": ap_dmg,
                "bonus_on": self.bonus_on_attack,
                "bonus_mult": self.bonus_multiplier,
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReplaceAttacksEffect":
        dtype = data.get("damage_type", "physical")
        return cls(
            count=data.get("count", 4),
            duration=data.get("duration"),
            damage_type=DamageType[dtype.upper()] if isinstance(dtype, str) else dtype,
            ad_value=data.get("ad_value", 125),
            ap_value=data.get("ap_value", 15),
            bonus_multiplier=data.get("bonus_multiplier", 1.0),
            bonus_on_attack=data.get("bonus_on_attack"),
            infinite_range=data.get("infinite_range", False),
        )


# ═══════════════════════════════════════════════════════════════════════════
# DECAYING BUFF EFFECT (Briar AS - buff malejący w czasie)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DecayingBuffEffect(Effect):
    """
    Buff który liniowo maleje do 0 przez czas trwania.
    
    Attributes:
        stat: Która statystyka (attack_speed, attack_damage, etc.)
        value: Początkowa wartość per star
        duration: Czas trwania w tickach
        is_percent: Czy to procent
    """
    effect_type: str = "decaying_buff"
    target_filter: EffectTarget = EffectTarget.ALLY
    
    stat: str = "attack_speed"
    value: StarValue = 3.0  # 300% AS
    duration: StarValue = 120  # 4 seconds
    is_percent: bool = True
    buff_target: str = "self"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        buff_target = caster if self.buff_target == "self" else target
        
        initial_value = get_star_value(self.value, star_level)
        duration = int(get_star_value(self.duration, star_level))
        
        # Store decaying buff on unit
        if not hasattr(buff_target, 'decaying_buffs'):
            buff_target.decaying_buffs = []
        
        buff_target.decaying_buffs.append({
            "stat": self.stat,
            "initial_value": initial_value,
            "current_value": initial_value,
            "remaining_ticks": duration,
            "total_duration": duration,
            "is_percent": self.is_percent,
        })
        
        # Apply initial buff
        if self.is_percent:
            buff_target.stats.add_percent_modifier(self.stat, initial_value)
        else:
            buff_target.stats.add_flat_modifier(self.stat, initial_value)
        
        return EffectResult(
            effect_type="decaying_buff",
            success=True,
            value=initial_value,
            targets=[buff_target.id],
            details={
                "stat": self.stat,
                "initial_value": initial_value,
                "duration_ticks": duration,
                "is_percent": self.is_percent,
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecayingBuffEffect":
        return cls(
            stat=data.get("stat", "attack_speed"),
            value=data.get("value", 3.0),
            duration=data.get("duration", 120),
            is_percent=data.get("is_percent", True),
            buff_target=data.get("target", "self"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# STACKING BUFF EFFECT (Viego - stacking on-hit damage per cast)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class StackingBuffEffect(Effect):
    """
    Buff który stackuje się z każdym triggerem.
    
    Attributes:
        stat: Statystyka do stackowania (lub special: "magic_damage_on_hit")
        value: Wartość dodawana per stack per star
        trigger: Kiedy stackować ("on_cast", "on_attack", "on_damage_dealt")
        frequency: Co ile triggerów dodać stack (1 = każdy, 3 = co trzeci)
        permanent: Czy stacki są permanentne (całą walkę)
        max_stacks: Max liczba stacków (None = unlimited)
    """
    effect_type: str = "stacking_buff"
    target_filter: EffectTarget = EffectTarget.SELF
    
    stat: str = "magic_damage_on_hit"
    value: StarValue = 24
    trigger: str = "on_cast"  # on_cast, on_attack, on_damage_dealt, on_damage_taken
    frequency: int = 1
    permanent: bool = True
    max_stacks: Optional[int] = None
    buff_target: str = "self"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        buff_target = caster if self.buff_target == "self" else target
        
        stack_value = get_star_value(self.value, star_level)
        
        # Initialize stacking system on unit if not present
        if not hasattr(buff_target, 'stacking_buffs'):
            buff_target.stacking_buffs = {}
        
        buff_key = f"{self.stat}_{self.trigger}"
        
        if buff_key not in buff_target.stacking_buffs:
            buff_target.stacking_buffs[buff_key] = {
                "stat": self.stat,
                "value_per_stack": stack_value,
                "current_stacks": 0,
                "total_value": 0,
                "trigger": self.trigger,
                "frequency": self.frequency,
                "trigger_count": 0,
                "permanent": self.permanent,
                "max_stacks": self.max_stacks,
            }
        
        # If trigger is on_cast, immediately add a stack
        if self.trigger == "on_cast":
            buff_data = buff_target.stacking_buffs[buff_key]
            buff_data["trigger_count"] += 1
            
            if buff_data["trigger_count"] >= self.frequency:
                buff_data["trigger_count"] = 0
                if self.max_stacks is None or buff_data["current_stacks"] < self.max_stacks:
                    buff_data["current_stacks"] += 1
                    buff_data["total_value"] += stack_value
        
        current_stacks = buff_target.stacking_buffs[buff_key]["current_stacks"]
        total_value = buff_target.stacking_buffs[buff_key]["total_value"]
        
        return EffectResult(
            effect_type="stacking_buff",
            success=True,
            value=total_value,
            targets=[buff_target.id],
            details={
                "stat": self.stat,
                "stacks": current_stacks,
                "value_per_stack": stack_value,
                "total_value": total_value,
                "trigger": self.trigger,
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StackingBuffEffect":
        return cls(
            stat=data.get("stat", "magic_damage_on_hit"),
            value=data.get("value", 24),
            trigger=data.get("trigger", "on_cast"),
            frequency=data.get("frequency", 1),
            permanent=data.get("permanent", True),
            max_stacks=data.get("max_stacks"),
            buff_target=data.get("target", "self"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# EFFECT GROUP - Grupuje efekty z wspólnym delay/aoe (Cho'Gath)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class EffectGroup(Effect):
    """
    Grupuje wiele efektów z wspólnym delay i aoe_radius.
    """
    effect_type: str = "effect_group"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    delay: int = 0
    aoe_radius: int = 0
    effects_data: List[Dict[str, Any]] = field(default_factory=list)
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        # Note: delay should be handled by simulation layer
        # Here we just apply all effects
        results = []
        
        for effect_data in self.effects_data:
            effect_type = effect_data.get("type")
            if effect_type and effect_type in EFFECT_REGISTRY:
                effect = EFFECT_REGISTRY[effect_type].from_dict(effect_data)
                result = effect.apply(caster, target, star_level, simulation)
                results.append(result)
        
        return EffectResult(
            effect_type="effect_group",
            success=True,
            value=len(results),
            targets=[target.id],
            details={
                "delay": self.delay,
                "aoe_radius": self.aoe_radius,
                "effects_count": len(results),
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EffectGroup":
        return cls(
            delay=data.get("delay", 0),
            aoe_radius=data.get("aoe_radius", 0),
            effects_data=data.get("effects", []),
        )


# ═══════════════════════════════════════════════════════════════════════════
# MANA REAVE - Zwiększa koszt many celu (Yorick)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ManaReaveEffect(Effect):
    """
    Zwiększa koszt many następnego casta celu.
    """
    effect_type: str = "mana_reave"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    value: int = 20
    duration: str = "next_cast"  # "next_cast" lub liczba ticków
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        mana_increase = get_star_value(self.value, star_level) if isinstance(self.value, list) else self.value
        
        # Store mana reave on target
        if not hasattr(target, 'mana_reave_stacks'):
            target.mana_reave_stacks = []
        
        target.mana_reave_stacks.append({
            "value": mana_increase,
            "duration": self.duration,
            "source_id": caster.id,
        })
        
        return EffectResult(
            effect_type="mana_reave",
            success=True,
            value=mana_increase,
            targets=[target.id],
            details={
                "mana_increase": mana_increase,
                "duration": self.duration,
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManaReaveEffect":
        return cls(
            value=data.get("value", 20),
            duration=data.get("duration", "next_cast"),
        )


# ═══════════════════════════════════════════════════════════════════════════
# PROJECTILE SPREAD - 3 pociski w stożku (Twisted Fate)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ProjectileSpreadEffect(Effect):
    """
    Wystrzeliwuje N pocisków w stożku, każdy trafia pierwszego wroga.
    """
    effect_type: str = "projectile_spread"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    projectile_count: int = 3
    spread_angle: int = 45
    range_val: int = 999
    value: StarValue = 70
    damage_type: DamageType = DamageType.MAGICAL
    scaling: str = "ap"
    falloff_per_enemy: float = 0.0
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        base_damage = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, target
        )
        
        # Get enemies in cone
        enemies = [u for u in simulation.units 
                   if u.is_alive() and u.team != caster.team]
        
        total_damage = 0
        hit_count = 0
        
        # Simple implementation: hit up to projectile_count enemies
        targets_hit = enemies[:self.projectile_count]
        
        for i, enemy in enumerate(targets_hit):
            # Apply falloff
            falloff = 1.0 - (self.falloff_per_enemy * i)
            damage = base_damage * max(0.1, falloff)
            
            from ..combat.damage import calculate_damage, apply_damage, DamageType as DT
            dt_map = {
                DamageType.PHYSICAL: DT.PHYSICAL,
                DamageType.MAGICAL: DT.MAGICAL,
                DamageType.TRUE: DT.TRUE,
            }
            
            result = calculate_damage(
                attacker=caster,
                defender=enemy,
                base_damage=damage,
                damage_type=dt_map[self.damage_type],
                rng=simulation.rng,
                can_crit=False,
                can_dodge=False,
                is_ability=True,
            )
            
            actual = apply_damage(caster, enemy, result)
            total_damage += actual
            hit_count += 1
        
        return EffectResult(
            effect_type="projectile_spread",
            success=hit_count > 0,
            value=total_damage,
            targets=[e.id for e in targets_hit],
            details={
                "projectiles": self.projectile_count,
                "hits": hit_count,
                "total_damage": round(total_damage, 1),
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectileSpreadEffect":
        dtype = data.get("damage_type", "magical")
        return cls(
            projectile_count=data.get("projectile_count", 3),
            spread_angle=data.get("spread_angle", 45),
            range_val=data.get("range", 999),
            value=data.get("value", 70),
            damage_type=DamageType[dtype.upper()] if isinstance(dtype, str) else dtype,
            scaling=data.get("scaling", "ap"),
            falloff_per_enemy=data.get("falloff_per_enemy", 0.0),
        )


# ═══════════════════════════════════════════════════════════════════════════
# MULTI STRIKE - Sekwencja uderzeń z efektami (Xin Zhao)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MultiStrikeEffect(Effect):
    """
    Wykonuje sekwencję uderzeń, każde z własnymi efektami.
    Ostatnie uderzenie może mieć dodatkowe efekty.
    """
    effect_type: str = "multi_strike"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    hits: int = 3
    per_hit: List[Dict[str, Any]] = field(default_factory=list)
    on_final_hit: List[Dict[str, Any]] = field(default_factory=list)
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        results = []
        
        for i in range(self.hits):
            # Apply per_hit effects
            for effect_data in self.per_hit:
                effect_type = effect_data.get("type")
                if effect_type and effect_type in EFFECT_REGISTRY:
                    effect = EFFECT_REGISTRY[effect_type].from_dict(effect_data)
                    result = effect.apply(caster, target, star_level, simulation)
                    results.append(result)
            
            # Apply on_final_hit for last strike
            if i == self.hits - 1:
                for effect_data in self.on_final_hit:
                    effect_type = effect_data.get("type")
                    if effect_type and effect_type in EFFECT_REGISTRY:
                        effect = EFFECT_REGISTRY[effect_type].from_dict(effect_data)
                        result = effect.apply(caster, target, star_level, simulation)
                        results.append(result)
        
        return EffectResult(
            effect_type="multi_strike",
            success=True,
            value=self.hits,
            targets=[target.id],
            details={
                "hits": self.hits,
                "effects_applied": len(results),
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MultiStrikeEffect":
        return cls(
            hits=data.get("hits", 3),
            per_hit=data.get("per_hit", []),
            on_final_hit=data.get("on_final_hit", []),
        )


# ═══════════════════════════════════════════════════════════════════════════
# CREATE ZONE - Tworzy strefę na czas (Ekko)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CreateZoneEffect(Effect):
    """
    Tworzy persistentną strefę na mapie. (Ekko, Kennen, Nasus)
    """
    effect_type: str = "create_zone"
    radius: float = 1.0
    duration: int = 90  # 3s
    on_end_effects: List[Dict] = field(default_factory=list)
    on_tick_effects: List[Dict] = field(default_factory=list)
    track_damage_taken: bool = False
    
    def apply(self, caster: "Unit", target: "Unit", star_level: int, simulation: "Simulation") -> EffectResult:
        if not hasattr(simulation, "active_zones"):
            simulation.active_zones = []
            
        zone = {
            "position": target.position,
            "radius": self.radius,
            "duration": self.duration,
            "remaining": self.duration,
            "caster": caster,
            "star_level": star_level,
            "on_end_effects": self.on_end_effects,
            "on_tick_effects": self.on_tick_effects,
            "damage_taken": 0.0 if self.track_damage_taken else None,
            "affected_targets": []
        }
        simulation.active_zones.append(zone)
        
        return EffectResult(effect_type="create_zone", success=True, value=float(self.duration))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CreateZoneEffect":
        on_end = data.get("on_end_effects", [])
        if not on_end and "on_end" in data:
            # Legacy support - on_end can be a list or single dict
            on_end_raw = data["on_end"]
            if isinstance(on_end_raw, list):
                on_end = on_end_raw
            else:
                on_end = [on_end_raw]
            
        return cls(
            radius=data.get("radius", 1.0),
            duration=data.get("duration", 90),
            on_end_effects=on_end,
            on_tick_effects=data.get("on_tick_effects", []),
            track_damage_taken=data.get("track_damage_taken", False)
        )



# ═══════════════════════════════════════════════════════════════════════════
# PERMANENT STACK - Stackowanie permanentne (Sion passive)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PermanentStackEffect(Effect):
    """
    Permanentnie stackuje statystykę na trigger (kill, takedown, cast, time).
    Używane jako passive, nie aktywne.
    """
    effect_type: str = "permanent_stack"
    target_filter: EffectTarget = EffectTarget.SELF
    
    stat: str = "max_hp"
    trigger: str = "on_kill"  # on_kill, on_takedown, on_cast, on_time
    value: StarValue = 20
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        stack_value = get_star_value(self.value, star_level)
        
        # Initialize permanent stacks on unit
        if not hasattr(caster, 'permanent_stacks'):
            caster.permanent_stacks = {}
        
        if self.stat not in caster.permanent_stacks:
            caster.permanent_stacks[self.stat] = 0
        
        caster.permanent_stacks[self.stat] += stack_value
        
        # Apply to stats
        if self.stat == "max_hp":
            caster.stats.add_flat_modifier("hp", stack_value)
        elif self.stat == "attack_damage":
            caster.stats.add_flat_modifier("attack_damage", stack_value)
        elif self.stat == "ability_power":
            caster.stats.add_flat_modifier("ability_power", stack_value)
        
        total = caster.permanent_stacks[self.stat]
        
        return EffectResult(
            effect_type="permanent_stack",
            success=True,
            value=total,
            targets=[caster.id],
            details={
                "stat": self.stat,
                "added": stack_value,
                "total": total,
                "trigger": self.trigger,
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PermanentStackEffect":
        return cls(
            stat=data.get("stat", "max_hp"),
            trigger=data.get("trigger", "on_kill"),
            value=data.get("value", 20),
        )


EFFECT_REGISTRY: Dict[str, type] = {
    # Offensive
    "damage": DamageEffect,
    "dot": DoTEffect,
    "burn": BurnEffect,
    "execute": ExecuteEffect,
    "sunder": SunderEffect,
    "shred": ShredEffect,
    "splash_damage": SplashDamageEffect,
    "ricochet": RicochetDamageEffect,
    "multi_hit": MultiHitEffect,
    "percent_hp_damage": PercentHPDamageEffect,
    "percent_damage_taken": PercentHPDamageEffect,  # Alias for zone damage
    "dash_through": DashThroughEffect,
    "hybrid_damage": HybridDamageEffect,  # NEW: AD+AP combined
    
    # CC
    "stun": StunEffect,
    "slow": SlowEffect,
    "chill": ChillEffect,
    "silence": SilenceEffect,
    "disarm": DisarmEffect,
    
    # Support
    "heal": HealEffect,
    "shield": ShieldEffect,
    "shield_self": ShieldSelfEffect,
    "wound": WoundEffect,
    "buff": BuffEffect,
    "buff_team": BuffTeamEffect,
    "mana_grant": ManaGrantEffect,
    "cleanse": CleanseEffect,
    "decaying_buff": DecayingBuffEffect,  # NEW: buff that decays over time
    "stacking_buff": StackingBuffEffect,  # NEW: stacking on trigger
    
    # Displacement
    "knockback": KnockbackEffect,
    "pull": PullEffect,
    "dash": DashEffect,
    
    # Special
    "replace_attacks": ReplaceAttacksEffect,
    
    # 2-Cost effects
    "effect_group": EffectGroup,
    "mana_reave": ManaReaveEffect,
    "projectile_spread": ProjectileSpreadEffect,
    "multi_strike": MultiStrikeEffect,
    "create_zone": CreateZoneEffect,
    "permanent_stack": PermanentStackEffect,
}


@dataclass
class IntervalTriggerEffect(Effect):
    """
    Pasywny efekt, który odpala inny efekt co X ticków. (Nautilus, Kobuko)
    """
    effect_type: str = "interval_trigger"
    interval: int = 120  # co ile ticków odpala
    trigger_effect: Dict = field(default_factory=dict)
    target_type: str = "self"  # na kogo aplikować triggerowany efekt
    
    def apply(self, caster: "Unit", target: "Unit", star_level: int, simulation: "Simulation") -> EffectResult:
        # Dodajemy do castera info o interwale (obsługiwane w simulation.py lub unit.tick)
        if not hasattr(caster, "interval_effects"):
            caster.interval_effects = []
            
        caster.interval_effects.append({
            "interval": self.interval,
            "next_tick": simulation.current_tick + self.interval,
            "effect_data": self.trigger_effect,
            "target_type": self.target_type,
            "star_level": star_level
        })
        
        return EffectResult(effect_type="interval_trigger", success=True, value=float(self.interval))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntervalTriggerEffect":
        return cls(
            interval=data.get("interval", 120),
            trigger_effect=data.get("effect", {}),
            target_type=data.get("target_type", "self")
        )


@dataclass
class ProjectileSwarmEffect(Effect):
    """
    Rój pocisków / jaskółek. (Jinx, Malzahar, Ahri)
    Wiele pocisków, które mogą re-targetować po śmierci celu.
    """
    effect_type: str = "projectile_swarm"
    count: int = 3
    jumps: int = 1  # Malzahar ma 10 ataków per swarm
    value: StarValue = 50
    scaling: str = "ap"
    damage_type: DamageType = DamageType.MAGICAL
    
    def apply(self, caster: "Unit", target: "Unit", star_level: int, simulation: "Simulation") -> EffectResult:
        count = self.count
        jumps = self.jumps
        dmg_val = get_star_value(self.value, star_level)
        
        # W tej wersji uproszczonej: od razu zadajemy obrażenia, 
        # ale emulujemy jaskółki (logic re-targeting byłaby w simulation.py pod projectile)
        total_dmg = 0
        targets_hit = []
        
        current_target = target
        for _ in range(count):
            for _ in range(jumps):
                if current_target and current_target.is_alive():
                    # Oblicz dmg
                    dmg = calculate_scaled_value(dmg_val, self.scaling, star_level, caster, current_target)
                    actual = current_target.take_damage(dmg, self.damage_type, caster, simulation)
                    total_dmg += actual
                    if current_target.id not in targets_hit:
                        targets_hit.append(current_target.id)
                else:
                    # Szukaj nowego celu (re-targeting)
                    enemies = simulation.get_enemies(caster.team)
                    if enemies:
                        current_target = min(enemies, key=lambda e: caster.position.distance(e.position))
                        # Powtórz dla nowego celu
                        dmg = calculate_scaled_value(dmg_val, self.scaling, star_level, caster, current_target)
                        actual = current_target.take_damage(dmg, self.damage_type, caster, simulation)
                        total_dmg += actual
                        if current_target.id not in targets_hit:
                            targets_hit.append(current_target.id)
                    else:
                        break
        
        return EffectResult(
            effect_type="projectile_swarm",
            success=total_dmg > 0,
            value=total_dmg,
            targets=targets_hit,
            details={"count": count, "jumps": jumps}
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectileSwarmEffect":
        dtype = data.get("damage_type", "magical")
        return cls(
            count=data.get("count", 3),
            jumps=data.get("jumps", 1),
            value=data.get("value", 50),
            scaling=data.get("scaling", "ap"),
            damage_type=DamageType[dtype.upper()] if isinstance(dtype, str) else dtype
        )



@dataclass
class TauntEffect(Effect):
    """
    Wymusza na wrogach atakowanie castera. (Loris)
    """
    effect_type: str = "taunt"
    duration: int = 90  # 3s
    aoe_radius: int = 2
    
    def apply(self, caster: "Unit", target: "Unit", star_level: int, simulation: "Simulation") -> EffectResult:
        # Znajdź wrogów w promieniu
        enemies = simulation.get_enemies_in_radius(caster.position, self.aoe_radius, caster.team)
        for enemy in enemies:
            enemy.force_target = caster
            enemy.taunt_remaining_ticks = self.duration
            
        return EffectResult(effect_type="taunt", success=len(enemies) > 0, value=float(len(enemies)))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TauntEffect":
        return cls(
            duration=data.get("duration", 90),
            aoe_radius=data.get("aoe_radius", 2)
        )


@dataclass
class HealOverTimeEffect(Effect):
    """
    Leczenie rozłożone w czasie. (Dr. Mundo, Kobuko)
    """
    effect_type: str = "heal_over_time"
    value: StarValue = 100
    scaling: str = "ap"
    value_percent_max_hp: float = 0.0
    duration: int = 150  # 5s
    tick_rate: int = 30  # co 1s
    
    def apply(self, caster: "Unit", target: "Unit", star_level: int, simulation: "Simulation") -> EffectResult:
        if not hasattr(target, "hots"):
            target.hots = []
            
        val = get_star_value(self.value, star_level)
        target.hots.append({
            "value": val,
            "scaling": self.scaling,
            "percent_hp": self.value_percent_max_hp,
            "duration": self.duration,
            "tick_rate": self.tick_rate,
            "next_tick": simulation.current_tick + self.tick_rate,
            "caster_id": caster.id
        })
        
        return EffectResult(effect_type="heal_over_time", success=True, value=float(val))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealOverTimeEffect":
        return cls(
            value=data.get("value", 100),
            scaling=data.get("scaling", "ap"),
            value_percent_max_hp=data.get("value_percent_max_hp", 0.0),
            duration=data.get("duration", 150),
            tick_rate=data.get("tick_rate", 30)
        )


# ═══════════════════════════════════════════════════════════════════════════
# TRANSFORM EFFECT - Bel'Veth transformation
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TransformEffect(Effect):
    """
    Transformacja jednostki - zmienia staty, dodaje on-hit effects.
    Bel'Veth: +33% HP, +AS, stacking true damage on hit.
    """
    effect_type: str = "transform"
    target_filter: EffectTarget = EffectTarget.SELF
    
    hp_percent_bonus: float = 0.0
    attack_speed_bonus: StarValue = 0.0
    attack_speed_scaling: str = "flat"  # "flat" or "ap"
    duration: int = -1  # -1 = combat duration
    on_hit_damage: StarValue = 0.0
    on_hit_damage_type: str = "true"
    stacking_per_hit: StarValue = 0.0
    
    def apply(self, caster: "Unit", target: "Unit", star_level: int, simulation: "Simulation") -> EffectResult:
        # Apply HP bonus
        if self.hp_percent_bonus > 0:
            hp_bonus = caster.stats.max_hp * self.hp_percent_bonus
            caster.stats.current_hp += hp_bonus
            caster.stats.max_hp += hp_bonus
        
        # Apply AS bonus
        as_bonus = get_star_value(self.attack_speed_bonus, star_level)
        if self.attack_speed_scaling == "ap":
            as_bonus *= (1 + caster.stats.ability_power / 100)
        caster.stats.attack_speed += caster.stats.attack_speed * as_bonus
        
        # Set up on-hit damage
        on_hit = get_star_value(self.on_hit_damage, star_level)
        stacking = get_star_value(self.stacking_per_hit, star_level)
        
        if not hasattr(caster, 'transform_on_hit'):
            caster.transform_on_hit = {}
        
        caster.transform_on_hit = {
            'base_damage': on_hit,
            'damage_type': self.on_hit_damage_type,
            'stacking': stacking,
            'current_stacks': 0
        }
        
        return EffectResult(
            effect_type="transform",
            success=True,
            value=hp_bonus if self.hp_percent_bonus > 0 else as_bonus
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransformEffect":
        stat_changes = data.get("stat_changes", {})
        on_hit = data.get("on_hit", {})
        
        return cls(
            hp_percent_bonus=stat_changes.get("hp_percent", 0.0),
            attack_speed_bonus=stat_changes.get("attack_speed", 0.0),
            attack_speed_scaling=stat_changes.get("attack_speed_scaling", "flat"),
            duration=data.get("duration", -1),
            on_hit_damage=on_hit.get("value", 0) if on_hit else 0,
            on_hit_damage_type=on_hit.get("damage_type", "true") if on_hit else "true",
            stacking_per_hit=on_hit.get("stacking_per_hit", 0) if on_hit else 0
        )


# ═══════════════════════════════════════════════════════════════════════════
# ACCUMULATOR EFFECT - Seraphine notes system
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AccumulatorEffect(Effect):
    """
    Akumuluje ładunki (nuty) i triggeruje efekty przy progu.
    Seraphine: 3 nuty/cast, każda zadaje dmg, przy 12 nutach fala leczenia+dmg.
    """
    effect_type: str = "accumulator"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    notes_per_cast: int = 3
    note_damage: StarValue = 0.0
    scaling: str = "ap"
    trigger_at: int = 12
    
    # On trigger effects (simplified - just heal + damage)
    trigger_heal: StarValue = 0.0
    trigger_damage: StarValue = 0.0
    trigger_falloff: float = 0.30
    
    def apply(self, caster: "Unit", target: "Unit", star_level: int, simulation: "Simulation") -> EffectResult:
        # Init accumulator
        if not hasattr(caster, 'accumulator_notes'):
            caster.accumulator_notes = 0
        
        # Deal note damage for each note
        note_dmg = get_star_value(self.note_damage, star_level)
        if self.scaling == "ap":
            note_dmg *= (1 + caster.stats.ability_power / 100)
        
        total_dmg = 0
        enemies = simulation.get_enemies(caster.team)
        
        for i in range(self.notes_per_cast):
            if enemies:
                enemy = enemies[i % len(enemies)]
                actual = enemy.take_damage(note_dmg, DamageType.MAGICAL, caster)
                total_dmg += actual
        
        caster.accumulator_notes += self.notes_per_cast
        
        # Check trigger
        triggered = False
        if caster.accumulator_notes >= self.trigger_at:
            triggered = True
            caster.accumulator_notes = 0
            
            # Heal allies
            heal_val = get_star_value(self.trigger_heal, star_level)
            if self.scaling == "ap":
                heal_val *= (1 + caster.stats.ability_power / 100)
            
            allies = simulation.get_allies(caster.team)
            for ally in allies:
                ally.heal(heal_val, caster)
            
            # Damage in line with falloff
            dmg_val = get_star_value(self.trigger_damage, star_level)
            if self.scaling == "ap":
                dmg_val *= (1 + caster.stats.ability_power / 100)
            
            for i, enemy in enumerate(enemies):
                falloff_mult = max(0.1, 1 - (self.trigger_falloff * i))
                actual_dmg = dmg_val * falloff_mult
                enemy.take_damage(actual_dmg, DamageType.MAGICAL, caster)
        
        return EffectResult(
            effect_type="accumulator",
            success=True,
            value=float(total_dmg),
            details={
                "notes": caster.accumulator_notes if hasattr(caster, 'accumulator_notes') else 0,
                "triggered": triggered
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccumulatorEffect":
        on_trigger = data.get("on_trigger", [])
        
        trigger_heal = 0
        trigger_damage = 0
        trigger_falloff = 0.30
        
        for effect in on_trigger:
            if effect.get("type") == "heal":
                trigger_heal = effect.get("ap_value", effect.get("value", 0))
            elif effect.get("type") == "damage":
                trigger_damage = effect.get("ap_value", effect.get("value", 0))
                trigger_falloff = effect.get("falloff_percent", 0.30)
        
        return cls(
            notes_per_cast=data.get("notes_per_cast", 3),
            note_damage=data.get("note_damage", 0),
            scaling=data.get("scaling", "ap"),
            trigger_at=data.get("trigger_at", 12),
            trigger_heal=trigger_heal,
            trigger_damage=trigger_damage,
            trigger_falloff=trigger_falloff
        )


# Add 3-cost effects to registry
EFFECT_REGISTRY["interval_trigger"] = IntervalTriggerEffect
EFFECT_REGISTRY["projectile_swarm"] = ProjectileSwarmEffect
EFFECT_REGISTRY["taunt"] = TauntEffect
EFFECT_REGISTRY["heal_over_time"] = HealOverTimeEffect

# Add 4-cost effects to registry
EFFECT_REGISTRY["transform"] = TransformEffect
EFFECT_REGISTRY["accumulator"] = AccumulatorEffect


def create_effect(effect_type: str, data: Dict[str, Any]) -> Effect:
    """
    Factory do tworzenia efektów z YAML.
    
    Args:
        effect_type: Typ efektu
        data: Dane z YAML
        
    Returns:
        Effect: Instancja efektu
    """
    effect_class = EFFECT_REGISTRY.get(effect_type)
    
    if effect_class is None:
        raise ValueError(f"Unknown effect type: {effect_type}. "
                        f"Available: {list(EFFECT_REGISTRY.keys())}")
    
    return effect_class.from_dict(data)


def parse_effects(effects_data: List[Dict[str, Any]]) -> List[Effect]:
    """
    Parsuje listę efektów z YAML.
    
    Args:
        effects_data: Lista efektów z YAML
        
    Returns:
        List[Effect]: Lista instancji efektów
    """
    effects = []
    for effect_data in effects_data:
        effect_type = effect_data.get("type", "damage")
        effect = create_effect(effect_type, effect_data)
        effects.append(effect)
    return effects

