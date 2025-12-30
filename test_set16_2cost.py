#!/usr/bin/env python3
"""
Test Set 16 2-Cost Abilities

Kompleksowe testy dla 19 championów 2-cost:
- Parsing YAML
- Skalowanie z gwiazdkami (1★, 2★, 3★)
- Skalowanie ze statystykami (AD, AP, HP, etc.)
- Nowe typy efektów
- Symulacje walk 8v8

Efekty używane przez 2-cost:
- hybrid_damage, damage, splash_damage (Offensive)
- dot, chill, stun (CC/DoT)
- shield_self, shield, heal, buff (Support)
- dash, knockback, replace_attacks (Displacement/Special)
- effect_group, mana_reave, projectile_spread, multi_strike, create_zone, permanent_stack (New)
"""

import sys
import yaml
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.abilities.ability import Ability
from src.abilities.effect import EFFECT_REGISTRY, create_effect
from src.units.unit import Unit
from src.units.stats import UnitStats
from src.core.hex_coord import HexCoord
from src.simulation.simulation import Simulation, SimulationConfig


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def load_abilities():
    """Load abilities from YAML."""
    with open("data/set16_abilities.yaml") as f:
        data = yaml.safe_load(f)
    return data.get("abilities", {})


def load_champions():
    """Load champions from YAML."""
    with open("data/set16_champions.yaml") as f:
        data = yaml.safe_load(f)
    return data.get("units", {})


def create_unit_from_set16(champ_id: str, team: int = 0, star_level: int = 1, 
                           position: HexCoord = None) -> Unit:
    """Create a Unit from set16 champion data."""
    champions = load_champions()
    
    if champ_id not in champions:
        raise ValueError(f"Champion {champ_id} not found in set16_champions.yaml")
    
    champ = champions[champ_id]
    
    stats = UnitStats.from_dict({
        "hp": champ["hp"],
        "attack_damage": champ["attack_damage"],
        "ability_power": 100,
        "armor": champ["armor"],
        "magic_resist": champ["magic_resist"],
        "attack_speed": champ["attack_speed"],
        "attack_range": champ["attack_range"],
        "max_mana": champ["max_mana"],
        "start_mana": champ.get("start_mana", 0),
        "crit_chance": champ.get("crit_chance", 0.25),
        "crit_damage": champ.get("crit_damage", 1.4),
    })
    
    # Apply star level scaling
    if star_level == 2:
        stats.base_hp = int(stats.base_hp * 1.8)
        stats.base_attack_damage = int(stats.base_attack_damage * 1.5)
    elif star_level == 3:
        stats.base_hp = int(stats.base_hp * 3.24)
        stats.base_attack_damage = int(stats.base_attack_damage * 2.25)
    
    stats.current_hp = stats.get_max_hp()
    
    if position is None:
        position = HexCoord(3, 3)
    
    unit = Unit(
        id=f"{champ_id}_{team}_{star_level}",
        name=champ["name"],
        unit_type=champ_id,
        team=team,
        position=position,
        stats=stats,
        star_level=star_level,
    )
    
    unit.abilities.append(champ.get("ability", ""))
    
    return unit


def create_simulation_with_abilities():
    """Create simulation with preloaded abilities."""
    abilities = load_abilities()
    
    config = SimulationConfig(
        ticks_per_second=30,
        max_ticks=900,
        grid_width=7,
        grid_height=8
    )
    sim = Simulation(seed=42, config=config)
    
    for aid, adata in abilities.items():
        sim._ability_cache[aid] = Ability.from_dict(aid, adata)
    
    return sim


# ═══════════════════════════════════════════════════════════════════════════
# 2-COST CHAMPION LIST
# ═══════════════════════════════════════════════════════════════════════════

TWO_COST_CHAMPIONS = [
    "tristana", "teemo", "twistedfate", "sion", "aphelios", "ashe",
    "neeko", "yasuo", "reksai", "chogath", "vi", "poppy", "tryndamere",
    "graves", "xinzhao", "yorick", "orianna", "ekko", "bard"
]

TWO_COST_ABILITIES = {
    "tristana": "buster_shot",
    "teemo": "toxic_dart",
    "twistedfate": "stacked_deck",
    "sion": "soul_furnace",
    "aphelios": "incendiary_onslaught",
    "ashe": "true_ice_arrow",
    "neeko": "pop_blossom",
    "yasuo": "sweeping_blade",
    "reksai": "burrow",
    "chogath": "rupture",
    "vi": "relentless_force",
    "poppy": "hammer_shock",
    "tryndamere": "undying_rage",
    "graves": "collateral_damage",
    "xinzhao": "three_talon_strike",
    "yorick": "mourning_mist",
    "orianna": "command_protect",
    "ekko": "parallel_convergence",
    "bard": "travelers_call",
}

# Effect composition for each 2-cost champion
TWO_COST_EFFECTS = {
    "tristana": ["hybrid_damage", "knockback"],
    "teemo": ["damage", "dot"],
    "twistedfate": ["projectile_spread"],  # + passive on_attack_bonus_damage
    "sion": ["shield_self"],  # + passive permanent_stack, on_expire_or_break
    "aphelios": ["replace_attacks"],  # + passive multi_target_attack
    "ashe": ["hybrid_damage", "chill"],
    "neeko": ["dash", "shield_self", "damage", "chill"],
    "yasuo": ["dash", "hybrid_damage"],
    "reksai": ["dash", "hybrid_damage", "replace_attacks"],
    "chogath": ["heal", "effect_group"],  # effect_group contains stun, damage, percent_hp_damage
    "vi": ["shield_self", "damage"],  # + every_n_casts modifier
    "poppy": ["shield_self", "damage", "stun"],  # + share mechanic
    "tryndamere": ["buff", "replace_attacks"],  # + armor_ignore_condition
    "graves": ["hybrid_damage"],  # + passive cone_attack
    "xinzhao": ["multi_strike"],  # contains damage, heal, stun
    "yorick": ["heal", "damage", "percent_hp_damage", "chill", "mana_reave"],
    "orianna": ["damage", "splash_damage", "shield"],
    "ekko": ["create_zone", "replace_attacks"],
    "bard": ["multi_hit"],  # + bonus_hits_per_3star
}


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1: ABILITY PARSING
# ═══════════════════════════════════════════════════════════════════════════

def test_ability_parsing():
    """Test that all 2-cost abilities parse correctly."""
    print("\n" + "=" * 70)
    print(" TEST 1: ABILITY PARSING")
    print("=" * 70)
    
    abilities = load_abilities()
    passed = 0
    failed = 0
    
    for champ, ability_id in TWO_COST_ABILITIES.items():
        if ability_id not in abilities:
            print(f"  ❌ {champ}: {ability_id} not found in YAML")
            failed += 1
            continue
        
        try:
            ability = Ability.from_dict(ability_id, abilities[ability_id])
            effect_count = len(ability.effects)
            print(f"  ✅ {champ}: {ability_id} ({effect_count} effects)")
            passed += 1
        except Exception as e:
            print(f"  ❌ {champ}: {ability_id} - {e}")
            failed += 1
    
    print(f"\n  Passed: {passed}/19")
    return failed == 0


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2: STAR LEVEL SCALING
# ═══════════════════════════════════════════════════════════════════════════

def test_star_scaling():
    """Test that ability values scale with star level."""
    print("\n" + "=" * 70)
    print(" TEST 2: STAR LEVEL SCALING")
    print("=" * 70)
    
    abilities = load_abilities()
    
    # Test a few abilities with clear value arrays
    test_cases = [
        ("buster_shot", "hybrid_damage", "ad_value", [250, 375, 565]),
        ("toxic_dart", "damage", "value", [125, 185, 285]),
        ("pop_blossom", "shield_self", "value", [400, 500, 600]),
        ("rupture", "heal", "value", [180, 200, 250]),
        ("travelers_call", "multi_hit", "value", [105, 160, 240]),
    ]
    
    passed = 0
    for ability_id, effect_type, field, expected in test_cases:
        try:
            ability = Ability.from_dict(ability_id, abilities[ability_id])
            
            # Find the effect
            for effect in ability.effects:
                if effect.effect_type == effect_type:
                    value = getattr(effect, field, None)
                    if value is None and hasattr(effect, 'value'):
                        value = effect.value
                    
                    if value == expected:
                        print(f"  ✅ {ability_id} {effect_type}.{field}: {value}")
                        passed += 1
                    else:
                        print(f"  ⚠️ {ability_id} {effect_type}.{field}: got {value}, expected {expected}")
                    break
        except Exception as e:
            print(f"  ❌ {ability_id}: {e}")
    
    print(f"\n  Passed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3: NEW EFFECT TYPES
# ═══════════════════════════════════════════════════════════════════════════

def test_new_effect_types():
    """Test that new 2-cost effect types work."""
    print("\n" + "=" * 70)
    print(" TEST 3: NEW EFFECT TYPES")
    print("=" * 70)
    
    new_effects = [
        "effect_group", "mana_reave", "projectile_spread",
        "multi_strike", "create_zone", "permanent_stack"
    ]
    
    passed = 0
    for effect_name in new_effects:
        if effect_name in EFFECT_REGISTRY:
            print(f"  ✅ {effect_name} registered")
            passed += 1
        else:
            print(f"  ❌ {effect_name} NOT in registry")
    
    # Test instantiation
    print("\n  Testing instantiation:")
    
    test_data = [
        ("effect_group", {"delay": 15, "aoe_radius": 2, "effects": []}),
        ("mana_reave", {"value": 20, "duration": "next_cast"}),
        ("projectile_spread", {"projectile_count": 3, "value": 70}),
        ("multi_strike", {"hits": 3, "per_hit": [], "on_final_hit": []}),
        ("create_zone", {"radius": 1, "duration": 90}),
        ("permanent_stack", {"stat": "max_hp", "trigger": "on_kill", "value": 20}),
    ]
    
    for effect_type, data in test_data:
        try:
            effect = create_effect(effect_type, data)
            print(f"  ✅ {effect_type} instantiated: {effect.effect_type}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {effect_type}: {e}")
    
    print(f"\n  Passed: {passed}/12")
    return passed == 12


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4: INDIVIDUAL ABILITY EFFECTS
# ═══════════════════════════════════════════════════════════════════════════

def test_individual_effects():
    """Test each 2-cost champion's ability effects."""
    print("\n" + "=" * 70)
    print(" TEST 4: INDIVIDUAL ABILITY EFFECTS")
    print("=" * 70)
    
    sim = create_simulation_with_abilities()
    abilities = load_abilities()
    
    results = []
    
    for champ_id in TWO_COST_CHAMPIONS:
        ability_id = TWO_COST_ABILITIES.get(champ_id)
        if not ability_id:
            continue
        
        try:
            # Create units
            caster = create_unit_from_set16(champ_id, team=0, star_level=2)
            target = create_unit_from_set16("sion", team=1, star_level=1)  # Tanky target
            
            # Register units
            sim.add_unit(caster)
            sim.add_unit(target)
            
            # Get ability
            ability = sim._ability_cache.get(ability_id)
            if not ability:
                continue
            
            # Apply effects
            for effect in ability.effects:
                try:
                    result = effect.apply(caster, target, caster.star_level, sim)
                    results.append({
                        "champ": champ_id,
                        "effect": effect.effect_type,
                        "success": result.success,
                        "value": result.value,
                    })
                    print(f"  ✅ {champ_id}: {effect.effect_type} = {result.value:.1f}")
                except Exception as e:
                    print(f"  ❌ {champ_id}: {effect.effect_type} - {e}")
                    results.append({
                        "champ": champ_id,
                        "effect": effect.effect_type,
                        "success": False,
                        "error": str(e),
                    })
            
            # Cleanup
            sim.units.remove(caster)
            sim.units.remove(target)
            
        except Exception as e:
            print(f"  ❌ {champ_id}: {e}")
    
    passed = sum(1 for r in results if r.get("success"))
    print(f"\n  Passed: {passed}/{len(results)}")
    return passed == len(results)


# ═══════════════════════════════════════════════════════════════════════════
# TEST 5: 8v8 BATTLE SIMULATION
# ═══════════════════════════════════════════════════════════════════════════

def test_8v8_battle():
    """Test full 8v8 battle with 2-cost champions."""
    print("\n" + "=" * 70)
    print(" TEST 5: 8v8 BATTLE SIMULATION (2-Cost Only)")
    print("=" * 70)
    
    sim = create_simulation_with_abilities()
    
    # Team 0 positions
    team0 = [
        ("tristana", HexCoord(0, 0), 2),
        ("teemo", HexCoord(1, 0), 1),
        ("ashe", HexCoord(2, 0), 2),
        ("graves", HexCoord(3, 0), 1),
        ("sion", HexCoord(0, 1), 2),
        ("chogath", HexCoord(1, 1), 1),
        ("vi", HexCoord(2, 1), 2),
        ("poppy", HexCoord(3, 1), 1),
    ]
    
    # Team 1 positions
    team1 = [
        ("yasuo", HexCoord(0, 6), 2),
        ("reksai", HexCoord(1, 6), 1),
        ("neeko", HexCoord(2, 6), 2),
        ("ekko", HexCoord(3, 6), 1),
        ("xinzhao", HexCoord(0, 7), 2),
        ("tryndamere", HexCoord(1, 7), 1),
        ("yorick", HexCoord(2, 7), 2),
        ("orianna", HexCoord(3, 7), 1),
    ]
    
    team0_units = []
    team1_units = []
    
    for champ_id, pos, star in team0:
        try:
            unit = create_unit_from_set16(champ_id, team=0, star_level=star, position=pos)
            if sim.grid.is_valid(pos) and sim.grid.is_walkable(pos):
                sim.add_unit(unit)
                team0_units.append(unit)
        except Exception as e:
            print(f"  ⚠️ Failed to create {champ_id}: {e}")
    
    for champ_id, pos, star in team1:
        try:
            unit = create_unit_from_set16(champ_id, team=1, star_level=star, position=pos)
            if sim.grid.is_valid(pos) and sim.grid.is_walkable(pos):
                sim.add_unit(unit)
                team1_units.append(unit)
        except Exception as e:
            print(f"  ⚠️ Failed to create {champ_id}: {e}")
    
    print(f"  Team 0: {len(team0_units)} units")
    print(f"  Team 1: {len(team1_units)} units")
    
    # Run simulation
    result = sim.run()
    
    print(f"\n  Battle Result:")
    print(f"    Duration: {result.get('duration_seconds', 0):.1f}s")
    print(f"    Ticks: {result.get('ticks_elapsed', 0)}")
    print(f"    Winner: Team {result.get('winner_team', 'None')}")
    
    # Count ability casts
    events = sim.get_log().get("events", [])
    casts = [e for e in events if e.get("type") == "ABILITY_CAST"]
    print(f"    Ability Casts: {len(casts)}")
    
    # Count effects
    effect_events = [e for e in events if e.get("type") == "EFFECT_APPLIED"]
    print(f"    Effects Applied: {len(effect_events)}")
    
    # Per-champion casts
    cast_counts = {}
    for cast in casts:
        ability_id = cast.get("data", {}).get("ability_id", "unknown")
        cast_counts[ability_id] = cast_counts.get(ability_id, 0) + 1
    
    print(f"\n  Casts per ability:")
    for ability_id, count in sorted(cast_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    - {ability_id}: {count}")
    
    return result.get("winner_team") is not None


# ═══════════════════════════════════════════════════════════════════════════
# TEST 6: EFFECT COMPOSITION
# ═══════════════════════════════════════════════════════════════════════════

def test_effect_composition():
    """Verify each 2-cost uses expected effects."""
    print("\n" + "=" * 70)
    print(" TEST 6: EFFECT COMPOSITION")
    print("=" * 70)
    
    abilities = load_abilities()
    
    passed = 0
    for champ_id, expected_effects in TWO_COST_EFFECTS.items():
        ability_id = TWO_COST_ABILITIES.get(champ_id)
        if not ability_id or ability_id not in abilities:
            continue
        
        ability = Ability.from_dict(ability_id, abilities[ability_id])
        actual_effects = [e.effect_type for e in ability.effects]
        
        # Check if all expected effects are present
        missing = [e for e in expected_effects if e not in actual_effects]
        
        if not missing:
            print(f"  ✅ {champ_id}: {actual_effects}")
            passed += 1
        else:
            print(f"  ⚠️ {champ_id}: has {actual_effects}, missing {missing}")
    
    print(f"\n  Passed: {passed}/{len(TWO_COST_EFFECTS)}")
    return passed == len(TWO_COST_EFFECTS)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print(" TFT SET 16 - 2-COST ABILITY TESTS")
    print("=" * 70)
    
    results = {
        "Ability Parsing": test_ability_parsing(),
        "Star Level Scaling": test_star_scaling(),
        "New Effect Types": test_new_effect_types(),
        "Individual Effects": test_individual_effects(),
        "8v8 Battle": test_8v8_battle(),
        "Effect Composition": test_effect_composition(),
    }
    
    print("\n" + "=" * 70)
    print(" SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    if all(results.values()):
        print("\n  🎉 ALL TESTS PASSED!")
    else:
        print("\n  ⚠️ Some tests failed")
    
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
