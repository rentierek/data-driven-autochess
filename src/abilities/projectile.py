"""
System projektili dla umiejętności.

Projectiles to pociski które podróżują przez siatkę z określoną prędkością.
Mogą śledzić cel (homing) lub lecieć w kierunku punktu.

FUNKCJE:
═══════════════════════════════════════════════════════════════════

    - Travel time bazowane na speed (hexów per tick)
    - Homing: śledzi cel nawet jeśli się poruszy
    - Non-homing: leci do punktu, może pudłować
    - can_miss: jeśli true, pudłuje gdy cel zginie

YAML CONFIG:
═══════════════════════════════════════════════════════════════════

    projectile:
      speed: 3          # hexów per tick
      homing: true      # śledzi cel
      can_miss: true    # pudłuje jeśli cel zginie
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING, Callable
import math

if TYPE_CHECKING:
    from ..units.unit import Unit
    from ..core.hex_coord import HexCoord
    from .ability import Ability


@dataclass
class Projectile:
    """
    Pocisk w locie.
    
    Attributes:
        source: Jednostka która wystrzeliła
        target: Cel (Unit dla homing, None dla point-based)
        target_position: Docelowa pozycja (dla non-homing)
        ability: Ability która zostanie wykonana przy trafieniu
        star_level: Poziom gwiazdek castera
        
        position: Aktualna pozycja (float dla płynnego ruchu)
        speed: Prędkość w hexach per tick
        homing: Czy śledzi cel
        can_miss: Czy może pudłować
        
        active: Czy pocisk jest aktywny
    """
    # Source & Target
    source: "Unit"
    target: Optional["Unit"]
    target_position: Optional["HexCoord"]
    ability: "Ability"
    star_level: int
    
    # Movement
    position_q: float
    position_r: float
    speed: float = 2.0
    homing: bool = True
    can_miss: bool = True
    
    # State
    active: bool = True
    ticks_alive: int = 0
    max_ticks: int = 300  # 10s timeout
    
    def get_target_position(self) -> tuple:
        """Zwraca docelową pozycję (q, r)."""
        if self.homing and self.target and self.target.is_alive():
            return (self.target.position.q, self.target.position.r)
        elif self.target_position:
            return (self.target_position.q, self.target_position.r)
        elif self.target:
            # Target died, keep last known position
            return (self.target.position.q, self.target.position.r)
        return (self.position_q, self.position_r)
    
    def tick(self) -> bool:
        """
        Aktualizuje pozycję projektilu.
        
        Returns:
            bool: True jeśli projektil dotarł do celu
        """
        if not self.active:
            return False
        
        self.ticks_alive += 1
        
        # Timeout protection
        if self.ticks_alive > self.max_ticks:
            self.active = False
            return False
        
        # Check if target died (dla can_miss)
        if self.can_miss and self.target and not self.target.is_alive():
            self.active = False
            return False
        
        # Get target position
        target_q, target_r = self.get_target_position()
        
        # Calculate distance
        dq = target_q - self.position_q
        dr = target_r - self.position_r
        distance = math.sqrt(dq * dq + dr * dr)
        
        # Check if arrived
        if distance <= self.speed:
            self.position_q = target_q
            self.position_r = target_r
            return True
        
        # Move towards target
        if distance > 0:
            self.position_q += (dq / distance) * self.speed
            self.position_r += (dr / distance) * self.speed
        
        return False
    
    def has_valid_target(self) -> bool:
        """Sprawdza czy cel jest jeszcze ważny."""
        if not self.can_miss:
            return True
        if self.target is None:
            return self.target_position is not None
        return self.target.is_alive()
    
    def to_dict(self) -> dict:
        return {
            "source_id": self.source.id,
            "target_id": self.target.id if self.target else None,
            "ability": self.ability.id,
            "position": (round(self.position_q, 2), round(self.position_r, 2)),
            "speed": self.speed,
            "homing": self.homing,
            "ticks_alive": self.ticks_alive,
        }


@dataclass
class ProjectileManager:
    """
    Zarządza wszystkimi aktywnymi projektilami.
    """
    projectiles: List[Projectile] = field(default_factory=list)
    
    def spawn(
        self,
        source: "Unit",
        target: "Unit",
        ability: "Ability",
        star_level: int,
    ) -> Projectile:
        """
        Tworzy nowy projektil.
        """
        config = ability.projectile
        
        projectile = Projectile(
            source=source,
            target=target,
            target_position=target.position if target else None,
            ability=ability,
            star_level=star_level,
            position_q=float(source.position.q),
            position_r=float(source.position.r),
            speed=config.speed if config else 2.0,
            homing=config.homing if config else True,
            can_miss=config.can_miss if config else True,
        )
        
        self.projectiles.append(projectile)
        return projectile
    
    def tick(self) -> List[Projectile]:
        """
        Aktualizuje wszystkie projektile.
        
        Returns:
            List[Projectile]: Lista projektili które dotarły do celu
        """
        arrived = []
        still_active = []
        
        for proj in self.projectiles:
            if proj.tick():
                arrived.append(proj)
            elif proj.active:
                still_active.append(proj)
        
        self.projectiles = still_active
        return arrived
    
    def get_active_count(self) -> int:
        return len(self.projectiles)
    
    def clear(self) -> None:
        self.projectiles.clear()
