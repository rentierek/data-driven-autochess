"""
Loader konfiguracji z automatycznym uzupełnianiem wartości domyślnych.

System data-driven wymaga ładowania definicji z plików YAML:
- defaults.yaml: wartości bazowe dla wszystkich statystyk
- units.yaml: definicje jednostek
- abilities.yaml: definicje umiejętności
- items.yaml: definicje przedmiotów

Logika merge (uzupełniania defaults):
    1. Wczytaj defaults.yaml - zawiera wartości bazowe
    2. Wczytaj konkretną definicję (np. jednostka "warrior")
    3. Dla każdego klucza w defaults, którego brak w definicji:
       - Użyj wartości z defaults
    4. Definicja może nadpisać defaults

Przykład:
    defaults.yaml:
        unit_defaults:
            hp: 500
            crit_chance: 0.25
            crit_damage: 1.4
            
    units.yaml:
        warrior:
            hp: 700  # nadpisuje default
            # crit_chance nie podane -> 0.25 z defaults
            # crit_damage nie podane -> 1.4 z defaults

Dzięki temu:
    - Nie musisz powtarzać wszystkich statystyk dla każdej jednostki
    - Możesz globalnie zmienić defaults
    - Definicje jednostek są czytelne i krótkie

Użycie:
    >>> loader = ConfigLoader("data/")
    >>> warrior = loader.load_unit("warrior")
    >>> warrior["crit_chance"]  # 0.25 z defaults
    0.25
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
import copy


class ConfigLoader:
    """
    Ładuje konfigurację z plików YAML z automatycznym merge defaults.
    
    Attributes:
        data_path (Path): Ścieżka do folderu data/
        _defaults (Dict): Cache wczytanych defaults
        _units (Dict): Cache wczytanych jednostek
        _abilities (Dict): Cache wczytanych abilities
        _items (Dict): Cache wczytanych items
        
    Example:
        >>> loader = ConfigLoader("data/")
        >>> unit_data = loader.load_unit("warrior")
        >>> unit_data["hp"]
        700
        >>> unit_data["crit_chance"]  # z defaults
        0.25
    """
    
    def __init__(self, data_path: str = "data/"):
        """
        Inicjalizuje loader z ścieżką do danych.
        
        Args:
            data_path: Ścieżka do folderu z plikami YAML
        """
        self.data_path = Path(data_path)
        self._defaults: Optional[Dict] = None
        self._units: Optional[Dict] = None
        self._abilities: Optional[Dict] = None
        self._items: Optional[Dict] = None
        self._synergies: Optional[Dict] = None
    
    # ─────────────────────────────────────────────────────────────────────────
    # WCZYTYWANIE PLIKÓW
    # ─────────────────────────────────────────────────────────────────────────
    
    def _load_yaml(self, filename: str) -> Dict:
        """
        Wczytuje plik YAML.
        
        Args:
            filename: Nazwa pliku (bez ścieżki)
            
        Returns:
            Dict: Zawartość pliku YAML
            
        Raises:
            FileNotFoundError: Jeśli plik nie istnieje
        """
        filepath = self.data_path / filename
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def get_defaults(self) -> Dict:
        """
        Zwraca słownik z wartościami domyślnymi.
        
        Cache'uje wczytany plik - kolejne wywołania są szybkie.
        
        Returns:
            Dict: Zawartość defaults.yaml
        """
        if self._defaults is None:
            self._defaults = self._load_yaml("defaults.yaml")
        return self._defaults
    
    def get_unit_defaults(self) -> Dict:
        """
        Zwraca domyślne wartości dla jednostek.
        
        Returns:
            Dict: Sekcja unit_defaults z defaults.yaml
        """
        return self.get_defaults().get("unit_defaults", {})
    
    def get_star_modifiers(self) -> Dict:
        """
        Zwraca modyfikatory poziomów gwiazd.
        
        Returns:
            Dict: Mapa star_level -> modyfikatory
        """
        return self.get_defaults().get("star_modifiers", {})
    
    def get_simulation_config(self) -> Dict:
        """
        Zwraca konfigurację symulacji.
        
        Returns:
            Dict: Ustawienia tick rate, grid size, etc.
        """
        return self.get_defaults().get("simulation", {})
    
    # ─────────────────────────────────────────────────────────────────────────
    # ŁADOWANIE JEDNOSTEK
    # ─────────────────────────────────────────────────────────────────────────
    
    def _get_all_units_raw(self) -> Dict:
        """Zwraca wszystkie surowe definicje jednostek."""
        if self._units is None:
            data = self._load_yaml("units.yaml")
            self._units = data.get("units", {})
        return self._units
    
    def load_unit(self, unit_id: str) -> Dict:
        """
        Wczytuje definicję jednostki z uzupełnionymi defaults.
        
        Proces merge:
        1. Zacznij od kopii unit_defaults
        2. Nadpisz wartościami z definicji jednostki
        3. Zwróć wynikowy słownik
        
        Args:
            unit_id: ID jednostki (klucz w units.yaml)
            
        Returns:
            Dict: Pełna definicja jednostki ze wszystkimi statami
            
        Raises:
            KeyError: Jeśli jednostka nie istnieje
            
        Example:
            >>> warrior = loader.load_unit("warrior")
            >>> warrior["hp"]  # z definicji jednostki
            700
            >>> warrior["crit_chance"]  # z defaults
            0.25
        """
        units = self._get_all_units_raw()
        
        if unit_id not in units:
            raise KeyError(f"Unit '{unit_id}' not found in units.yaml")
        
        # Deep copy defaults
        result = copy.deepcopy(self.get_unit_defaults())
        
        # Merge unit-specific values
        unit_data = units[unit_id]
        result = self._deep_merge(result, unit_data)
        
        # Dodaj ID
        result["id"] = unit_id
        
        return result
    
    def load_all_units(self) -> Dict[str, Dict]:
        """
        Wczytuje wszystkie definicje jednostek.
        
        Returns:
            Dict[str, Dict]: Mapa unit_id -> definicja
        """
        units = self._get_all_units_raw()
        return {uid: self.load_unit(uid) for uid in units.keys()}
    
    def get_unit_ids(self) -> list[str]:
        """
        Zwraca listę wszystkich ID jednostek.
        
        Returns:
            List[str]: Lista ID
        """
        return list(self._get_all_units_raw().keys())
    
    # ─────────────────────────────────────────────────────────────────────────
    # ŁADOWANIE ABILITIES
    # ─────────────────────────────────────────────────────────────────────────
    
    def _get_all_abilities_raw(self) -> Dict:
        """Zwraca wszystkie surowe definicje abilities."""
        if self._abilities is None:
            data = self._load_yaml("abilities.yaml")
            self._abilities = data.get("abilities", {})
        return self._abilities
    
    def load_ability(self, ability_id: str) -> Dict:
        """
        Wczytuje definicję umiejętności.
        
        Args:
            ability_id: ID ability
            
        Returns:
            Dict: Definicja umiejętności
            
        Raises:
            KeyError: Jeśli ability nie istnieje
        """
        abilities = self._get_all_abilities_raw()
        
        if ability_id not in abilities:
            raise KeyError(f"Ability '{ability_id}' not found in abilities.yaml")
        
        result = copy.deepcopy(abilities[ability_id])
        result["id"] = ability_id
        
        return result
    
    # ─────────────────────────────────────────────────────────────────────────
    # ŁADOWANIE ITEMS
    # ─────────────────────────────────────────────────────────────────────────
    
    def _get_all_items_raw(self) -> Dict:
        """Zwraca wszystkie surowe definicje itemów."""
        if self._items is None:
            data = self._load_yaml("items.yaml")
            self._items = data.get("items", {})
        return self._items
    
    def load_item(self, item_id: str) -> Dict:
        """
        Wczytuje definicję przedmiotu.
        
        Args:
            item_id: ID itema
            
        Returns:
            Dict: Definicja przedmiotu
            
        Raises:
            KeyError: Jeśli item nie istnieje
        """
        items = self._get_all_items_raw()
        
        if item_id not in items:
            raise KeyError(f"Item '{item_id}' not found in items.yaml")
        
        result = copy.deepcopy(items[item_id])
        result["id"] = item_id
        
        return result
    
    # ─────────────────────────────────────────────────────────────────────────
    # HELPERY
    # ─────────────────────────────────────────────────────────────────────────
    
    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        """
        Głęboko łączy dwa słowniki.
        
        Override nadpisuje wartości w base.
        Nested dicts są merge'owane rekurencyjnie.
        
        Args:
            base: Słownik bazowy (domyślne wartości)
            override: Słownik nadpisujący
            
        Returns:
            Dict: Połączony słownik
        """
        result = copy.deepcopy(base)
        
        for key, value in override.items():
            if (
                key in result 
                and isinstance(result[key], dict) 
                and isinstance(value, dict)
            ):
                result[key] = ConfigLoader._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        
        return result
    
    def reload(self) -> None:
        """
        Czyści cache i wymusza ponowne wczytanie plików.
        
        Przydatne podczas edycji plików YAML w runtime.
        """
        self._defaults = None
        self._units = None
        self._abilities = None
        self._items = None
        self._synergies = None
