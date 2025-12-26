"""
UnitStats - przechowuje wszystkie statystyki jednostki.

Statystyki jednostki dzielą się na:
1. BAZOWE (base_*) - wartości z definicji jednostki lub defaults
2. PŁASKIE BONUSY (flat_*) - dodawane bezpośrednio (z itemów, buffów)
3. PROCENTOWE BONUSY (percent_*) - mnożniki procentowe

Wzór obliczania efektywnej statystyki:
    effective = (base + flat_bonus) * (1 + percent_bonus)
    
Przykład:
    base_attack_damage = 100
    flat_attack_damage = 20  (z itemu)
    percent_attack_damage = 0.1  (10% z buffa)
    
    effective = (100 + 20) * (1 + 0.1) = 120 * 1.1 = 132

Lista wszystkich statystyk:
─────────────────────────────────────────────────────────────────
Statystyka          | Opis                           | Default
─────────────────────────────────────────────────────────────────
hp                  | Aktualne punkty życia          | 500
max_hp              | Maksymalne HP                  | 500
mana                | Aktualna mana                  | 0
max_mana            | Maksymalna mana                | 100
start_mana          | Mana na starcie walki          | 0
attack_damage       | Obrażenia bazowe (AD)          | 50
ability_power       | Moc umiejętności (AP)          | 0
armor               | Pancerz (redukcja phys dmg)    | 20
magic_resist        | Odporność mag (redukcja mag)   | 20
attack_speed        | Ataki na sekundę               | 0.7
attack_range        | Zasięg w hexach (1=melee)      | 1
movement_speed      | Hexy na tick                   | 1.0
crit_chance         | Szansa na krytyka              | 0.25
crit_damage         | Mnożnik krytyka                | 1.4
dodge_chance        | Szansa na unik                 | 0.0
lifesteal           | % dmg fizycznego jako HP       | 0.0
spell_vamp          | % dmg ze spelli jako HP        | 0.0
─────────────────────────────────────────────────────────────────

Star Level Modifiers (mnożniki gwiazd):
    1★: HP×1.0, DMG×1.0
    2★: HP×1.8, DMG×1.8
    3★: HP×3.24, DMG×3.24

Crit działa TYLKO na auto-ataki (nie na umiejętności).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class UnitStats:
    """
    Kontener na wszystkie statystyki jednostki.
    
    Przechowuje wartości bazowe oraz modyfikatory.
    Efektywne wartości obliczane są przez metody get_*.
    
    Attributes:
        base_hp (float): Bazowe max HP
        base_attack_damage (float): Bazowe AD
        base_ability_power (float): Bazowe AP
        base_armor (float): Bazowy pancerz
        base_magic_resist (float): Bazowa MR
        base_attack_speed (float): Bazowe AS
        base_attack_range (int): Bazowy zasięg
        base_movement_speed (float): Bazowa prędkość
        base_crit_chance (float): Bazowa szansa na crit
        base_crit_damage (float): Bazowy mnożnik crita
        base_dodge_chance (float): Bazowa szansa na unik
        base_lifesteal (float): Bazowy lifesteal
        base_spell_vamp (float): Bazowy spell vamp
        base_max_mana (float): Bazowe max mana
        base_start_mana (float): Bazowa mana startowa
        
        current_hp (float): Aktualne HP
        current_mana (float): Aktualna mana
        
        flat_* / percent_*: Modyfikatory z itemów/buffów
        
    Example:
        >>> stats = UnitStats.from_dict({"hp": 700, "crit_chance": 0.35})
        >>> stats.get_crit_chance()
        0.35
        >>> stats.add_flat_modifier("attack_damage", 20)
        >>> stats.get_attack_damage()  # 50 + 20 = 70 (jeśli base=50)
        70.0
    """
    
    # ─────────────────────────────────────────────────────────────────────────
    # WARTOŚCI BAZOWE
    # ─────────────────────────────────────────────────────────────────────────
    
    base_hp: float = 500.0
    base_attack_damage: float = 50.0
    base_ability_power: float = 0.0
    base_armor: float = 20.0
    base_magic_resist: float = 20.0
    base_attack_speed: float = 0.7
    base_attack_range: int = 1
    base_movement_speed: float = 1.0
    base_crit_chance: float = 0.25
    base_crit_damage: float = 1.4
    base_dodge_chance: float = 0.0
    base_lifesteal: float = 0.0
    base_spell_vamp: float = 0.0
    base_max_mana: float = 100.0
    base_start_mana: float = 0.0
    
    # ─────────────────────────────────────────────────────────────────────────
    # AKTUALNE WARTOŚCI (zmieniają się w trakcie walki)
    # ─────────────────────────────────────────────────────────────────────────
    
    current_hp: float = field(default=0.0, repr=False)
    current_mana: float = field(default=0.0, repr=False)
    
    # ─────────────────────────────────────────────────────────────────────────
    # MODYFIKATORY (z itemów, buffów, synergii)
    # ─────────────────────────────────────────────────────────────────────────
    
    # Flat bonuses (dodawane bezpośrednio)
    flat_hp: float = field(default=0.0, repr=False)
    flat_attack_damage: float = field(default=0.0, repr=False)
    flat_ability_power: float = field(default=0.0, repr=False)
    flat_armor: float = field(default=0.0, repr=False)
    flat_magic_resist: float = field(default=0.0, repr=False)
    flat_attack_speed: float = field(default=0.0, repr=False)
    flat_crit_chance: float = field(default=0.0, repr=False)
    flat_crit_damage: float = field(default=0.0, repr=False)
    flat_dodge_chance: float = field(default=0.0, repr=False)
    flat_lifesteal: float = field(default=0.0, repr=False)
    flat_spell_vamp: float = field(default=0.0, repr=False)
    flat_mana: float = field(default=0.0, repr=False)
    flat_omnivamp: float = field(default=0.0, repr=False)  # Heal from ALL damage
    
    # Percent bonuses (mnożniki, np. 0.1 = +10%)
    percent_hp: float = field(default=0.0, repr=False)
    percent_attack_damage: float = field(default=0.0, repr=False)
    percent_ability_power: float = field(default=0.0, repr=False)
    percent_armor: float = field(default=0.0, repr=False)
    percent_magic_resist: float = field(default=0.0, repr=False)
    percent_attack_speed: float = field(default=0.0, repr=False)
    
    # Special stats
    base_omnivamp: float = field(default=0.0, repr=False)  # % heal from all damage
    
    def __post_init__(self):
        """Inicjalizuje HP i mana na wartości startowe."""
        if self.current_hp == 0.0:
            self.current_hp = self.get_max_hp()
        if self.current_mana == 0.0:
            self.current_mana = self.base_start_mana
    
    # ─────────────────────────────────────────────────────────────────────────
    # FACTORY METHODS
    # ─────────────────────────────────────────────────────────────────────────
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UnitStats":
        """
        Tworzy UnitStats ze słownika (np. z YAML).
        
        Mapowanie kluczy z YAML/JSON na atrybuty:
            hp -> base_hp
            attack_damage -> base_attack_damage
            crit_chance -> base_crit_chance
            etc.
        
        Args:
            data: Słownik z definicji jednostki
            
        Returns:
            UnitStats: Nowa instancja
            
        Example:
            >>> data = {"hp": 700, "crit_chance": 0.35, "attack_range": 4}
            >>> stats = UnitStats.from_dict(data)
            >>> stats.base_hp
            700.0
        """
        stats = cls()
        
        # Mapowanie nazw z YAML na atrybuty
        mapping = {
            "hp": "base_hp",
            "max_hp": "base_hp",  # alias
            "attack_damage": "base_attack_damage",
            "ability_power": "base_ability_power",
            "armor": "base_armor",
            "magic_resist": "base_magic_resist",
            "attack_speed": "base_attack_speed",
            "attack_range": "base_attack_range",
            "movement_speed": "base_movement_speed",
            "crit_chance": "base_crit_chance",
            "crit_damage": "base_crit_damage",
            "dodge_chance": "base_dodge_chance",
            "lifesteal": "base_lifesteal",
            "spell_vamp": "base_spell_vamp",
            "max_mana": "base_max_mana",
            "start_mana": "base_start_mana",
            "mana": "current_mana",  # aktualna mana
        }
        
        for yaml_key, attr_name in mapping.items():
            if yaml_key in data:
                setattr(stats, attr_name, float(data[yaml_key]))
        
        # Reinicjalizuj HP i mana
        stats.current_hp = stats.get_max_hp()
        stats.current_mana = stats.base_start_mana
        
        return stats
    
    # ─────────────────────────────────────────────────────────────────────────
    # EFEKTYWNE WARTOŚCI (base + modyfikatory)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _calc_effective(self, base: float, flat: float, percent: float) -> float:
        """
        Oblicza efektywną wartość statystyki.
        
        Wzór: (base + flat) * (1 + percent)
        """
        return (base + flat) * (1 + percent)
    
    def get_max_hp(self) -> float:
        """Zwraca efektywne maksymalne HP."""
        return self._calc_effective(
            self.base_hp, self.flat_hp, self.percent_hp
        )
    
    def get_attack_damage(self) -> float:
        """Zwraca efektywne obrażenia ataku."""
        return self._calc_effective(
            self.base_attack_damage, 
            self.flat_attack_damage, 
            self.percent_attack_damage
        )
    
    def get_ability_power(self) -> float:
        """Zwraca efektywną moc umiejętności."""
        return self._calc_effective(
            self.base_ability_power,
            self.flat_ability_power,
            self.percent_ability_power
        )
    
    def get_armor(self) -> float:
        """Zwraca efektywny pancerz."""
        return self._calc_effective(
            self.base_armor, self.flat_armor, self.percent_armor
        )
    
    def get_magic_resist(self) -> float:
        """Zwraca efektywną odporność na magię."""
        return self._calc_effective(
            self.base_magic_resist, 
            self.flat_magic_resist, 
            self.percent_magic_resist
        )
    
    def get_attack_speed(self) -> float:
        """
        Zwraca efektywną prędkość ataku.
        
        Ograniczona do zakresu [0.2, 5.0] (TFT-style cap).
        """
        raw = self._calc_effective(
            self.base_attack_speed,
            self.flat_attack_speed,
            self.percent_attack_speed
        )
        return max(0.2, min(5.0, raw))
    
    def get_attack_range(self) -> int:
        """Zwraca zasięg ataku (bez modyfikatorów - zazwyczaj stały)."""
        return self.base_attack_range
    
    def get_movement_speed(self) -> float:
        """Zwraca prędkość ruchu."""
        return self.base_movement_speed
    
    def get_crit_chance(self) -> float:
        """
        Zwraca szansę na krytyka.
        
        Ograniczona do [0.0, 1.0].
        """
        raw = self.base_crit_chance + self.flat_crit_chance
        return max(0.0, min(1.0, raw))
    
    def get_crit_damage(self) -> float:
        """
        Zwraca mnożnik krytyka.
        
        Minimum 1.0 (100% = brak bonusu).
        """
        raw = self.base_crit_damage + self.flat_crit_damage
        return max(1.0, raw)
    
    def get_dodge_chance(self) -> float:
        """
        Zwraca szansę na unik.
        
        Ograniczona do [0.0, 1.0].
        """
        raw = self.base_dodge_chance + self.flat_dodge_chance
        return max(0.0, min(1.0, raw))
    
    def get_lifesteal(self) -> float:
        """Zwraca lifesteal (może przekroczyć 1.0)."""
        return self.base_lifesteal + self.flat_lifesteal
    
    def get_spell_vamp(self) -> float:
        """Zwraca spell vamp."""
        return self.base_spell_vamp + self.flat_spell_vamp
    
    def get_max_mana(self) -> float:
        """Zwraca maksymalną manę."""
        return self.base_max_mana + self.flat_mana
    
    def get_omnivamp(self) -> float:
        """
        Zwraca omnivamp (heal z wszystkich obrażeń).
        
        Ograniczone do [0.0, 1.0].
        """
        raw = self.base_omnivamp + self.flat_omnivamp
        return max(0.0, min(1.0, raw))
    
    # ─────────────────────────────────────────────────────────────────────────
    # MODYFIKACJA STATYSTYK
    # ─────────────────────────────────────────────────────────────────────────
    
    def add_flat_modifier(self, stat: str, value: float) -> None:
        """
        Dodaje płaski modyfikator do statystyki.
        
        Args:
            stat: Nazwa statystyki (np. "attack_damage", "hp")
            value: Wartość do dodania
            
        Example:
            >>> stats.add_flat_modifier("attack_damage", 20)
        """
        attr = f"flat_{stat}"
        if hasattr(self, attr):
            current = getattr(self, attr)
            setattr(self, attr, current + value)
    
    def add_percent_modifier(self, stat: str, value: float) -> None:
        """
        Dodaje procentowy modyfikator do statystyki.
        
        Args:
            stat: Nazwa statystyki
            value: Wartość (np. 0.1 = +10%)
            
        Example:
            >>> stats.add_percent_modifier("attack_speed", 0.25)  # +25% AS
        """
        attr = f"percent_{stat}"
        if hasattr(self, attr):
            current = getattr(self, attr)
            setattr(self, attr, current + value)
    
    def remove_flat_modifier(self, stat: str, value: float) -> None:
        """Usuwa płaski modyfikator."""
        self.add_flat_modifier(stat, -value)
    
    def remove_percent_modifier(self, stat: str, value: float) -> None:
        """Usuwa procentowy modyfikator."""
        self.add_percent_modifier(stat, -value)
    
    def apply_star_level(self, star_level: int, modifiers: Dict[int, Dict]) -> None:
        """
        Aplikuje modyfikatory poziomu gwiazd.
        
        Args:
            star_level: Poziom gwiazd (1, 2, lub 3)
            modifiers: Słownik z star_modifiers z defaults
            
        Example:
            >>> stats.apply_star_level(2, {2: {"hp_multiplier": 1.8, "damage_multiplier": 1.8}})
        """
        if star_level not in modifiers:
            return
        
        mods = modifiers[star_level]
        
        hp_mult = mods.get("hp_multiplier", 1.0)
        dmg_mult = mods.get("damage_multiplier", 1.0)
        
        self.base_hp *= hp_mult
        self.base_attack_damage *= dmg_mult
        self.base_ability_power *= dmg_mult
        
        # Aktualizuj current_hp
        self.current_hp = self.get_max_hp()
    
    # ─────────────────────────────────────────────────────────────────────────
    # HP I MANA MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────
    
    def take_damage(self, amount: float) -> float:
        """
        Otrzymuje obrażenia (po redukcji).
        
        Args:
            amount: Ilość obrażeń
            
        Returns:
            float: Faktycznie zadane obrażenia
        """
        actual = min(self.current_hp, amount)
        self.current_hp -= actual
        return actual
    
    def heal(self, amount: float) -> float:
        """
        Leczy jednostkę.
        
        Args:
            amount: Ilość leczenia
            
        Returns:
            float: Faktycznie wyleczone HP
        """
        max_hp = self.get_max_hp()
        actual = min(max_hp - self.current_hp, amount)
        self.current_hp += actual
        return actual
    
    def add_mana(self, amount: float) -> float:
        """
        Dodaje manę (np. z ataku lub otrzymanych obrażeń).
        
        Mana jest ograniczona do max_mana.
        
        Args:
            amount: Ilość many
            
        Returns:
            float: Overflow (nadmiar many ponad max)
        """
        max_mana = self.get_max_mana()
        new_mana = self.current_mana + amount
        self.current_mana = min(max_mana, new_mana)
        
        # Return overflow
        overflow = max(0.0, new_mana - max_mana)
        return overflow
    
    def spend_mana(self, amount: float) -> bool:
        """
        Wydaje manę na umiejętność.
        
        Args:
            amount: Koszt many
            
        Returns:
            bool: True jeśli wystarczyło many
        """
        if self.current_mana >= amount:
            self.current_mana -= amount
            return True
        return False
    
    def is_mana_full(self) -> bool:
        """Sprawdza czy mana jest pełna."""
        return self.current_mana >= self.get_max_mana()
    
    def is_alive(self) -> bool:
        """Sprawdza czy jednostka żyje."""
        return self.current_hp > 0
    
    def hp_percent(self) -> float:
        """Zwraca procent HP (0.0 - 1.0)."""
        max_hp = self.get_max_hp()
        if max_hp <= 0:
            return 0.0
        return self.current_hp / max_hp
    
    def mana_percent(self) -> float:
        """Zwraca procent many (0.0 - 1.0)."""
        max_mana = self.get_max_mana()
        if max_mana <= 0:
            return 1.0
        return self.current_mana / max_mana
    
    # ─────────────────────────────────────────────────────────────────────────
    # RESET
    # ─────────────────────────────────────────────────────────────────────────
    
    def reset_for_combat(self) -> None:
        """
        Resetuje statystyki na początek walki.
        
        - HP = max HP
        - Mana = start_mana
        """
        self.current_hp = self.get_max_hp()
        self.current_mana = self.base_start_mana
    
    def clear_modifiers(self) -> None:
        """Czyści wszystkie modyfikatory (flat i percent)."""
        # Flat
        self.flat_hp = 0.0
        self.flat_attack_damage = 0.0
        self.flat_ability_power = 0.0
        self.flat_armor = 0.0
        self.flat_magic_resist = 0.0
        self.flat_attack_speed = 0.0
        self.flat_crit_chance = 0.0
        self.flat_crit_damage = 0.0
        self.flat_dodge_chance = 0.0
        self.flat_lifesteal = 0.0
        self.flat_spell_vamp = 0.0
        self.flat_mana = 0.0
        
        # Percent
        self.percent_hp = 0.0
        self.percent_attack_damage = 0.0
        self.percent_ability_power = 0.0
        self.percent_armor = 0.0
        self.percent_magic_resist = 0.0
        self.percent_attack_speed = 0.0
