"""
System obliczania obrażeń z obsługą Critical Strike i Dodge.

TYPY OBRAŻEŃ:
═══════════════════════════════════════════════════════════════════

    PHYSICAL (Fizyczne)
    ─────────────────────────────────────────────────────────────
    - Pochodzą z: auto-ataków i niektórych umiejętności
    - Redukowane przez: ARMOR
    - Wzór redukcji (TFT-style):
        reduction = armor / (armor + 100)
        
    Przykłady:
        0 armor   -> 0% redukcji
        50 armor  -> 33% redukcji
        100 armor -> 50% redukcji
        200 armor -> 67% redukcji
        
    MAGICAL (Magiczne)
    ─────────────────────────────────────────────────────────────
    - Pochodzą z: umiejętności (większość)
    - Redukowane przez: MAGIC RESIST
    - Ten sam wzór co ARMOR
    
    TRUE (Prawdziwe)
    ─────────────────────────────────────────────────────────────
    - Nie podlegają żadnej redukcji
    - Przechodzą przez armor i MR
    - Używane przez niektóre specjalne efekty

CRITICAL STRIKE:
═══════════════════════════════════════════════════════════════════

    Działa TYLKO na auto-ataki, NIE na umiejętności!
    
    Sekwencja:
    1. Rzuć kością: rng.random() < crit_chance
    2. Jeśli crit: damage *= crit_damage
    3. Crit jest PRZED redukcją od armor
    
    Przykład (crit_chance=0.25, crit_damage=1.4):
        Base damage = 100
        Crit roll = 0.15 (sukces, bo < 0.25)
        After crit = 100 * 1.4 = 140
        After armor = 140 * (1 - reduction)

DODGE:
═══════════════════════════════════════════════════════════════════

    Działa TYLKO na auto-ataki!
    
    Jeśli dodge:
    - Obrażenia = 0
    - Nie zyskuje się many z ataku
    - Logowane jako "dodged"

LIFESTEAL / SPELL VAMP:
═══════════════════════════════════════════════════════════════════

    Lifesteal - % obrażeń FIZYCZNYCH zamieniane na HP
    Spell Vamp - % obrażeń ze SPELLI zamieniane na HP
    
    Obliczane PO redukcji, NA finalnych obrażeniach.

KOLEJNOŚĆ OBLICZEŃ:
═══════════════════════════════════════════════════════════════════

    1. Bazowe obrażenia (AD lub AP scaled)
    2. Crit roll (tylko dla auto-attacks)
    3. Dodge roll (tylko dla auto-attacks)
    4. Redukcja (armor/MR, nie dla TRUE)
    5. Lifesteal/Spell Vamp
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..units.unit import Unit
    from ..core.rng import GameRNG


class DamageType(Enum):
    """
    Typ obrażeń - określa jak są redukowane.
    """
    PHYSICAL = auto()   # Redukowane przez Armor
    MAGICAL = auto()    # Redukowane przez Magic Resist
    TRUE = auto()       # Nie redukowane


@dataclass
class DamageResult:
    """
    Wynik obliczenia obrażeń.
    
    Zawiera wszystkie informacje o ataku/umiejętności,
    potrzebne do logowania i efektów (lifesteal, mana from damage).
    
    Attributes:
        raw_damage (float): Obrażenia po crit, przed redukcją
        pre_mitigation_damage (float): Obrażenia PRZED armor/MR (= raw_damage)
        final_damage (float): Obrażenia po redukcji (faktycznie zadane)
        damage_type (DamageType): Typ obrażeń
        is_crit (bool): Czy był krytyk
        was_dodged (bool): Czy atak został uniknięty
        reduction (float): Wartość redukcji (0.0 - 1.0)
        lifesteal_amount (float): Ilość HP odzyskanego przez lifesteal
        
    Note:
        pre_mitigation_damage jest potrzebne do TFT mana formula:
        mana = 1% * pre_mitigation + 3% * post_mitigation
    """
    raw_damage: float
    pre_mitigation_damage: float  # Added for TFT mana calculation
    final_damage: float
    damage_type: DamageType
    is_crit: bool = False
    was_dodged: bool = False
    reduction: float = 0.0
    lifesteal_amount: float = 0.0
    
    def to_dict(self) -> dict:
        """Serializuje wynik do słownika."""
        return {
            "raw_damage": round(self.raw_damage, 1),
            "pre_mitigation_damage": round(self.pre_mitigation_damage, 1),
            "final_damage": round(self.final_damage, 1),
            "damage_type": self.damage_type.name,
            "is_crit": self.is_crit,
            "was_dodged": self.was_dodged,
            "reduction": round(self.reduction, 3),
            "lifesteal": round(self.lifesteal_amount, 1),
        }


def calculate_reduction(resistance: float) -> float:
    """
    Oblicza redukcję obrażeń z armor/MR.
    
    Wzór TFT-style:
        reduction = resistance / (resistance + 100)
    
    Args:
        resistance: Wartość armor lub magic resist
        
    Returns:
        float: Redukcja jako ułamek (0.0 - ~1.0)
        
    Examples:
        >>> calculate_reduction(0)
        0.0
        >>> calculate_reduction(50)
        0.333...
        >>> calculate_reduction(100)
        0.5
        >>> calculate_reduction(200)
        0.666...
        
    Note:
        Ujemny armor daje ujemną redukcję (zwiększa obrażenia).
        Wzór nadal działa: -50 armor -> -100% redukcja (2x dmg)
    """
    return resistance / (resistance + 100)


def calculate_damage(
    attacker: "Unit",
    defender: "Unit",
    base_damage: float,
    damage_type: DamageType,
    rng: "GameRNG",
    can_crit: bool = True,
    can_dodge: bool = True,
    is_ability: bool = False,
) -> DamageResult:
    """
    Oblicza obrażenia od ataku lub umiejętności.
    
    Pełny pipeline:
    1. [Crit] - tylko dla auto-attacks (can_crit=True, is_ability=False)
    2. [Dodge] - tylko dla auto-attacks (can_dodge=True, is_ability=False)
    3. [Redukcja] - armor dla PHYSICAL, MR dla MAGICAL, 0 dla TRUE
    4. [Final] - max(0, po redukcji)
    5. [Lifesteal] - obliczany ale NIE aplikowany (to robi caller)
    
    Args:
        attacker: Jednostka atakująca
        defender: Jednostka broniąca się
        base_damage: Bazowe obrażenia (AD lub AP-scaled)
        damage_type: PHYSICAL, MAGICAL, lub TRUE
        rng: Generator losowości
        can_crit: Czy może być krytyk (False dla spelli)
        can_dodge: Czy można uniknąć (False dla spelli)
        is_ability: Czy to umiejętność (True = spell vamp zamiast lifesteal)
        
    Returns:
        DamageResult: Pełny wynik z wszystkimi informacjami
        
    Example:
        >>> result = calculate_damage(warrior, mage, 100, DamageType.PHYSICAL, rng)
        >>> result.is_crit
        True
        >>> result.final_damage
        93.3  # po redukcji z armor
    """
    damage = base_damage
    is_crit = False
    was_dodged = False
    reduction = 0.0
    
    # ─────────────────────────────────────────────────────────────────────
    # CRIT (tylko auto-attacks)
    # ─────────────────────────────────────────────────────────────────────
    
    if can_crit and not is_ability:
        crit_chance = attacker.stats.get_crit_chance()
        if rng.roll_crit(crit_chance):
            is_crit = True
            crit_multiplier = attacker.stats.get_crit_damage()
            damage *= crit_multiplier
    
    raw_damage = damage
    
    # ─────────────────────────────────────────────────────────────────────
    # DODGE (tylko auto-attacks)
    # ─────────────────────────────────────────────────────────────────────
    
    if can_dodge and not is_ability:
        dodge_chance = defender.stats.get_dodge_chance()
        if rng.roll_dodge(dodge_chance):
            was_dodged = True
            return DamageResult(
                raw_damage=raw_damage,
                pre_mitigation_damage=raw_damage,
                final_damage=0.0,
                damage_type=damage_type,
                is_crit=is_crit,
                was_dodged=True,
                reduction=0.0,
                lifesteal_amount=0.0,
            )
    
    # ─────────────────────────────────────────────────────────────────────
    # REDUKCJA
    # ─────────────────────────────────────────────────────────────────────
    
    if damage_type == DamageType.PHYSICAL:
        armor = defender.stats.get_armor()
        reduction = calculate_reduction(armor)
    elif damage_type == DamageType.MAGICAL:
        mr = defender.stats.get_magic_resist()
        reduction = calculate_reduction(mr)
    elif damage_type == DamageType.TRUE:
        reduction = 0.0
    
    final_damage = damage * (1 - reduction)
    final_damage = max(0.0, final_damage)
    
    # ─────────────────────────────────────────────────────────────────────
    # LIFESTEAL / SPELL VAMP
    # ─────────────────────────────────────────────────────────────────────
    
    lifesteal_amount = 0.0
    
    if is_ability:
        # Spell vamp
        spell_vamp = attacker.stats.get_spell_vamp()
        if spell_vamp > 0:
            lifesteal_amount = final_damage * spell_vamp
    else:
        # Lifesteal (fizyczne auto-attacks)
        if damage_type == DamageType.PHYSICAL:
            lifesteal = attacker.stats.get_lifesteal()
            if lifesteal > 0:
                lifesteal_amount = final_damage * lifesteal
    
    return DamageResult(
        raw_damage=raw_damage,
        pre_mitigation_damage=raw_damage,
        final_damage=final_damage,
        damage_type=damage_type,
        is_crit=is_crit,
        was_dodged=was_dodged,
        reduction=reduction,
        lifesteal_amount=lifesteal_amount,
    )


def apply_damage(
    attacker: "Unit",
    defender: "Unit",
    damage_result: DamageResult,
) -> float:
    """
    Aplikuje obrażenia do obrońcy i lifesteal do atakującego.
    
    Args:
        attacker: Atakujący (dostaje lifesteal)
        defender: Broniący się (otrzymuje obrażenia)
        damage_result: Wynik z calculate_damage
        
    Returns:
        float: Faktycznie zadane obrażenia
        
    Note:
        - Zmniejsza HP obrońcy
        - Dodaje HP atakującemu (lifesteal)
        - Dodaje manę obrońcy (za otrzymane obrażenia)
    """
    if damage_result.was_dodged:
        return 0.0
    
    # Zadaj obrażenia
    actual_damage = defender.stats.take_damage(damage_result.final_damage)
    
    # Mana za otrzymane obrażenia
    defender.gain_mana_on_damage()
    
    # Lifesteal
    if damage_result.lifesteal_amount > 0:
        attacker.stats.heal(damage_result.lifesteal_amount)
    
    # Sprawdź śmierć
    if not defender.stats.is_alive():
        defender.die()
    
    return actual_damage
