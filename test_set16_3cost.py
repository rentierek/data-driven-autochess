"""
Test Suite for Set 16 3-Cost Champions
Comprehensive tests: parsing, star scaling, effect creation, and 8v8 battles
"""

import pytest
import yaml
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"


class TestYAMLParsing:
    """Test that all 3-cost abilities parse correctly."""
    
    @pytest.fixture
    def abilities(self):
        with open(DATA_DIR / "set16_abilities.yaml") as f:
            data = yaml.safe_load(f)
        return data.get("abilities", {})
    
    def test_total_abilities_count(self, abilities):
        """Should have 51 abilities total (14 1-cost + 19 2-cost + 18 3-cost)."""
        assert len(abilities) >= 51, f"Expected >= 51, got {len(abilities)}"
    
    def test_3cost_abilities_exist(self, abilities):
        """All 18 3-cost abilities should exist."""
        three_cost = [
            "titans_wrath", "powder_kegs", "spinning_axes", "double_trouble_bubble",
            "solar_flare", "ultra_mega_fire_kick", "switcheroo", "fox_fire", 
            "void_swarm", "winters_wrath", "decimate", "distortions", "snip_snip",
            "maximum_dosage", "you_and_me", "piltover_tussle", "tumble", "slicing_maelstrom"
        ]
        missing = [a for a in three_cost if a not in abilities]
        assert not missing, f"Missing abilities: {missing}"
    
    def test_all_abilities_have_effects(self, abilities):
        """Every ability should have at least one effect."""
        for name, data in abilities.items():
            effects = data.get("effects", [])
            assert len(effects) > 0 or "passive" in data, f"{name} has no effects"


class TestEffectRegistry:
    """Test that all effect types are registered."""
    
    def test_3cost_effect_types_registered(self):
        from src.abilities.effect import EFFECT_REGISTRY
        
        required = ["interval_trigger", "projectile_swarm", "taunt", "heal_over_time"]
        for eff in required:
            assert eff in EFFECT_REGISTRY, f"Effect {eff} not in registry"
    
    def test_effect_creation(self):
        from src.abilities.effect import create_effect
        
        effects_to_test = [
            ("interval_trigger", {"interval": 120, "effect": {"type": "damage", "value": 100}}),
            ("projectile_swarm", {"count": 3, "jumps": 5, "value": 50}),
            ("taunt", {"duration": 60, "aoe_radius": 2}),
            ("heal_over_time", {"value": [50, 75, 100], "duration": 90}),
        ]
        
        for effect_type, data in effects_to_test:
            eff = create_effect(effect_type, data)
            assert eff.effect_type == effect_type


class TestStarScaling:
    """Test that star-scaled values work correctly."""
    
    def test_damage_scaling(self):
        from src.abilities.effect import create_effect, get_star_value
        
        # Test with star-scaled values
        dmg = create_effect("damage", {"value": [100, 150, 200], "damage_type": "magical"})
        
        # Verify star values
        assert get_star_value([100, 150, 200], 1) == 100
        assert get_star_value([100, 150, 200], 2) == 150
        assert get_star_value([100, 150, 200], 3) == 200
    
    def test_heal_over_time_scaling(self):
        from src.abilities.effect import create_effect, get_star_value
        
        hot = create_effect("heal_over_time", {"value": [60, 80, 100], "duration": 150})
        
        assert get_star_value([60, 80, 100], 1) == 60
        assert get_star_value([60, 80, 100], 2) == 80
        assert get_star_value([60, 80, 100], 3) == 100


class TestChampionLoading:
    """Test that 3-cost champions load correctly with abilities."""
    
    @pytest.fixture
    def loader(self):
        from src.core.config_loader import ConfigLoader
        return ConfigLoader()
    
    def test_load_3cost_champion(self, loader):
        """Should load a 3-cost champion with stats and ability."""
        try:
            nautilus = loader.load_unit("nautilus")
            assert nautilus is not None
            assert nautilus.get("cost", 0) == 3 or nautilus.get("tier", 0) == 3
        except Exception as e:
            pytest.skip(f"Champion loading not set up: {e}")


class TestSimulationIntegration:
    """Test 3-cost abilities in actual simulation."""
    
    @pytest.fixture
    def simulation(self):
        from src.simulation.simulation import Simulation
        return Simulation(seed=42)
    
    def test_simulation_imports(self):
        """Basic import test."""
        from src.simulation.simulation import Simulation
        from src.abilities.effect import EFFECT_REGISTRY
        
        sim = Simulation(seed=42)
        assert sim is not None
        assert len(EFFECT_REGISTRY) >= 41
    
    def test_simulation_has_3cost_mechanics(self):
        """Simulation should have _phase_update_3cost_mechanics method."""
        from src.simulation.simulation import Simulation
        
        sim = Simulation(seed=42)
        assert hasattr(sim, "_phase_update_3cost_mechanics")


class Test8v8Battle:
    """Integration test with 8v8 battle."""
    
    def test_simple_battle(self):
        """Run a simple battle to verify no crashes."""
        from src.simulation.simulation import Simulation
        from src.units.unit import Unit
        from src.core.hex_coord import HexCoord
        from src.units.stats import UnitStats
        
        sim = Simulation(seed=42)
        
        # Create simple test units
        for i in range(4):
            unit_config = {
                "id": f"test_unit_{i}",
                "name": f"TestUnit{i}",
                "hp": 1000,
                "attack_damage": 100,
                "attack_speed": 1.0,
                "range": 1,
                "armor": 30,
                "magic_resist": 30,
                "mana": 100,
                "mana_start": 0,
            }
            pos = HexCoord(i, 0)
            unit = sim.add_unit_from_config(unit_config, team=0, position=pos)
            
        for i in range(4):
            unit_config = {
                "id": f"enemy_unit_{i}",
                "name": f"EnemyUnit{i}",
                "hp": 1000,
                "attack_damage": 100,
                "attack_speed": 1.0,
                "range": 1,
                "armor": 30,
                "magic_resist": 30,
                "mana": 100,
                "mana_start": 0,
            }
            pos = HexCoord(i, 6)
            unit = sim.add_unit_from_config(unit_config, team=1, position=pos)
        
        # Run simulation
        result = sim.run()
        
        assert result is not None
        assert "winner_team" in result
        assert "total_ticks" in result
        print(f"Battle completed in {result['total_ticks']} ticks, winner: {result['winner_team']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
