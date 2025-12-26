"""
System Champion Classes - modyfikatory zachowania jednostek.

Champion Classes pozwalają na modyfikację:
- Generowania many (mnożniki do attack/damage mana)
- Pasywnej regeneracji many
- Domyślnego selektora targetingu
- Specjalnych zachowań (np. start mana locked)

UŻYCIE:
═══════════════════════════════════════════════════════════════════

    # W units.yaml
    units:
      assassin:
        name: "Assassin"
        mana_class: "assassin"   # używa klasy
        # ... stats
    
    # W kodzie
    class_loader = ChampionClassLoader("data/")
    unit_class = class_loader.get_class("assassin")
    
    # Aplikuj modyfikatory
    mana_from_attack = base_mana * unit_class.mana_per_attack_multiplier

KLASY DOSTĘPNE:
═══════════════════════════════════════════════════════════════════

    sorcerer   - więcej many z damage, pasywna regen, mniej z ataków
    assassin   - skok na backline, szybsza mana z ataków
    guardian   - więcej many z damage, frontline targeting
    marksman   - celuje najdalszego
    executioner - dobija rannych (lowest_hp)
    support    - pasywna regen, start mana locked
    brawler    - balansowane statystyki
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from pathlib import Path
import yaml


@dataclass
class ChampionClass:
    """
    Definicja klasy jednostki.
    
    Attributes:
        id: Identyfikator klasy (np. "assassin")
        name: Nazwa wyświetlana
        description: Opis klasy
        
        mana_per_attack_multiplier: Mnożnik many z ataków (1.0 = 100%)
        mana_from_damage_multiplier: Mnożnik many z otrzymanych obrażeń
        mana_per_second_bonus: Dodatkowa pasywna regeneracja many/s
        
        default_target_selector: Domyślny selektor (None = nearest)
        
        starts_mana_locked: Czy zaczyna z mana lock
        mana_lock_duration_start: Czas mana lock na starcie (ticks)
    """
    id: str
    name: str
    description: str = ""
    
    # Mana modifiers
    mana_per_attack_multiplier: float = 1.0
    mana_from_damage_multiplier: float = 1.0
    mana_per_second_bonus: float = 0.0
    
    # Targeting
    default_target_selector: Optional[str] = None
    
    # Special behavior
    starts_mana_locked: bool = False
    mana_lock_duration_start: int = 0  # ticks
    
    @classmethod
    def from_dict(cls, class_id: str, data: Dict[str, Any]) -> "ChampionClass":
        """
        Tworzy ChampionClass ze słownika (YAML).
        
        Args:
            class_id: ID klasy
            data: Dane z YAML
            
        Returns:
            ChampionClass: Nowa instancja
        """
        return cls(
            id=class_id,
            name=data.get("name", class_id.title()),
            description=data.get("description", ""),
            
            mana_per_attack_multiplier=data.get("mana_per_attack_multiplier", 1.0),
            mana_from_damage_multiplier=data.get("mana_from_damage_multiplier", 1.0),
            mana_per_second_bonus=data.get("mana_per_second_bonus", 0.0),
            
            default_target_selector=data.get("default_target_selector"),
            
            starts_mana_locked=data.get("starts_mana_locked", False),
            mana_lock_duration_start=data.get("mana_lock_duration_start", 0),
        )
    
    def apply_mana_from_attack(self, base_mana: float) -> float:
        """Aplikuje mnożnik do many z ataku."""
        return base_mana * self.mana_per_attack_multiplier
    
    def apply_mana_from_damage(self, base_mana: float) -> float:
        """Aplikuje mnożnik do many z obrażeń."""
        return base_mana * self.mana_from_damage_multiplier
    
    def get_mana_per_tick(self, ticks_per_second: int = 30) -> float:
        """Zwraca pasywną regenerację many per tick."""
        if self.mana_per_second_bonus <= 0:
            return 0.0
        return self.mana_per_second_bonus / ticks_per_second


# Domyślna klasa (brak modyfikacji)
DEFAULT_CLASS = ChampionClass(
    id="default",
    name="Default",
    description="No class modifiers",
)


class ChampionClassLoader:
    """
    Loader klas jednostek z pliku YAML.
    
    Attributes:
        data_path: Ścieżka do folderu data/
        _classes: Cache wczytanych klas
        _enabled: Czy system klas jest włączony
    """
    
    def __init__(self, data_path: str = "data/"):
        """
        Inicjalizuje loader.
        
        Args:
            data_path: Ścieżka do folderu z plikami YAML
        """
        self.data_path = Path(data_path)
        self._classes: Dict[str, ChampionClass] = {}
        self._enabled: bool = True
        self._loaded: bool = False
    
    def _load_config(self) -> None:
        """Wczytuje konfigurację systemu klas z defaults.yaml."""
        defaults_path = self.data_path / "defaults.yaml"
        
        if not defaults_path.exists():
            self._enabled = False
            return
        
        with open(defaults_path, "r", encoding="utf-8") as f:
            defaults = yaml.safe_load(f)
        
        champion_config = defaults.get("champion_classes", {})
        self._enabled = champion_config.get("enabled", True)
    
    def _load_classes(self) -> None:
        """Wczytuje definicje klas z classes.yaml."""
        if self._loaded:
            return
        
        self._load_config()
        
        if not self._enabled:
            self._loaded = True
            return
        
        classes_path = self.data_path / "classes.yaml"
        
        if not classes_path.exists():
            self._loaded = True
            return
        
        with open(classes_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        classes_data = data.get("classes", {})
        
        for class_id, class_config in classes_data.items():
            self._classes[class_id] = ChampionClass.from_dict(class_id, class_config)
        
        self._loaded = True
    
    def is_enabled(self) -> bool:
        """Sprawdza czy system klas jest włączony."""
        self._load_classes()
        return self._enabled
    
    def get_class(self, class_id: Optional[str]) -> ChampionClass:
        """
        Zwraca klasę po ID.
        
        Args:
            class_id: ID klasy lub None
            
        Returns:
            ChampionClass: Klasa lub DEFAULT_CLASS jeśli nie znaleziono
        """
        self._load_classes()
        
        if not self._enabled or class_id is None:
            return DEFAULT_CLASS
        
        return self._classes.get(class_id, DEFAULT_CLASS)
    
    def get_all_classes(self) -> Dict[str, ChampionClass]:
        """Zwraca wszystkie wczytane klasy."""
        self._load_classes()
        return self._classes.copy()
    
    def reload(self) -> None:
        """Przeładowuje klasy z pliku."""
        self._classes.clear()
        self._loaded = False
