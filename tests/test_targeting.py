"""
Testy dla systemu targetingu.

Testuje wszystkie selektory celów i ich parametry.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.targeting import (
    get_selector, parse_target_type, SELECTOR_REGISTRY,
    NearestSelector, FarthestSelector, LowestHPPercentSelector,
    HighestStatSelector, ClusterSelector, BacklineSelector,
)
from src.core.hex_coord import HexCoord
from src.core.hex_grid import HexGrid
from src.core.rng import GameRNG
from src.units.unit import Unit
from src.units.stats import UnitStats


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def grid():
    """Tworzy standardową siatkę 7x8."""
    return HexGrid(width=7, height=8)


@pytest.fixture
def rng():
    """Deterministyczny RNG."""
    return GameRNG(seed=12345)


def create_unit(unit_id: str, team: int, position: HexCoord, hp: float = 500, ad: float = 50) -> Unit:
    """Helper do tworzenia jednostek testowych."""
    stats = UnitStats(base_hp=hp, base_attack_damage=ad)
    stats.current_hp = hp
    return Unit(
        id=unit_id,
        name=f"Unit_{unit_id}",
        unit_type="test",
        team=team,
        position=position,
        stats=stats,
    )


# ═══════════════════════════════════════════════════════════════════════════
# TEST: SELECTOR REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

def test_selector_registry_has_all_selectors():
    """Sprawdza czy registry zawiera wszystkie selektory."""
    expected = [
        "nearest", "farthest", "lowest_hp_percent", "lowest_hp",
        "lowest_hp_flat", "highest_stat", "cluster", "random",
        "frontline", "backline", "current_target"
    ]
    for name in expected:
        assert name in SELECTOR_REGISTRY, f"Brak selektora: {name}"


def test_get_selector_returns_correct_type():
    """Sprawdza czy get_selector zwraca poprawny typ."""
    selector = get_selector("nearest")
    assert isinstance(selector, NearestSelector)
    
    selector = get_selector("farthest", max_range=5)
    assert isinstance(selector, FarthestSelector)
    assert selector.max_range == 5


def test_get_selector_unknown_raises():
    """Sprawdza czy nieznany selektor rzuca wyjątek."""
    with pytest.raises(ValueError):
        get_selector("unknown_selector")


# ═══════════════════════════════════════════════════════════════════════════
# TEST: NEAREST SELECTOR
# ═══════════════════════════════════════════════════════════════════════════

def test_nearest_selects_closest(grid, rng):
    """Nearest selector wybiera najbliższego wroga."""
    source = create_unit("source", team=0, position=HexCoord(0, 0))
    
    enemy_close = create_unit("close", team=1, position=HexCoord(1, 0))  # dist 1
    enemy_far = create_unit("far", team=1, position=HexCoord(3, 3))      # dist 6
    
    selector = NearestSelector()
    target = selector.select(source, [enemy_close, enemy_far], grid, rng)
    
    assert target == enemy_close


def test_nearest_with_max_range(grid, rng):
    """Nearest respektuje max_range."""
    source = create_unit("source", team=0, position=HexCoord(0, 0))
    
    enemy_close = create_unit("close", team=1, position=HexCoord(5, 5))  # dist 10
    
    selector = NearestSelector(max_range=3)
    target = selector.select(source, [enemy_close], grid, rng)
    
    assert target is None  # poza zasięgiem


def test_nearest_tiebreaker_deterministic(grid, rng):
    """Przy równej odległości wybór jest deterministyczny."""
    source = create_unit("source", team=0, position=HexCoord(2, 2))
    
    # Dwóch wrogów w tej samej odległości
    enemy1 = create_unit("a_enemy", team=1, position=HexCoord(3, 2))
    enemy2 = create_unit("b_enemy", team=1, position=HexCoord(1, 2))
    
    selector = NearestSelector()
    
    # Ten sam RNG seed = ten sam wynik
    target1 = selector.select(source, [enemy1, enemy2], grid, GameRNG(42))
    target2 = selector.select(source, [enemy1, enemy2], grid, GameRNG(42))
    
    assert target1 == target2


# ═══════════════════════════════════════════════════════════════════════════
# TEST: FARTHEST SELECTOR
# ═══════════════════════════════════════════════════════════════════════════

def test_farthest_selects_furthest(grid, rng):
    """Farthest selector wybiera najdalszego wroga."""
    source = create_unit("source", team=0, position=HexCoord(0, 0))
    
    enemy_close = create_unit("close", team=1, position=HexCoord(1, 0))
    enemy_far = create_unit("far", team=1, position=HexCoord(5, 5))
    
    selector = FarthestSelector()
    target = selector.select(source, [enemy_close, enemy_far], grid, rng)
    
    assert target == enemy_far


# ═══════════════════════════════════════════════════════════════════════════
# TEST: LOWEST HP SELECTOR
# ═══════════════════════════════════════════════════════════════════════════

def test_lowest_hp_percent_selects_wounded(grid, rng):
    """Lowest HP % wybiera jednostkę z najniższym % HP."""
    source = create_unit("source", team=0, position=HexCoord(0, 0))
    
    # 80% HP
    enemy_healthy = create_unit("healthy", team=1, position=HexCoord(1, 0), hp=500)
    enemy_healthy.stats.current_hp = 400
    
    # 30% HP
    enemy_wounded = create_unit("wounded", team=1, position=HexCoord(2, 0), hp=500)
    enemy_wounded.stats.current_hp = 150
    
    selector = LowestHPPercentSelector()
    target = selector.select(source, [enemy_healthy, enemy_wounded], grid, rng)
    
    assert target == enemy_wounded


def test_lowest_hp_percent_prefers_lower_even_if_higher_absolute(grid, rng):
    """Lowest HP % preferuje niższy %, nawet jeśli ma więcej absolutnego HP."""
    source = create_unit("source", team=0, position=HexCoord(0, 0))
    
    # Tank: 500/2000 HP = 25%
    tank = create_unit("tank", team=1, position=HexCoord(1, 0), hp=2000)
    tank.stats.current_hp = 500
    
    # Squishy: 250/500 HP = 50%
    squishy = create_unit("squishy", team=1, position=HexCoord(2, 0), hp=500)
    squishy.stats.current_hp = 250
    
    selector = LowestHPPercentSelector()
    target = selector.select(source, [tank, squishy], grid, rng)
    
    assert target == tank  # 25% < 50%


# ═══════════════════════════════════════════════════════════════════════════
# TEST: HIGHEST STAT SELECTOR
# ═══════════════════════════════════════════════════════════════════════════

def test_highest_stat_selects_max_ad(grid, rng):
    """Highest stat wybiera jednostkę z najwyższym AD."""
    source = create_unit("source", team=0, position=HexCoord(0, 0))
    
    low_ad = create_unit("low", team=1, position=HexCoord(1, 0), ad=50)
    high_ad = create_unit("high", team=1, position=HexCoord(2, 0), ad=150)
    
    selector = HighestStatSelector(stat="attack_damage")
    target = selector.select(source, [low_ad, high_ad], grid, rng)
    
    assert target == high_ad


def test_highest_stat_supports_aliases(grid, rng):
    """Highest stat obsługuje aliasy (ad, as, ap, mr)."""
    source = create_unit("source", team=0, position=HexCoord(0, 0))
    enemy = create_unit("enemy", team=1, position=HexCoord(1, 0), ad=100)
    
    # Test alias "ad"
    selector = HighestStatSelector(stat="ad")
    target = selector.select(source, [enemy], grid, rng)
    assert target == enemy


# ═══════════════════════════════════════════════════════════════════════════
# TEST: CLUSTER SELECTOR
# ═══════════════════════════════════════════════════════════════════════════

def test_cluster_selects_grouped_enemies(grid, rng):
    """Cluster wybiera jednostkę z największą liczbą sąsiadów."""
    source = create_unit("source", team=0, position=HexCoord(0, 0))
    
    # Grupa skupiona
    center = create_unit("center", team=1, position=HexCoord(3, 3))
    neighbor1 = create_unit("n1", team=1, position=HexCoord(3, 2))
    neighbor2 = create_unit("n2", team=1, position=HexCoord(4, 3))
    
    # Jednostka samotna
    alone = create_unit("alone", team=1, position=HexCoord(6, 6))
    
    candidates = [center, neighbor1, neighbor2, alone]
    
    selector = ClusterSelector(radius=2)
    target = selector.select(source, candidates, grid, rng)
    
    # Powinien wybrać center (2 sąsiadów) lub jednego z sąsiadów (1-2 sąsiadów)
    # ale NIE alone (0 sąsiadów)
    assert target != alone


# ═══════════════════════════════════════════════════════════════════════════
# TEST: BACKLINE SELECTOR
# ═══════════════════════════════════════════════════════════════════════════

def test_backline_for_team0_selects_high_r(grid, rng):
    """Dla team 0: backline wroga = wysokie r (daleko od góry)."""
    source = create_unit("source", team=0, position=HexCoord(2, 0))  # team 0 na górze
    
    frontline = create_unit("front", team=1, position=HexCoord(2, 3))  # niskie r
    backline = create_unit("back", team=1, position=HexCoord(2, 7))   # wysokie r
    
    selector = BacklineSelector()
    target = selector.select(source, [frontline, backline], grid, rng)
    
    assert target == backline


def test_backline_for_team1_selects_low_r(grid, rng):
    """Dla team 1: backline wroga = niskie r (daleko od dołu)."""
    source = create_unit("source", team=1, position=HexCoord(2, 7))  # team 1 na dole
    
    frontline = create_unit("front", team=0, position=HexCoord(2, 4))  # wysokie r
    backline = create_unit("back", team=0, position=HexCoord(2, 0))   # niskie r
    
    selector = BacklineSelector()
    target = selector.select(source, [frontline, backline], grid, rng)
    
    assert target == backline


# ═══════════════════════════════════════════════════════════════════════════
# TEST: PARSE TARGET TYPE
# ═══════════════════════════════════════════════════════════════════════════

def test_parse_target_type_string():
    """parse_target_type obsługuje prosty string."""
    selector = parse_target_type("nearest")
    assert isinstance(selector, NearestSelector)


def test_parse_target_type_dict():
    """parse_target_type obsługuje dict z parametrami."""
    selector = parse_target_type({
        "selector": "cluster",
        "radius": 3,
        "max_range": 5
    })
    assert isinstance(selector, ClusterSelector)
    assert selector.radius == 3
    assert selector.max_range == 5


def test_parse_target_type_fallback():
    """parse_target_type zwraca NearestSelector dla nierozpoznanych typów."""
    selector = parse_target_type(None)
    assert isinstance(selector, NearestSelector)


# ═══════════════════════════════════════════════════════════════════════════
# TEST: EMPTY CANDIDATES
# ═══════════════════════════════════════════════════════════════════════════

def test_all_selectors_handle_empty_candidates(grid, rng):
    """Wszystkie selektory zwracają None dla pustej listy."""
    source = create_unit("source", team=0, position=HexCoord(0, 0))
    
    for name in SELECTOR_REGISTRY:
        if name == "highest_stat":
            selector = get_selector(name, stat="attack_damage")
        elif name == "cluster":
            selector = get_selector(name, radius=2)
        else:
            selector = get_selector(name)
        
        result = selector.select(source, [], grid, rng)
        assert result is None, f"Selektor {name} powinien zwrócić None dla pustej listy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
