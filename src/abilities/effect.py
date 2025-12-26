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
    """
    effect_type: str = "damage"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    damage_type: DamageType = DamageType.MAGICAL
    value: StarValue = 100
    scaling: Optional[str] = None
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        # Oblicz damage
        damage = calculate_scaled_value(
            self.value, self.scaling, star_level, caster, target
        )
        
        # Importuj damage system
        from ..combat.damage import calculate_damage, apply_damage, DamageType as DT
        
        # Mapowanie enum
        dt_map = {
            DamageType.PHYSICAL: DT.PHYSICAL,
            DamageType.MAGICAL: DT.MAGICAL,
            DamageType.TRUE: DT.TRUE,
        }
        
        # Oblicz z redukcją (ability = no crit, no dodge)
        result = calculate_damage(
            attacker=caster,
            defender=target,
            base_damage=damage,
            damage_type=dt_map[self.damage_type],
            rng=simulation.rng,
            can_crit=False,
            can_dodge=False,
            is_ability=True,
        )
        
        # Aplikuj
        actual = apply_damage(caster, target, result)
        
        return EffectResult(
            effect_type="damage",
            success=True,
            value=actual,
            targets=[target.id],
            details={
                "damage_type": self.damage_type.name,
                "raw": round(damage, 1),
                "final": round(actual, 1),
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DamageEffect":
        dt_str = data.get("damage_type", "magical").upper()
        return cls(
            damage_type=DamageType[dt_str],
            value=data.get("value", 100),
            scaling=data.get("scaling"),
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
    """
    effect_type: str = "knockback"
    target_filter: EffectTarget = EffectTarget.ENEMY
    
    distance: StarValue = 2
    stun_duration: StarValue = 15  # krótki stun po knockback
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        distance = int(get_star_value(self.distance, star_level))
        stun_dur = int(get_star_value(self.stun_duration, star_level))
        
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
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnockbackEffect":
        return cls(
            distance=data.get("distance", 2),
            stun_duration=data.get("stun_duration", 15),
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
    """
    effect_type: str = "dash"
    target_filter: EffectTarget = EffectTarget.SELF
    
    distance: StarValue = 2
    direction: str = "to_target"  # "to_target" | "away_from_target"
    
    def apply(
        self,
        caster: "Unit",
        target: "Unit",
        star_level: int,
        simulation: "Simulation",
    ) -> EffectResult:
        distance = int(get_star_value(self.distance, star_level))
        
        if self.direction == "to_target":
            dir_q = target.position.q - caster.position.q
            dir_r = target.position.r - caster.position.r
        else:  # away_from_target
            dir_q = caster.position.q - target.position.q
            dir_r = caster.position.r - target.position.r
        
        length = max(1, abs(dir_q) + abs(dir_r))
        new_q = caster.position.q + int((dir_q / length) * distance)
        new_r = caster.position.r + int((dir_r / length) * distance)
        
        from ..core.hex_coord import HexCoord
        new_pos = HexCoord(new_q, new_r)
        
        moved = False
        if simulation.grid.is_valid(new_pos) and simulation.grid.is_walkable(new_pos):
            simulation.grid.move_unit(caster, new_pos)
            caster.position = new_pos
            moved = True
        
        return EffectResult(
            effect_type="dash",
            success=moved,
            value=distance,
            targets=[caster.id],
            details={
                "distance": distance,
                "direction": self.direction,
                "moved": moved,
            }
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DashEffect":
        return cls(
            distance=data.get("distance", 2),
            direction=data.get("direction", "to_target"),
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
# EFFECT REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

EFFECT_REGISTRY: Dict[str, type] = {
    # Offensive
    "damage": DamageEffect,
    "dot": DoTEffect,
    "burn": BurnEffect,
    "execute": ExecuteEffect,
    "sunder": SunderEffect,
    "shred": ShredEffect,
    
    # CC
    "stun": StunEffect,
    "slow": SlowEffect,
    "silence": SilenceEffect,
    "disarm": DisarmEffect,
    
    # Support
    "heal": HealEffect,
    "shield": ShieldEffect,
    "wound": WoundEffect,
    "buff": BuffEffect,
    "mana_grant": ManaGrantEffect,
    "cleanse": CleanseEffect,
    
    # Displacement
    "knockback": KnockbackEffect,
    "pull": PullEffect,
    "dash": DashEffect,
}


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

