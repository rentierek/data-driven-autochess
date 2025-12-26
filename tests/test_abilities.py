"""
Testy dla systemu umiejętności.

Testuje:
- Skalowanie wartości (star values)
- Skalowanie ze statystykami
- Wszystkie typy efektów
- Ability parsing z YAML
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.abilities import (
    Ability, ProjectileConfig, AoEConfig,
    get_star_value, calculate_scaled_value, ScalingConfig,
    DamageEffect, HealEffect, ShieldEffect, StunEffect,
    BurnEffect, WoundEffect, DoTEffect, SlowEffect,
    ExecuteEffect, BuffEffect,
    EFFECT_REGISTRY, create_effect, parse_effects,
    DamageType,
)
from src.units.unit import Unit
from src.units.stats import UnitStats
from src.core.hex_coord import HexCoord


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

def create_test_unit(
    unit_id: str = "test", 
    team: int = 0,
    hp: float = 500,
    ad: float = 100,
    ap: float = 100,
    armor: float = 50,
    mr: float = 50,
) -> Unit:
    """Tworzy jednostkę testową."""
    stats = UnitStats(
        base_hp=hp,
        base_attack_damage=ad,
        base_ability_power=ap,
        base_armor=armor,
        base_magic_resist=mr,
    )
    stats.current_hp = hp
    return Unit(
        id=unit_id,
        name=f"Unit_{unit_id}",
        unit_type="test",
        team=team,
        position=HexCoord(0, 0),
        stats=stats,
    )


# ═══════════════════════════════════════════════════════════════════════════
# TEST: STAR VALUE SCALING
# ═══════════════════════════════════════════════════════════════════════════

def test_star_value_list():
    """Lista wartości per star."""
    assert get_star_value([100, 200, 400], 1) == 100
    assert get_star_value([100, 200, 400], 2) == 200
    assert get_star_value([100, 200, 400], 3) == 400


def test_star_value_single():
    """Pojedyncza wartość dla wszystkich star."""
    assert get_star_value(150, 1) == 150
    assert get_star_value(150, 2) == 150
    assert get_star_value(150, 3) == 150


def test_star_value_out_of_bounds():
    """Star poza zakresem używa ostatniej wartości."""
    assert get_star_value([100, 200], 5) == 200  # clamp to last


# ═══════════════════════════════════════════════════════════════════════════
# TEST: STAT SCALING
# ═══════════════════════════════════════════════════════════════════════════

def test_scaling_with_ap():
    """Skalowanie z AP: value × (AP/100)."""
    caster = create_test_unit(ap=150)
    
    # 200 base, 150 AP → 200 × 1.5 = 300
    result = calculate_scaled_value(200, "ap", 1, caster) 
    assert result == pytest.approx(300, rel=0.01)


def test_scaling_with_ad():
    """Skalowanie z AD."""
    caster = create_test_unit(ad=80)
    
    # 100 base, 80 AD → 100 × 0.8 = 80
    result = calculate_scaled_value(100, "ad", 1, caster)
    assert result == pytest.approx(80, rel=0.01)


def test_scaling_with_armor():
    """Skalowanie z Armor."""
    caster = create_test_unit(armor=200)
    
    # 100 base, 200 armor → 100 × 2.0 = 200
    result = calculate_scaled_value(100, "armor", 1, caster)
    assert result == pytest.approx(200, rel=0.01)


def test_scaling_none():
    """Brak skalowania = surowa wartość."""
    caster = create_test_unit(ap=999)
    
    result = calculate_scaled_value(100, None, 1, caster)
    assert result == 100


def test_scaling_with_star_and_stat():
    """Kombinacja star value i stat scaling."""
    caster = create_test_unit(ap=120)
    
    # Star 2 = 350, AP 120 → 350 × 1.2 = 420
    result = calculate_scaled_value([200, 350, 600], "ap", 2, caster)
    assert result == pytest.approx(420, rel=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# TEST: EFFECT REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

def test_effect_registry_contains_all():
    """Registry zawiera wszystkie 19 typów efektów."""
    expected = [
        # Offensive
        "damage", "dot", "burn", "execute", "sunder", "shred",
        # CC
        "stun", "slow", "silence", "disarm",
        # Support
        "heal", "shield", "wound", "buff", "mana_grant", "cleanse",
        # Displacement
        "knockback", "pull", "dash",
    ]
    assert len(EFFECT_REGISTRY) == 19
    for effect_type in expected:
        assert effect_type in EFFECT_REGISTRY, f"Missing: {effect_type}"


def test_create_effect_damage():
    """Tworzenie DamageEffect z dict."""
    data = {
        "damage_type": "magical",
        "value": [200, 350, 600],
        "scaling": "ap",
    }
    effect = create_effect("damage", data)
    
    assert isinstance(effect, DamageEffect)
    assert effect.damage_type == DamageType.MAGICAL
    assert effect.scaling == "ap"


def test_create_effect_unknown_raises():
    """Nieznany typ efektu rzuca wyjątek."""
    with pytest.raises(ValueError):
        create_effect("unknown_effect", {})


# ═══════════════════════════════════════════════════════════════════════════
# TEST: PARSE EFFECTS
# ═══════════════════════════════════════════════════════════════════════════

def test_parse_effects_multiple():
    """Parsowanie wielu efektów."""
    data = [
        {"type": "damage", "damage_type": "physical", "value": 100},
        {"type": "stun", "duration": 30},
        {"type": "burn", "value": 20, "duration": 90},
    ]
    effects = parse_effects(data)
    
    assert len(effects) == 3
    assert effects[0].effect_type == "damage"
    assert effects[1].effect_type == "stun"
    assert effects[2].effect_type == "burn"


# ═══════════════════════════════════════════════════════════════════════════
# TEST: ABILITY CLASS
# ═══════════════════════════════════════════════════════════════════════════

def test_ability_from_dict():
    """Tworzenie Ability z dict."""
    data = {
        "name": "Fireball",
        "mana_cost": 80,
        "cast_time": [20, 18, 15],
        "target_type": "current_target",
        "effects": [
            {"type": "damage", "damage_type": "magical", "value": [200, 350, 600]},
        ],
    }
    ability = Ability.from_dict("fireball", data)
    
    assert ability.id == "fireball"
    assert ability.name == "Fireball"
    assert ability.mana_cost == 80
    assert len(ability.effects) == 1


def test_ability_cast_time_per_star():
    """Cast time różni się per star."""
    ability = Ability(
        id="test",
        name="Test",
        cast_time=[20, 15, 10],
        effects=[],
    )
    
    assert ability.get_cast_time(1) == 20
    assert ability.get_cast_time(2) == 15
    assert ability.get_cast_time(3) == 10


def test_ability_with_projectile():
    """Ability z projectile config."""
    data = {
        "name": "Arrow",
        "projectile": {"speed": 4, "homing": True},
        "effects": [],
    }
    ability = Ability.from_dict("arrow", data)
    
    assert ability.projectile is not None
    assert ability.projectile.speed == 4
    assert ability.projectile.homing == True


def test_ability_with_aoe():
    """Ability z AoE config."""
    data = {
        "name": "Explosion",
        "aoe": {"type": "circle", "radius": [1, 2, 2]},
        "effects": [],
    }
    ability = Ability.from_dict("explosion", data)
    
    assert ability.aoe is not None
    assert ability.aoe.aoe_type == "circle"
    assert ability.get_aoe_radius(1) == 1
    assert ability.get_aoe_radius(3) == 2


# ═══════════════════════════════════════════════════════════════════════════
# TEST: UNIT DEBUFF METHODS
# ═══════════════════════════════════════════════════════════════════════════

def test_unit_add_shield():
    """Unit.add_shield dodaje tarczę."""
    unit = create_test_unit()
    unit.add_shield(200, 90)
    
    assert unit.shield_hp == 200
    assert unit.shield_remaining_ticks == 90


def test_unit_add_wound():
    """Unit.add_wound dodaje wound."""
    unit = create_test_unit()
    unit.add_wound(50, 150)
    
    assert unit.wound_percent == 50
    assert unit.wound_remaining_ticks == 150


def test_unit_add_burn():
    """Unit.add_burn dodaje burn."""
    unit = create_test_unit()
    unit.add_burn(30, 90, "source_id")
    
    assert len(unit.burns) == 1
    assert unit.burns[0]["dps"] == 30


def test_unit_add_slow():
    """Unit.add_slow dodaje slow."""
    unit = create_test_unit()
    unit.add_slow(40, 60)
    
    assert unit.slow_percent == 40
    assert unit.slow_remaining_ticks == 60


def test_unit_tick_debuffs_expires():
    """tick_debuffs wygasza efekty."""
    unit = create_test_unit()
    unit.add_wound(50, 2)  # 2 ticki
    
    unit.tick_debuffs()  # 1 pozostał
    assert unit.wound_percent == 50
    
    unit.tick_debuffs()  # 0 - wygasa
    assert unit.wound_percent == 0


def test_unit_tick_debuffs_burn_damage():
    """tick_debuffs zadaje burn damage."""
    unit = create_test_unit(hp=500)
    unit.add_burn(30, 30, "src")  # 30 dps for 1s
    
    # Burn zadaje dps/tps per tick
    damage = unit.tick_debuffs(ticks_per_second=30)
    
    assert damage == pytest.approx(1.0, rel=0.1)  # 30/30 = 1 per tick
    assert unit.stats.current_hp < 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
