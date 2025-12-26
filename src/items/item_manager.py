"""
ItemManager - zarządza przedmiotami w symulacji.

ODPOWIEDZIALNOŚCI:
═══════════════════════════════════════════════════════════════════════════

    1. Ładowanie definicji itemów z YAML
    2. Wyposażanie jednostek w przedmioty
    3. Obliczanie bonusów statystyk
    4. Obsługa triggerów (on_hit, on_ability_cast, etc.)
    5. Aplikowanie efektów przedmiotów

FLOW:
═══════════════════════════════════════════════════════════════════════════

    on_battle_start():
        - Equip items to units
        - Apply on_equip effects
        - Add granted traits
    
    on_hit(attacker, defender):
        - Apply on_hit effects
        - Apply conditional effects
    
    on_ability_cast(caster):
        - Apply on_ability_cast effects
        - Apply on_first_cast effects (once per battle)
    
    on_tick(tick):
        - Apply on_interval effects
    
    on_take_damage(unit, damage):
        - Apply on_take_damage effects
    
    on_kill(killer, victim):
        - Apply on_kill effects
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, TYPE_CHECKING, Callable
from collections import defaultdict

from .item import Item, ItemStats, ItemTrigger, TriggerType
from .item_effect import ItemEffect, ConditionalEffect, EffectTarget

if TYPE_CHECKING:
    from ..units.unit import Unit
    from ..simulation.simulation import Simulation


# ═══════════════════════════════════════════════════════════════════════════
# EFFECT APPLICATORS
# ═══════════════════════════════════════════════════════════════════════════

def apply_stat_bonus(
    owner: "Unit", 
    targets: List["Unit"], 
    effect: ItemEffect,
    simulation: "Simulation",
) -> int:
    """Aplikuje bonus statystyki."""
    stat = effect.params.get("stat", "attack_damage")
    value = effect.value
    count = 0
    
    for unit in targets:
        if not unit.is_alive():
            continue
        
        # Apply using item_stats stacking if applicable
        if effect.params.get("stacking"):
            max_stacks = effect.params.get("max_stacks", 25)
            if unit.item_stats.add_stacking_stat(stat, value, max_stacks * value):
                count += 1
        else:
            # Direct stat modification
            if stat == "armor":
                unit.stats.base_armor += value
            elif stat == "magic_resist":
                unit.stats.base_magic_resist += value
            elif stat == "attack_damage":
                unit.stats.base_attack_damage += value
            elif stat == "ability_power":
                unit.stats.base_ability_power += value
            elif stat == "attack_speed":
                unit.stats.base_attack_speed += value
            elif stat == "hp":
                unit.stats.base_hp += value
                unit.stats.current_hp += value
            elif stat == "crit_chance":
                unit.stats.base_crit_chance += value
            elif stat == "crit_damage":
                unit.stats.base_crit_damage += value
            count += 1
    
    return count


def apply_stacking_stat(
    owner: "Unit",
    targets: List["Unit"],
    effect: ItemEffect,
    simulation: "Simulation",
) -> int:
    """Aplikuje stackujący się bonus (Titan's Resolve)."""
    stat = effect.params.get("stat", "attack_damage")
    value = effect.value
    max_stacks = effect.params.get("max_stacks", 25)
    count = 0
    
    for unit in targets:
        if not unit.is_alive():
            continue
        
        # Use the item_stats stacking system
        if unit.item_stats.add_stacking_stat(stat, value, max_stacks * value):
            count += 1
    
    return count


def apply_mana_grant(
    owner: "Unit",
    targets: List["Unit"],
    effect: ItemEffect,
    simulation: "Simulation",
) -> int:
    """Daje manę."""
    value = effect.value
    count = 0
    
    for unit in targets:
        if not unit.is_alive():
            continue
        unit.stats.add_mana(value)
        count += 1
    
    return count


def apply_heal(
    owner: "Unit",
    targets: List["Unit"],
    effect: ItemEffect,
    simulation: "Simulation",
) -> int:
    """Leczy jednostki."""
    value = effect.value
    count = 0
    
    for unit in targets:
        if not unit.is_alive():
            continue
        unit.stats.heal(value)
        count += 1
    
    return count


def apply_shield(
    owner: "Unit",
    targets: List["Unit"],
    effect: ItemEffect,
    simulation: "Simulation",
) -> int:
    """Daje tarczę."""
    value = effect.value
    duration = effect.params.get("duration", 999)
    count = 0
    
    for unit in targets:
        if not unit.is_alive():
            continue
        unit.add_shield(value, duration)
        count += 1
    
    return count


def apply_slow(
    owner: "Unit",
    targets: List["Unit"],
    effect: ItemEffect,
    simulation: "Simulation",
) -> int:
    """Aplicuje spowolnienie."""
    value = effect.value
    duration = effect.params.get("duration", 60)
    count = 0
    
    for unit in targets:
        if not unit.is_alive():
            continue
        # Use the existing add_slow method on Unit
        unit.add_slow(value, duration)
        count += 1
    
    return count


def apply_damage(
    owner: "Unit",
    targets: List["Unit"],
    effect: ItemEffect,
    simulation: "Simulation",
) -> int:
    """Zadaje obrażenia."""
    value = effect.value
    damage_type = effect.params.get("damage_type", "magic")
    count = 0
    
    from ..combat.damage import DamageType, calculate_damage, apply_damage
    
    for unit in targets:
        if not unit.is_alive():
            continue
        
        dtype = DamageType.MAGICAL if damage_type == "magic" else DamageType.PHYSICAL
        result = calculate_damage(
            attacker=owner,
            defender=unit,
            base_damage=value,
            damage_type=dtype,
            rng=simulation.rng,
            can_crit=False,
            can_dodge=False,
            is_ability=True,
        )
        apply_damage(owner, unit, result)
        count += 1
    
    return count


# Registry efektów itemów
ITEM_EFFECT_APPLICATORS: Dict[str, Callable] = {
    "stat_bonus": apply_stat_bonus,
    "stacking_stat": apply_stacking_stat,
    "mana_grant": apply_mana_grant,
    "heal": apply_heal,
    "shield": apply_shield,
    "slow": apply_slow,
    "damage": apply_damage,
}


# ═══════════════════════════════════════════════════════════════════════════
# ITEM MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class ItemManager:
    """
    Zarządza systemem przedmiotów w symulacji.
    
    Odpowiedzialności:
        - Ładowanie definicji itemów
        - Wyposażanie jednostek
        - Obsługa triggerów
        - Aplikowanie efektów
    
    Attributes:
        simulation: Referencja do symulacji
        items: Załadowane definicje itemów
        _first_cast_triggered: Set unit IDs które już castowały
    """
    
    MAX_ITEM_SLOTS = 3
    
    def __init__(self, simulation: "Simulation"):
        self.simulation = simulation
        self.items: Dict[str, Item] = {}
        self._first_cast_triggered: Set[str] = set()
    
    def load_items(self, items_data: Dict[str, Dict]) -> None:
        """
        Ładuje definicje itemów z YAML.
        
        Args:
            items_data: Słownik item_id -> definicja
        """
        for item_id, data in items_data.items():
            self.items[item_id] = Item.from_dict(item_id, data)
    
    def get_item(self, item_id: str) -> Optional[Item]:
        """Zwraca item po ID."""
        return self.items.get(item_id)
    
    # ─────────────────────────────────────────────────────────────────────────
    # EQUIPPING
    # ─────────────────────────────────────────────────────────────────────────
    
    def equip_item(self, unit: "Unit", item_id: str) -> bool:
        """
        Wyposaża jednostkę w przedmiot.
        
        Args:
            unit: Jednostka
            item_id: ID przedmiotu
            
        Returns:
            True jeśli sukces
        """
        item = self.items.get(item_id)
        if not item:
            return False
        
        # Check slot limit
        if len(unit.equipped_items) >= self.MAX_ITEM_SLOTS:
            return False
        
        # Check unique
        if item.unique:
            for equipped in unit.equipped_items:
                if equipped.id == item.id:
                    return False
        
        # Equip
        unit.equipped_items.append(item)
        unit.item_stats.add_item(item)
        
        # Add granted traits
        for trait_id in item.grants_traits:
            if trait_id not in unit.traits:
                unit.traits.append(trait_id)
        
        return True
    
    def equip_items_from_config(self, unit: "Unit", item_ids: List[str]) -> int:
        """
        Wyposaża jednostkę w przedmioty z configu.
        
        Returns:
            Liczba wyposażonych itemów
        """
        count = 0
        for item_id in item_ids[:self.MAX_ITEM_SLOTS]:
            if self.equip_item(unit, item_id):
                count += 1
        return count
    
    # ─────────────────────────────────────────────────────────────────────────
    # TARGET RESOLUTION
    # ─────────────────────────────────────────────────────────────────────────
    
    def _get_targets(
        self,
        owner: "Unit",
        target: EffectTarget,
        attack_target: Optional["Unit"] = None,
        range_param: int = 2,
    ) -> List["Unit"]:
        """Zwraca listę celów dla efektu."""
        targets = []
        
        if target == EffectTarget.SELF:
            if owner.is_alive():
                targets.append(owner)
                
        elif target == EffectTarget.TARGET:
            if attack_target and attack_target.is_alive():
                targets.append(attack_target)
                
        elif target == EffectTarget.ENEMIES:
            enemy_team = 1 if owner.team == 0 else 0
            targets = [u for u in self.simulation.units 
                      if u.is_alive() and u.team == enemy_team]
                      
        elif target == EffectTarget.ALLIES:
            targets = [u for u in self.simulation.units
                      if u.is_alive() and u.team == owner.team]
                      
        elif target == EffectTarget.ENEMIES_IN_RANGE:
            enemy_team = 1 if owner.team == 0 else 0
            for u in self.simulation.units:
                if u.is_alive() and u.team == enemy_team:
                    dist = owner.position.distance(u.position)
                    if dist <= range_param:
                        targets.append(u)
                        
        elif target == EffectTarget.ALLIES_IN_RANGE:
            for u in self.simulation.units:
                if u.is_alive() and u.team == owner.team:
                    dist = owner.position.distance(u.position)
                    if dist <= range_param:
                        targets.append(u)
                        
        elif target == EffectTarget.ALLIES_IN_ROW:
            # Same row (r coordinate in hex)
            owner_r = owner.position.r
            targets = [u for u in self.simulation.units
                      if u.is_alive() and u.team == owner.team and u.position.r == owner_r]
                      
        elif target == EffectTarget.ADJACENT:
            for neighbor_pos in owner.position.neighbors():
                neighbor = self.simulation.grid.get_unit_at(neighbor_pos)
                if neighbor and neighbor.is_alive():
                    targets.append(neighbor)
        
        return targets
    
    # ─────────────────────────────────────────────────────────────────────────
    # EFFECT APPLICATION
    # ─────────────────────────────────────────────────────────────────────────
    
    def _apply_effect(
        self,
        owner: "Unit",
        effect: ItemEffect,
        attack_target: Optional["Unit"] = None,
    ) -> int:
        """Aplikuje pojedynczy efekt itema."""
        range_param = effect.params.get("range", 2)
        targets = self._get_targets(owner, effect.target, attack_target, range_param)
        
        applicator = ITEM_EFFECT_APPLICATORS.get(effect.effect_type)
        if applicator:
            return applicator(owner, targets, effect, self.simulation)
        
        return 0
    
    def _apply_triggered_effects(
        self,
        unit: "Unit",
        trigger_type: TriggerType,
        attack_target: Optional["Unit"] = None,
    ) -> None:
        """Aplikuje efekty z danym triggerem."""
        for item in unit.equipped_items:
            for effect in item.effects:
                if effect.trigger and effect.trigger.trigger_type == trigger_type:
                    # Check trigger params (e.g. interval)
                    if trigger_type == TriggerType.ON_INTERVAL:
                        interval = effect.trigger.params.get("interval", 120)
                        tick = self.simulation.tick
                        if tick == 0 or tick % interval != 0:
                            continue
                    
                    self._apply_effect(unit, effect, attack_target)
    
    # ─────────────────────────────────────────────────────────────────────────
    # TRIGGER HANDLERS
    # ─────────────────────────────────────────────────────────────────────────
    
    def on_battle_start(self) -> None:
        """Wywoływane na początku walki."""
        self._first_cast_triggered.clear()
        
        for unit in self.simulation.units:
            if not unit.is_alive():
                continue
            
            # Apply on_equip effects
            self._apply_triggered_effects(unit, TriggerType.ON_EQUIP)
    
    def on_tick(self, tick: int) -> None:
        """Wywoływane co tick."""
        if tick == 0:
            return
        
        for unit in self.simulation.units:
            if not unit.is_alive():
                continue
            
            self._apply_triggered_effects(unit, TriggerType.ON_INTERVAL)
    
    def on_hit(self, attacker: "Unit", defender: "Unit") -> None:
        """Wywoływane przy podstawowym ataku."""
        if not attacker.is_alive():
            return
        
        self._apply_triggered_effects(attacker, TriggerType.ON_HIT, defender)
    
    def on_ability_cast(self, caster: "Unit") -> None:
        """Wywoływane gdy jednostka castuje ability."""
        if not caster.is_alive():
            return
        
        # Check first cast
        if caster.id not in self._first_cast_triggered:
            self._first_cast_triggered.add(caster.id)
            self._apply_triggered_effects(caster, TriggerType.ON_FIRST_CAST)
        
        self._apply_triggered_effects(caster, TriggerType.ON_ABILITY_CAST)
    
    def on_take_damage(self, unit: "Unit", damage: float) -> None:
        """Wywoływane gdy jednostka otrzymuje obrażenia."""
        if not unit.is_alive():
            return
        
        self._apply_triggered_effects(unit, TriggerType.ON_TAKE_DAMAGE)
    
    def on_kill(self, killer: "Unit", victim: "Unit") -> None:
        """Wywoływane gdy jednostka zabija wroga."""
        if not killer.is_alive():
            return
        
        self._apply_triggered_effects(killer, TriggerType.ON_KILL, victim)
    
    # ─────────────────────────────────────────────────────────────────────────
    # CONDITIONAL EFFECTS (DAMAGE CALC)
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_conditional_modifiers(
        self, 
        attacker: "Unit", 
        defender: "Unit"
    ) -> Dict[str, float]:
        """
        Zwraca modyfikatory z efektów warunkowych.
        
        Wywoływane podczas damage calculation.
        
        Returns:
            Dict z modyfikatorami (damage_amp, damage_reduction, etc.)
        """
        modifiers: Dict[str, float] = defaultdict(float)
        
        for item in attacker.equipped_items:
            for cond_effect in item.conditional_effects:
                mods = cond_effect.check_and_get_modifier(attacker, defender)
                if mods:
                    for key, value in mods.items():
                        modifiers[key] += value
        
        return dict(modifiers)
    
    # ─────────────────────────────────────────────────────────────────────────
    # DEBUG / INFO
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_unit_items_summary(self, unit: "Unit") -> List[Dict[str, Any]]:
        """Zwraca podsumowanie itemów jednostki."""
        result = []
        for item in unit.equipped_items:
            result.append({
                "id": item.id,
                "name": item.name,
                "stats": item.stats,
                "flags": item.flags,
            })
        return result
