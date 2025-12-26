"""
Item - definicja przedmiotu i kalkulacja statystyk.

Każdy przedmiot może zawierać:
- Statystyki flat (armor: 20)
- Statystyki procentowe (ad_percent: 0.35)
- Flagi specjalne (ability_crit: true)
- Efekty triggerowane (on_hit, on_ability_cast, etc.)
- Efekty warunkowe (Giant Slayer, etc.)
- Granty traitów (grants_traits: ["mystic"])

FLOW:
═══════════════════════════════════════════════════════════════════════════

    1. Item loaded from YAML
    2. Unit equips item -> ItemStats updated
    3. ItemStats calculates effective stats:
       - Base * (1 + percent_bonus) + flat_bonus
    4. Triggers fired on events (on_hit, on_ability_cast, etc.)
    5. Conditional effects checked during damage calculation
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from enum import Enum, auto

if TYPE_CHECKING:
    from .item_effect import ItemEffect, ConditionalEffect


# ═══════════════════════════════════════════════════════════════════════════
# TRIGGER TYPES
# ═══════════════════════════════════════════════════════════════════════════

class TriggerType(Enum):
    """Typy triggerów dla efektów itemów."""
    
    ON_EQUIP = auto()          # Start walki (gdy item założony)
    ON_HIT = auto()            # Przy każdym podstawowym ataku
    ON_ABILITY_CAST = auto()   # Gdy caster castuje ability
    ON_TAKE_DAMAGE = auto()    # Gdy unit otrzymuje obrażenia
    ON_KILL = auto()           # Po zabiciu wroga
    ON_INTERVAL = auto()       # Co X ticków
    ON_FIRST_CAST = auto()     # Pierwszy cast ability
    ON_DEATH = auto()          # Gdy unit ginie
    
    @classmethod
    def from_string(cls, s: str) -> "TriggerType":
        """Konwertuje string na TriggerType."""
        mapping = {
            "on_equip": cls.ON_EQUIP,
            "on_hit": cls.ON_HIT,
            "on_ability_cast": cls.ON_ABILITY_CAST,
            "on_take_damage": cls.ON_TAKE_DAMAGE,
            "on_kill": cls.ON_KILL,
            "on_interval": cls.ON_INTERVAL,
            "on_first_cast": cls.ON_FIRST_CAST,
            "on_death": cls.ON_DEATH,
        }
        return mapping.get(s.lower(), cls.ON_EQUIP)


@dataclass
class ItemTrigger:
    """Trigger dla efektu itema."""
    
    trigger_type: TriggerType
    params: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ItemTrigger":
        """Tworzy ItemTrigger z danych YAML."""
        trigger_str = data.get("trigger", "on_equip")
        trigger_type = TriggerType.from_string(trigger_str)
        params = data.get("trigger_params", {})
        return cls(trigger_type=trigger_type, params=params)


# ═══════════════════════════════════════════════════════════════════════════
# ITEM
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Item:
    """
    Definicja przedmiotu.
    
    Attributes:
        id: Unikalny identyfikator
        name: Wyświetlana nazwa
        description: Opis efektu
        stats: Statystyki (flat i percent)
        components: Lista komponentów (dla combined items)
        effects: Efekty triggerowane
        conditional_effects: Efekty warunkowe
        flags: Flagi specjalne (ability_crit, etc.)
        grants_traits: Traity nadawane przez item
        unique: Czy tylko jeden taki item per unit
    """
    
    id: str
    name: str
    description: str = ""
    stats: Dict[str, float] = field(default_factory=dict)
    components: List[str] = field(default_factory=list)
    effects: List["ItemEffect"] = field(default_factory=list)
    conditional_effects: List["ConditionalEffect"] = field(default_factory=list)
    flags: Dict[str, bool] = field(default_factory=dict)
    grants_traits: List[str] = field(default_factory=list)
    unique: bool = False
    
    @classmethod
    def from_dict(cls, item_id: str, data: Dict[str, Any]) -> "Item":
        """Tworzy Item z danych YAML."""
        from .item_effect import ItemEffect, ConditionalEffect
        
        # Parse effects
        effects = []
        for effect_data in data.get("effects", []):
            trigger = ItemTrigger.from_dict(effect_data)
            for eff in effect_data.get("effects", []):
                effects.append(ItemEffect.from_dict(eff, trigger))
        
        # Parse conditional effects
        conditional = []
        for cond_data in data.get("conditional_effects", []):
            conditional.append(ConditionalEffect.from_dict(cond_data))
        
        return cls(
            id=item_id,
            name=data.get("name", item_id),
            description=data.get("description", ""),
            stats=data.get("stats", {}),
            components=data.get("components", []),
            effects=effects,
            conditional_effects=conditional,
            flags=data.get("flags", {}),
            grants_traits=data.get("grants_traits", []),
            unique=data.get("unique", False),
        )
    
    def get_flat_stats(self) -> Dict[str, float]:
        """Zwraca tylko flat staty (bez _percent)."""
        return {k: v for k, v in self.stats.items() if not k.endswith("_percent")}
    
    def get_percent_stats(self) -> Dict[str, float]:
        """Zwraca procentowe staty (z _percent w nazwie)."""
        result = {}
        for k, v in self.stats.items():
            if k.endswith("_percent"):
                # Remove "_percent" suffix
                base_stat = k[:-8]
                result[base_stat] = v
        return result
    
    def has_flag(self, flag: str) -> bool:
        """Sprawdza czy item ma flagę."""
        return self.flags.get(flag, False)


# ═══════════════════════════════════════════════════════════════════════════
# ITEM STATS (CALCULATOR)
# ═══════════════════════════════════════════════════════════════════════════

# Mapowanie nazw statów z itemów na nazwy w UnitStats
STAT_MAPPING = {
    "ad": "attack_damage",
    "attack_damage": "attack_damage",
    "ap": "ability_power",
    "ability_power": "ability_power",
    "armor": "armor",
    "mr": "magic_resist",
    "magic_resist": "magic_resist",
    "hp": "hp",
    "max_hp": "hp",
    "attack_speed": "attack_speed",
    "as": "attack_speed",
    "crit_chance": "crit_chance",
    "crit_damage": "crit_damage",
    "dodge_chance": "dodge_chance",
    "lifesteal": "lifesteal",
    "omnivamp": "omnivamp",
    "mana": "mana",
    "start_mana": "start_mana",
    "mana_per_second": "mana_per_second",
}


@dataclass
class ItemStats:
    """
    Kalkulator bonusów z przedmiotów dla jednostki.
    
    Oblicza:
    - Flat bonuses: +20 armor
    - Percent bonuses: +35% AD (z bazy)
    - Special flags: ability_crit
    
    Usage:
        item_stats = ItemStats()
        item_stats.add_item(infinity_edge)
        
        effective_ad = item_stats.get_effective_stat("attack_damage", base_ad)
    """
    
    # Flat bonuses per stat
    _flat_bonuses: Dict[str, float] = field(default_factory=dict)
    
    # Percent bonuses per stat (applied to BASE, not total)
    _percent_bonuses: Dict[str, float] = field(default_factory=dict)
    
    # Special flags
    _flags: Dict[str, bool] = field(default_factory=dict)
    
    # Equipped items (for effect processing)
    _equipped_items: List[Item] = field(default_factory=list)
    
    # Granted traits from items
    _granted_traits: List[str] = field(default_factory=list)
    
    # Stacking stats (for Titan's Resolve etc.)
    _stacking_stats: Dict[str, float] = field(default_factory=dict)
    _stacking_limits: Dict[str, float] = field(default_factory=dict)
    
    def add_item(self, item: Item) -> None:
        """
        Dodaje bonusy z itema.
        
        Args:
            item: Przedmiot do dodania
        """
        self._equipped_items.append(item)
        
        # Add flat stats
        for stat, value in item.get_flat_stats().items():
            normalized = STAT_MAPPING.get(stat, stat)
            self._flat_bonuses[normalized] = self._flat_bonuses.get(normalized, 0) + value
        
        # Add percent stats
        for stat, value in item.get_percent_stats().items():
            normalized = STAT_MAPPING.get(stat, stat)
            self._percent_bonuses[normalized] = self._percent_bonuses.get(normalized, 0) + value
        
        # Add flags
        for flag, value in item.flags.items():
            self._flags[flag] = self._flags.get(flag, False) or value
        
        # Add granted traits
        self._granted_traits.extend(item.grants_traits)
    
    def get_flat_bonus(self, stat: str) -> float:
        """Zwraca flat bonus dla statu."""
        normalized = STAT_MAPPING.get(stat, stat)
        base = self._flat_bonuses.get(normalized, 0)
        stacking = self._stacking_stats.get(normalized, 0)
        return base + stacking
    
    def get_percent_bonus(self, stat: str) -> float:
        """Zwraca procentowy bonus dla statu (0.35 = +35%)."""
        normalized = STAT_MAPPING.get(stat, stat)
        return self._percent_bonuses.get(normalized, 0)
    
    def get_effective_stat(self, stat: str, base_value: float) -> float:
        """
        Oblicza efektywną wartość statystyki.
        
        Formula: (base * (1 + percent_bonus)) + flat_bonus
        
        Args:
            stat: Nazwa statystyki
            base_value: Bazowa wartość statystyki
            
        Returns:
            Efektywna wartość
        """
        percent = self.get_percent_bonus(stat)
        flat = self.get_flat_bonus(stat)
        return (base_value * (1 + percent)) + flat
    
    def has_flag(self, flag: str) -> bool:
        """Sprawdza czy ma flagę z itemów."""
        return self._flags.get(flag, False)
    
    def get_granted_traits(self) -> List[str]:
        """Zwraca listę traitów nadanych przez itemy."""
        return self._granted_traits.copy()
    
    def get_equipped_items(self) -> List[Item]:
        """Zwraca listę wyposażonych itemów."""
        return self._equipped_items.copy()
    
    def add_stacking_stat(self, stat: str, value: float, max_stacks: float) -> bool:
        """
        Dodaje stacking stat (np. Titan's Resolve).
        
        Args:
            stat: Nazwa statystyki
            value: Wartość do dodania
            max_stacks: Maksymalna wartość stacków
            
        Returns:
            True jeśli dodano (nie osiągnięto limitu)
        """
        normalized = STAT_MAPPING.get(stat, stat)
        
        # Set limit if not set
        if normalized not in self._stacking_limits:
            self._stacking_limits[normalized] = max_stacks
        
        current = self._stacking_stats.get(normalized, 0)
        limit = self._stacking_limits[normalized]
        
        if current >= limit:
            return False
        
        new_value = min(current + value, limit)
        self._stacking_stats[normalized] = new_value
        return True
    
    def get_stacking_stat(self, stat: str) -> float:
        """Zwraca aktualną wartość stacking statu."""
        normalized = STAT_MAPPING.get(stat, stat)
        return self._stacking_stats.get(normalized, 0)
    
    def reset(self) -> None:
        """Resetuje wszystkie bonusy (nowa walka)."""
        self._flat_bonuses.clear()
        self._percent_bonuses.clear()
        self._flags.clear()
        self._equipped_items.clear()
        self._granted_traits.clear()
        self._stacking_stats.clear()
        self._stacking_limits.clear()
