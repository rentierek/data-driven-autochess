"""
Test suite for Set 16 Trait System.

Tests:
1. Effect applicators functionality
2. Trait loading from YAML
3. Trait stat bonuses
4. 8v8 battles with active traits
"""

import pytest
import yaml
from dataclasses import dataclass
from typing import Dict, List, Any

# Import trait system
from src.traits.trait_manager import TRAIT_EFFECT_APPLICATORS, TraitManager
from src.traits.trait import Trait, TraitEffect, EffectTarget
from src.simulation.simulation import Simulation
from src.core.hex_coord import HexCoord
from src.core.config_loader import ConfigLoader


# ═══════════════════════════════════════════════════════════════════════════
# MOCK CLASSES FOR TESTING
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MockStats:
    """Mock stats for testing."""
    base_hp: float = 1000
    current_hp: float = 1000
    base_armor: float = 50
    base_magic_resist: float = 50
    base_attack_damage: float = 100
    base_ability_power: float = 0
    base_attack_speed: float = 1.0
    base_crit_chance: float = 0.25
    base_crit_damage: float = 0.5
    base_durability: float = 0
    max_hp: float = 1000
    
    def heal(self, amount):
        self.current_hp = min(self.max_hp, self.current_hp + amount)
    
    def add_mana(self, amount):
        pass


@dataclass
class MockUnit:
    """Mock unit for testing trait applicators."""
    id: str = "test_unit"
    stats: MockStats = None
    shield: int = 0
    shield_duration: int = 0
    
    def __post_init__(self):
        if self.stats is None:
            self.stats = MockStats()
    
    def is_alive(self):
        return self.stats.current_hp > 0
    
    def add_shield(self, value, duration):
        self.shield = value
        self.shield_duration = duration


# ═══════════════════════════════════════════════════════════════════════════
# EFFECT APPLICATOR TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestEffectApplicators:
    """Test individual effect applicators."""
    
    def test_stat_bonus(self):
        """Test stat_bonus applicator."""
        unit = MockUnit()
        effect = TraitEffect(
            effect_type="stat_bonus",
            value=30,
            target=EffectTarget.HOLDERS,
            params={"stat": "armor"}
        )
        
        count = TRAIT_EFFECT_APPLICATORS["stat_bonus"]([unit], effect)
        
        assert count == 1
        assert unit.stats.base_armor == 80  # 50 + 30
    
    def test_stat_percent(self):
        """Test stat_percent applicator."""
        unit = MockUnit()
        effect = TraitEffect(
            effect_type="stat_percent",
            value=0.25,
            target=EffectTarget.HOLDERS,
            params={"stat": "hp"}
        )
        
        count = TRAIT_EFFECT_APPLICATORS["stat_percent"]([unit], effect)
        
        assert count == 1
        assert unit.stats.base_hp == 1250  # 1000 * 1.25
    
    def test_damage_amp(self):
        """Test damage_amp applicator."""
        unit = MockUnit()
        effect = TraitEffect(
            effect_type="damage_amp",
            value=0.20,
            target=EffectTarget.HOLDERS,
            params={}
        )
        
        count = TRAIT_EFFECT_APPLICATORS["damage_amp"]([unit], effect)
        
        assert count == 1
        assert unit.stats.base_damage_amp == 0.20
    
    def test_shield_percent_hp(self):
        """Test shield_percent_hp applicator."""
        unit = MockUnit()
        effect = TraitEffect(
            effect_type="shield_percent_hp",
            value=0.30,
            target=EffectTarget.HOLDERS,
            params={}
        )
        
        count = TRAIT_EFFECT_APPLICATORS["shield_percent_hp"]([unit], effect)
        
        assert count == 1
        assert unit.shield == 300  # 1000 * 0.30
    
    def test_target_missing_hp_as(self):
        """Test Quickstriker applicator."""
        unit = MockUnit()
        effect = TraitEffect(
            effect_type="target_missing_hp_as",
            value=0,
            target=EffectTarget.HOLDERS,
            params={"min": 0.10, "max": 0.30}
        )
        
        count = TRAIT_EFFECT_APPLICATORS["target_missing_hp_as"]([unit], effect)
        
        assert count == 1
        assert hasattr(unit, 'target_missing_hp_as')
        assert unit.target_missing_hp_as["min"] == 0.10
        assert unit.target_missing_hp_as["max"] == 0.30


# ═══════════════════════════════════════════════════════════════════════════
# YAML LOADING TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestTraitLoading:
    """Test trait loading from YAML."""
    
    def test_load_set16_traits(self):
        """Load set16_traits.yaml and verify structure."""
        with open('data/set16_traits.yaml', 'r') as f:
            data = yaml.safe_load(f)
        
        traits = data.get('traits', {})
        
        # Check counts
        assert len(traits) == 40
        
        # Check specific traits exist
        assert 'arcanist' in traits
        assert 'bruiser' in traits
        assert 'darkin' in traits
        assert 'demacia' in traits
    
    def test_arcanist_structure(self):
        """Verify Arcanist trait structure."""
        with open('data/set16_traits.yaml', 'r') as f:
            data = yaml.safe_load(f)
        
        arcanist = data['traits']['arcanist']
        
        assert arcanist['name'] == 'Arcanist'
        assert 2 in arcanist['thresholds']
        assert 4 in arcanist['thresholds']
        assert 6 in arcanist['thresholds']


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS - BATTLE SIMULATIONS
# ═══════════════════════════════════════════════════════════════════════════

class TestBattleSimulations:
    """Test 8v8 battles with active traits."""
    
    def test_4v4_simple_battle(self):
        """Basic 4v4 battle works."""
        sim = Simulation(seed=42)
        loader = ConfigLoader()
        sim._config_loader = loader
        
        for i in range(4):
            sim.add_unit_from_config({
                'id': f'a{i}', 'name': f'A{i}',
                'hp': 2000, 'attack_damage': 100, 'attack_speed': 1.0,
                'range': 2, 'armor': 40, 'magic_resist': 40,
                'mana': 50, 'mana_start': 30, 'ability': 'arcane_bolt',
            }, team=0, position=HexCoord(i, 0), star_level=2)
        
        for i in range(4):
            sim.add_unit_from_config({
                'id': f'b{i}', 'name': f'B{i}',
                'hp': 2000, 'attack_damage': 100, 'attack_speed': 1.0,
                'range': 2, 'armor': 40, 'magic_resist': 40,
                'mana': 50, 'mana_start': 30, 'ability': 'arcane_bolt',
            }, team=1, position=HexCoord(i, 3), star_level=2)
        
        result = sim.run()
        
        assert result['total_ticks'] > 0
        assert result['total_ticks'] < 3000


# ═══════════════════════════════════════════════════════════════════════════
# MAIN TEST RUNNER
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
