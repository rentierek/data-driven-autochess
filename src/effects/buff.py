"""
System buffów i debuffów.

Buffy to tymczasowe modyfikacje statystyk jednostki.
Mogą być pozytywne (buffs) lub negatywne (debuffs).

STRUKTURA BUFFA:
═══════════════════════════════════════════════════════════════════

    Buff składa się z:
    - ID i nazwa
    - Czas trwania (w tickach)
    - Lista modyfikatorów statystyk
    - Zachowanie przy stackowaniu
    - Flaga is_debuff

MODYFIKATORY STATYSTYK:
═══════════════════════════════════════════════════════════════════

    StatModifier określa jak buff zmienia statystykę:
    
    {
        "stat": "attack_damage",
        "type": "flat" | "percent",
        "value": 10
    }
    
    flat: dodawane bezpośrednio
        AD + 20 -> base_attack_damage += 20
        
    percent: mnożnik procentowy
        +15% AS -> percent_attack_speed += 0.15

STACKOWANIE:
═══════════════════════════════════════════════════════════════════

    NONE (brak stackowania)
    ─────────────────────────────────────────────────────────────
    Nowy buff zastępuje stary.
    
    REFRESH (odświeżanie)
    ─────────────────────────────────────────────────────────────
    Nowy buff odświeża czas trwania starego.
    Wartości modyfikatorów się nie zmieniają.
    
    INTENSITY (intensywność)
    ─────────────────────────────────────────────────────────────
    Nowy buff dodaje stack.
    Każdy stack zwiększa efekt modyfikatorów.
    Czas trwania może być odświeżany lub niezależny.

CYKL ŻYCIA:
═══════════════════════════════════════════════════════════════════

    1. APPLY
       - Buff dodany do jednostki
       - Modyfikatory aplikowane do stats
       
    2. TICK
       - Zmniejszenie remaining_ticks
       - Jeśli remaining_ticks <= 0 -> EXPIRE
       
    3. EXPIRE
       - Modyfikatory usuwane z stats
       - Buff usuwany z listy
       - Opcjonalny on_expire effect

Przykład użycia:
    >>> buff = Buff.from_dict({
    ...     "id": "attack_speed_boost",
    ...     "name": "Attack Speed Boost",
    ...     "duration_ticks": 90,  # 3 sekundy
    ...     "modifiers": [
    ...         {"stat": "attack_speed", "type": "percent", "value": 0.3}
    ...     ]
    ... })
    >>> unit.add_buff(buff)
    >>> unit.stats.get_attack_speed()  # +30%
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Any, TYPE_CHECKING, Optional
import copy

if TYPE_CHECKING:
    from ..units.unit import Unit


class StackBehavior(Enum):
    """Zachowanie przy nakładaniu tego samego buffa."""
    
    NONE = auto()       # Zastąp stary nowym
    REFRESH = auto()    # Odśwież czas trwania
    INTENSITY = auto()  # Zwiększ stacking (mocniejszy efekt)


@dataclass
class StatModifier:
    """
    Pojedynczy modyfikator statystyki.
    
    Attributes:
        stat (str): Nazwa statystyki (bez prefiksu flat_/percent_)
        mod_type (str): "flat" lub "percent"
        value (float): Wartość modyfikatora
        
    Example:
        >>> mod = StatModifier("attack_damage", "flat", 20)
        >>> # Dodaje +20 do flat_attack_damage
    """
    stat: str
    mod_type: str  # "flat" lub "percent"
    value: float
    
    def apply_to(self, unit: "Unit") -> None:
        """
        Aplikuje modyfikator do jednostki.
        
        Args:
            unit: Jednostka do modyfikacji
        """
        if self.mod_type == "flat":
            unit.stats.add_flat_modifier(self.stat, self.value)
        elif self.mod_type == "percent":
            unit.stats.add_percent_modifier(self.stat, self.value)
    
    def remove_from(self, unit: "Unit") -> None:
        """
        Usuwa modyfikator z jednostki.
        
        Args:
            unit: Jednostka
        """
        if self.mod_type == "flat":
            unit.stats.remove_flat_modifier(self.stat, self.value)
        elif self.mod_type == "percent":
            unit.stats.remove_percent_modifier(self.stat, self.value)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializuje modyfikator."""
        return {
            "stat": self.stat,
            "type": self.mod_type,
            "value": self.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StatModifier":
        """Tworzy modyfikator ze słownika."""
        return cls(
            stat=data["stat"],
            mod_type=data["type"],
            value=float(data["value"]),
        )


@dataclass
class Buff:
    """
    Buff lub debuff nakładany na jednostkę.
    
    Attributes:
        id (str): Unikalny identyfikator typu buffa
        name (str): Nazwa wyświetlana
        duration_ticks (int): Całkowity czas trwania
        remaining_ticks (int): Pozostały czas
        modifiers (List[StatModifier]): Lista modyfikatorów
        stacks (int): Aktualna liczba stacków
        max_stacks (int): Maksymalna liczba stacków
        stack_behavior (StackBehavior): Jak się stackuje
        is_debuff (bool): Czy to debuff (negatywny)
        source_id (Optional[str]): ID jednostki która nałożyła
        
    Note:
        Buffy z tym samym `id` są traktowane jako ten sam typ.
    """
    id: str
    name: str
    duration_ticks: int
    remaining_ticks: int = field(default=0)
    modifiers: List[StatModifier] = field(default_factory=list)
    stacks: int = 1
    max_stacks: int = 1
    stack_behavior: StackBehavior = StackBehavior.REFRESH
    is_debuff: bool = False
    source_id: Optional[str] = None
    
    def __post_init__(self):
        """Inicjalizuje remaining_ticks jeśli nie podano."""
        if self.remaining_ticks == 0:
            self.remaining_ticks = self.duration_ticks
    
    # ─────────────────────────────────────────────────────────────────────────
    # FACTORY
    # ─────────────────────────────────────────────────────────────────────────
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Buff":
        """
        Tworzy buff ze słownika (np. z YAML).
        
        Args:
            data: Słownik z definicją buffa
            
        Returns:
            Buff: Nowa instancja
        """
        modifiers = [
            StatModifier.from_dict(m) 
            for m in data.get("modifiers", [])
        ]
        
        stack_behavior_str = data.get("stack_behavior", "REFRESH").upper()
        try:
            stack_behavior = StackBehavior[stack_behavior_str]
        except KeyError:
            stack_behavior = StackBehavior.REFRESH
        
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            duration_ticks=data.get("duration_ticks", 90),
            modifiers=modifiers,
            max_stacks=data.get("max_stacks", 1),
            stack_behavior=stack_behavior,
            is_debuff=data.get("is_debuff", False),
        )
    
    # ─────────────────────────────────────────────────────────────────────────
    # APLIKACJA / USUWANIE
    # ─────────────────────────────────────────────────────────────────────────
    
    def apply_to(self, unit: "Unit") -> None:
        """
        Aplikuje buff do jednostki.
        
        Dodaje wszystkie modyfikatory do statystyk.
        
        Args:
            unit: Jednostka
        """
        for modifier in self.modifiers:
            # Skaluj wartość przez liczbę stacków
            scaled_modifier = StatModifier(
                stat=modifier.stat,
                mod_type=modifier.mod_type,
                value=modifier.value * self.stacks,
            )
            scaled_modifier.apply_to(unit)
    
    def remove_from(self, unit: "Unit") -> None:
        """
        Usuwa buff z jednostki.
        
        Usuwa wszystkie modyfikatory ze statystyk.
        
        Args:
            unit: Jednostka
        """
        for modifier in self.modifiers:
            scaled_modifier = StatModifier(
                stat=modifier.stat,
                mod_type=modifier.mod_type,
                value=modifier.value * self.stacks,
            )
            scaled_modifier.remove_from(unit)
    
    # ─────────────────────────────────────────────────────────────────────────
    # STACKOWANIE
    # ─────────────────────────────────────────────────────────────────────────
    
    def refresh_or_stack(self, new_buff: "Buff") -> None:
        """
        Obsługuje nałożenie tego samego buffa.
        
        Zachowanie zależy od stack_behavior:
        - NONE: nic (stary buff pozostaje)
        - REFRESH: odśwież czas trwania
        - INTENSITY: dodaj stack (do max)
        
        Args:
            new_buff: Nowy buff tego samego typu
        """
        if self.stack_behavior == StackBehavior.NONE:
            return
        
        if self.stack_behavior == StackBehavior.REFRESH:
            self.remaining_ticks = self.duration_ticks
        
        elif self.stack_behavior == StackBehavior.INTENSITY:
            old_stacks = self.stacks
            self.stacks = min(self.stacks + 1, self.max_stacks)
            self.remaining_ticks = self.duration_ticks
            
            # Trzeba zaktualizować modyfikatory jeśli stacking się zmienił
            # To jest uproszczone - w praktyce trzeba by usunąć stare i dodać nowe
    
    def add_stack(self, unit: "Unit") -> bool:
        """
        Dodaje jeden stack.
        
        Args:
            unit: Jednostka (do aktualizacji modyfikatorów)
            
        Returns:
            bool: True jeśli stack został dodany
        """
        if self.stacks >= self.max_stacks:
            return False
        
        # Usuń stare modyfikatory
        self.remove_from(unit)
        
        # Zwiększ stacking
        self.stacks += 1
        
        # Aplikuj nowe modyfikatory
        self.apply_to(unit)
        
        return True
    
    # ─────────────────────────────────────────────────────────────────────────
    # TICK
    # ─────────────────────────────────────────────────────────────────────────
    
    def tick(self) -> None:
        """Aktualizuje czas trwania (wywoływane co tick)."""
        if self.remaining_ticks > 0:
            self.remaining_ticks -= 1
    
    def is_expired(self) -> bool:
        """Sprawdza czy buff wygasł."""
        return self.remaining_ticks <= 0
    
    def time_remaining_seconds(self, ticks_per_second: int = 30) -> float:
        """
        Zwraca pozostały czas w sekundach.
        
        Args:
            ticks_per_second: Ticki na sekundę
            
        Returns:
            float: Czas w sekundach
        """
        return self.remaining_ticks / ticks_per_second
    
    # ─────────────────────────────────────────────────────────────────────────
    # SERIALIZACJA
    # ─────────────────────────────────────────────────────────────────────────
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializuje buff do słownika."""
        return {
            "id": self.id,
            "name": self.name,
            "remaining_ticks": self.remaining_ticks,
            "duration_ticks": self.duration_ticks,
            "stacks": self.stacks,
            "max_stacks": self.max_stacks,
            "is_debuff": self.is_debuff,
            "modifiers": [m.to_dict() for m in self.modifiers],
        }
    
    def copy(self) -> "Buff":
        """Tworzy kopię buffa."""
        return Buff(
            id=self.id,
            name=self.name,
            duration_ticks=self.duration_ticks,
            remaining_ticks=self.duration_ticks,  # reset
            modifiers=[copy.copy(m) for m in self.modifiers],
            stacks=1,  # reset
            max_stacks=self.max_stacks,
            stack_behavior=self.stack_behavior,
            is_debuff=self.is_debuff,
            source_id=self.source_id,
        )
    
    def __repr__(self) -> str:
        stacks_str = f" x{self.stacks}" if self.stacks > 1 else ""
        return f"Buff({self.id}{stacks_str}, {self.remaining_ticks}t)"
