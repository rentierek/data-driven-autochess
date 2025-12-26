"""
Testy dla systemu many i castowania.

Testuje:
- TFT mana formula (1% pre + 3% post, cap 42.5)
- Mana overflow
- Mana lock podczas castowania
- Pasywna regeneracja many
- Champion Classes
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.units.unit import Unit
from src.units.stats import UnitStats
from src.units.state_machine import UnitStateMachine, UnitState
from src.units.champion_class import ChampionClass, ChampionClassLoader, DEFAULT_CLASS
from src.core.hex_coord import HexCoord


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def unit():
    """Tworzy testową jednostkę z pełną maną."""
    stats = UnitStats(base_hp=500, base_max_mana=100, base_start_mana=0)
    stats.current_hp = 500
    stats.current_mana = 0
    return Unit(
        id="test_unit",
        name="Test",
        unit_type="test",
        team=0,
        position=HexCoord(0, 0),
        stats=stats,
    )


@pytest.fixture
def class_loader():
    """Loader klas z data/."""
    return ChampionClassLoader("data/")


# ═══════════════════════════════════════════════════════════════════════════
# TEST: MANA FROM ATTACK
# ═══════════════════════════════════════════════════════════════════════════

def test_mana_from_attack_basic(unit):
    """Jednostka zyskuje manę z ataku."""
    unit.mana_per_attack = 10
    gained = unit.gain_mana_on_attack()
    
    assert gained == 10
    assert unit.stats.current_mana == 10


def test_mana_from_attack_respects_max(unit):
    """Mana nie przekracza max_mana."""
    unit.mana_per_attack = 10
    unit.stats.current_mana = 95
    
    gained = unit.gain_mana_on_attack()
    
    assert unit.stats.current_mana == 100  # capped
    assert gained == 10  # still returns full amount


def test_mana_from_attack_blocked_when_locked(unit):
    """Mana nie jest zyskiwana gdy mana_locked."""
    unit.mana_per_attack = 10
    unit.state.start_cast(15)  # start casting -> mana lock
    
    assert unit.is_mana_locked()
    
    gained = unit.gain_mana_on_attack()
    
    assert gained == 0
    assert unit.stats.current_mana == 0


# ═══════════════════════════════════════════════════════════════════════════
# TEST: TFT MANA FORMULA
# ═══════════════════════════════════════════════════════════════════════════

def test_tft_mana_formula_basic(unit):
    """TFT formula: 1% pre + 3% post."""
    # 200 raw, 150 final
    # mana = 200 * 0.01 + 150 * 0.03 = 2 + 4.5 = 6.5
    
    gained = unit.gain_mana_on_damage(
        pre_mitigation_damage=200,
        post_mitigation_damage=150
    )
    
    assert gained == pytest.approx(6.5, rel=0.01)


def test_tft_mana_formula_cap(unit):
    """TFT formula respektuje cap 42.5."""
    # Bardzo duże obrażenia
    # 5000 * 0.01 + 5000 * 0.03 = 50 + 150 = 200 -> capped to 42.5
    
    gained = unit.gain_mana_on_damage(
        pre_mitigation_damage=5000,
        post_mitigation_damage=5000
    )
    
    assert gained == pytest.approx(42.5, rel=0.01)


def test_tft_mana_formula_custom_config(unit):
    """TFT formula używa custom config."""
    config = {
        "mana_from_damage": {
            "pre_mitigation_percent": 0.05,  # 5%
            "post_mitigation_percent": 0.10,  # 10%
            "cap": 100.0
        }
    }
    
    # 100 * 0.05 + 100 * 0.10 = 5 + 10 = 15
    gained = unit.gain_mana_on_damage(
        pre_mitigation_damage=100,
        post_mitigation_damage=100,
        mana_config=config
    )
    
    assert gained == pytest.approx(15.0, rel=0.01)


def test_mana_from_damage_blocked_when_locked(unit):
    """Mana z damage nie jest zyskiwana gdy mana_locked."""
    unit.state.start_cast(15)
    
    gained = unit.gain_mana_on_damage(
        pre_mitigation_damage=200,
        post_mitigation_damage=150
    )
    
    assert gained == 0


# ═══════════════════════════════════════════════════════════════════════════
# TEST: MANA OVERFLOW
# ═══════════════════════════════════════════════════════════════════════════

def test_mana_overflow_basic(unit):
    """add_mana zwraca overflow."""
    unit.stats.current_mana = 95
    
    overflow = unit.stats.add_mana(10)
    
    assert unit.stats.current_mana == 100  # capped
    assert overflow == 5  # 95 + 10 - 100 = 5


def test_consume_mana_with_overflow_enabled(unit):
    """consume_mana_for_cast przekazuje overflow."""
    unit.stats.current_mana = 100
    unit._pending_mana_overflow = 5  # symulacja overflow
    
    remaining = unit.consume_mana_for_cast(mana_overflow_enabled=True)
    
    assert remaining == 5  # overflow przechodzi
    assert unit.stats.current_mana == 5


def test_consume_mana_with_overflow_disabled(unit):
    """consume_mana_for_cast resetuje do 0 gdy disabled."""
    unit.stats.current_mana = 100
    unit._pending_mana_overflow = 5
    
    remaining = unit.consume_mana_for_cast(mana_overflow_enabled=False)
    
    assert remaining == 0
    assert unit.stats.current_mana == 0


# ═══════════════════════════════════════════════════════════════════════════
# TEST: STATE MACHINE - MANA LOCK
# ═══════════════════════════════════════════════════════════════════════════

def test_mana_lock_on_cast_start():
    """start_cast włącza mana lock."""
    fsm = UnitStateMachine()
    
    assert not fsm.is_mana_locked()
    
    fsm.start_cast(15)
    
    assert fsm.is_mana_locked()


def test_mana_lock_expires_after_cast():
    """Mana lock wygasa po zakończeniu casta."""
    fsm = UnitStateMachine()
    fsm.start_cast(cast_time_ticks=3)  # 3 ticki
    
    fsm.tick()  # 2 remaining
    assert fsm.is_mana_locked()
    
    fsm.tick()  # 1 remaining
    assert fsm.is_mana_locked()
    
    fsm.tick()  # 0 remaining - cast ends
    assert not fsm.is_mana_locked()


def test_mana_lock_extended_duration():
    """Mana lock może trwać dłużej niż cast."""
    fsm = UnitStateMachine()
    fsm.start_cast(
        cast_time_ticks=2,
        mana_lock_duration=3  # 2 + 3 = 5 ticki lock
    )
    
    fsm.tick()  # cast: 1, lock: 4
    fsm.tick()  # cast: 0 (ends), lock: 3
    
    assert fsm.current == UnitState.IDLE  # cast zakończony
    assert fsm.is_mana_locked()  # ale lock trwa
    
    fsm.tick()  # lock: 2
    fsm.tick()  # lock: 1
    fsm.tick()  # lock: 0
    
    assert not fsm.is_mana_locked()


# ═══════════════════════════════════════════════════════════════════════════
# TEST: STATE MACHINE - EFFECT TRIGGER
# ═══════════════════════════════════════════════════════════════════════════

def test_effect_trigger_instant():
    """Instant effect (delay=0) triggeruje natychmiast."""
    fsm = UnitStateMachine()
    fsm.start_cast(cast_time_ticks=15, effect_delay_ticks=0)
    
    assert fsm.should_trigger_effect()  # natychmiast gotowy


def test_effect_trigger_delayed():
    """Delayed effect czeka na effect_delay."""
    fsm = UnitStateMachine()
    fsm.start_cast(cast_time_ticks=15, effect_delay_ticks=3)
    
    assert not fsm.should_trigger_effect()  # jeszcze nie
    
    fsm.tick()  # delay: 2
    assert not fsm.should_trigger_effect()
    
    fsm.tick()  # delay: 1
    assert not fsm.should_trigger_effect()
    
    fsm.tick()  # delay: 0 - teraz!
    assert fsm.should_trigger_effect()


def test_effect_triggers_only_once():
    """Effect triggeruje tylko raz per cast."""
    fsm = UnitStateMachine()
    fsm.start_cast(cast_time_ticks=15, effect_delay_ticks=0)
    
    assert fsm.should_trigger_effect()
    
    fsm.mark_effect_triggered()
    
    assert not fsm.should_trigger_effect()


# ═══════════════════════════════════════════════════════════════════════════
# TEST: PASSIVE MANA REGEN
# ═══════════════════════════════════════════════════════════════════════════

def test_passive_mana_regen(unit):
    """Pasywna regeneracja many działa."""
    gained = unit.gain_mana_passive(
        ticks_per_second=30,
        mana_per_second=30  # = 1 mana per tick
    )
    
    assert gained == pytest.approx(1.0, rel=0.01)
    assert unit.stats.current_mana == pytest.approx(1.0, rel=0.01)


def test_passive_mana_regen_disabled(unit):
    """Pasywna regeneracja = 0 gdy wyłączona."""
    gained = unit.gain_mana_passive(
        ticks_per_second=30,
        mana_per_second=0  # disabled
    )
    
    assert gained == 0


def test_passive_mana_regen_blocked_when_locked(unit):
    """Pasywna regeneracja blokowana przez mana lock."""
    unit.state.start_cast(15)
    
    gained = unit.gain_mana_passive(
        ticks_per_second=30,
        mana_per_second=30
    )
    
    assert gained == 0


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CHAMPION CLASSES
# ═══════════════════════════════════════════════════════════════════════════

def test_champion_class_loader(class_loader):
    """ChampionClassLoader ładuje klasy."""
    assert class_loader.is_enabled()
    
    assassin = class_loader.get_class("assassin")
    assert assassin.name == "Assassin"
    assert assassin.default_target_selector == "backline"


def test_champion_class_default_for_unknown(class_loader):
    """Nieznana klasa zwraca DEFAULT_CLASS."""
    unknown = class_loader.get_class("nonexistent")
    assert unknown == DEFAULT_CLASS


def test_champion_class_mana_multipliers(class_loader):
    """Champion classes mają poprawne mnożniki."""
    sorcerer = class_loader.get_class("sorcerer")
    
    assert sorcerer.mana_per_attack_multiplier == 0.5  # -50%
    assert sorcerer.mana_from_damage_multiplier == 1.5  # +50%
    assert sorcerer.mana_per_second_bonus == 5  # +5/s


def test_champion_class_apply_mana_from_attack():
    """ChampionClass aplikuje mnożnik do mana from attack."""
    champion_class = ChampionClass(
        id="test",
        name="Test",
        mana_per_attack_multiplier=1.5,
    )
    
    base_mana = 10
    modified = champion_class.apply_mana_from_attack(base_mana)
    
    assert modified == 15  # 10 * 1.5


def test_champion_class_mana_per_tick():
    """ChampionClass oblicza mana per tick."""
    champion_class = ChampionClass(
        id="test",
        name="Test",
        mana_per_second_bonus=30,  # 30/s = 1/tick @ 30 TPS
    )
    
    mana_per_tick = champion_class.get_mana_per_tick(ticks_per_second=30)
    
    assert mana_per_tick == pytest.approx(1.0, rel=0.01)


def test_all_classes_load(class_loader):
    """Wszystkie zdefiniowane klasy ładują się poprawnie."""
    expected_classes = [
        "sorcerer", "assassin", "guardian", 
        "marksman", "executioner", "support", "brawler"
    ]
    
    for class_id in expected_classes:
        champion_class = class_loader.get_class(class_id)
        assert champion_class.id == class_id, f"Klasa {class_id} nie załadowała się poprawnie"


# ═══════════════════════════════════════════════════════════════════════════
# TEST: STATS ADD_MANA
# ═══════════════════════════════════════════════════════════════════════════

def test_stats_add_mana_returns_overflow():
    """UnitStats.add_mana zwraca overflow."""
    stats = UnitStats(base_max_mana=100)
    stats.current_mana = 90
    
    overflow = stats.add_mana(15)
    
    assert stats.current_mana == 100
    assert overflow == 5  # 90 + 15 - 100


def test_stats_add_mana_no_overflow():
    """UnitStats.add_mana zwraca 0 gdy brak overflow."""
    stats = UnitStats(base_max_mana=100)
    stats.current_mana = 50
    
    overflow = stats.add_mana(10)
    
    assert stats.current_mana == 60
    assert overflow == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
