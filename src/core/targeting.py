"""
System zaawansowanego targetingu dla jednostek.

Selektory celów pozwalają na różne strategie wyboru celu:
- nearest/farthest: odległość
- lowest_hp: dobijanie rannych
- highest_stat: priorytetyzacja silnych
- cluster: AoE optymalizacja
- backline/frontline: pozycja na mapie

UŻYCIE:
═══════════════════════════════════════════════════════════════════

    # Z kodu
    selector = get_selector("lowest_hp_percent", max_range=5)
    target = selector.select(unit, enemies, grid, rng)
    
    # Z YAML (abilities.yaml)
    target_type: "nearest"                    # prosty string
    target_type:                              # rozszerzony format
      selector: "lowest_hp_percent"
      max_range: 5

SELEKTORY:
═══════════════════════════════════════════════════════════════════

    nearest         - najbliższy wróg (domyślny)
    farthest        - najdalszy wróg
    lowest_hp_percent - najniższe % HP (dobijanie)
    lowest_hp_flat  - najniższe HP absolutne
    highest_stat    - najwyższa wartość statystyki
    cluster         - hex z najwięcej wrogami w radius
    random          - losowy cel
    frontline       - najbliższy do własnego spawnu
    backline        - najdalszy od własnego spawnu (assassin)
    current_target  - utrzymuj aktualny cel jeśli żyje

PARAMETRY:
═══════════════════════════════════════════════════════════════════

    max_range (int): Maksymalny zasięg w hexach (None = globalny)
    stat (str): Dla highest_stat - nazwa statystyki
    radius (int): Dla cluster - promień sprawdzania skupiska
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..units.unit import Unit
    from .hex_grid import HexGrid
    from .hex_coord import HexCoord
    from .rng import GameRNG


# ═══════════════════════════════════════════════════════════════════════════
# BAZA SELEKTORA
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TargetSelector(ABC):
    """
    Bazowa klasa dla selektorów celów.
    
    Attributes:
        max_range: Maksymalny zasięg (None = brak limitu)
    """
    max_range: Optional[int] = None
    
    @abstractmethod
    def select(
        self,
        source: "Unit",
        candidates: List["Unit"],
        grid: "HexGrid",
        rng: "GameRNG",
    ) -> Optional["Unit"]:
        """
        Wybiera cel spośród kandydatów.
        
        Args:
            source: Jednostka szukająca celu
            candidates: Lista potencjalnych celów (żywi wrogowie)
            grid: Siatka hexagonalna
            rng: Generator losowości
            
        Returns:
            Wybrany cel lub None jeśli brak
        """
        pass
    
    def filter_by_range(
        self, 
        source: "Unit", 
        candidates: List["Unit"]
    ) -> List["Unit"]:
        """
        Filtruje kandydatów po max_range.
        
        Args:
            source: Jednostka źródłowa
            candidates: Lista kandydatów
            
        Returns:
            Przefiltrowana lista
        """
        if self.max_range is None:
            return candidates
        
        return [
            c for c in candidates 
            if source.position.distance(c.position) <= self.max_range
        ]
    
    def _tiebreaker(
        self, 
        candidates: List["Unit"], 
        rng: "GameRNG"
    ) -> Optional["Unit"]:
        """
        Deterministycznie rozstrzyga remisy.
        
        Sortuje po ID (stabilność) i losuje przy remisie.
        """
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        
        # Sortuj po ID dla stabilności, potem losuj
        candidates.sort(key=lambda u: u.id)
        return rng.choice(candidates)


# ═══════════════════════════════════════════════════════════════════════════
# SELEKTORY ODLEGŁOŚCI
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class NearestSelector(TargetSelector):
    """
    Wybiera najbliższego wroga.
    
    Domyślny selektor - TFT standard.
    Przy równej odległości, deterministyczny losowy wybór.
    """
    
    def select(
        self,
        source: "Unit",
        candidates: List["Unit"],
        grid: "HexGrid",
        rng: "GameRNG",
    ) -> Optional["Unit"]:
        candidates = self.filter_by_range(source, candidates)
        if not candidates:
            return None
        
        # Sortuj po odległości
        candidates.sort(key=lambda c: source.position.distance(c.position))
        
        # Znajdź wszystkich z minimalną odległością
        min_dist = source.position.distance(candidates[0].position)
        closest = [c for c in candidates if source.position.distance(c.position) == min_dist]
        
        return self._tiebreaker(closest, rng)


@dataclass
class FarthestSelector(TargetSelector):
    """
    Wybiera najdalszego wroga.
    
    Przydatne dla niektórych umiejętności range.
    """
    
    def select(
        self,
        source: "Unit",
        candidates: List["Unit"],
        grid: "HexGrid",
        rng: "GameRNG",
    ) -> Optional["Unit"]:
        candidates = self.filter_by_range(source, candidates)
        if not candidates:
            return None
        
        # Sortuj po odległości (malejąco)
        candidates.sort(key=lambda c: source.position.distance(c.position), reverse=True)
        
        # Znajdź wszystkich z maksymalną odległością
        max_dist = source.position.distance(candidates[0].position)
        farthest = [c for c in candidates if source.position.distance(c.position) == max_dist]
        
        return self._tiebreaker(farthest, rng)


# ═══════════════════════════════════════════════════════════════════════════
# SELEKTORY HP
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class LowestHPPercentSelector(TargetSelector):
    """
    Wybiera wroga z najniższym % HP.
    
    Idealne do dobijania rannych jednostek.
    """
    
    def select(
        self,
        source: "Unit",
        candidates: List["Unit"],
        grid: "HexGrid",
        rng: "GameRNG",
    ) -> Optional["Unit"]:
        candidates = self.filter_by_range(source, candidates)
        if not candidates:
            return None
        
        def hp_percent(unit: "Unit") -> float:
            max_hp = unit.stats.get_max_hp()
            if max_hp <= 0:
                return 0
            return unit.stats.current_hp / max_hp
        
        # Sortuj po % HP (rosnąco)
        candidates.sort(key=hp_percent)
        
        # Znajdź wszystkich z minimalnym % HP
        min_hp = hp_percent(candidates[0])
        lowest = [c for c in candidates if hp_percent(c) == min_hp]
        
        return self._tiebreaker(lowest, rng)


@dataclass
class LowestHPFlatSelector(TargetSelector):
    """
    Wybiera wroga z najniższym HP absolutnym.
    
    Przydatne do execute'ów (zabij jednostkę poniżej X HP).
    """
    
    def select(
        self,
        source: "Unit",
        candidates: List["Unit"],
        grid: "HexGrid",
        rng: "GameRNG",
    ) -> Optional["Unit"]:
        candidates = self.filter_by_range(source, candidates)
        if not candidates:
            return None
        
        # Sortuj po HP (rosnąco)
        candidates.sort(key=lambda c: c.stats.current_hp)
        
        # Znajdź wszystkich z minimalnym HP
        min_hp = candidates[0].stats.current_hp
        lowest = [c for c in candidates if c.stats.current_hp == min_hp]
        
        return self._tiebreaker(lowest, rng)


# ═══════════════════════════════════════════════════════════════════════════
# SELEKTOR STATYSTYK
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HighestStatSelector(TargetSelector):
    """
    Wybiera wroga z najwyższą wartością danej statystyki.
    
    Attributes:
        stat: Nazwa statystyki (attack_damage, attack_speed, hp, ability_power, etc.)
    """
    stat: str = "attack_damage"
    
    def select(
        self,
        source: "Unit",
        candidates: List["Unit"],
        grid: "HexGrid",
        rng: "GameRNG",
    ) -> Optional["Unit"]:
        candidates = self.filter_by_range(source, candidates)
        if not candidates:
            return None
        
        def get_stat_value(unit: "Unit") -> float:
            """Pobiera wartość statystyki z jednostki."""
            stats = unit.stats
            
            # Mapowanie nazw na metody
            stat_getters = {
                "attack_damage": stats.get_attack_damage,
                "ad": stats.get_attack_damage,
                "ability_power": stats.get_ability_power,
                "ap": stats.get_ability_power,
                "attack_speed": stats.get_attack_speed,
                "as": stats.get_attack_speed,
                "hp": lambda: stats.current_hp,
                "max_hp": stats.get_max_hp,
                "armor": stats.get_armor,
                "magic_resist": stats.get_magic_resist,
                "mr": stats.get_magic_resist,
                "crit_chance": stats.get_crit_chance,
                "crit_damage": stats.get_crit_damage,
            }
            
            getter = stat_getters.get(self.stat.lower())
            if getter:
                return getter()
            return 0.0
        
        # Sortuj po statystyce (malejąco)
        candidates.sort(key=get_stat_value, reverse=True)
        
        # Znajdź wszystkich z maksymalną wartością
        max_val = get_stat_value(candidates[0])
        highest = [c for c in candidates if get_stat_value(c) == max_val]
        
        return self._tiebreaker(highest, rng)


# ═══════════════════════════════════════════════════════════════════════════
# SELEKTOR CLUSTER (AoE)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ClusterSelector(TargetSelector):
    """
    Wybiera wroga w pozycji z największym skupiskiem wrogów.
    
    Idealne dla AoE umiejętności.
    
    Attributes:
        radius: Promień sprawdzania skupiska
    """
    radius: int = 2
    
    def select(
        self,
        source: "Unit",
        candidates: List["Unit"],
        grid: "HexGrid",
        rng: "GameRNG",
    ) -> Optional["Unit"]:
        candidates = self.filter_by_range(source, candidates)
        if not candidates:
            return None
        
        def count_nearby(unit: "Unit") -> int:
            """Liczy wrogów w radius od jednostki."""
            count = 0
            for other in candidates:
                if other.id != unit.id:
                    if unit.position.distance(other.position) <= self.radius:
                        count += 1
            return count
        
        # Sortuj po liczbie wrogów w pobliżu (malejąco)
        candidates.sort(key=count_nearby, reverse=True)
        
        # Znajdź wszystkich z maksymalną liczbą
        max_count = count_nearby(candidates[0])
        best = [c for c in candidates if count_nearby(c) == max_count]
        
        return self._tiebreaker(best, rng)


# ═══════════════════════════════════════════════════════════════════════════
# SELEKTOR LOSOWY
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class RandomSelector(TargetSelector):
    """
    Wybiera losowego wroga.
    
    Deterministyczny (zależy od seed RNG).
    """
    
    def select(
        self,
        source: "Unit",
        candidates: List["Unit"],
        grid: "HexGrid",
        rng: "GameRNG",
    ) -> Optional["Unit"]:
        candidates = self.filter_by_range(source, candidates)
        if not candidates:
            return None
        
        return rng.choice(candidates)


# ═══════════════════════════════════════════════════════════════════════════
# SELEKTORY POZYCYJNE (FRONTLINE/BACKLINE)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class FrontlineSelector(TargetSelector):
    """
    Wybiera wroga najbliżej frontu (naszej strony).
    
    Front zależy od teamu:
    - Team 0: niskie r (góra planszy)
    - Team 1: wysokie r (dół planszy)
    
    Frontline wroga = jego jednostka najbliżej naszego spawnu.
    """
    
    def select(
        self,
        source: "Unit",
        candidates: List["Unit"],
        grid: "HexGrid",
        rng: "GameRNG",
    ) -> Optional["Unit"]:
        candidates = self.filter_by_range(source, candidates)
        if not candidates:
            return None
        
        # Określ kierunek frontu na podstawie teamu
        # Team 0 spawnuje na górze (niskie r), więc frontline wroga = wysokie r
        # Team 1 spawnuje na dole (wysokie r), więc frontline wroga = niskie r
        
        if source.team == 0:
            # Szukamy wroga z najniższym r (najbliżej naszego spawnu)
            candidates.sort(key=lambda c: c.position.r)
        else:
            # Szukamy wroga z najwyższym r (najbliżej naszego spawnu)
            candidates.sort(key=lambda c: c.position.r, reverse=True)
        
        # Znajdź wszystkich na froncie (ten sam r)
        front_r = candidates[0].position.r
        frontline = [c for c in candidates if c.position.r == front_r]
        
        return self._tiebreaker(frontline, rng)


@dataclass
class BacklineSelector(TargetSelector):
    """
    Wybiera wroga najdalej od frontu (na tyłach wroga).
    
    Idealne dla assassinów - skok na carry/maga.
    
    Backline wroga = jego jednostka najdalej od naszego spawnu.
    """
    
    def select(
        self,
        source: "Unit",
        candidates: List["Unit"],
        grid: "HexGrid",
        rng: "GameRNG",
    ) -> Optional["Unit"]:
        candidates = self.filter_by_range(source, candidates)
        if not candidates:
            return None
        
        # Określ kierunek backline na podstawie teamu
        # Team 0 spawnuje na górze, backline wroga = niskie r (daleko od nas)
        # Team 1 spawnuje na dole, backline wroga = wysokie r (daleko od nas)
        
        if source.team == 0:
            # Szukamy wroga z najwyższym r (najdalej od naszego spawnu = backline wroga)
            candidates.sort(key=lambda c: c.position.r, reverse=True)
        else:
            # Szukamy wroga z najniższym r (najdalej od naszego spawnu = backline wroga)
            candidates.sort(key=lambda c: c.position.r)
        
        # Znajdź wszystkich na backline (ten sam r)
        back_r = candidates[0].position.r
        backline = [c for c in candidates if c.position.r == back_r]
        
        return self._tiebreaker(backline, rng)


# ═══════════════════════════════════════════════════════════════════════════
# SELEKTOR AKTUALNEGO CELU
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CurrentTargetSelector(TargetSelector):
    """
    Utrzymuje aktualny cel jeśli jest prawidłowy.
    
    Fallback do nearest jeśli brak celu lub martwy.
    """
    
    def select(
        self,
        source: "Unit",
        candidates: List["Unit"],
        grid: "HexGrid",
        rng: "GameRNG",
    ) -> Optional["Unit"]:
        # Sprawdź aktualny cel
        if source.target and source.target.is_alive():
            # Sprawdź max_range
            if self.max_range is None:
                return source.target
            if source.position.distance(source.target.position) <= self.max_range:
                return source.target
        
        # Fallback do nearest
        return NearestSelector(max_range=self.max_range).select(
            source, candidates, grid, rng
        )


# ═══════════════════════════════════════════════════════════════════════════
# FACTORY
# ═══════════════════════════════════════════════════════════════════════════

# Registry selektorów
SELECTOR_REGISTRY: Dict[str, type] = {
    "nearest": NearestSelector,
    "farthest": FarthestSelector,
    "lowest_hp_percent": LowestHPPercentSelector,
    "lowest_hp": LowestHPPercentSelector,  # alias
    "lowest_hp_flat": LowestHPFlatSelector,
    "highest_stat": HighestStatSelector,
    "cluster": ClusterSelector,
    "random": RandomSelector,
    "frontline": FrontlineSelector,
    "backline": BacklineSelector,
    "current_target": CurrentTargetSelector,
}


def get_selector(
    selector_type: str,
    max_range: Optional[int] = None,
    **kwargs: Any
) -> TargetSelector:
    """
    Tworzy selektor na podstawie typu.
    
    Args:
        selector_type: Nazwa selektora (z registry)
        max_range: Opcjonalny limit zasięgu
        **kwargs: Dodatkowe parametry (stat, radius, etc.)
        
    Returns:
        TargetSelector: Instancja selektora
        
    Raises:
        ValueError: Jeśli nieznany typ selektora
        
    Example:
        >>> selector = get_selector("lowest_hp_percent", max_range=5)
        >>> selector = get_selector("highest_stat", stat="attack_damage")
        >>> selector = get_selector("cluster", radius=2)
    """
    selector_class = SELECTOR_REGISTRY.get(selector_type.lower())
    
    if selector_class is None:
        raise ValueError(f"Unknown selector type: {selector_type}. "
                        f"Available: {list(SELECTOR_REGISTRY.keys())}")
    
    return selector_class(max_range=max_range, **kwargs)


def parse_target_type(config: Any) -> TargetSelector:
    """
    Parsuje target_type z YAML do selektora.
    
    Obsługuje dwa formaty:
    1. String: "nearest"
    2. Dict: {selector: "lowest_hp", max_range: 5}
    
    Args:
        config: Wartość target_type z YAML
        
    Returns:
        TargetSelector: Sparsowany selektor
        
    Example:
        >>> parse_target_type("nearest")
        NearestSelector(max_range=None)
        
        >>> parse_target_type({"selector": "cluster", "radius": 3})
        ClusterSelector(max_range=None, radius=3)
    """
    if isinstance(config, str):
        return get_selector(config)
    
    if isinstance(config, dict):
        selector_type = config.get("selector", "nearest")
        max_range = config.get("max_range")
        
        # Wyciągnij dodatkowe parametry
        extra_kwargs = {
            k: v for k, v in config.items() 
            if k not in ("selector", "max_range")
        }
        
        return get_selector(selector_type, max_range=max_range, **extra_kwargs)
    
    # Fallback
    return NearestSelector()
