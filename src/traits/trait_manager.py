"""
TraitManager - zarządza traitami w symulacji.

Odpowiedzialności:
- Liczenie unikalnych jednostek per trait
- Aktywacja progów przy spełnieniu warunków
- Aplikowanie efektów do odpowiednich celów
- Obsługa triggerów (on_battle_start, on_hp_threshold, etc.)

FLOW:
═══════════════════════════════════════════════════════════════════════════

    1. on_battle_start() - Simulation calls this at tick 0
       - Count unique units per trait per team
       - Get active threshold for each trait
       - Apply "on_battle_start" triggered effects
       
    2. on_tick(tick) - Called every tick
       - Check "on_time" triggers
       - Check "on_interval" triggers
       
    3. on_unit_damaged(unit) - When unit takes damage
       - Check "on_hp_threshold" triggers
       
    4. on_unit_death(unit) - When unit dies
       - Check "on_death" triggers
       - Recount traits (unit removed)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, TYPE_CHECKING, Any
from collections import defaultdict

from .trait import (
    Trait, TraitThreshold, TraitEffect, TraitTrigger,
    TriggerType, EffectTarget, ActiveTraitEffect,
)

if TYPE_CHECKING:
    from ..units.unit import Unit
    from ..simulation.simulation import Simulation


# ═══════════════════════════════════════════════════════════════════════════
# TRAIT EFFECT APPLICATORS
# ═══════════════════════════════════════════════════════════════════════════

def apply_stat_bonus(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Aplikuje bonus do statystyki.
    
    Params:
        stat: nazwa statystyki (armor, mr, attack_speed, hp, ad, ap)
        
    Returns:
        Liczba jednostek do których zastosowano
    """
    stat = effect.params.get("stat", "armor")
    value = effect.value
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
            
        # Apply buff through stats system
        if stat == "armor":
            unit.stats.base_armor += value
        elif stat == "mr" or stat == "magic_resist":
            unit.stats.base_magic_resist += value
        elif stat == "attack_speed":
            unit.stats.base_attack_speed += value
        elif stat == "hp" or stat == "max_hp":
            unit.stats.base_hp += value
            unit.stats.current_hp += value  # Also heal
        elif stat == "ad" or stat == "attack_damage":
            unit.stats.base_attack_damage += value
        elif stat == "ap" or stat == "ability_power":
            unit.stats.base_ability_power += value
        elif stat == "crit_chance":
            unit.stats.base_crit_chance += value
        elif stat == "dodge_chance":
            unit.stats.base_dodge_chance += value
        elif stat == "lifesteal":
            unit.stats.base_lifesteal += value
        
        count += 1
    
    return count


def apply_shield(units: List["Unit"], effect: TraitEffect) -> int:
    """Daje tarczę jednostkom."""
    value = effect.value
    duration = effect.params.get("duration", 999)  # domyślnie permanent
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        unit.add_shield(value, duration)
        count += 1
    
    return count


def apply_damage_amp(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Zwiększa zadawane obrażenia procentowo.
    
    Note: Wymaga obsługi w damage.py przez buff system.
    Na razie dodajemy jako buff.
    """
    value = effect.value  # np. 0.15 = 15% więcej dmg
    duration = effect.params.get("duration", 999)
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        # Dodaj jako buff damage_amp
        from ..effects.buff import Buff
        buff = Buff(
            id=f"trait_damage_amp_{id(effect)}",
            stat="damage_amp",
            value=value,
            remaining_ticks=duration,
            source="trait",
        )
        unit.add_buff(buff)
        count += 1
    
    return count


def apply_damage_reduction(units: List["Unit"], effect: TraitEffect) -> int:
    """Redukuje otrzymywane obrażenia procentowo."""
    value = effect.value
    duration = effect.params.get("duration", 999)
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        from ..effects.buff import Buff
        buff = Buff(
            id=f"trait_damage_reduction_{id(effect)}",
            stat="damage_reduction",
            value=value,
            remaining_ticks=duration,
            source="trait",
        )
        unit.add_buff(buff)
        count += 1
    
    return count


# Registry efektów traitów
TRAIT_EFFECT_APPLICATORS = {
    "stat_bonus": apply_stat_bonus,
    "shield": apply_shield,
    "damage_amp": apply_damage_amp,
    "damage_reduction": apply_damage_reduction,
}


# ═══════════════════════════════════════════════════════════════════════════
# TRAIT MANAGER
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TeamTraitState:
    """Stan traitów dla jednego teamu."""
    # trait_id -> set of unique base_unit_ids
    trait_counts: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    # trait_id -> active threshold count
    active_thresholds: Dict[str, int] = field(default_factory=dict)
    # Lista aktywnych efektów (do śledzenia one-time triggers)
    active_effects: List[ActiveTraitEffect] = field(default_factory=list)


class TraitManager:
    """
    Zarządza systemem traitów w symulacji.
    
    Główne zadania:
    - Liczenie unikalnych jednostek per trait
    - Określanie aktywnych progów
    - Aplikowanie efektów przy triggerach
    
    Attributes:
        simulation: Referencja do symulacji
        traits: Załadowane definicje traitów
        team_states: Stan traitów per team
    """
    
    def __init__(self, simulation: "Simulation"):
        self.simulation = simulation
        self.traits: Dict[str, Trait] = {}
        self.team_states: Dict[int, TeamTraitState] = {
            0: TeamTraitState(),
            1: TeamTraitState(),
        }
        self._hp_threshold_triggered: Dict[str, Set[str]] = defaultdict(set)  # unit_id -> set of trait_ids
    
    def load_traits(self, traits_data: Dict[str, Dict]) -> None:
        """
        Ładuje definicje traitów z YAML.
        
        Args:
            traits_data: Słownik trait_id -> definicja
        """
        for trait_id, data in traits_data.items():
            self.traits[trait_id] = Trait.from_dict(trait_id, data)
    
    # ─────────────────────────────────────────────────────────────────────────
    # COUNTING
    # ─────────────────────────────────────────────────────────────────────────
    
    def count_traits(self) -> None:
        """
        Przelicza traity dla wszystkich teamów.
        
        WAŻNE: Liczy tylko UNIKALNE jednostki!
        2x ta sama jednostka (np. 2x Warrior) = 1 do traitu.
        """
        # Reset counts
        for team in [0, 1]:
            self.team_states[team].trait_counts = defaultdict(set)
        
        # Count unique units per trait
        for unit in self.simulation.units:
            if not unit.is_alive():
                continue
            
            team = unit.team
            base_id = unit.base_id  # np. "warrior" (nie instance ID)
            
            for trait_id in unit.traits:
                # Dodaj base_id do seta (automatycznie unikalne)
                self.team_states[team].trait_counts[trait_id].add(base_id)
        
        # Determine active thresholds
        self._update_active_thresholds()
    
    def _update_active_thresholds(self) -> None:
        """Aktualizuje aktywne progi na podstawie countów."""
        for team in [0, 1]:
            state = self.team_states[team]
            state.active_thresholds = {}
            
            for trait_id, base_ids in state.trait_counts.items():
                count = len(base_ids)
                
                if trait_id not in self.traits:
                    continue
                
                trait = self.traits[trait_id]
                threshold = trait.get_active_threshold(count)
                
                if threshold:
                    state.active_thresholds[trait_id] = threshold.count
    
    def get_trait_count(self, team: int, trait_id: str) -> int:
        """Zwraca liczbę unikalnych jednostek z traitem."""
        return len(self.team_states[team].trait_counts.get(trait_id, set()))
    
    def get_active_threshold(self, team: int, trait_id: str) -> Optional[int]:
        """Zwraca aktywny próg dla traitu lub None."""
        return self.team_states[team].active_thresholds.get(trait_id)
    
    # ─────────────────────────────────────────────────────────────────────────
    # EFFECT APPLICATION
    # ─────────────────────────────────────────────────────────────────────────
    
    def _get_target_units(
        self,
        team: int,
        trait_id: str,
        target: EffectTarget,
        trigger_unit: Optional["Unit"] = None,
    ) -> List["Unit"]:
        """
        Zwraca jednostki do których należy zastosować efekt.
        
        Args:
            team: Team którego dotyczy trait
            trait_id: ID traitu
            target: Typ celu (holders, team, self, etc.)
            trigger_unit: Jednostka która triggered (dla self/adjacent)
        """
        units = []
        
        if target == EffectTarget.HOLDERS:
            # Tylko jednostki z tym traitem
            for unit in self.simulation.units:
                if unit.is_alive() and unit.team == team and trait_id in unit.traits:
                    units.append(unit)
                    
        elif target == EffectTarget.TEAM:
            # Cały team
            for unit in self.simulation.units:
                if unit.is_alive() and unit.team == team:
                    units.append(unit)
                    
        elif target == EffectTarget.SELF:
            # Tylko jednostka która triggered
            if trigger_unit and trigger_unit.is_alive():
                units.append(trigger_unit)
                
        elif target == EffectTarget.ADJACENT:
            # Sąsiedzi trigger_unit
            if trigger_unit and trigger_unit.is_alive():
                for neighbor_pos in trigger_unit.position.neighbors():
                    neighbor = self.simulation.grid.get_unit_at(neighbor_pos)
                    if neighbor and neighbor.is_alive() and neighbor.team == team:
                        units.append(neighbor)
                        
        elif target == EffectTarget.ENEMIES:
            # Wrogowie
            enemy_team = 1 if team == 0 else 0
            for unit in self.simulation.units:
                if unit.is_alive() and unit.team == enemy_team:
                    units.append(unit)
                    
        elif target == EffectTarget.NEAREST_ALLY:
            # Najbliższy sojusznik do trigger_unit
            if trigger_unit:
                closest = None
                closest_dist = float('inf')
                for unit in self.simulation.units:
                    if (unit.is_alive() and unit.team == team 
                        and unit.id != trigger_unit.id):
                        dist = trigger_unit.position.distance(unit.position)
                        if dist < closest_dist:
                            closest_dist = dist
                            closest = unit
                if closest:
                    units.append(closest)
        
        return units
    
    def _apply_effect(
        self,
        team: int,
        trait_id: str,
        effect: TraitEffect,
        trigger_unit: Optional["Unit"] = None,
    ) -> int:
        """
        Aplikuje pojedynczy efekt traitu.
        
        Returns:
            Liczba jednostek do których zastosowano
        """
        units = self._get_target_units(team, trait_id, effect.target, trigger_unit)
        
        applicator = TRAIT_EFFECT_APPLICATORS.get(effect.effect_type)
        if applicator:
            return applicator(units, effect)
        
        return 0
    
    def _apply_threshold_effects(
        self,
        team: int,
        trait_id: str,
        threshold: TraitThreshold,
        trigger_unit: Optional["Unit"] = None,
    ) -> None:
        """Aplikuje wszystkie efekty progu."""
        for effect in threshold.effects:
            self._apply_effect(team, trait_id, effect, trigger_unit)
    
    # ─────────────────────────────────────────────────────────────────────────
    # TRIGGER HANDLERS
    # ─────────────────────────────────────────────────────────────────────────
    
    def on_battle_start(self) -> None:
        """
        Wywoływane na początku walki (tick 0).
        
        - Przelicza traity
        - Aktywuje efekty z triggerem on_battle_start
        """
        self.count_traits()
        
        for team in [0, 1]:
            state = self.team_states[team]
            
            for trait_id, threshold_count in state.active_thresholds.items():
                trait = self.traits.get(trait_id)
                if not trait:
                    continue
                
                threshold = trait.thresholds.get(threshold_count)
                if not threshold:
                    continue
                
                # Check if this is a battle_start trigger
                if threshold.trigger.trigger_type == TriggerType.ON_BATTLE_START:
                    self._apply_threshold_effects(team, trait_id, threshold)
    
    def on_tick(self, tick: int) -> None:
        """
        Wywoływane co tick.
        
        Sprawdza:
        - on_time triggers (aktywacja po X tickach)
        - on_interval triggers (aktywacja co X ticków)
        """
        for team in [0, 1]:
            state = self.team_states[team]
            
            for trait_id, threshold_count in state.active_thresholds.items():
                trait = self.traits.get(trait_id)
                if not trait:
                    continue
                
                threshold = trait.thresholds.get(threshold_count)
                if not threshold:
                    continue
                
                trigger = threshold.trigger
                
                # ON_TIME: aktywacja dokładnie po X tickach
                if trigger.trigger_type == TriggerType.ON_TIME:
                    target_tick = trigger.params.get("ticks", 300)
                    if tick == target_tick:
                        self._apply_threshold_effects(team, trait_id, threshold)
                
                # ON_INTERVAL: aktywacja co X ticków
                elif trigger.trigger_type == TriggerType.ON_INTERVAL:
                    interval = trigger.params.get("interval", 120)
                    if tick > 0 and tick % interval == 0:
                        self._apply_threshold_effects(team, trait_id, threshold)
    
    def on_unit_damaged(self, unit: "Unit") -> None:
        """
        Wywoływane gdy jednostka otrzymuje obrażenia.
        
        Sprawdza on_hp_threshold triggers.
        """
        if not unit.is_alive():
            return
        
        hp_percent = unit.stats.hp_percent()
        team = unit.team
        
        for trait_id in unit.traits:
            # Skip jeśli już triggered dla tej jednostki
            if trait_id in self._hp_threshold_triggered.get(unit.id, set()):
                continue
            
            if trait_id not in self.traits:
                continue
            
            trait = self.traits[trait_id]
            threshold_count = self.team_states[team].active_thresholds.get(trait_id)
            
            if threshold_count is None:
                continue
            
            threshold = trait.thresholds.get(threshold_count)
            if not threshold:
                continue
            
            trigger = threshold.trigger
            
            if trigger.trigger_type == TriggerType.ON_HP_THRESHOLD:
                hp_threshold = trigger.params.get("threshold", 0.5)
                
                if hp_percent <= hp_threshold:
                    # Mark as triggered
                    if unit.id not in self._hp_threshold_triggered:
                        self._hp_threshold_triggered[unit.id] = set()
                    self._hp_threshold_triggered[unit.id].add(trait_id)
                    
                    # Apply effects with trigger_unit=unit
                    self._apply_threshold_effects(team, trait_id, threshold, unit)
    
    def on_unit_death(self, unit: "Unit") -> None:
        """
        Wywoływane gdy jednostka ginie.
        
        - Sprawdza on_death triggers
        - Przelicza traity (jednostka usunięta)
        """
        team = unit.team
        
        # Check on_death triggers BEFORE recounting
        for trait_id, threshold_count in self.team_states[team].active_thresholds.items():
            trait = self.traits.get(trait_id)
            if not trait:
                continue
            
            threshold = trait.thresholds.get(threshold_count)
            if not threshold:
                continue
            
            if threshold.trigger.trigger_type == TriggerType.ON_DEATH:
                # Check if dead unit had this trait
                if trait_id in unit.traits:
                    self._apply_threshold_effects(team, trait_id, threshold, unit)
        
        # Recount traits
        self.count_traits()
    
    def on_first_cast(self, unit: "Unit") -> None:
        """Wywoływane gdy jednostka pierwszy raz castuje ability."""
        team = unit.team
        
        for trait_id in unit.traits:
            if trait_id not in self.traits:
                continue
            
            trait = self.traits[trait_id]
            threshold_count = self.team_states[team].active_thresholds.get(trait_id)
            
            if threshold_count is None:
                continue
            
            threshold = trait.thresholds.get(threshold_count)
            if not threshold:
                continue
            
            if threshold.trigger.trigger_type == TriggerType.ON_FIRST_CAST:
                self._apply_threshold_effects(team, trait_id, threshold, unit)
    
    # ─────────────────────────────────────────────────────────────────────────
    # DEBUG / INFO
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_team_traits_summary(self, team: int) -> Dict[str, Dict[str, Any]]:
        """
        Zwraca podsumowanie traitów dla teamu.
        
        Returns:
            Dict[trait_id, {"count": int, "active_threshold": int, "name": str}]
        """
        state = self.team_states[team]
        result = {}
        
        for trait_id, base_ids in state.trait_counts.items():
            count = len(base_ids)
            if count == 0:
                continue
            
            trait = self.traits.get(trait_id)
            active = state.active_thresholds.get(trait_id)
            
            result[trait_id] = {
                "count": count,
                "active_threshold": active,
                "name": trait.name if trait else trait_id,
                "thresholds": trait.get_threshold_counts() if trait else [],
            }
        
        return result
