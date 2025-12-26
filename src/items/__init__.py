"""
System przedmiotów (Items) dla symulacji auto-battler.

Moduł zawiera:
- Item: Definicja przedmiotu z statami, efektami i flagami
- ItemStats: Kalkulator bonusów z przedmiotów (percent AD/AP, etc.)
- ItemEffect: Efekty triggerowane przez itemy
- ItemManager: Zarządzanie itemami w symulacji
- ConditionalEffect: Efekty warunkowe (np. Giant Slayer)

Użycie:
    from src.items import Item, ItemManager, ItemStats
    
    # Load items
    manager = ItemManager(simulation)
    manager.load_items(items_data)
    
    # Equip item to unit
    manager.equip_item(unit, "infinity_edge")
"""

from .item import (
    Item,
    ItemStats,
    ItemTrigger,
    TriggerType as ItemTriggerType,
)
from .item_effect import (
    ItemEffect,
    ConditionalEffect,
    EffectCondition,
)
from .item_manager import ItemManager

__all__ = [
    # Core
    "Item",
    "ItemStats",
    "ItemTrigger",
    "ItemTriggerType",
    # Effects
    "ItemEffect",
    "ConditionalEffect",
    "EffectCondition",
    # Manager
    "ItemManager",
]
