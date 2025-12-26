"""
Unit - główna klasa reprezentująca jednostkę na polu bitwy.

Jednostka łączy wszystkie komponenty:
- UnitStats: statystyki (HP, AD, crit, etc.)
- UnitStateMachine: aktualny stan (IDLE, MOVING, etc.)
- Pozycja na siatce (HexCoord)
- Lista buffów, przedmiotów, umiejętności

Cykl życia jednostki:
═══════════════════════════════════════════════════════════════════

    1. TWORZENIE
       - Z definicji YAML (ConfigLoader.load_unit)
       - Ustawiany team, pozycja startowa, poziom gwiazd
       
    2. START WALKI
       - reset_for_combat() - HP=max, mana=start_mana
       - Umieszczenie na siatce (HexGrid.place_unit)
       
    3. PĘTLA WALKI (per tick)
       - update_buffs() - odliczanie buffów
       - check_ability() - czy może użyć skilla
       - ai_decision() - wybór celu/akcji
       - execute_action() - ruch/atak/cast
       
    4. ŚMIERĆ
       - HP <= 0 -> state = DEAD
       - Usunięcie z siatki
       - on_death triggers

Identyfikacja:
    Każda jednostka ma unikalne `id` (string).
    Format: "{unit_type}_{team}_{index}" np. "warrior_0_1"

Przykład użycia:
    >>> unit = Unit.from_config(loader.load_unit("warrior"), team=0, position=HexCoord(0, 0))
    >>> unit.stats.get_crit_chance()
    0.25
    >>> unit.state.current
    UnitState.IDLE
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, TYPE_CHECKING
import uuid

from ..core.hex_coord import HexCoord
from .stats import UnitStats
from .state_machine import UnitState, UnitStateMachine

if TYPE_CHECKING:
    from ..effects.buff import Buff


@dataclass
class Unit:
    """
    Reprezentuje jednostkę na polu bitwy.
    
    Attributes:
        id (str): Unikalny identyfikator
        name (str): Nazwa jednostki (np. "Warrior")
        unit_type (str): Typ/ID z YAML (np. "warrior")
        team (int): Numer drużyny (0 lub 1)
        position (HexCoord): Aktualna pozycja na siatce
        stats (UnitStats): Statystyki jednostki
        state (UnitStateMachine): Maszyna stanów
        star_level (int): Poziom gwiazd (1-3)
        
        target (Optional[Unit]): Aktualny cel ataku
        
        abilities (List[str]): ID umiejętności
        items (List[str]): ID przedmiotów
        traits (List[str]): Traity jednostki (do synergii)
        buffs (List[Buff]): Aktywne buffy/debuffy
        
        attack_cooldown (float): Pozostały czas do następnego ataku
        
    Note:
        - Jednostki są porównywane po `id`
        - `position` jest synchronizowane z HexGrid
    """
    
    # Identyfikacja
    id: str
    name: str
    unit_type: str
    team: int
    
    # Pozycja i stan
    position: HexCoord
    stats: UnitStats
    state: UnitStateMachine = field(default_factory=UnitStateMachine)
    star_level: int = 1
    
    # Cel
    target: Optional["Unit"] = field(default=None, repr=False)
    target_id: Optional[str] = field(default=None, repr=False)  # dla serializacji
    
    # Komponenty
    abilities: List[str] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    traits: List[str] = field(default_factory=list)
    buffs: List["Buff"] = field(default_factory=list, repr=False)
    
    # Combat state
    attack_cooldown: float = field(default=0.0, repr=False)
    mana_per_attack: float = field(default=10.0, repr=False)  # mana gained on attack
    mana_on_damage: float = field(default=5.0, repr=False)    # mana gained when damaged (legacy)
    
    # Mana overflow tracking (TFT-style)
    _pending_mana_overflow: float = field(default=0.0, repr=False)
    
    # Champion class (optional)
    mana_class: Optional[str] = field(default=None, repr=False)
    
    # ─────────────────────────────────────────────────────────────────────────
    # SHIELD, DEBUFFS, STATUS EFFECTS
    # ─────────────────────────────────────────────────────────────────────────
    
    # Shield (tymczasowe HP)
    shield_hp: float = field(default=0.0, repr=False)
    shield_remaining_ticks: int = field(default=0, repr=False)
    
    # Wound (redukcja leczenia %)
    wound_percent: float = field(default=0.0, repr=False)
    wound_remaining_ticks: int = field(default=0, repr=False)
    
    # Burn (true damage per second)
    burns: List[Dict] = field(default_factory=list, repr=False)
    
    # DoT (damage over time z typem)
    dots: List[Dict] = field(default_factory=list, repr=False)
    
    # Slow (attack speed reduction)
    slow_percent: float = field(default=0.0, repr=False)
    slow_remaining_ticks: int = field(default=0, repr=False)
    
    # Armor/MR reduction
    armor_reduction: float = field(default=0.0, repr=False)
    armor_reduction_ticks: int = field(default=0, repr=False)
    mr_reduction: float = field(default=0.0, repr=False)
    mr_reduction_ticks: int = field(default=0, repr=False)
    
    # Silence (blocks casting)
    silence_remaining_ticks: int = field(default=0, repr=False)
    
    # Disarm (blocks auto-attacks)
    disarm_remaining_ticks: int = field(default=0, repr=False)
    
    # ─────────────────────────────────────────────────────────────────────────
    # FACTORY METHODS
    # ─────────────────────────────────────────────────────────────────────────
    
    @classmethod
    def from_config(
        cls,
        config: Dict[str, Any],
        team: int,
        position: HexCoord,
        star_level: int = 1,
        unit_id: Optional[str] = None
    ) -> "Unit":
        """
        Tworzy jednostkę z konfiguracji (słownika z ConfigLoader).
        
        Args:
            config: Słownik z load_unit() (zawiera defaults)
            team: Numer drużyny (0 lub 1)
            position: Pozycja startowa
            star_level: Poziom gwiazd (1-3)
            unit_id: Opcjonalne ID (generowane jeśli brak)
            
        Returns:
            Unit: Nowa jednostka
            
        Example:
            >>> config = loader.load_unit("warrior")
            >>> unit = Unit.from_config(config, team=0, position=HexCoord(0, 0))
        """
        unit_type = config.get("id", "unknown")
        name = config.get("name", unit_type.title())
        
        # Generuj ID jeśli nie podano
        if unit_id is None:
            unit_id = f"{unit_type}_{team}_{uuid.uuid4().hex[:6]}"
        
        # Twórz stats z konfiga
        stats = UnitStats.from_dict(config)
        
        # Pobierz abilities i traits
        ability = config.get("ability")
        abilities = [ability] if ability else []
        
        traits = config.get("traits", [])
        if isinstance(traits, str):
            traits = [traits]
        
        unit = cls(
            id=unit_id,
            name=name,
            unit_type=unit_type,
            team=team,
            position=position,
            stats=stats,
            star_level=star_level,
            abilities=abilities,
            traits=traits,
        )
        
        # Aplikuj modyfikatory gwiazd
        # (to powinno być z defaults, ale na razie hardcoded)
        star_mods = {
            1: {"hp_multiplier": 1.0, "damage_multiplier": 1.0},
            2: {"hp_multiplier": 1.8, "damage_multiplier": 1.8},
            3: {"hp_multiplier": 3.24, "damage_multiplier": 3.24},
        }
        unit.stats.apply_star_level(star_level, star_mods)
        
        return unit
    
    # ─────────────────────────────────────────────────────────────────────────
    # STAN I ŻYCIE
    # ─────────────────────────────────────────────────────────────────────────
    
    def is_alive(self) -> bool:
        """Sprawdza czy jednostka żyje."""
        return self.stats.is_alive() and self.state.is_alive()
    
    def is_dead(self) -> bool:
        """Sprawdza czy jednostka jest martwa."""
        return not self.is_alive()
    
    def can_act(self) -> bool:
        """Sprawdza czy jednostka może działać."""
        return self.is_alive() and self.state.can_act()
    
    def die(self) -> None:
        """Ustawia jednostkę jako martwą."""
        self.stats.current_hp = 0
        self.state.die()
        self.target = None
        self.target_id = None
    
    def reset_for_combat(self) -> None:
        """
        Resetuje jednostkę na początek walki.
        
        - HP = max HP
        - Mana = start_mana
        - Stan = IDLE
        - Brak celu
        - Czyści buffy
        """
        self.stats.reset_for_combat()
        self.state.reset()
        self.target = None
        self.target_id = None
        self.attack_cooldown = 0.0
        self.buffs.clear()
    
    # ─────────────────────────────────────────────────────────────────────────
    # COMBAT
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_attack_cooldown_ticks(self, ticks_per_second: int = 30) -> float:
        """
        Oblicza cooldown ataku w tickach.
        
        Wzór: ticks_per_second / attack_speed
        
        Args:
            ticks_per_second: Ticki na sekundę (domyślnie 30)
            
        Returns:
            float: Ticki między atakami
            
        Example:
            AS = 1.0 -> 30 ticks cooldown
            AS = 0.5 -> 60 ticks cooldown
            AS = 2.0 -> 15 ticks cooldown
        """
        attack_speed = self.stats.get_attack_speed()
        if attack_speed <= 0:
            return float('inf')
        return ticks_per_second / attack_speed
    
    def can_attack(self) -> bool:
        """
        Sprawdza czy jednostka może atakować.
        
        Returns:
            bool: True jeśli może atakować w tym ticku
        """
        return (
            self.is_alive() 
            and self.attack_cooldown <= 0 
            and self.state.current == UnitState.ATTACKING
        )
    
    def start_attack_cooldown(self, ticks_per_second: int = 30) -> None:
        """Rozpoczyna cooldown po ataku."""
        self.attack_cooldown = self.get_attack_cooldown_ticks(ticks_per_second)
    
    def tick_cooldowns(self) -> None:
        """Zmniejsza cooldowny o 1 tick."""
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1
    
    def get_attack_range(self) -> int:
        """Zwraca zasięg ataku."""
        return self.stats.get_attack_range()
    
    def in_attack_range(self, target: "Unit") -> bool:
        """
        Sprawdza czy cel jest w zasięgu ataku.
        
        Args:
            target: Cel
            
        Returns:
            bool: True jeśli w zasięgu
        """
        distance = self.position.distance(target.position)
        return distance <= self.get_attack_range()
    
    def is_enemy(self, other: "Unit") -> bool:
        """Sprawdza czy jednostka jest wrogiem."""
        return self.team != other.team
    
    def is_ally(self, other: "Unit") -> bool:
        """Sprawdza czy jednostka jest sojusznikiem."""
        return self.team == other.team and self.id != other.id
    
    # ─────────────────────────────────────────────────────────────────────────
    # MANA SYSTEM (TFT-style)
    # ─────────────────────────────────────────────────────────────────────────
    
    def is_mana_locked(self) -> bool:
        """
        Sprawdza czy mana jest zablokowana.
        
        Returns:
            bool: True jeśli nie można zyskiwać many
        """
        return self.state.is_mana_locked()
    
    def gain_mana_on_attack(self, mana_config: dict = None) -> float:
        """
        Zyskuje manę za atak.
        
        Args:
            mana_config: Opcjonalna konfiguracja many (z defaults.yaml)
            
        Returns:
            float: Ilość zyskanej many (0 jeśli locked)
        """
        if self.is_mana_locked():
            return 0.0
        
        mana_gain = self.mana_per_attack
        
        # Apply champion class multiplier if present
        # (champion_class is applied in simulation layer)
        
        overflow = self.stats.add_mana(mana_gain)
        self._pending_mana_overflow += overflow
        return mana_gain
    
    def gain_mana_on_damage(
        self, 
        pre_mitigation_damage: float = 0.0,
        post_mitigation_damage: float = 0.0,
        mana_config: dict = None,
    ) -> float:
        """
        Zyskuje manę za otrzymane obrażenia (TFT formula).
        
        Formula: 1% pre-mitigation + 3% post-mitigation, cap 42.5
        
        Args:
            pre_mitigation_damage: Obrażenia przed armor/MR
            post_mitigation_damage: Obrażenia po redukcji
            mana_config: Opcjonalna konfiguracja many
            
        Returns:
            float: Ilość zyskanej many (0 jeśli locked)
        """
        if self.is_mana_locked():
            return 0.0
        
        # TFT formula
        if mana_config:
            pre_percent = mana_config.get("mana_from_damage", {}).get("pre_mitigation_percent", 0.01)
            post_percent = mana_config.get("mana_from_damage", {}).get("post_mitigation_percent", 0.03)
            cap = mana_config.get("mana_from_damage", {}).get("cap", 42.5)
        else:
            pre_percent = 0.01
            post_percent = 0.03
            cap = 42.5
        
        mana_gain = pre_mitigation_damage * pre_percent + post_mitigation_damage * post_percent
        mana_gain = min(mana_gain, cap)
        
        # Fallback to legacy formula if no damage values provided
        if pre_mitigation_damage == 0 and post_mitigation_damage == 0:
            mana_gain = self.mana_on_damage
        
        overflow = self.stats.add_mana(mana_gain)
        self._pending_mana_overflow += overflow
        return mana_gain
    
    def gain_mana_passive(self, ticks_per_second: int = 30, mana_per_second: float = 0.0) -> float:
        """
        Zyskuje pasywną regenerację many.
        
        Args:
            ticks_per_second: Ticki na sekundę
            mana_per_second: Mana per second z konfiguracji
            
        Returns:
            float: Ilość zyskanej many na ten tick
        """
        if self.is_mana_locked() or mana_per_second <= 0:
            return 0.0
        
        mana_per_tick = mana_per_second / ticks_per_second
        overflow = self.stats.add_mana(mana_per_tick)
        self._pending_mana_overflow += overflow
        return mana_per_tick
    
    def consume_mana_for_cast(self, mana_overflow_enabled: bool = True) -> float:
        """
        Zużywa manę na cast i zarządza overflow.
        
        Args:
            mana_overflow_enabled: Czy nadmiar many przenosi się po caście
            
        Returns:
            float: Ilość pozostałej many (overflow)
        """
        max_mana = self.stats.get_max_mana()
        current_mana = self.stats.current_mana
        
        if mana_overflow_enabled:
            overflow = max(0, current_mana - max_mana) + self._pending_mana_overflow
        else:
            overflow = 0.0
        
        # Reset mana to overflow amount
        self.stats.current_mana = overflow
        self._pending_mana_overflow = 0.0
        
        return overflow
    
    def can_cast_ability(self) -> bool:
        """
        Sprawdza czy może użyć umiejętności.
        
        Returns:
            bool: True jeśli ma pełną manę i ma ability
        """
        return self.stats.is_mana_full() and len(self.abilities) > 0
    
    # ─────────────────────────────────────────────────────────────────────────
    # TARGET
    # ─────────────────────────────────────────────────────────────────────────
    
    def set_target(self, target: Optional["Unit"]) -> None:
        """
        Ustawia cel ataku.
        
        Args:
            target: Nowy cel lub None
        """
        self.target = target
        self.target_id = target.id if target else None
    
    def clear_target(self) -> None:
        """Czyści cel."""
        self.target = None
        self.target_id = None
    
    def has_valid_target(self) -> bool:
        """
        Sprawdza czy ma prawidłowy cel.
        
        Returns:
            bool: True jeśli cel istnieje i żyje
        """
        return self.target is not None and self.target.is_alive()
    
    # ─────────────────────────────────────────────────────────────────────────
    # BUFFS
    # ─────────────────────────────────────────────────────────────────────────
    
    def add_buff(self, buff: "Buff") -> None:
        """
        Dodaje buff do jednostki.
        
        Args:
            buff: Buff do dodania
            
        Note:
            Buff automatycznie aplikuje swoje modyfikatory do stats.
        """
        # Sprawdź czy buff już istnieje (refresh/stack)
        existing = self.get_buff_by_id(buff.id)
        
        if existing:
            existing.refresh_or_stack(buff)
        else:
            self.buffs.append(buff)
            buff.apply_to(self)
    
    def remove_buff(self, buff_id: str) -> bool:
        """
        Usuwa buff z jednostki.
        
        Args:
            buff_id: ID buffa do usunięcia
            
        Returns:
            bool: True jeśli buff został usunięty
        """
        for i, buff in enumerate(self.buffs):
            if buff.id == buff_id:
                buff.remove_from(self)
                self.buffs.pop(i)
                return True
        return False
    
    def get_buff_by_id(self, buff_id: str) -> Optional["Buff"]:
        """Znajduje buff po ID."""
        for buff in self.buffs:
            if buff.id == buff_id:
                return buff
        return None
    
    def update_buffs(self) -> List["Buff"]:
        """
        Aktualizuje czas trwania buffów.
        
        Returns:
            List[Buff]: Lista wygasłych buffów
        """
        expired = []
        
        for buff in self.buffs[:]:  # kopia listy
            buff.tick()
            if buff.is_expired():
                buff.remove_from(self)
                self.buffs.remove(buff)
                expired.append(buff)
        
        return expired
    
    # ─────────────────────────────────────────────────────────────────────────
    # SERIALIZACJA
    # ─────────────────────────────────────────────────────────────────────────
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serializuje jednostkę do słownika (dla event logu).
        
        Returns:
            Dict: Reprezentacja jednostki
        """
        return {
            "id": self.id,
            "name": self.name,
            "unit_type": self.unit_type,
            "team": self.team,
            "position": [self.position.q, self.position.r],
            "star_level": self.star_level,
            "hp": round(self.stats.current_hp, 1),
            "max_hp": round(self.stats.get_max_hp(), 1),
            "mana": round(self.stats.current_mana, 1),
            "max_mana": round(self.stats.get_max_mana(), 1),
            "state": self.state.current.name,
            "target_id": self.target_id,
        }
    
    def to_snapshot(self) -> Dict[str, Any]:
        """
        Zwraca pełny snapshot stanu jednostki.
        
        Bardziej szczegółowy niż to_dict, używany do debug/replay.
        """
        return {
            **self.to_dict(),
            "stats": {
                "attack_damage": self.stats.get_attack_damage(),
                "ability_power": self.stats.get_ability_power(),
                "armor": self.stats.get_armor(),
                "magic_resist": self.stats.get_magic_resist(),
                "attack_speed": self.stats.get_attack_speed(),
                "attack_range": self.stats.get_attack_range(),
                "crit_chance": self.stats.get_crit_chance(),
                "crit_damage": self.stats.get_crit_damage(),
            },
            "buffs": [b.id for b in self.buffs],
            "items": self.items,
            "abilities": self.abilities,
        }
    
    # ─────────────────────────────────────────────────────────────────────────
    # DEBUFF / STATUS EFFECT METHODS
    # ─────────────────────────────────────────────────────────────────────────
    
    def add_shield(self, amount: float, duration: int) -> None:
        """
        Dodaje tarczę (tymczasowe HP).
        
        Args:
            amount: Ilość HP tarczy
            duration: Czas trwania w tickach
        """
        self.shield_hp = max(self.shield_hp, amount)  # nie stackuje, bierz większy
        self.shield_remaining_ticks = max(self.shield_remaining_ticks, duration)
    
    def add_wound(self, percent: float, duration: int) -> None:
        """
        Dodaje wound (redukcja leczenia).
        
        Args:
            percent: % redukcji leczenia
            duration: Czas trwania w tickach
        """
        self.wound_percent = max(self.wound_percent, percent)
        self.wound_remaining_ticks = max(self.wound_remaining_ticks, duration)
    
    def add_burn(self, dps: float, duration: int, source_id: str) -> None:
        """
        Dodaje burn (true damage per second).
        
        Args:
            dps: Damage per second
            duration: Czas trwania w tickach
            source_id: ID jednostki która nałożyła burn
        """
        self.burns.append({
            "dps": dps,
            "remaining": duration,
            "source_id": source_id,
        })
    
    def add_dot(
        self, 
        damage: float, 
        damage_type: str,  # "physical" | "magical"
        duration: int, 
        interval: int,
        source_id: str,
    ) -> None:
        """
        Dodaje DoT (damage over time).
        
        Args:
            damage: Damage per tick
            damage_type: Typ obrażeń
            duration: Czas trwania w tickach
            interval: Co ile ticków damage
            source_id: ID źródła
        """
        self.dots.append({
            "damage": damage,
            "damage_type": damage_type,
            "remaining": duration,
            "interval": interval,
            "next_tick": interval,
            "source_id": source_id,
        })
    
    def add_slow(self, percent: float, duration: int) -> None:
        """
        Dodaje slow (attack speed reduction).
        
        Args:
            percent: % spowolnienia
            duration: Czas trwania w tickach
        """
        self.slow_percent = max(self.slow_percent, percent)
        self.slow_remaining_ticks = max(self.slow_remaining_ticks, duration)
    
    def add_armor_reduction(self, amount: float, duration: int, is_percent: bool = False) -> None:
        """Dodaje redukcję Armor."""
        self.armor_reduction = max(self.armor_reduction, amount)
        self.armor_reduction_ticks = max(self.armor_reduction_ticks, duration)
    
    def add_mr_reduction(self, amount: float, duration: int, is_percent: bool = False) -> None:
        """Dodaje redukcję Magic Resist."""
        self.mr_reduction = max(self.mr_reduction, amount)
        self.mr_reduction_ticks = max(self.mr_reduction_ticks, duration)
    
    def add_silence(self, duration: int) -> None:
        """Dodaje silence (blokuje castowanie)."""
        self.silence_remaining_ticks = max(self.silence_remaining_ticks, duration)
    
    def add_disarm(self, duration: int) -> None:
        """Dodaje disarm (blokuje auto-ataki)."""
        self.disarm_remaining_ticks = max(self.disarm_remaining_ticks, duration)
    
    def is_silenced(self) -> bool:
        """Czy jednostka jest silenced."""
        return self.silence_remaining_ticks > 0
    
    def is_disarmed(self) -> bool:
        """Czy jednostka jest disarmed."""
        return self.disarm_remaining_ticks > 0
    
    def tick_debuffs(self, ticks_per_second: int = 30) -> float:
        """
        Aktualizuje wszystkie debuffs - wywoływane co tick.
        
        Returns:
            float: Sumaryczny damage z burn/dot
        """
        total_damage = 0.0
        
        # Shield expiry
        if self.shield_remaining_ticks > 0:
            self.shield_remaining_ticks -= 1
            if self.shield_remaining_ticks <= 0:
                self.shield_hp = 0
        
        # Wound expiry
        if self.wound_remaining_ticks > 0:
            self.wound_remaining_ticks -= 1
            if self.wound_remaining_ticks <= 0:
                self.wound_percent = 0
        
        # Slow expiry
        if self.slow_remaining_ticks > 0:
            self.slow_remaining_ticks -= 1
            if self.slow_remaining_ticks <= 0:
                self.slow_percent = 0
        
        # Armor reduction expiry
        if self.armor_reduction_ticks > 0:
            self.armor_reduction_ticks -= 1
            if self.armor_reduction_ticks <= 0:
                self.armor_reduction = 0
        
        # MR reduction expiry
        if self.mr_reduction_ticks > 0:
            self.mr_reduction_ticks -= 1
            if self.mr_reduction_ticks <= 0:
                self.mr_reduction = 0
        
        # Silence expiry
        if self.silence_remaining_ticks > 0:
            self.silence_remaining_ticks -= 1
        
        # Disarm expiry
        if self.disarm_remaining_ticks > 0:
            self.disarm_remaining_ticks -= 1
        
        # Burns (TRUE damage per second)
        active_burns = []
        for burn in self.burns:
            burn["remaining"] -= 1
            # Damage co sekundę (30 ticków)
            dps_per_tick = burn["dps"] / ticks_per_second
            total_damage += dps_per_tick
            
            if burn["remaining"] > 0:
                active_burns.append(burn)
        self.burns = active_burns
        
        # DoTs (z typem damage)
        active_dots = []
        for dot in self.dots:
            dot["remaining"] -= 1
            dot["next_tick"] -= 1
            
            if dot["next_tick"] <= 0:
                total_damage += dot["damage"]
                dot["next_tick"] = dot["interval"]
            
            if dot["remaining"] > 0:
                active_dots.append(dot)
        self.dots = active_dots
        
        # Aplikuj damage (TRUE dla burn, normalne dla dot)
        if total_damage > 0:
            self.stats.take_damage(total_damage)
        
        return total_damage
    
    def die(self) -> None:
        """Zabija jednostkę."""
        self.stats.current_hp = 0
        self.state.die()
    
    # ─────────────────────────────────────────────────────────────────────────
    # COMPARISON
    # ─────────────────────────────────────────────────────────────────────────
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Unit):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        return hash(self.id)
    
    def __repr__(self) -> str:
        return f"Unit({self.id}, {self.name}, team={self.team}, hp={self.stats.current_hp:.0f})"
