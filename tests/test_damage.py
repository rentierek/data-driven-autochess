"""
Testy dla systemu walki i obrażeń.

Testuje:
- DamageResult z pre_mitigation_damage
- Wzór redukcji (TFT-style)
- Critical strike
- Dodge
- Lifesteal / Spell vamp
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.combat.damage import (
    DamageType, DamageResult, 
    calculate_reduction, calculate_damage, apply_damage
)
from src.units.unit import Unit
from src.units.stats import UnitStats
from src.core.hex_coord import HexCoord
from src.core.rng import GameRNG


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def rng():
    """Deterministyczny RNG."""
    return GameRNG(seed=12345)


def create_unit(hp=500, armor=0, mr=0, crit_chance=0, crit_damage=1.4, dodge=0, lifesteal=0):
    """Helper do tworzenia jednostek testowych."""
    stats = UnitStats(
        base_hp=hp,
        base_armor=armor,
        base_magic_resist=mr,
        base_crit_chance=crit_chance,
        base_crit_damage=crit_damage,
        base_dodge_chance=dodge,
        base_lifesteal=lifesteal,
    )
    stats.current_hp = hp
    return Unit(
        id="test",
        name="Test",
        unit_type="test",
        team=0,
        position=HexCoord(0, 0),
        stats=stats,
    )


# ═══════════════════════════════════════════════════════════════════════════
# TEST: DAMAGE REDUCTION
# ═══════════════════════════════════════════════════════════════════════════

def test_reduction_zero_armor():
    """0 armor = 0% redukcji."""
    assert calculate_reduction(0) == 0.0


def test_reduction_50_armor():
    """50 armor = 33% redukcji."""
    reduction = calculate_reduction(50)
    assert reduction == pytest.approx(0.333, rel=0.01)


def test_reduction_100_armor():
    """100 armor = 50% redukcji."""
    reduction = calculate_reduction(100)
    assert reduction == pytest.approx(0.5, rel=0.01)


def test_reduction_200_armor():
    """200 armor = 67% redukcji."""
    reduction = calculate_reduction(200)
    assert reduction == pytest.approx(0.667, rel=0.01)


def test_reduction_negative_armor():
    """Ujemny armor daje ujemną redukcję (więcej dmg)."""
    reduction = calculate_reduction(-50)
    # -50 / (-50 + 100) = -50 / 50 = -1.0 → damage *= (1 - (-1)) = 2x
    assert reduction == pytest.approx(-1.0, rel=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# TEST: DAMAGE RESULT
# ═══════════════════════════════════════════════════════════════════════════

def test_damage_result_has_pre_mitigation():
    """DamageResult ma pole pre_mitigation_damage."""
    result = DamageResult(
        raw_damage=100,
        pre_mitigation_damage=100,
        final_damage=50,
        damage_type=DamageType.PHYSICAL,
    )
    
    assert result.pre_mitigation_damage == 100
    assert result.final_damage == 50


def test_damage_result_to_dict():
    """DamageResult serializuje się poprawnie."""
    result = DamageResult(
        raw_damage=100,
        pre_mitigation_damage=100,
        final_damage=50,
        damage_type=DamageType.PHYSICAL,
        is_crit=True,
    )
    
    d = result.to_dict()
    
    assert d["raw_damage"] == 100
    assert d["pre_mitigation_damage"] == 100
    assert d["final_damage"] == 50
    assert d["damage_type"] == "PHYSICAL"
    assert d["is_crit"] == True


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CALCULATE DAMAGE - PHYSICAL
# ═══════════════════════════════════════════════════════════════════════════

def test_physical_damage_vs_no_armor(rng):
    """Fizyczne obrażenia bez armor = pełne damage."""
    attacker = create_unit()
    defender = create_unit(armor=0)
    
    result = calculate_damage(
        attacker, defender,
        base_damage=100,
        damage_type=DamageType.PHYSICAL,
        rng=rng,
        can_crit=False,
        can_dodge=False,
    )
    
    assert result.final_damage == 100
    assert result.reduction == 0


def test_physical_damage_vs_100_armor(rng):
    """Fizyczne obrażenia vs 100 armor = 50% redukcji."""
    attacker = create_unit()
    defender = create_unit(armor=100)
    
    result = calculate_damage(
        attacker, defender,
        base_damage=100,
        damage_type=DamageType.PHYSICAL,
        rng=rng,
        can_crit=False,
        can_dodge=False,
    )
    
    assert result.final_damage == pytest.approx(50, rel=0.01)
    assert result.reduction == pytest.approx(0.5, rel=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CALCULATE DAMAGE - MAGICAL
# ═══════════════════════════════════════════════════════════════════════════

def test_magical_damage_vs_mr(rng):
    """Magiczne obrażenia redukowane przez MR."""
    attacker = create_unit()
    defender = create_unit(mr=100)
    
    result = calculate_damage(
        attacker, defender,
        base_damage=100,
        damage_type=DamageType.MAGICAL,
        rng=rng,
        can_crit=False,
        can_dodge=False,
    )
    
    assert result.final_damage == pytest.approx(50, rel=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CALCULATE DAMAGE - TRUE
# ═══════════════════════════════════════════════════════════════════════════

def test_true_damage_ignores_armor(rng):
    """True damage ignoruje armor."""
    attacker = create_unit()
    defender = create_unit(armor=200)
    
    result = calculate_damage(
        attacker, defender,
        base_damage=100,
        damage_type=DamageType.TRUE,
        rng=rng,
        can_crit=False,
        can_dodge=False,
    )
    
    assert result.final_damage == 100
    assert result.reduction == 0


def test_true_damage_ignores_mr(rng):
    """True damage ignoruje MR."""
    attacker = create_unit()
    defender = create_unit(mr=200)
    
    result = calculate_damage(
        attacker, defender,
        base_damage=100,
        damage_type=DamageType.TRUE,
        rng=rng,
        can_crit=False,
        can_dodge=False,
    )
    
    assert result.final_damage == 100


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CRITICAL STRIKE
# ═══════════════════════════════════════════════════════════════════════════

def test_crit_increases_damage():
    """Crit mnoży obrażenia przez crit_damage."""
    # RNG seed gdzie crit zawsze wystąpi
    attacker = create_unit(crit_chance=1.0, crit_damage=1.5)  # 100% crit
    defender = create_unit(armor=0)
    
    result = calculate_damage(
        attacker, defender,
        base_damage=100,
        damage_type=DamageType.PHYSICAL,
        rng=GameRNG(1),
        can_crit=True,
        can_dodge=False,
    )
    
    assert result.is_crit == True
    # raw_damage powinno być 100 * 1.5 = 150
    assert result.raw_damage == 150


def test_crit_disabled_for_abilities():
    """Crit nie działa dla umiejętności."""
    attacker = create_unit(crit_chance=1.0, crit_damage=1.5)
    defender = create_unit()
    
    result = calculate_damage(
        attacker, defender,
        base_damage=100,
        damage_type=DamageType.MAGICAL,
        rng=GameRNG(1),
        can_crit=True,
        can_dodge=True,
        is_ability=True,  # to jest ability
    )
    
    assert result.is_crit == False


# ═══════════════════════════════════════════════════════════════════════════
# TEST: DODGE
# ═══════════════════════════════════════════════════════════════════════════

def test_dodge_negates_damage():
    """Dodge redukuje damage do 0."""
    attacker = create_unit()
    defender = create_unit(dodge=1.0)  # 100% dodge
    
    result = calculate_damage(
        attacker, defender,
        base_damage=100,
        damage_type=DamageType.PHYSICAL,
        rng=GameRNG(1),
        can_crit=False,
        can_dodge=True,
    )
    
    assert result.was_dodged == True
    assert result.final_damage == 0


def test_dodge_disabled_for_abilities():
    """Dodge nie działa dla umiejętności."""
    attacker = create_unit()
    defender = create_unit(dodge=1.0)
    
    result = calculate_damage(
        attacker, defender,
        base_damage=100,
        damage_type=DamageType.MAGICAL,
        rng=GameRNG(1),
        can_crit=True,
        can_dodge=True,
        is_ability=True,
    )
    
    assert result.was_dodged == False
    assert result.final_damage > 0


# ═══════════════════════════════════════════════════════════════════════════
# TEST: LIFESTEAL
# ═══════════════════════════════════════════════════════════════════════════

def test_lifesteal_calculated():
    """Lifesteal obliczany poprawnie."""
    attacker = create_unit(lifesteal=0.2)  # 20% lifesteal
    defender = create_unit(armor=0)
    
    result = calculate_damage(
        attacker, defender,
        base_damage=100,
        damage_type=DamageType.PHYSICAL,
        rng=GameRNG(42),
        can_crit=False,
        can_dodge=False,
    )
    
    assert result.lifesteal_amount == pytest.approx(20, rel=0.01)


def test_lifesteal_based_on_final_damage():
    """Lifesteal bazuje na final damage (po redukcji)."""
    attacker = create_unit(lifesteal=0.2)
    defender = create_unit(armor=100)  # 50% redukcji
    
    result = calculate_damage(
        attacker, defender,
        base_damage=100,
        damage_type=DamageType.PHYSICAL,
        rng=GameRNG(42),
        can_crit=False,
        can_dodge=False,
    )
    
    # final_damage = 50, lifesteal = 50 * 0.2 = 10
    assert result.lifesteal_amount == pytest.approx(10, rel=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# TEST: APPLY DAMAGE
# ═══════════════════════════════════════════════════════════════════════════

def test_apply_damage_reduces_hp():
    """apply_damage redukuje HP obrońcy."""
    attacker = create_unit()
    defender = create_unit(hp=500)
    
    result = DamageResult(
        raw_damage=100,
        pre_mitigation_damage=100,
        final_damage=100,
        damage_type=DamageType.PHYSICAL,
    )
    
    apply_damage(attacker, defender, result)
    
    assert defender.stats.current_hp == 400


def test_apply_damage_heals_attacker():
    """apply_damage leczy atakującego (lifesteal)."""
    attacker = create_unit(hp=500)
    attacker.stats.current_hp = 400  # uszkodzony
    defender = create_unit(hp=500)
    
    result = DamageResult(
        raw_damage=100,
        pre_mitigation_damage=100,
        final_damage=100,
        damage_type=DamageType.PHYSICAL,
        lifesteal_amount=20,
    )
    
    apply_damage(attacker, defender, result)
    
    assert attacker.stats.current_hp == 420  # healed


def test_apply_damage_kills_defender():
    """apply_damage zabija obrońcę gdy HP <= 0."""
    attacker = create_unit()
    defender = create_unit(hp=50)
    
    result = DamageResult(
        raw_damage=100,
        pre_mitigation_damage=100,
        final_damage=100,
        damage_type=DamageType.PHYSICAL,
    )
    
    apply_damage(attacker, defender, result)
    
    assert not defender.is_alive()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
