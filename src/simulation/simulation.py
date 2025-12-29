"""
Główny silnik symulacji walki.

Symulacja odbywa się w 30 tickach na sekundę (konfigurowalnie).
Każdy tick wykonuje sekwencję faz w określonej kolejności.

PĘTLA TICKA:
═══════════════════════════════════════════════════════════════════

    1. UPDATE_BUFFS
       ─────────────────────────────────────────────────────────
       • Zmniejsz remaining_ticks każdego buffa
       • Usuń wygasłe buffy
       • Loguj BUFF_EXPIRE dla usuniętych
       
    2. CHECK_ABILITY_TRIGGERS
       ─────────────────────────────────────────────────────────
       • Dla każdej jednostki z pełną maną:
         - Jeśli ma ability -> ustaw CASTING
         - Rozpocznij cast time
       
    3. AI_DECISION
       ─────────────────────────────────────────────────────────
       • Dla każdej żywej jednostki która może działać:
         
         IDLE -> Szukaj celu
           - Znajdź najbliższego wroga
           - Jeśli w zasięgu -> ATTACKING
           - Jeśli poza zasięgiem -> MOVING
           
         MOVING -> Waliduj cel
           - Jeśli cel martwy -> IDLE
           - Jeśli dotarł do zasięgu -> ATTACKING
           
         ATTACKING -> Sprawdź cel
           - Jeśli cel martwy -> IDLE
           - Jeśli cel uciekł -> MOVING
           
    4. EXECUTE_ACTIONS
       ─────────────────────────────────────────────────────────
       • MOVING: 
         - Znajdź ścieżkę A* do celu
         - Wykonaj 1 krok
         - Loguj UNIT_MOVE
         
       • ATTACKING:
         - Zmniejsz attack_cooldown
         - Jeśli cooldown <= 0:
           - Wykonaj atak (calculate_damage)
           - Loguj UNIT_ATTACK, UNIT_DAMAGE
           - Dodaj manę atakującemu
           - Sprawdź śmierć celu
           
       • CASTING:
         - Zmniejsz cast_remaining
         - Jeśli cast skończony:
           - Wykonaj ability
           - Loguj ABILITY_CAST
           
    5. LOG_EVENTS
       ─────────────────────────────────────────────────────────
       • (Logowanie dzieje się w każdej fazie inline)
       
    6. CHECK_END_CONDITION
       ─────────────────────────────────────────────────────────
       • Policz żywe jednostki każdego teamu
       • Jeśli jeden team wymarł -> koniec
       • Loguj SIMULATION_END

PRIORYTETYZACJA CELÓW:
═══════════════════════════════════════════════════════════════════

    Domyślna logika (TFT-style):
    1. Najbliższy wróg (najmniejsza odległość hex)
    2. Przy równej odległości - losowy wybór (deterministic)

DETERMINIZM:
═══════════════════════════════════════════════════════════════════

    Symulacja jest w pełni deterministyczna:
    • Ten sam seed = te same wyniki
    • Jednostki przetwarzane w stałej kolejności
    • Wszystkie "losowe" decyzje przez GameRNG

Przykład użycia:
    >>> sim = Simulation(seed=12345)
    >>> sim.add_unit(warrior_config, team=0, position=HexCoord(0, 0))
    >>> sim.add_unit(mage_config, team=1, position=HexCoord(3, 3))
    >>> result = sim.run()
    >>> result["winner_team"]
    0
    >>> sim.save_log("output/battle.json")
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from ..core.hex_coord import HexCoord
from ..core.hex_grid import HexGrid
from ..core.pathfinding import find_path, find_path_next_step
from ..core.rng import GameRNG
from ..core.config_loader import ConfigLoader
from ..units.unit import Unit
from ..units.state_machine import UnitState
from ..combat.damage import DamageType, calculate_damage, apply_damage
from ..events.event_logger import EventLogger, EventType
from ..abilities import Ability, ProjectileManager, EFFECT_REGISTRY
from ..traits import TraitManager
from ..items import ItemManager


@dataclass
class SimulationConfig:
    """
    Konfiguracja symulacji.
    
    Attributes:
        ticks_per_second (int): Ticki na sekundę (30 = TFT standard)
        max_ticks (int): Maksymalna liczba ticków (timeout)
        grid_width (int): Szerokość siatki
        grid_height (int): Wysokość siatki
        mana_per_attack (float): Mana za atak
        mana_on_damage (float): Mana za otrzymane obrażenia
    """
    ticks_per_second: int = 30
    max_ticks: int = 3000  # 100 sekund
    grid_width: int = 7
    grid_height: int = 8
    mana_per_attack: float = 10.0
    mana_on_damage: float = 5.0


class Simulation:
    """
    Główny silnik symulacji walki.
    
    Zarządza siatką, jednostkami, i wykonuje pętlę ticków.
    
    Attributes:
        seed (int): Ziarno losowości
        tick (int): Aktualny tick
        config (SimulationConfig): Konfiguracja
        grid (HexGrid): Siatka hexagonalna
        units (List[Unit]): Wszystkie jednostki
        rng (GameRNG): Generator losowości
        logger (EventLogger): Logger zdarzeń
        is_finished (bool): Czy symulacja się zakończyła
        winner_team (Optional[int]): Zwycięski team (None = remis)
        
    Example:
        >>> sim = Simulation(seed=12345)
        >>> sim.add_unit_from_config(warrior_config, team=0, position=HexCoord(0, 0))
        >>> result = sim.run()
    """
    
    def __init__(
        self,
        seed: int = 0,
        config: Optional[SimulationConfig] = None,
    ):
        """
        Inicjalizuje symulację.
        
        Args:
            seed: Ziarno losowości (determinizm)
            config: Konfiguracja (domyślne wartości jeśli None)
        """
        self.seed = seed
        self.config = config or SimulationConfig()
        self.tick = 0
        
        # Komponenty
        self.grid = HexGrid(
            width=self.config.grid_width, 
            height=self.config.grid_height
        )
        self.rng = GameRNG(seed)
        self.logger = EventLogger(
            seed=seed,
            grid_width=self.config.grid_width,
            grid_height=self.config.grid_height,
            ticks_per_second=self.config.ticks_per_second,
        )
        
        # Stan
        self.units: List[Unit] = []
        self.is_finished = False
        self.winner_team: Optional[int] = None
        
        # Ability system
        self.projectile_manager = ProjectileManager()
        self._ability_cache: Dict[str, Ability] = {}
        self._config_loader: Optional[ConfigLoader] = None
        
        # Trait system
        self.trait_manager: Optional[TraitManager] = None
        
        # Item system
        self.item_manager: Optional[ItemManager] = None
    
    # ─────────────────────────────────────────────────────────────────────────
    # DODAWANIE JEDNOSTEK
    # ─────────────────────────────────────────────────────────────────────────
    
    def add_unit(self, unit: Unit) -> bool:
        """
        Dodaje jednostkę do symulacji.
        
        Args:
            unit: Jednostka do dodania
            
        Returns:
            bool: True jeśli dodano pomyślnie
        """
        if not self.grid.place_unit(unit, unit.position):
            return False
        
        self.units.append(unit)
        return True
    
    def add_unit_from_config(
        self,
        config: Dict[str, Any],
        team: int,
        position: HexCoord,
        star_level: int = 1,
    ) -> Optional[Unit]:
        """
        Tworzy i dodaje jednostkę z konfiguracji.
        
        Args:
            config: Słownik z ConfigLoader.load_unit()
            team: Numer drużyny
            position: Pozycja startowa
            star_level: Poziom gwiazd
            
        Returns:
            Optional[Unit]: Stworzona jednostka lub None
        """
        unit = Unit.from_config(config, team, position, star_level)
        
        if self.add_unit(unit):
            return unit
        return None
    
    # ─────────────────────────────────────────────────────────────────────────
    # GŁÓWNA PĘTLA
    # ─────────────────────────────────────────────────────────────────────────
    
    def run(self) -> Dict[str, Any]:
        """
        Uruchamia symulację do końca.
        
        Returns:
            Dict: Wynik symulacji
                - winner_team: int lub None (remis)
                - total_ticks: int
                - survivors: List[Dict]
        """
        # Log start
        self._log_start()
        
        # Activate traits at battle start
        if self.trait_manager:
            self.trait_manager.on_battle_start()
        
        # Activate items at battle start (equip, apply on_equip effects)
        if self.item_manager:
            self.item_manager.on_battle_start()
        
        # Główna pętla
        while not self.is_finished and self.tick < self.config.max_ticks:
            self._run_tick()
            self.tick += 1
        
        # Log end
        self._log_end()
        
        return self.get_result()
    
    def _run_tick(self) -> None:
        """Wykonuje jeden tick symulacji."""
        
        # 0. Trait time-based triggers
        if self.trait_manager:
            self.trait_manager.on_tick(self.tick)
        
        # 0b. Item interval triggers
        if self.item_manager:
            self.item_manager.on_tick(self.tick)
        
        # 1. Update buffs
        self._phase_update_buffs()
        
        # 2. Check ability triggers
        self._phase_check_abilities()
        
        # 3. AI decision
        self._phase_ai_decision()
        
        # 4. Execute actions
        self._phase_execute_actions()
        
        # 5. Check end condition
        self._phase_check_end()
    
    # ─────────────────────────────────────────────────────────────────────────
    # FAZY TICKA
    # ─────────────────────────────────────────────────────────────────────────
    
    def _phase_update_buffs(self) -> None:
        """Faza 1: Aktualizacja buffów."""
        for unit in self._get_alive_units():
            expired = unit.update_buffs()
            for buff in expired:
                self.logger.log_buff_expire(self.tick, unit.id, buff.id)
    
    def _phase_check_abilities(self) -> None:
        """Faza 2: Sprawdzenie triggerów umiejętności."""
        for unit in self._get_alive_units():
            if unit.can_cast_ability() and unit.state.current == UnitState.ATTACKING:
                # Get ability for unit
                ability = self._get_unit_ability(unit)
                if ability:
                    cast_time = ability.get_cast_time(unit.star_level)
                else:
                    cast_time = 15  # fallback
                
                unit.state.start_cast(cast_time)
                old_state = UnitState.ATTACKING
                self.logger.log_state_change(
                    self.tick, unit.id, 
                    old_state.name, UnitState.CASTING.name
                )
    
    def _phase_ai_decision(self) -> None:
        """Faza 3: Decyzje AI."""
        for unit in self._get_alive_units():
            if not unit.can_act():
                continue
            
            state = unit.state.current
            
            if state == UnitState.IDLE:
                self._ai_idle(unit)
            elif state == UnitState.MOVING:
                self._ai_moving(unit)
            elif state == UnitState.ATTACKING:
                self._ai_attacking(unit)
    
    def _phase_execute_actions(self) -> None:
        """Faza 4: Wykonanie akcji."""
        for unit in self._get_alive_units():
            # Check if cast completed (effect point reached)
            if unit.state.should_trigger_effect():
                self._execute_ability(unit)
            
            # Tick debuffs (burn, dot, slow, etc.)
            unit.tick_debuffs(self.config.ticks_per_second)
            
            # Tick cooldowns
            unit.tick_cooldowns()
            
            # Tick state machine (stun/cast countdown)
            unit.state.tick()
            
            state = unit.state.current
            
            if state == UnitState.MOVING:
                self._execute_move(unit)
            elif state == UnitState.ATTACKING:
                self._execute_attack(unit)
            elif state == UnitState.CASTING:
                pass
        
        # Update projectiles
        arrived = self.projectile_manager.tick()
        for proj in arrived:
            self._execute_projectile_impact(proj)
    
    def _phase_check_end(self) -> None:
        """Faza 6: Sprawdzenie warunku końca."""
        team_alive = {0: 0, 1: 0}
        
        for unit in self.units:
            if unit.is_alive():
                team_alive[unit.team] = team_alive.get(unit.team, 0) + 1
        
        # Sprawdź czy któryś team wymarł
        if team_alive.get(0, 0) == 0 and team_alive.get(1, 0) == 0:
            # Remis (obaj wymarli w tym samym ticku)
            self.is_finished = True
            self.winner_team = None
        elif team_alive.get(0, 0) == 0:
            self.is_finished = True
            self.winner_team = 1
        elif team_alive.get(1, 0) == 0:
            self.is_finished = True
            self.winner_team = 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # AI HELPERS
    # ─────────────────────────────────────────────────────────────────────────
    
    def _ai_idle(self, unit: Unit) -> None:
        """AI dla stanu IDLE - szukaj celu."""
        target = self._find_target(unit)
        
        if target is None:
            return  # Brak wrogów
        
        unit.set_target(target)
        self.logger.log_target_acquired(self.tick, unit.id, target.id)
        
        if unit.in_attack_range(target):
            self._transition_state(unit, UnitState.ATTACKING)
        else:
            self._transition_state(unit, UnitState.MOVING)
    
    def _ai_moving(self, unit: Unit) -> None:
        """AI dla stanu MOVING - waliduj cel."""
        if not unit.has_valid_target():
            unit.clear_target()
            self._transition_state(unit, UnitState.IDLE)
            return
        
        target = unit.target
        if unit.in_attack_range(target):
            self._transition_state(unit, UnitState.ATTACKING)
    
    def _ai_attacking(self, unit: Unit) -> None:
        """AI dla stanu ATTACKING - sprawdź cel."""
        if not unit.has_valid_target():
            unit.clear_target()
            self._transition_state(unit, UnitState.IDLE)
            return
        
        target = unit.target
        if not unit.in_attack_range(target):
            self._transition_state(unit, UnitState.MOVING)
    
    def _find_target(self, unit: Unit) -> Optional[Unit]:
        """
        Znajduje cel dla jednostki.
        
        Priorytet: najbliższy żywy wróg.
        Przy równej odległości: deterministycznie losowy.
        """
        enemies = [
            u for u in self.units 
            if u.is_alive() and u.team != unit.team
        ]
        
        if not enemies:
            return None
        
        # Sortuj po odległości
        enemies.sort(key=lambda e: unit.position.distance(e.position))
        
        # Znajdź wszystkich z minimalną odległością
        min_dist = unit.position.distance(enemies[0].position)
        closest = [e for e in enemies if unit.position.distance(e.position) == min_dist]
        
        # Deterministyczny wybór przy remisie
        if len(closest) > 1:
            return self.rng.choice(closest)
        
        return closest[0]
    
    # ─────────────────────────────────────────────────────────────────────────
    # EXECUTE HELPERS
    # ─────────────────────────────────────────────────────────────────────────
    
    def _execute_move(self, unit: Unit) -> None:
        """Wykonuje ruch jednostki."""
        if not unit.has_valid_target():
            return
        
        target = unit.target
        
        # Znajdź następny krok A*
        next_pos = find_path_next_step(
            self.grid,
            unit.position,
            target.position,
            ignore_units={target.id},  # Możemy iść "pod" cel
        )
        
        if next_pos is None:
            return  # Brak ścieżki
        
        old_pos = unit.position
        
        # Wykonaj ruch na siatce
        if self.grid.move_unit(unit, next_pos):
            unit.position = next_pos
            self.logger.log_move(
                self.tick, unit.id,
                old_pos.q, old_pos.r,
                next_pos.q, next_pos.r,
            )
    
    def _execute_attack(self, unit: Unit) -> None:
        """Wykonuje atak jednostki."""
        if not unit.can_attack():
            return
        
        if not unit.has_valid_target():
            return
        
        target = unit.target
        
        # Oblicz obrażenia
        base_damage = unit.stats.get_attack_damage()
        damage_result = calculate_damage(
            attacker=unit,
            defender=target,
            base_damage=base_damage,
            damage_type=DamageType.PHYSICAL,
            rng=self.rng,
            can_crit=True,
            can_dodge=True,
            is_ability=False,
        )
        
        # Loguj atak
        self.logger.log_attack(
            self.tick, unit.id, target.id,
            damage_result.final_damage,
            damage_result.is_crit,
            damage_result.was_dodged,
        )
        
        if not damage_result.was_dodged:
            # Aplikuj obrażenia
            apply_damage(unit, target, damage_result)
            
            # Item on_hit effects
            if self.item_manager:
                self.item_manager.on_hit(unit, target)
                
                # Item on_crit effects (Striker's Flail)
                if damage_result.is_crit:
                    self.item_manager.on_crit(unit, target)
            
            # Loguj obrażenia
            self.logger.log_damage(
                self.tick, target.id, unit.id,
                damage_result.final_damage,
                damage_result.damage_type.name,
                target.stats.current_hp,
            )
            
            # Mana za atak
            unit.gain_mana_on_attack()
            
            # Sprawdź śmierć
            if target.is_dead():
                self.logger.log_death(self.tick, target.id, unit.id)
                self.grid.remove_unit(target)
                
                # Item on_kill effects
                if self.item_manager:
                    self.item_manager.on_kill(unit, target)
                
                # Clear target
                unit.clear_target()
                self._transition_state(unit, UnitState.IDLE)
        
        # Cooldown
        unit.start_attack_cooldown(self.config.ticks_per_second)
    
    # ─────────────────────────────────────────────────────────────────────────
    # UTILITY
    # ─────────────────────────────────────────────────────────────────────────
    
    def _get_alive_units(self) -> List[Unit]:
        """Zwraca listę żywych jednostek."""
        return [u for u in self.units if u.is_alive()]
    
    def _transition_state(self, unit: Unit, new_state: UnitState) -> None:
        """Zmienia stan jednostki i loguje."""
        old_state = unit.state.current
        if unit.state.transition_to(new_state):
            self.logger.log_state_change(
                self.tick, unit.id,
                old_state.name, new_state.name,
            )
    
    def _log_start(self) -> None:
        """Loguje start symulacji."""
        unit_snapshots = [u.to_snapshot() for u in self.units]
        self.logger.log_simulation_start(self.tick, unit_snapshots)
    
    def _log_end(self) -> None:
        """Loguje koniec symulacji."""
        survivors = [u.to_dict() for u in self.units if u.is_alive()]
        self.logger.log_simulation_end(self.tick, self.winner_team, survivors)
    
    # ─────────────────────────────────────────────────────────────────────────
    # WYNIKI
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_result(self) -> Dict[str, Any]:
        """
        Zwraca wynik symulacji.
        
        Returns:
            Dict z:
                - winner_team: int lub None
                - total_ticks: int
                - duration_seconds: float
                - survivors: List[Dict]
        """
        survivors = [u.to_dict() for u in self.units if u.is_alive()]
        
        return {
            "winner_team": self.winner_team,
            "total_ticks": self.tick,
            "duration_seconds": self.tick / self.config.ticks_per_second,
            "survivors": survivors,
        }
    
    def save_log(self, filepath: str) -> None:
        """Zapisuje log do pliku JSON."""
        self.logger.save(filepath)
    
    def get_log(self) -> Dict[str, Any]:
        """Zwraca log jako słownik."""
        return self.logger.to_dict()
    
    # ─────────────────────────────────────────────────────────────────────────
    # ABILITY SYSTEM
    # ─────────────────────────────────────────────────────────────────────────
    
    def set_config_loader(self, loader: ConfigLoader) -> None:
        """Ustawia loader do ładowania abilities."""
        self._config_loader = loader
    
    def set_trait_manager(self, traits_data: Dict[str, Any]) -> None:
        """
        Tworzy i konfiguruje TraitManager.
        
        Args:
            traits_data: Słownik z traits.yaml (klucz 'traits')
        """
        self.trait_manager = TraitManager(self)
        self.trait_manager.load_traits(traits_data)
    
    def set_item_manager(self, items_data: Dict[str, Any]) -> None:
        """
        Tworzy i konfiguruje ItemManager.
        
        Args:
            items_data: Słownik z items.yaml (klucz 'items')
        """
        self.item_manager = ItemManager(self)
        self.item_manager.load_items(items_data)
    
    def _get_unit_ability(self, unit: Unit) -> Optional[Ability]:
        """
        Zwraca Ability dla jednostki.
        
        Cache'uje abilities dla wydajności.
        """
        if not unit.abilities:
            return None
        
        ability_id = unit.abilities[0]  # Pierwsza ability
        
        # Check cache
        if ability_id in self._ability_cache:
            return self._ability_cache[ability_id]
        
        # Load from config
        if self._config_loader is None:
            return None
        
        try:
            ability_data = self._config_loader.load_ability(ability_id)
            ability = Ability.from_dict(ability_id, ability_data)
            self._ability_cache[ability_id] = ability
            return ability
        except KeyError:
            return None
    
    def _execute_ability(self, unit: Unit) -> None:
        """Wykonuje umiejętność jednostki."""
        ability = self._get_unit_ability(unit)
        if ability is None:
            return
        
        target = unit.target
        if not target or not target.is_alive():
            return
        
        # IMPORTANT: Mark effect as triggered FIRST to prevent multiple casts
        unit.state.mark_effect_triggered()
        
        # Consume mana
        unit.stats.spend_mana(ability.mana_cost)
        
        # Log ability cast
        self.logger.log_ability_cast(
            self.tick, unit.id, ability.id,
            target.id if target else None,
        )
        
        # Item on_ability_cast effects (Blue Buff, etc.)
        if self.item_manager:
            self.item_manager.on_ability_cast(unit)
        
        # Check if projectile-based
        if ability.projectile:
            # Spawn projectile instead of instant effect
            self.projectile_manager.spawn(
                source=unit,
                target=target,
                ability=ability,
                star_level=unit.star_level,
            )
        else:
            # Instant effect
            self._apply_ability_effects(unit, target, ability)
    
    def _execute_projectile_impact(self, proj) -> None:
        """Wykonuje efekty po trafieniu projectile."""
        from .simulation import Simulation  # self reference for typing
        
        if not proj.target or not proj.target.is_alive():
            return
        
        self._apply_ability_effects(
            proj.source, 
            proj.target, 
            proj.ability,
            proj.star_level,
        )
    
    def _apply_ability_effects(
        self, 
        caster: Unit, 
        target: Unit, 
        ability: Ability,
        star_level: Optional[int] = None,
    ) -> None:
        """
        Aplikuje wszystkie efekty ability.
        
        Obsługuje AoE jeśli ability ma AoE config.
        """
        star = star_level or caster.star_level
        
        # Get targets (AoE or single)
        if ability.aoe:
            from ..abilities.aoe import AoECalculator
            
            # Get enemy units for AoE
            enemies = [u for u in self.units 
                       if u.is_alive() and u.team != caster.team]
            
            targets = AoECalculator.get_targets(
                aoe_type=ability.aoe.aoe_type,
                origin=caster.position,
                target=target.position,
                radius=ability.get_aoe_radius(star),
                angle=60,  # default cone angle
                width=1,   # default line width
                candidates=enemies,
                primary_target=target,
            )
        else:
            targets = [target]
        
        # Apply all effects to all targets
        for effect in ability.effects:
            for t in targets:
                if not t.is_alive():
                    continue
                    
                try:
                    result = effect.apply(caster, t, star, self)
                    
                    # Log effect
                    if result.success:
                        self.logger.log_ability_effect(
                            self.tick,
                            caster.id,
                            ability.id,
                            effect.effect_type,
                            result.value,
                            result.targets,
                        )
                        
                        # Check if target died
                        if not t.is_alive():
                            self._handle_unit_death(t)
                            
                except Exception as e:
                    # Log error but continue
                    pass
    
    def _handle_unit_death(self, unit: Unit) -> None:
        """Obsługuje śmierć jednostki."""
        if unit.is_alive():
            return
        
        unit.state.die()
        self.logger.log_death(self.tick, unit.id)
        
        # Clear from grid
        self.grid.remove_unit(unit)

