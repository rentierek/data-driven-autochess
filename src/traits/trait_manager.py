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
    
    Dodaje do base_damage_amp w stats.
    """
    value = effect.value  # np. 0.15 = 15% więcej dmg
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        # Use base_damage_amp stat directly
        unit.stats.base_damage_amp += value
        count += 1
    
    return count


def apply_damage_reduction(units: List["Unit"], effect: TraitEffect) -> int:
    """Redukuje otrzymywane obrażenia procentowo."""
    value = effect.value
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        # Use base_durability stat directly
        unit.stats.base_durability += value
        count += 1
    
    return count


def apply_heal(units: List["Unit"], effect: TraitEffect) -> int:
    """Leczy jednostki."""
    value = effect.value
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        unit.stats.heal(value)
        count += 1
    
    return count


def apply_mana(units: List["Unit"], effect: TraitEffect) -> int:
    """Dodaje manę jednostkom."""
    value = effect.value
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        unit.stats.add_mana(value)
        count += 1
    
    return count


def apply_stat_percent(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Stat bonus as percent of base stat.
    E.g. value=0.25 with stat=hp adds 25% of base HP.
    """
    stat = effect.params.get("stat", "hp")
    percent = effect.value
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        base_stat = f"base_{stat}"
        if hasattr(unit.stats, base_stat):
            base_val = getattr(unit.stats, base_stat)
            bonus = base_val * percent
            setattr(unit.stats, base_stat, base_val + bonus)
            if stat == "hp":
                unit.stats.current_hp += bonus
        count += 1
    
    return count


def apply_shield_percent_hp(units: List["Unit"], effect: TraitEffect) -> int:
    """Shield as percent of max HP."""
    percent = effect.value
    duration = effect.params.get("duration", 999)
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        shield_value = unit.stats.max_hp * percent
        unit.add_shield(int(shield_value), duration)
        count += 1
    
    return count


def apply_mana_regen(units: List["Unit"], effect: TraitEffect) -> int:
    """Grant mana per interval (stored as modifier)."""
    value = effect.value
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        if not hasattr(unit, 'mana_regen'):
            unit.mana_regen = 0
        unit.mana_regen += value
        count += 1
    
    return count


def apply_mana_generation_bonus(units: List["Unit"], effect: TraitEffect) -> int:
    """Bonus % mana from all sources (Invoker)."""
    value = effect.value
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        if not hasattr(unit, 'mana_gen_mult'):
            unit.mana_gen_mult = 1.0
        unit.mana_gen_mult += value
        count += 1
    
    return count


def apply_target_missing_hp_as(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Quickstriker: AS scales with TARGET missing HP.
    min/max define the range (0% missing = min, 100% missing = max).
    """
    min_as = effect.params.get("min", 0.10)
    max_as = effect.params.get("max", 0.30)
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        unit.target_missing_hp_as = {"min": min_as, "max": max_as}
        count += 1
    
    return count


def apply_distance_damage_bonus(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Longshot: Bonus damage per hex distance.
    """
    value = effect.value  # e.g. 0.02 = 2% per hex
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        unit.distance_damage_bonus = value
        count += 1
    
    return count


def apply_self_missing_hp_damage(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Slayer: Bonus damage scales with OWN missing HP.
    max_bonus = max bonus at 0 HP (e.g. 0.5 = 50%).
    """
    max_bonus = effect.params.get("max_bonus", 0.50)
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        unit.self_missing_hp_damage_bonus = max_bonus
        count += 1
    
    return count


def apply_ability_applies_debuff(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Disruptor: Abilities apply a debuff to targets.
    """
    debuff = effect.params.get("debuff", "dazzle")
    debuff_value = effect.value  # e.g. 0.20 = 20% damage reduction
    duration = effect.params.get("duration", 90)
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        unit.ability_applies_debuff = {
            "type": debuff,
            "value": debuff_value,
            "duration": duration
        }
        count += 1
    
    return count


def apply_damage_vs_debuffed(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Disruptor: Bonus damage vs targets with specific debuff.
    """
    debuff = effect.params.get("debuff", "dazzle")
    bonus = effect.params.get("bonus", 0.25)
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        if not hasattr(unit, 'damage_vs_debuff'):
            unit.damage_vs_debuff = {}
        unit.damage_vs_debuff[debuff] = bonus
        count += 1
    
    return count


def apply_shimmer_fused(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Zaun: Shimmer-Fused buff (durability + decaying AS).
    """
    durability = effect.params.get("durability", 0.10)
    attack_speed = effect.params.get("attack_speed", 0.90)
    decay_duration = effect.params.get("decay_duration", 120)
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        # Apply durability
        unit.stats.base_durability += durability
        # Apply AS (will decay)
        unit.stats.base_attack_speed += attack_speed
        # Mark for decay
        unit.shimmer_fused = {
            "as_bonus": attack_speed,
            "decay_duration": decay_duration,
            "decay_per_tick": attack_speed / decay_duration
        }
        count += 1
    
    return count


def apply_on_attack_counter(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Gunslinger: Every Nth attack deals bonus damage.
    """
    count_threshold = effect.params.get("count", 4)
    bonus_damage = effect.params.get("bonus_damage", 100)
    damage_type = effect.params.get("damage_type", "physical")
    result = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        unit.attack_counter_bonus = {
            "count": count_threshold,
            "damage": bonus_damage,
            "type": damage_type
        }
        result += 1
    
    return result


def apply_mana_cost_reduction(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Demacia Rally: Reduce mana costs.
    """
    reduction = effect.value  # e.g. 0.10 = 10% reduction
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        if not hasattr(unit, 'mana_cost_mult'):
            unit.mana_cost_mult = 1.0
        unit.mana_cost_mult *= (1 - reduction)
        count += 1
    
    return count


def apply_random_mutation(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Void: Apply random mutation to units.
    Mutations stored in effect.params['mutations'].
    """
    import random
    
    mutations = effect.params.get('mutations', [
        {'id': 'razor_claws', 'ad': 25, 'crit_chance': 0.15},
        {'id': 'void_armor', 'armor': 40, 'mr': 40},
        {'id': 'void_speed', 'attack_speed': 0.30},
        {'id': 'mana_siphon', 'mana_on_hit': 5},
    ])
    
    count = 0
    for unit in units:
        if not unit.is_alive():
            continue
        
        # Pick random mutation
        mutation = random.choice(mutations)
        unit.void_mutation = mutation['id']
        
        # Apply stat bonuses
        for stat, value in mutation.items():
            if stat == 'id':
                continue
            if stat == 'mana_on_hit':
                unit.mana_on_hit = value
            elif hasattr(unit.stats, f'base_{stat}'):
                current = getattr(unit.stats, f'base_{stat}')
                setattr(unit.stats, f'base_{stat}', current + value)
        
        count += 1
    
    return count


def apply_grant_souls(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Shadow Isles: Track souls on death.
    This is applied passively, not directly.
    """
    return 0  # Handled by on_unit_death


def apply_percent_hp_damage(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Demacia 7: Deal % max HP damage to enemies.
    """
    percent = effect.value
    count = 0
    
    from ..combat.damage import DamageType
    
    for unit in units:
        if not unit.is_alive():
            continue
        damage = unit.stats.max_hp * percent
        unit.take_damage(damage, DamageType.MAGICAL, None)
        count += 1
    
    return count


def apply_heal_percent(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Heal as percent of max HP (Zaun 5).
    """
    percent = effect.value
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        heal_amount = unit.stats.max_hp * percent
        unit.stats.heal(heal_amount)
        count += 1
    
    return count


def apply_ascend_buff(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Shurima 4: Ascend buff - major stat boost for duration.
    """
    duration = effect.params.get('duration', 90)
    count = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        
        # Apply ascension buff
        unit.stats.base_attack_damage *= 1.5
        unit.stats.base_ability_power *= 1.5
        unit.stats.base_attack_speed += 0.50
        unit.stats.base_durability += 0.20
        
        unit.ascended = {'duration': duration, 'start_tick': 0}  # Will be set by caller
        count += 1
    
    return count


def apply_spawn_tower(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Freljord: Spawn Frozen Tower(s) with auras.
    Front = HP bonus, Back = Damage Amp.
    """
    count = effect.params.get('count', 1)
    auras = effect.params.get('auras', {})
    holder_mult = effect.params.get('holder_multiplier', 1.5)
    on_death = effect.params.get('on_death', None)
    
    result = 0
    for unit in units:
        if not unit.is_alive():
            continue
        
        # Apply aura bonuses based on position
        # Front = rows 0-1, Back = rows 2-3
        row = unit.position.r if hasattr(unit, 'position') else 0
        is_front = row <= 1
        
        if is_front and 'front' in auras:
            front_aura = auras['front']
            if front_aura.get('stat') == 'hp':
                percent = front_aura.get('value_percent', 0.08)
                mult = holder_mult if hasattr(unit, 'traits') and 'freljord' in unit.traits else 1.0
                hp_bonus = unit.stats.base_hp * percent * mult
                unit.stats.base_hp += hp_bonus
                unit.stats.current_hp += hp_bonus
        elif not is_front and 'back' in auras:
            back_aura = auras['back']
            if back_aura.get('stat') == 'damage_amp':
                mult = holder_mult if hasattr(unit, 'traits') and 'freljord' in unit.traits else 1.0
                dmg_amp = back_aura.get('value', 0.10) * mult
                unit.stats.base_damage_amp += dmg_amp
        
        # Store on_death effect
        if on_death:
            unit.freljord_tower_death = on_death
        
        result += 1
    
    return result


def apply_summon_unit(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Noxus: Summon Atakhan when enemy loses 15% HP.
    Star level scales with Noxus count.
    """
    unit_type = effect.params.get('unit', 'atakhan')
    star_source = effect.params.get('star_level_source', 'noxus_count')
    
    result = 0
    for unit in units:
        if not unit.is_alive():
            continue
        
        # Mark unit as having summon capability
        unit.can_summon = {
            'unit_type': unit_type,
            'star_source': star_source,
            'summoned': False
        }
        result += 1
    
    return result


def apply_path_bonus(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Ionia: Apply path-specific bonuses.
    Paths: precision (crit), generosity (gold), spirit (HP + stacking).
    Random path selection per team if not specified.
    """
    import random
    
    # Get path - random if not specified
    path = effect.params.get('path', None)
    if path is None:
        path = random.choice(['precision', 'generosity', 'spirit'])
    
    multiplier = effect.params.get('multiplier', 1.0)
    
    bonuses = {
        'precision': {
            'crit_chance': 0.20,
            'crit_damage': 0.20,
            'description': 'Precision Path - Crit bonus'
        },
        'generosity': {
            'gold_per_round': 2,
            'description': 'Generosity Path - Gold bonus'
        },
        'spirit': {
            'hp': 200,
            'stacking_ad': 3,
            'stacking_ap': 3,
            'description': 'Spirit Path - HP + stacking AD/AP'
        }
    }
    
    path_bonus = bonuses.get(path, bonuses['spirit'])
    result = 0
    
    for unit in units:
        if not unit.is_alive():
            continue
        
        # Store selected path on unit
        unit.ionia_path = path
        
        for stat, value in path_bonus.items():
            if stat == 'description':
                continue
            if stat == 'hp':
                bonus = value * multiplier
                unit.stats.base_hp += bonus
                unit.stats.current_hp += bonus
            elif stat == 'crit_chance':
                unit.stats.base_crit_chance += value * multiplier
            elif stat == 'crit_damage':
                unit.stats.base_crit_damage += value * multiplier
            elif stat == 'gold_per_round':
                # Gold handled elsewhere, just mark it
                unit.gold_bonus = value * multiplier
            elif stat.startswith('stacking_'):
                # Stacking bonus per cast
                if not hasattr(unit, 'ionia_stacking'):
                    unit.ionia_stacking = {'ad': 0, 'ap': 0}
                unit.ionia_stacking = {
                    'ad': path_bonus.get('stacking_ad', 0) * multiplier,
                    'ap': path_bonus.get('stacking_ap', 0) * multiplier
                }
        
        result += 1
    
    return result



def apply_darkin_damage(units: List["Unit"], effect: TraitEffect) -> int:
    """
    Darkin 3: When healed 600+ HP, deal 100 magic damage to 2 nearest enemies.
    """
    damage = effect.params.get('damage', 100)
    target_count = effect.params.get('target_count', 2)
    
    result = 0
    for unit in units:
        if not unit.is_alive():
            continue
        
        # Track healing
        unit.darkin_heal_damage = {
            'threshold': 600,
            'damage': damage,
            'targets': target_count,
            'healed': 0
        }
        result += 1
    
    return result


# Registry efektów traitów
TRAIT_EFFECT_APPLICATORS = {
    "stat_bonus": apply_stat_bonus,
    "shield": apply_shield,
    "damage_amp": apply_damage_amp,
    "damage_reduction": apply_damage_reduction,
    "heal": apply_heal,
    "mana": apply_mana,
    # New Set 16 applicators
    "stat_percent": apply_stat_percent,
    "shield_percent_hp": apply_shield_percent_hp,
    "mana_regen": apply_mana_regen,
    "mana_generation_bonus": apply_mana_generation_bonus,
    "target_missing_hp_as": apply_target_missing_hp_as,
    "distance_damage_bonus": apply_distance_damage_bonus,

    "self_missing_hp_damage": apply_self_missing_hp_damage,
    "ability_applies_debuff": apply_ability_applies_debuff,
    "damage_vs_debuffed": apply_damage_vs_debuffed,
    "shimmer_fused": apply_shimmer_fused,
    "on_attack_counter": apply_on_attack_counter,
    # Complex trait applicators
    "mana_cost_reduction": apply_mana_cost_reduction,
    "random_mutation": apply_random_mutation,
    "grant_souls": apply_grant_souls,
    "percent_hp_damage": apply_percent_hp_damage,
    "heal_percent": apply_heal_percent,
    "ascend_buff": apply_ascend_buff,
    # Advanced trait applicators
    "spawn_tower": apply_spawn_tower,
    "summon_unit": apply_summon_unit,
    "path_bonus": apply_path_bonus,
    "darkin_damage": apply_darkin_damage,
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
        
        # Complex trait tracking
        self._team_initial_hp: Dict[int, float] = {0: 0, 1: 0}  # Track initial team HP for Demacia rally
        self._rally_stacks: Dict[int, int] = {0: 0, 1: 0}  # Rally stacks per team
        self._souls: Dict[int, int] = {0: 0, 1: 0}  # Shadow Isles souls per team
        self._unit_heal_tracking: Dict[str, float] = {}  # Track healing for Darkin
        self._void_mutations_applied: Dict[str, str] = {}  # unit_id -> mutation_id
        self._shimmer_timers: Dict[str, int] = {}  # unit_id -> last shimmer tick

    
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
