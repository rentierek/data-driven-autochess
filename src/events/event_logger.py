"""
System logowania zdarzeń do formatu JSON dla replay.

Każde zdarzenie w symulacji (ruch, atak, obrażenia, śmierć etc.)
jest zapisywane z pełnym kontekstem. Log może być później użyty
do odtworzenia walki w wizualizacji.

TYPY ZDARZEŃ:
═══════════════════════════════════════════════════════════════════

    SIMULATION_START
    ─────────────────────────────────────────────────────────────
    Początek symulacji.
    Data: seed, grid_size, units (lista snapshottów)
    
    SIMULATION_END  
    ─────────────────────────────────────────────────────────────
    Koniec symulacji.
    Data: winner_team, total_ticks, survivors
    
    UNIT_SPAWN
    ─────────────────────────────────────────────────────────────
    Pojawienie się jednostki na planszy.
    Data: unit snapshot
    
    UNIT_MOVE
    ─────────────────────────────────────────────────────────────
    Ruch jednostki.
    Data: from [q, r], to [q, r]
    
    UNIT_ATTACK
    ─────────────────────────────────────────────────────────────
    Wykonanie ataku.
    Data: target_id, damage_result
    
    UNIT_DAMAGE
    ─────────────────────────────────────────────────────────────
    Otrzymanie obrażeń.
    Data: source_id, damage, damage_type, hp_after
    
    UNIT_HEAL
    ─────────────────────────────────────────────────────────────
    Otrzymanie leczenia.
    Data: source, amount, hp_after
    
    UNIT_DEATH
    ─────────────────────────────────────────────────────────────
    Śmierć jednostki.
    Data: killer_id
    
    ABILITY_CAST
    ─────────────────────────────────────────────────────────────
    Użycie umiejętności.
    Data: ability_id, targets, effects
    
    BUFF_APPLY
    ─────────────────────────────────────────────────────────────
    Nałożenie buffa.
    Data: buff_id, source_id, duration
    
    BUFF_EXPIRE
    ─────────────────────────────────────────────────────────────
    Wygaśnięcie buffa.
    Data: buff_id
    
    STATE_CHANGE
    ─────────────────────────────────────────────────────────────
    Zmiana stanu jednostki.
    Data: from_state, to_state
    
    TARGET_ACQUIRED
    ─────────────────────────────────────────────────────────────
    Jednostka wybrała nowy cel.
    Data: target_id

FORMAT LOGU:
═══════════════════════════════════════════════════════════════════

{
    "metadata": {
        "version": "1.0",
        "seed": 12345,
        "ticks_per_second": 30,
        "grid": {"width": 7, "height": 8},
        "timestamp": "2024-01-01T12:00:00"
    },
    "initial_state": {
        "units": [...]
    },
    "events": [
        {
            "tick": 0,
            "type": "SIMULATION_START",
            "data": {...}
        },
        {
            "tick": 1,
            "type": "UNIT_MOVE",
            "unit_id": "warrior_0_abc123",
            "data": {"from": [0, 0], "to": [1, 0]}
        },
        ...
    ],
    "final_state": {
        "winner_team": 0,
        "survivors": [...],
        "total_ticks": 150
    }
}
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional
from datetime import datetime
import json
from pathlib import Path


class EventType(Enum):
    """Typ zdarzenia w symulacji."""
    
    # Symulacja
    SIMULATION_START = auto()
    SIMULATION_END = auto()
    TICK_START = auto()  # opcjonalne - do debug
    
    # Jednostki
    UNIT_SPAWN = auto()
    UNIT_MOVE = auto()
    UNIT_ATTACK = auto()
    UNIT_DAMAGE = auto()
    UNIT_HEAL = auto()
    UNIT_DEATH = auto()
    UNIT_MANA_GAIN = auto()
    
    # Umiejętności
    ABILITY_CAST = auto()
    ABILITY_EFFECT = auto()
    
    # Buffy
    BUFF_APPLY = auto()
    BUFF_EXPIRE = auto()
    BUFF_STACK = auto()
    
    # Stan
    STATE_CHANGE = auto()
    TARGET_ACQUIRED = auto()
    TARGET_LOST = auto()


@dataclass
class GameEvent:
    """
    Pojedyncze zdarzenie w symulacji.
    
    Attributes:
        tick (int): Numer ticka kiedy zdarzenie nastąpiło
        event_type (EventType): Typ zdarzenia
        unit_id (Optional[str]): ID jednostki (jeśli dotyczy jednostki)
        target_id (Optional[str]): ID celu (jeśli dotyczy)
        data (Dict): Dodatkowe dane specyficzne dla typu zdarzenia
    """
    tick: int
    event_type: EventType
    unit_id: Optional[str] = None
    target_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializuje zdarzenie do słownika."""
        result = {
            "tick": self.tick,
            "type": self.event_type.name,
        }
        
        if self.unit_id:
            result["unit_id"] = self.unit_id
        if self.target_id:
            result["target_id"] = self.target_id
        if self.data:
            result["data"] = self.data
        
        return result


class EventLogger:
    """
    Logger zdarzeń symulacji.
    
    Zbiera wszystkie zdarzenia i może je zapisać do pliku JSON.
    
    Attributes:
        events (List[GameEvent]): Lista wszystkich zdarzeń
        metadata (Dict): Metadane symulacji
        initial_state (Dict): Stan początkowy
        final_state (Dict): Stan końcowy
        
    Example:
        >>> logger = EventLogger(seed=12345, grid_width=7, grid_height=8)
        >>> logger.log(GameEvent(tick=0, event_type=EventType.SIMULATION_START))
        >>> logger.log_move(tick=1, unit_id="warrior_0", from_pos=HexCoord(0,0), to_pos=HexCoord(1,0))
        >>> logger.save("output/battle_12345.json")
    """
    
    def __init__(
        self,
        seed: int,
        grid_width: int = 7,
        grid_height: int = 8,
        ticks_per_second: int = 30,
    ):
        """
        Inicjalizuje logger.
        
        Args:
            seed: Ziarno losowości symulacji
            grid_width: Szerokość siatki
            grid_height: Wysokość siatki
            ticks_per_second: Ticki na sekundę
        """
        self.events: List[GameEvent] = []
        self.metadata: Dict[str, Any] = {
            "version": "1.0",
            "seed": seed,
            "ticks_per_second": ticks_per_second,
            "grid": {"width": grid_width, "height": grid_height},
            "timestamp": datetime.now().isoformat(),
        }
        self.initial_state: Dict[str, Any] = {}
        self.final_state: Dict[str, Any] = {}
    
    # ─────────────────────────────────────────────────────────────────────────
    # LOGOWANIE OGÓLNE
    # ─────────────────────────────────────────────────────────────────────────
    
    def log(self, event: GameEvent) -> None:
        """
        Dodaje zdarzenie do logu.
        
        Args:
            event: Zdarzenie do zalogowania
        """
        self.events.append(event)
    
    def log_event(
        self,
        tick: int,
        event_type: EventType,
        unit_id: Optional[str] = None,
        target_id: Optional[str] = None,
        **data: Any,
    ) -> GameEvent:
        """
        Tworzy i loguje zdarzenie.
        
        Args:
            tick: Numer ticka
            event_type: Typ zdarzenia
            unit_id: ID jednostki
            target_id: ID celu
            **data: Dodatkowe dane
            
        Returns:
            GameEvent: Utworzone zdarzenie
        """
        event = GameEvent(
            tick=tick,
            event_type=event_type,
            unit_id=unit_id,
            target_id=target_id,
            data=dict(data),
        )
        self.log(event)
        return event
    
    # ─────────────────────────────────────────────────────────────────────────
    # POMOCNICZE METODY LOGOWANIA
    # ─────────────────────────────────────────────────────────────────────────
    
    def log_simulation_start(self, tick: int, units: List[Dict]) -> None:
        """Loguje start symulacji."""
        self.initial_state = {"units": units}
        self.log_event(tick, EventType.SIMULATION_START, units=units)
    
    def log_simulation_end(
        self, 
        tick: int, 
        winner_team: Optional[int],
        survivors: List[Dict],
    ) -> None:
        """Loguje koniec symulacji."""
        self.final_state = {
            "winner_team": winner_team,
            "total_ticks": tick,
            "survivors": survivors,
        }
        self.log_event(
            tick, 
            EventType.SIMULATION_END,
            winner_team=winner_team,
            total_ticks=tick,
            survivors=[s["id"] for s in survivors],
        )
    
    def log_move(
        self,
        tick: int,
        unit_id: str,
        from_q: int,
        from_r: int,
        to_q: int,
        to_r: int,
    ) -> None:
        """Loguje ruch jednostki."""
        self.log_event(
            tick,
            EventType.UNIT_MOVE,
            unit_id=unit_id,
            **{"from": [from_q, from_r], "to": [to_q, to_r]},
        )
    
    def log_attack(
        self,
        tick: int,
        unit_id: str,
        target_id: str,
        damage: float,
        is_crit: bool = False,
        was_dodged: bool = False,
    ) -> None:
        """Loguje atak."""
        self.log_event(
            tick,
            EventType.UNIT_ATTACK,
            unit_id=unit_id,
            target_id=target_id,
            damage=round(damage, 1),
            is_crit=is_crit,
            was_dodged=was_dodged,
        )
    
    def log_damage(
        self,
        tick: int,
        unit_id: str,
        source_id: str,
        damage: float,
        damage_type: str,
        hp_after: float,
    ) -> None:
        """Loguje otrzymanie obrażeń."""
        self.log_event(
            tick,
            EventType.UNIT_DAMAGE,
            unit_id=unit_id,
            source_id=source_id,
            damage=round(damage, 1),
            damage_type=damage_type,
            hp_after=round(hp_after, 1),
        )
    
    def log_death(
        self,
        tick: int,
        unit_id: str,
        killer_id: Optional[str] = None,
    ) -> None:
        """Loguje śmierć jednostki."""
        self.log_event(
            tick,
            EventType.UNIT_DEATH,
            unit_id=unit_id,
            killer_id=killer_id,
        )
    
    def log_state_change(
        self,
        tick: int,
        unit_id: str,
        from_state: str,
        to_state: str,
    ) -> None:
        """Loguje zmianę stanu."""
        self.log_event(
            tick,
            EventType.STATE_CHANGE,
            unit_id=unit_id,
            from_state=from_state,
            to_state=to_state,
        )
    
    def log_target_acquired(
        self,
        tick: int,
        unit_id: str,
        target_id: str,
    ) -> None:
        """Loguje znalezienie celu."""
        self.log_event(
            tick,
            EventType.TARGET_ACQUIRED,
            unit_id=unit_id,
            target_id=target_id,
        )
    
    def log_ability_cast(
        self,
        tick: int,
        unit_id: str,
        ability_id: str,
        targets: List[str],
    ) -> None:
        """Loguje użycie umiejętności."""
        self.log_event(
            tick,
            EventType.ABILITY_CAST,
            unit_id=unit_id,
            ability_id=ability_id,
            targets=targets,
        )
    
    def log_ability_effect(
        self,
        tick: int,
        unit_id: str,
        ability_id: str,
        effect_type: str,
        value: float,
        targets: List[str],
    ) -> None:
        """Loguje efekt umiejętności."""
        self.log_event(
            tick,
            EventType.ABILITY_EFFECT,
            unit_id=unit_id,
            ability_id=ability_id,
            effect_type=effect_type,
            value=round(value, 1) if isinstance(value, float) else value,
            targets=targets,
        )
    
    def log_buff_apply(
        self,
        tick: int,
        unit_id: str,
        buff_id: str,
        source_id: Optional[str] = None,
        duration: int = 0,
    ) -> None:
        """Loguje nałożenie buffa."""
        self.log_event(
            tick,
            EventType.BUFF_APPLY,
            unit_id=unit_id,
            buff_id=buff_id,
            source_id=source_id,
            duration=duration,
        )
    
    def log_buff_expire(
        self,
        tick: int,
        unit_id: str,
        buff_id: str,
    ) -> None:
        """Loguje wygaśnięcie buffa."""
        self.log_event(
            tick,
            EventType.BUFF_EXPIRE,
            unit_id=unit_id,
            buff_id=buff_id,
        )
    
    # ─────────────────────────────────────────────────────────────────────────
    # SERIALIZACJA
    # ─────────────────────────────────────────────────────────────────────────
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serializuje cały log do słownika.
        
        Returns:
            Dict: Pełny log w formacie dla JSON
        """
        return {
            "metadata": self.metadata,
            "initial_state": self.initial_state,
            "events": [e.to_dict() for e in self.events],
            "final_state": self.final_state,
        }
    
    def save(self, filepath: str) -> None:
        """
        Zapisuje log do pliku JSON.
        
        Args:
            filepath: Ścieżka do pliku
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    def to_json(self, indent: Optional[int] = 2) -> str:
        """
        Zwraca log jako string JSON.
        
        Args:
            indent: Wcięcie (None = compact)
            
        Returns:
            str: JSON string
        """
        return json.dump(self.to_dict(), indent=indent, ensure_ascii=False)
    
    # ─────────────────────────────────────────────────────────────────────────
    # STATYSTYKI
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_event_count(self) -> int:
        """Zwraca liczbę zdarzeń."""
        return len(self.events)
    
    def get_events_by_type(self, event_type: EventType) -> List[GameEvent]:
        """Filtruje zdarzenia po typie."""
        return [e for e in self.events if e.event_type == event_type]
    
    def get_events_for_unit(self, unit_id: str) -> List[GameEvent]:
        """Filtruje zdarzenia dla jednostki."""
        return [e for e in self.events if e.unit_id == unit_id]
    
    def get_events_in_tick(self, tick: int) -> List[GameEvent]:
        """Filtruje zdarzenia w ticku."""
        return [e for e in self.events if e.tick == tick]
