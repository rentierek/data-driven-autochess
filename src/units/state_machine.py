"""
State Machine dla jednostek.

Każda jednostka ma JEDEN aktualny stan, który określa co robi.
Tranzycje między stanami są wyzwalane przez zdarzenia w symulacji.

STANY:
═══════════════════════════════════════════════════════════════════

    IDLE (Bezczynność)
    ─────────────────────────────────────────────────────────────
    Jednostka nie ma celu lub cel zginął.
    W tym stanie AI szuka najbliższego wroga.
    
    Wejście: brak celu, cel zginął
    Wyjście: 
        -> MOVING (znaleziono cel poza zasięgiem)
        -> ATTACKING (znaleziono cel w zasięgu)
        
    MOVING (Ruch)
    ─────────────────────────────────────────────────────────────
    Jednostka porusza się w stronę celu.
    Używa A* pathfinding, jeden krok na tick (zależnie od movement_speed).
    
    Wejście: cel poza zasięgiem ataku
    Wyjście:
        -> IDLE (cel zginął lub zgubiony)
        -> ATTACKING (dotarł do zasięgu)
        
    ATTACKING (Atak)
    ─────────────────────────────────────────────────────────────
    Jednostka atakuje cel.
    Ataki mają cooldown bazowany na attack_speed.
    Po każdym ataku jednostka zyskuje manaę.
    
    Wejście: cel w zasięgu
    Wyjście:
        -> IDLE (cel zginął)
        -> CASTING (pełna mana i ma ability)
        -> MOVING (cel uciekł poza zasięg)
        
    CASTING (Rzucanie skilla)
    ─────────────────────────────────────────────────────────────
    Jednostka rzuca umiejętność.
    Trwa określoną liczbę ticków (cast time).
    Po rzuceniu mana spada do 0.
    
    Wejście: pełna mana
    Wyjście:
        -> ATTACKING (skill rzucony)
        -> IDLE (cel zginął w trakcie casta)
        
    STUNNED (Ogłuszony)
    ─────────────────────────────────────────────────────────────
    Jednostka nie może nic robić.
    Stun ma czas trwania w tickach.
    
    Wejście: otrzymanie efektu stun
    Wyjście:
        -> poprzedni stan (stun wygasł)
        
    DEAD (Martwy)
    ─────────────────────────────────────────────────────────────
    Jednostka nie żyje.
    Stan końcowy - brak wyjścia.
    
    Wejście: HP <= 0
    Wyjście: (brak)

DIAGRAM TRANZYCJI:
═══════════════════════════════════════════════════════════════════

                    ┌─────────────────────┐
                    │       START         │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌──────────────────────┐
              ┌─────│        IDLE          │◄────────┐
              │     └──────────┬───────────┘         │
              │                │                     │
    cel w zasięgu     cel poza zasięgiem        cel zginął
              │                │                     │
              ▼                ▼                     │
    ┌─────────────────┐ ┌──────────────────┐        │
    │    ATTACKING    │ │      MOVING      │────────┤
    └────────┬────────┘ └──────────────────┘        │
             │                  ▲                    │
    pełna mana                  │ cel uciekł        │
             │                  │                    │
             ▼                  │                    │
    ┌─────────────────┐         │                    │
    │    CASTING      │─────────┴────────────────────┘
    └─────────────────┘  (po rzuceniu skilla)
    
    
    STUNNED i DEAD mogą nastąpić z każdego stanu:
    
    * ────stun────► STUNNED ───wygaśnięcie───► poprzedni stan
    * ────HP=0────► DEAD (koniec)
"""

from __future__ import annotations
from enum import Enum, auto
from typing import Optional


class UnitState(Enum):
    """
    Enum stanów jednostki.
    
    Każdy stan reprezentuje co jednostka aktualnie robi.
    """
    
    IDLE = auto()       # Bezczynność - szuka celu
    MOVING = auto()     # Ruch w stronę celu
    ATTACKING = auto()  # Atakowanie celu
    CASTING = auto()    # Rzucanie umiejętności
    STUNNED = auto()    # Ogłuszony - nie może działać
    DEAD = auto()       # Martwy - stan końcowy
    
    def can_act(self) -> bool:
        """
        Sprawdza czy jednostka może wykonywać akcje w tym stanie.
        
        Returns:
            bool: True jeśli może działać
        """
        return self in (UnitState.IDLE, UnitState.MOVING, UnitState.ATTACKING)
    
    def can_be_targeted(self) -> bool:
        """
        Sprawdza czy jednostka może być celem ataku.
        
        Returns:
            bool: True jeśli może być atakowana
        """
        return self != UnitState.DEAD
    
    def is_terminal(self) -> bool:
        """
        Sprawdza czy to stan końcowy (bez wyjścia).
        
        Returns:
            bool: True jeśli DEAD
        """
        return self == UnitState.DEAD
    
    def __str__(self) -> str:
        return self.name


class UnitStateMachine:
    """
    Maszyna stanów dla jednostki z zaawansowanym systemem castowania.
    
    Zarządza tranzycjami między stanami i pamięta poprzedni stan
    (potrzebny do powrotu ze STUNNED).
    
    CASTING PHASES:
    ═══════════════════════════════════════════════════════════════════
    
        Cast Start (CASTING state begin)
        ─────────────────────────────────────────────────────────────
        • Jednostka przestaje atakować
        • Mana zostaje zresetowana do 0 (lub overflow jeśli enabled)
        • Mana Lock włączony
        
        Effect Point (effect_delay_remaining == 0)
        ─────────────────────────────────────────────────────────────
        • Ability faktycznie odpala (damage/heal)
        • Log ABILITY_EFFECT
        • effect_triggered = True
        
        Cast End (cast_remaining == 0)
        ─────────────────────────────────────────────────────────────
        • Animacja kończy się
        • Powrót do IDLE lub ATTACKING
        • Mana Lock kończy się (lub trwa dalej jeśli configured)
    
    Attributes:
        current (UnitState): Aktualny stan
        previous (Optional[UnitState]): Poprzedni stan (dla stun)
        stun_remaining (int): Pozostałe ticki stuna
        cast_remaining (int): Pozostałe ticki casta (do końca animacji)
        effect_delay_remaining (int): Ticki do effect point (ability fires)
        effect_triggered (bool): Czy efekt już wystąpił w tym caście
        mana_locked (bool): Czy mana jest zablokowana
        mana_lock_remaining (int): Pozostałe ticki mana lock
        
    Example:
        >>> fsm = UnitStateMachine()
        >>> fsm.current
        UnitState.IDLE
        >>> fsm.start_cast(cast_time=15, effect_delay=8)
        >>> fsm.is_mana_locked()
        True
    """
    
    def __init__(self, initial: UnitState = UnitState.IDLE):
        """
        Tworzy maszynę stanów.
        
        Args:
            initial: Stan początkowy (domyślnie IDLE)
        """
        self.current: UnitState = initial
        self.previous: Optional[UnitState] = None
        
        # Stun tracking
        self.stun_remaining: int = 0
        
        # Cast tracking (enhanced)
        self.cast_remaining: int = 0
        self.effect_delay_remaining: int = 0
        self.effect_triggered: bool = False
        
        # Mana lock tracking
        self.mana_locked: bool = False
        self.mana_lock_remaining: int = 0
    
    def transition_to(self, new_state: UnitState) -> bool:
        """
        Przechodzi do nowego stanu.
        
        Args:
            new_state: Docelowy stan
            
        Returns:
            bool: True jeśli tranzycja dozwolona
            
        Note:
            - Nie można wyjść ze stanu DEAD
            - Zapamiętuje poprzedni stan dla STUNNED
        """
        # Ze stanu DEAD nie ma powrotu
        if self.current == UnitState.DEAD:
            return False
        
        # Zapamiętaj poprzedni stan (dla powrotu ze stun)
        if new_state == UnitState.STUNNED:
            self.previous = self.current
        
        self.current = new_state
        return True
    
    def apply_stun(self, duration_ticks: int) -> None:
        """
        Nakłada stun na jednostkę.
        
        Args:
            duration_ticks: Czas trwania w tickach
            
        Note:
            Stun przerywa casting ale NIE resetuje mana lock
            (jednostka nie zyskuje many podczas stuna).
        """
        if self.current == UnitState.DEAD:
            return
        
        # Jeśli był w casting, przerwij ale zachowaj mana lock
        if self.current == UnitState.CASTING:
            self.cast_remaining = 0
            self.effect_delay_remaining = 0
            self.effect_triggered = False
        
        self.stun_remaining = duration_ticks
        self.transition_to(UnitState.STUNNED)
    
    def start_cast(
        self, 
        cast_time_ticks: int, 
        effect_delay_ticks: int = 0,
        mana_lock_duration: Optional[int] = None,
    ) -> None:
        """
        Rozpoczyna castowanie umiejętności.
        
        Args:
            cast_time_ticks: Całkowity czas casta (do końca animacji)
            effect_delay_ticks: Opóźnienie efektu od startu
                (0 = instant, >0 = delayed effect)
            mana_lock_duration: Czas blokady many po caście
                (None = tylko podczas casta, int = dodatkowe ticki po)
                
        Note:
            effect_delay_ticks musi być <= cast_time_ticks
            
        Example:
            # Instant cast (efekt natychmiast, animacja 0.5s)
            >>> fsm.start_cast(15, effect_delay=0)
            
            # Delayed effect (efekt po 0.27s, animacja 0.5s)
            >>> fsm.start_cast(15, effect_delay=8)
        """
        if self.current == UnitState.DEAD:
            return
        
        # Ustaw timery casta
        self.cast_remaining = cast_time_ticks
        self.effect_delay_remaining = min(effect_delay_ticks, cast_time_ticks)
        self.effect_triggered = False
        
        # Ustaw mana lock
        self.mana_locked = True
        if mana_lock_duration is not None:
            self.mana_lock_remaining = cast_time_ticks + mana_lock_duration
        else:
            self.mana_lock_remaining = cast_time_ticks  # lock tylko podczas casta
        
        self.transition_to(UnitState.CASTING)
    
    def tick(self) -> Optional[UnitState]:
        """
        Aktualizuje maszynę stanów (wywoływane co tick).
        
        Returns:
            Optional[UnitState]: Nowy stan jeśli nastąpiła tranzycja
        """
        # Mana lock countdown (niezależne od stanu)
        if self.mana_lock_remaining > 0:
            self.mana_lock_remaining -= 1
            if self.mana_lock_remaining <= 0:
                self.mana_locked = False
        
        # Stun countdown
        if self.current == UnitState.STUNNED:
            self.stun_remaining -= 1
            if self.stun_remaining <= 0:
                # Powrót do poprzedniego stanu
                old = self.previous or UnitState.IDLE
                self.current = old
                self.previous = None
                return self.current
        
        # Cast countdown
        if self.current == UnitState.CASTING:
            # Effect delay countdown
            if self.effect_delay_remaining > 0:
                self.effect_delay_remaining -= 1
            
            # Cast time countdown
            self.cast_remaining -= 1
            if self.cast_remaining <= 0:
                # Skill rzucony - wróć do IDLE
                self.current = UnitState.IDLE
                self.effect_triggered = False
                return self.current
        
        return None
    
    def should_trigger_effect(self) -> bool:
        """
        Sprawdza czy efekt powinien zostać odpalony w tym ticku.
        
        Returns:
            bool: True jeśli effect point osiągnięty
            
        Note:
            Zwraca True tylko RAZ per cast.
            Wywołaj mark_effect_triggered() po obsłudze.
        """
        return (
            self.current == UnitState.CASTING 
            and self.effect_delay_remaining <= 0 
            and not self.effect_triggered
        )
    
    def mark_effect_triggered(self) -> None:
        """Oznacza efekt jako odpalony."""
        self.effect_triggered = True
    
    def is_mana_locked(self) -> bool:
        """
        Sprawdza czy mana jest zablokowana.
        
        Returns:
            bool: True jeśli nie można zyskać many
        """
        return self.mana_locked
    
    def get_cast_progress(self, total_cast_time: int) -> float:
        """
        Zwraca progres casta (0.0 - 1.0).
        
        Args:
            total_cast_time: Oryginalny czas casta
            
        Returns:
            float: Progres (1.0 = zakończony)
        """
        if total_cast_time <= 0:
            return 1.0
        elapsed = total_cast_time - self.cast_remaining
        return min(1.0, max(0.0, elapsed / total_cast_time))
    
    def die(self) -> None:
        """Ustawia stan na DEAD."""
        self.current = UnitState.DEAD
        self.previous = None
        self.stun_remaining = 0
        self.cast_remaining = 0
        self.effect_delay_remaining = 0
        self.effect_triggered = False
        self.mana_locked = False
        self.mana_lock_remaining = 0
    
    def reset(self) -> None:
        """Resetuje maszynę do stanu początkowego."""
        self.current = UnitState.IDLE
        self.previous = None
        self.stun_remaining = 0
        self.cast_remaining = 0
        self.effect_delay_remaining = 0
        self.effect_triggered = False
        self.mana_locked = False
        self.mana_lock_remaining = 0
    
    def can_act(self) -> bool:
        """Sprawdza czy jednostka może działać."""
        return self.current.can_act()
    
    def is_alive(self) -> bool:
        """Sprawdza czy jednostka żyje."""
        return self.current != UnitState.DEAD
    
    def is_casting(self) -> bool:
        """Sprawdza czy jednostka castuje."""
        return self.current == UnitState.CASTING
    
    def __repr__(self) -> str:
        extra = ""
        if self.current == UnitState.STUNNED:
            extra = f", stun={self.stun_remaining}"
        elif self.current == UnitState.CASTING:
            effect_status = "triggered" if self.effect_triggered else f"in {self.effect_delay_remaining}"
            extra = f", cast={self.cast_remaining}, effect={effect_status}"
        if self.mana_locked:
            extra += ", mana_locked"
        return f"UnitStateMachine({self.current.name}{extra})"

