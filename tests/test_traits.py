"""
Testy systemu traitów.

Testuje:
- Unikalne liczenie jednostek (2x ta sama = 1)
- Aktywację progów (2/4/6)
- Efekty stat_bonus
- Triggery on_battle_start, on_tick, on_hp_threshold
"""

import pytest
from src.traits import Trait, TraitThreshold, TraitEffect, TraitTrigger, TriggerType, EffectTarget
from src.traits import TraitManager
from src.core.hex_coord import HexCoord
from src.units.unit import Unit
from src.units.stats import UnitStats
from typing import Dict, Any


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

def make_unit_config(unit_id: str, traits: list, **overrides) -> Dict[str, Any]:
    """Tworzy minimalną konfigurację jednostki."""
    config = {
        "id": unit_id,
        "name": unit_id.title(),
        "hp": 1000,
        "attack_damage": 50,
        "armor": 20,
        "mr": 20,
        "attack_speed": 1.0,
        "attack_range": 1,
        "ability_power": 0,
        "mana": 0,
        "max_mana": 100,
        "crit_chance": 0.0,
        "dodge_chance": 0.0,
        "traits": traits,
    }
    config.update(overrides)
    return config


def make_unit(unit_id: str, team: int, traits: list, position=(0, 0)) -> Unit:
    """Tworzy jednostkę z traitami."""
    config = make_unit_config(unit_id, traits)
    return Unit.from_config(config, team=team, position=HexCoord(*position))


# ═══════════════════════════════════════════════════════════════════════════
# TRAIT PARSING TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_trait_from_dict():
    """Trait.from_dict parsuje YAML poprawnie."""
    data = {
        "name": "Knight",
        "description": "Knights gain armor.",
        "thresholds": {
            2: {
                "trigger": "on_battle_start",
                "effects": [
                    {"type": "stat_bonus", "stat": "armor", "value": 20, "target": "holders"}
                ]
            },
            4: {
                "trigger": "on_battle_start",
                "effects": [
                    {"type": "stat_bonus", "stat": "armor", "value": 40, "target": "holders"}
                ]
            }
        }
    }
    
    trait = Trait.from_dict("knight", data)
    
    assert trait.id == "knight"
    assert trait.name == "Knight"
    assert trait.description == "Knights gain armor."
    assert 2 in trait.thresholds
    assert 4 in trait.thresholds
    assert trait.thresholds[2].count == 2
    assert trait.thresholds[4].count == 4


def test_trait_get_active_threshold():
    """get_active_threshold zwraca najwyższy aktywny próg."""
    data = {
        "name": "Test",
        "thresholds": {
            2: {"effects": []},
            4: {"effects": []},
            6: {"effects": []},
        }
    }
    trait = Trait.from_dict("test", data)
    
    # 0-1 unit: no threshold
    assert trait.get_active_threshold(0) is None
    assert trait.get_active_threshold(1) is None
    
    # 2-3 units: threshold 2
    assert trait.get_active_threshold(2).count == 2
    assert trait.get_active_threshold(3).count == 2
    
    # 4-5 units: threshold 4
    assert trait.get_active_threshold(4).count == 4
    assert trait.get_active_threshold(5).count == 4
    
    # 6+ units: threshold 6
    assert trait.get_active_threshold(6).count == 6
    assert trait.get_active_threshold(10).count == 6


def test_trait_trigger_from_dict():
    """TraitTrigger parsuje różne typy triggerów."""
    # on_battle_start (default)
    trigger = TraitTrigger.from_dict({})
    assert trigger.trigger_type == TriggerType.ON_BATTLE_START
    
    # on_hp_threshold
    trigger = TraitTrigger.from_dict({
        "trigger": "on_hp_threshold",
        "trigger_params": {"threshold": 0.5}
    })
    assert trigger.trigger_type == TriggerType.ON_HP_THRESHOLD
    assert trigger.params["threshold"] == 0.5
    
    # on_time
    trigger = TraitTrigger.from_dict({
        "trigger": "on_time",
        "trigger_params": {"ticks": 300}
    })
    assert trigger.trigger_type == TriggerType.ON_TIME
    assert trigger.params["ticks"] == 300


def test_trait_effect_from_dict():
    """TraitEffect parsuje efekty z YAML."""
    effect = TraitEffect.from_dict({
        "type": "stat_bonus",
        "stat": "armor",
        "value": 25,
        "target": "holders"
    })
    
    assert effect.effect_type == "stat_bonus"
    assert effect.target == EffectTarget.HOLDERS
    assert effect.value == 25
    assert effect.params["stat"] == "armor"


# ═══════════════════════════════════════════════════════════════════════════
# UNIQUE UNIT COUNTING TESTS
# ═══════════════════════════════════════════════════════════════════════════

class MockSimulation:
    """Mock symulacji dla testów TraitManager."""
    
    def __init__(self):
        self.units = []
        self.tick = 0
        self.grid = MockGrid()
        self.logger = MockLogger()


class MockGrid:
    def get_unit_at(self, pos):
        return None


class MockLogger:
    def log_event(self, *args, **kwargs):
        pass


def test_unique_unit_counting():
    """2x ta sama jednostka = 1 do traitu."""
    sim = MockSimulation()
    manager = TraitManager(sim)
    
    # Add 2x warrior (same base_id)
    warrior1 = make_unit("warrior", team=0, traits=["knight"], position=(0, 0))
    warrior2 = make_unit("warrior", team=0, traits=["knight"], position=(1, 0))
    
    sim.units = [warrior1, warrior2]
    
    # Count traits
    manager.count_traits()
    
    # Should be 1 (unique), not 2
    assert manager.get_trait_count(0, "knight") == 1


def test_different_units_count_separately():
    """Różne jednostki liczą się osobno."""
    sim = MockSimulation()
    manager = TraitManager(sim)
    
    warrior = make_unit("warrior", team=0, traits=["knight"], position=(0, 0))
    guardian = make_unit("guardian", team=0, traits=["knight"], position=(1, 0))
    
    sim.units = [warrior, guardian]
    
    manager.count_traits()
    
    # Should be 2 (different base_ids)
    assert manager.get_trait_count(0, "knight") == 2


def test_trait_threshold_activation():
    """Próg aktywuje się przy wystarczającej liczbie jednostek."""
    sim = MockSimulation()
    manager = TraitManager(sim)
    
    # Load simple trait
    manager.load_traits({
        "knight": {
            "name": "Knight",
            "thresholds": {
                2: {"effects": []},
                4: {"effects": []},
            }
        }
    })
    
    # 1 unit - no threshold
    unit1 = make_unit("warrior", team=0, traits=["knight"], position=(0, 0))
    sim.units = [unit1]
    manager.count_traits()
    assert manager.get_active_threshold(0, "knight") is None
    
    # 2 different units - threshold 2
    unit2 = make_unit("guardian", team=0, traits=["knight"], position=(1, 0))
    sim.units = [unit1, unit2]
    manager.count_traits()
    assert manager.get_active_threshold(0, "knight") == 2
    
    # 4 different units - threshold 4
    unit3 = make_unit("paladin", team=0, traits=["knight"], position=(2, 0))
    unit4 = make_unit("crusader", team=0, traits=["knight"], position=(3, 0))
    sim.units = [unit1, unit2, unit3, unit4]
    manager.count_traits()
    assert manager.get_active_threshold(0, "knight") == 4


# ═══════════════════════════════════════════════════════════════════════════
# EFFECT APPLICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_stat_bonus_holders():
    """stat_bonus z target='holders' działa tylko dla posiadaczy traitu."""
    sim = MockSimulation()
    manager = TraitManager(sim)
    
    # Load trait that gives 50 armor to holders
    manager.load_traits({
        "knight": {
            "name": "Knight",
            "thresholds": {
                2: {
                    "trigger": "on_battle_start",
                    "effects": [
                        {"type": "stat_bonus", "stat": "armor", "value": 50, "target": "holders"}
                    ]
                }
            }
        }
    })
    
    # 2 knights, 1 non-knight
    knight1 = make_unit("warrior", team=0, traits=["knight"], position=(0, 0))
    knight2 = make_unit("guardian", team=0, traits=["knight"], position=(1, 0))
    mage = make_unit("mage", team=0, traits=["sorcerer"], position=(2, 0))
    
    starting_armor_knight1 = knight1.stats.base_armor
    starting_armor_knight2 = knight2.stats.base_armor
    starting_armor_mage = mage.stats.base_armor
    
    sim.units = [knight1, knight2, mage]
    
    # Activate traits
    manager.on_battle_start()
    
    # Knights should have +50 armor
    assert knight1.stats.base_armor == starting_armor_knight1 + 50
    assert knight2.stats.base_armor == starting_armor_knight2 + 50
    
    # Mage should NOT have bonus
    assert mage.stats.base_armor == starting_armor_mage


def test_stat_bonus_team():
    """stat_bonus z target='team' działa dla całego teamu."""
    sim = MockSimulation()
    manager = TraitManager(sim)
    
    # Trait gives 30 MR to whole team
    manager.load_traits({
        "mystic": {
            "name": "Mystic",
            "thresholds": {
                2: {
                    "trigger": "on_battle_start",
                    "effects": [
                        {"type": "stat_bonus", "stat": "mr", "value": 30, "target": "team"}
                    ]
                }
            }
        }
    })
    
    mystic1 = make_unit("shaman", team=0, traits=["mystic"], position=(0, 0))
    mystic2 = make_unit("druid", team=0, traits=["mystic"], position=(1, 0))
    warrior = make_unit("warrior", team=0, traits=["knight"], position=(2, 0))
    
    starting_mr = warrior.stats.base_magic_resist
    
    sim.units = [mystic1, mystic2, warrior]
    manager.on_battle_start()
    
    # ALL team 0 units should have +30 MR
    assert mystic1.stats.base_magic_resist == 20 + 30
    assert mystic2.stats.base_magic_resist == 20 + 30
    assert warrior.stats.base_magic_resist == starting_mr + 30


def test_thresholds_replace_not_stack():
    """Wyższy próg ZASTĘPUJE niższy, nie stackuje."""
    sim = MockSimulation()
    manager = TraitManager(sim)
    
    manager.load_traits({
        "brawler": {
            "name": "Brawler",
            "thresholds": {
                2: {
                    "trigger": "on_battle_start",
                    "effects": [
                        {"type": "stat_bonus", "stat": "hp", "value": 200, "target": "holders"}
                    ]
                },
                4: {
                    "trigger": "on_battle_start",
                    "effects": [
                        {"type": "stat_bonus", "stat": "hp", "value": 400, "target": "holders"}
                    ]
                }
            }
        }
    })
    
    # 4 brawlers
    units = [
        make_unit(f"brawler{i}", team=0, traits=["brawler"], position=(i, 0))
        for i in range(4)
    ]
    
    starting_hp = units[0].stats.base_hp
    sim.units = units
    manager.on_battle_start()
    
    # Should have +400 HP (threshold 4), NOT +200+400=600
    assert units[0].stats.base_hp == starting_hp + 400


# ═══════════════════════════════════════════════════════════════════════════
# TIME-BASED TRIGGER TESTS
# ═══════════════════════════════════════════════════════════════════════════

def test_on_time_trigger():
    """on_time trigger aktywuje się dokładnie po X tickach."""
    sim = MockSimulation()
    manager = TraitManager(sim)
    
    manager.load_traits({
        "ascended": {
            "name": "Ascended",
            "thresholds": {
                2: {
                    "trigger": "on_time",
                    "trigger_params": {"ticks": 100},
                    "effects": [
                        {"type": "stat_bonus", "stat": "ad", "value": 50, "target": "holders"}
                    ]
                }
            }
        }
    })
    
    unit1 = make_unit("celestial1", team=0, traits=["ascended"], position=(0, 0))
    unit2 = make_unit("celestial2", team=0, traits=["ascended"], position=(1, 0))
    
    starting_ad = unit1.stats.base_attack_damage
    sim.units = [unit1, unit2]
    
    # Battle start - doesn't trigger on_time
    manager.on_battle_start()
    assert unit1.stats.base_attack_damage == starting_ad  # No change yet
    
    # Tick 50 - not yet
    sim.tick = 50
    manager.on_tick(50)
    assert unit1.stats.base_attack_damage == starting_ad
    
    # Tick 100 - should trigger!
    sim.tick = 100
    manager.on_tick(100)
    assert unit1.stats.base_attack_damage == starting_ad + 50


def test_on_interval_trigger():
    """on_interval trigger aktywuje się co X ticków (stacking)."""
    sim = MockSimulation()
    manager = TraitManager(sim)
    
    manager.load_traits({
        "machine": {
            "name": "Machine",
            "thresholds": {
                2: {
                    "trigger": "on_interval",
                    "trigger_params": {"interval": 30},
                    "effects": [
                        {"type": "stat_bonus", "stat": "attack_speed", "value": 0.1, "target": "holders"}
                    ]
                }
            }
        }
    })
    
    unit1 = make_unit("robot1", team=0, traits=["machine"], position=(0, 0))
    unit2 = make_unit("robot2", team=0, traits=["machine"], position=(1, 0))
    
    starting_as = unit1.stats.base_attack_speed
    sim.units = [unit1, unit2]
    manager.on_battle_start()  # Count traits
    
    # Tick 0 - doesn't trigger (tick > 0 check)
    manager.on_tick(0)
    assert unit1.stats.base_attack_speed == starting_as
    
    # Tick 30 - first trigger
    manager.on_tick(30)
    assert unit1.stats.base_attack_speed == pytest.approx(starting_as + 0.1)
    
    # Tick 60 - second trigger (stacking)
    manager.on_tick(60)
    assert unit1.stats.base_attack_speed == pytest.approx(starting_as + 0.2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
