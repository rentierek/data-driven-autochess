"""
System współrzędnych hexagonalnych (Axial Coordinates).

Używamy Axial Coordinates (q, r) gdzie:
- q = kolumna (oś pozioma)
- r = wiersz (oś ukośna)

Konwersja do Cube Coordinates:
    s = -q - r
    Cube: (q, r, s) gdzie q + r + s = 0

Układ sąsiadów (pointy-top hexagons, zgodnie z zegarem od E):
    Kierunek   (dq, dr)
    ─────────────────────
    E  (→)     (+1,  0)
    SE (↘)     ( 0, +1)
    SW (↙)     (-1, +1)
    W  (←)     (-1,  0)
    NW (↖)     ( 0, -1)
    NE (↗)     (+1, -1)

Odległość między hexami:
    distance = (|q1-q2| + |r1-r2| + |s1-s2|) / 2
    
    Gdzie s = -q - r, więc:
    distance = (|dq| + |dr| + |dq + dr|) / 2
    
    Lub prościej (equivalent):
    distance = max(|dq|, |dr|, |dq + dr|)

Przykład użycia:
    >>> a = HexCoord(0, 0)
    >>> b = HexCoord(2, 1)
    >>> a.distance(b)
    3
    >>> a.neighbors()
    [HexCoord(1, 0), HexCoord(0, 1), HexCoord(-1, 1), 
     HexCoord(-1, 0), HexCoord(0, -1), HexCoord(1, -1)]
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Iterator


# Kierunki sąsiadów w układzie axial (pointy-top)
# Kolejność: E, SE, SW, W, NW, NE
HEX_DIRECTIONS: List[Tuple[int, int]] = [
    (+1, 0),   # E
    (0, +1),   # SE
    (-1, +1),  # SW
    (-1, 0),   # W
    (0, -1),   # NW
    (+1, -1),  # NE
]


@dataclass(frozen=True)
class HexCoord:
    """
    Współrzędna hexagonalna w systemie axial (q, r).
    
    Klasa jest niemutowalna (frozen=True) i zoptymalizowana (slots=True).
    Może być używana jako klucz w słowniku lub element zbioru.
    
    Attributes:
        q (int): Współrzędna kolumny (oś pozioma)
        r (int): Współrzędna wiersza (oś ukośna)
        
    Note:
        Współrzędna s w systemie cube jest wyliczana jako: s = -q - r
        Zachodzi zawsze: q + r + s = 0
    """
    q: int
    r: int
    
    # ─────────────────────────────────────────────────────────────────────────
    # WŁAŚCIWOŚCI
    # ─────────────────────────────────────────────────────────────────────────
    
    @property
    def s(self) -> int:
        """
        Trzecia współrzędna w systemie cube.
        
        Returns:
            int: Wartość s spełniająca q + r + s = 0
        """
        return -self.q - self.r
    
    @property
    def cube(self) -> Tuple[int, int, int]:
        """
        Konwersja do współrzędnych cube (q, r, s).
        
        Returns:
            Tuple[int, int, int]: Krotka (q, r, s)
        """
        return (self.q, self.r, self.s)
    
    @property
    def axial(self) -> Tuple[int, int]:
        """
        Współrzędne axial jako krotka.
        
        Returns:
            Tuple[int, int]: Krotka (q, r)
        """
        return (self.q, self.r)
    
    # ─────────────────────────────────────────────────────────────────────────
    # ODLEGŁOŚĆ
    # ─────────────────────────────────────────────────────────────────────────
    
    def distance(self, other: HexCoord) -> int:
        """
        Oblicza odległość Manhattan między dwoma hexami.
        
        Wzór (cube distance):
            distance = (|dq| + |dr| + |ds|) / 2
            
        Lub equivalentnie:
            distance = max(|dq|, |dr|, |ds|)
        
        Args:
            other: Druga współrzędna hexagonalna
            
        Returns:
            int: Odległość w liczbie kroków (hexów)
            
        Example:
            >>> HexCoord(0, 0).distance(HexCoord(2, 1))
            3
        """
        dq = abs(self.q - other.q)
        dr = abs(self.r - other.r)
        ds = abs(self.s - other.s)
        return (dq + dr + ds) // 2
    
    # ─────────────────────────────────────────────────────────────────────────
    # SĄSIEDZI
    # ─────────────────────────────────────────────────────────────────────────
    
    def neighbors(self) -> List[HexCoord]:
        """
        Zwraca listę 6 sąsiednich hexów.
        
        Kolejność sąsiadów (zgodnie z zegarem od E):
            E, SE, SW, W, NW, NE
        
        Returns:
            List[HexCoord]: Lista 6 sąsiadów
            
        Example:
            >>> HexCoord(0, 0).neighbors()
            [HexCoord(q=1, r=0), HexCoord(q=0, r=1), ...]
        """
        return [
            HexCoord(self.q + dq, self.r + dr)
            for dq, dr in HEX_DIRECTIONS
        ]
    
    def neighbor(self, direction: int) -> HexCoord:
        """
        Zwraca sąsiada w określonym kierunku.
        
        Args:
            direction: Indeks kierunku (0-5)
                0 = E, 1 = SE, 2 = SW, 3 = W, 4 = NW, 5 = NE
                
        Returns:
            HexCoord: Sąsiad w podanym kierunku
            
        Raises:
            IndexError: Jeśli direction nie jest w zakresie 0-5
        """
        dq, dr = HEX_DIRECTIONS[direction]
        return HexCoord(self.q + dq, self.r + dr)
    
    # ─────────────────────────────────────────────────────────────────────────
    # LINIA DO CELU
    # ─────────────────────────────────────────────────────────────────────────
    
    def line_to(self, other: HexCoord) -> List[HexCoord]:
        """
        Zwraca listę hexów tworzących linię prostą do celu.
        
        Używa interpolacji liniowej w przestrzeni cube z zaokrąglaniem.
        
        Args:
            other: Cel linii
            
        Returns:
            List[HexCoord]: Lista hexów od self do other (włącznie)
            
        Example:
            >>> HexCoord(0, 0).line_to(HexCoord(3, 0))
            [HexCoord(0, 0), HexCoord(1, 0), HexCoord(2, 0), HexCoord(3, 0)]
        """
        n = self.distance(other)
        if n == 0:
            return [self]
        
        results: List[HexCoord] = []
        for i in range(n + 1):
            t = i / n
            # Interpolacja liniowa w cube coordinates
            q = self.q + (other.q - self.q) * t
            r = self.r + (other.r - self.r) * t
            s = self.s + (other.s - self.s) * t
            # Zaokrąglenie do najbliższego hexa
            results.append(_cube_round(q, r, s))
        
        return results
    
    # ─────────────────────────────────────────────────────────────────────────
    # RING I SPIRAL
    # ─────────────────────────────────────────────────────────────────────────
    
    def ring(self, radius: int) -> List[HexCoord]:
        """
        Zwraca wszystkie hexy w pierścieniu o danym promieniu.
        
        Pierścień to hexy dokładnie w odległości `radius` od centrum.
        
        Args:
            radius: Promień pierścienia (>= 0)
            
        Returns:
            List[HexCoord]: Hexy tworzące pierścień
            
        Note:
            - radius=0 zwraca [self]
            - radius=1 zwraca 6 sąsiadów
            - radius=n zwraca 6*n hexów (dla n > 0)
        """
        if radius == 0:
            return [self]
        
        results: List[HexCoord] = []
        # Start od kierunku 4 (NW) * radius
        current = HexCoord(
            self.q + HEX_DIRECTIONS[4][0] * radius,
            self.r + HEX_DIRECTIONS[4][1] * radius
        )
        
        for direction in range(6):
            for _ in range(radius):
                results.append(current)
                current = current.neighbor(direction)
        
        return results
    
    def spiral(self, radius: int) -> Iterator[HexCoord]:
        """
        Generator hexów w spirali od centrum do promienia.
        
        Yields hexy warstwami: centrum, potem ring(1), ring(2), ...
        
        Args:
            radius: Maksymalny promień spirali
            
        Yields:
            HexCoord: Kolejne hexy w spirali
        """
        for r in range(radius + 1):
            for hex_coord in self.ring(r):
                yield hex_coord
    
    # ─────────────────────────────────────────────────────────────────────────
    # OPERATORY ARYTMETYCZNE
    # ─────────────────────────────────────────────────────────────────────────
    
    def __add__(self, other: HexCoord) -> HexCoord:
        """Dodawanie współrzędnych."""
        return HexCoord(self.q + other.q, self.r + other.r)
    
    def __sub__(self, other: HexCoord) -> HexCoord:
        """Odejmowanie współrzędnych."""
        return HexCoord(self.q - other.q, self.r - other.r)
    
    def __mul__(self, scalar: int) -> HexCoord:
        """Mnożenie przez skalar."""
        return HexCoord(self.q * scalar, self.r * scalar)
    
    def __neg__(self) -> HexCoord:
        """Negacja (punkt przeciwny względem origin)."""
        return HexCoord(-self.q, -self.r)
    
    # ─────────────────────────────────────────────────────────────────────────
    # REPREZENTACJA
    # ─────────────────────────────────────────────────────────────────────────
    
    def __repr__(self) -> str:
        return f"HexCoord(q={self.q}, r={self.r})"
    
    def __str__(self) -> str:
        return f"({self.q}, {self.r})"


# ─────────────────────────────────────────────────────────────────────────────
# FUNKCJE POMOCNICZE
# ─────────────────────────────────────────────────────────────────────────────

def _cube_round(q: float, r: float, s: float) -> HexCoord:
    """
    Zaokrągla współrzędne cube do najbliższego hexa.
    
    Algorytm:
    1. Zaokrąglij każdą współrzędną do najbliższej int
    2. Znajdź współrzędną z największym błędem zaokrąglenia
    3. Skoryguj ją tak, żeby q + r + s = 0
    
    Args:
        q, r, s: Współrzędne cube (float)
        
    Returns:
        HexCoord: Najbliższy hex
    """
    rq = round(q)
    rr = round(r)
    rs = round(s)
    
    dq = abs(rq - q)
    dr = abs(rr - r)
    ds = abs(rs - s)
    
    # Koryguj współrzędną z największym błędem
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    # else: rs = -rq - rr (nie używamy s w axial)
    
    return HexCoord(int(rq), int(rr))


def hex_from_cube(q: int, r: int, s: int) -> HexCoord:
    """
    Tworzy HexCoord z współrzędnych cube.
    
    Args:
        q, r, s: Współrzędne cube (muszą spełniać q + r + s = 0)
        
    Returns:
        HexCoord: Współrzędna axial
        
    Raises:
        ValueError: Jeśli q + r + s != 0
    """
    if q + r + s != 0:
        raise ValueError(f"Invalid cube coordinates: {q} + {r} + {s} != 0")
    return HexCoord(q, r)
