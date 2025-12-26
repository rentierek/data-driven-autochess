"""
Siatka hexagonalna (HexGrid) z obsługą zajętości pól.

HexGrid zarządza przestrzenią gry:
- Określa wymiary siatki (width x height)
- Śledzi które pola są zajęte przez jednostki
- Waliduje czy pozycje są w granicach

Układ siatki:
    Używamy układu "odd-r" (offset coordinates) do mapowania 
    na regularną siatkę width x height:
    
    r=0:  (0,0) (1,0) (2,0) (3,0) ...
    r=1:   (0,1) (1,1) (2,1) (3,1) ...  <- przesunięte o 0.5 wizualnie
    r=2:  (0,2) (1,2) (2,2) (3,2) ...
    
    Gdzie (x, y) to współrzędne offset, a (q, r) to axial.
    
Konwersja offset <-> axial:
    axial.q = offset.x - (offset.y // 2)  # dla odd-r
    axial.r = offset.y
    
    offset.x = axial.q + (axial.r // 2)
    offset.y = axial.r

Przykład użycia:
    >>> grid = HexGrid(width=7, height=8)
    >>> grid.is_valid(HexCoord(0, 0))
    True
    >>> grid.is_valid(HexCoord(10, 10))
    False
    >>> grid.place_unit(unit, HexCoord(2, 3))
    >>> grid.is_occupied(HexCoord(2, 3))
    True
"""

from __future__ import annotations
from typing import Dict, Optional, List, Set, TYPE_CHECKING
from dataclasses import dataclass, field

from .hex_coord import HexCoord

if TYPE_CHECKING:
    from ..units.unit import Unit


@dataclass
class HexGrid:
    """
    Siatka hexagonalna z obsługą kolizji i zajętości.
    
    Attributes:
        width (int): Szerokość siatki w hexach
        height (int): Wysokość siatki w hexach
        _occupancy (Dict[HexCoord, Unit]): Mapa pozycja -> jednostka
        _unit_positions (Dict[str, HexCoord]): Mapa unit_id -> pozycja
        
    Note:
        - Pozycje są w układzie axial (q, r)
        - Grid waliduje granice używając konwersji do offset
        - Jednostki są identyfikowane przez ich `id` atrybut
    """
    width: int
    height: int
    _occupancy: Dict[HexCoord, "Unit"] = field(default_factory=dict, repr=False)
    _unit_positions: Dict[str, HexCoord] = field(default_factory=dict, repr=False)
    
    # ─────────────────────────────────────────────────────────────────────────
    # WALIDACJA POZYCJI
    # ─────────────────────────────────────────────────────────────────────────
    
    def is_valid(self, pos: HexCoord) -> bool:
        """
        Sprawdza czy pozycja jest w granicach siatki.
        
        Konwertuje axial na offset i sprawdza granice.
        
        Args:
            pos: Pozycja do sprawdzenia (axial)
            
        Returns:
            bool: True jeśli pozycja jest w granicach
            
        Example:
            >>> grid = HexGrid(7, 8)
            >>> grid.is_valid(HexCoord(0, 0))
            True
            >>> grid.is_valid(HexCoord(-1, 0))
            False
        """
        offset_x, offset_y = self._axial_to_offset(pos)
        return 0 <= offset_x < self.width and 0 <= offset_y < self.height
    
    def is_occupied(self, pos: HexCoord) -> bool:
        """
        Sprawdza czy pole jest zajęte przez jednostkę.
        
        Args:
            pos: Pozycja do sprawdzenia
            
        Returns:
            bool: True jeśli pole jest zajęte
        """
        return pos in self._occupancy
    
    def is_walkable(self, pos: HexCoord) -> bool:
        """
        Sprawdza czy na pole można wejść.
        
        Pole jest walkable jeśli:
        - Jest w granicach siatki
        - Nie jest zajęte
        
        Args:
            pos: Pozycja do sprawdzenia
            
        Returns:
            bool: True jeśli można wejść na pole
        """
        return self.is_valid(pos) and not self.is_occupied(pos)
    
    # ─────────────────────────────────────────────────────────────────────────
    # ZARZĄDZANIE JEDNOSTKAMI
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_unit_at(self, pos: HexCoord) -> Optional["Unit"]:
        """
        Zwraca jednostkę na danej pozycji.
        
        Args:
            pos: Pozycja do sprawdzenia
            
        Returns:
            Optional[Unit]: Jednostka lub None jeśli pole puste
        """
        return self._occupancy.get(pos)
    
    def get_unit_position(self, unit_id: str) -> Optional[HexCoord]:
        """
        Zwraca pozycję jednostki o danym ID.
        
        Args:
            unit_id: Identyfikator jednostki
            
        Returns:
            Optional[HexCoord]: Pozycja lub None jeśli nie znaleziono
        """
        return self._unit_positions.get(unit_id)
    
    def place_unit(self, unit: "Unit", pos: HexCoord) -> bool:
        """
        Umieszcza jednostkę na siatce.
        
        Args:
            unit: Jednostka do umieszczenia
            pos: Docelowa pozycja
            
        Returns:
            bool: True jeśli udało się umieścić
            
        Raises:
            ValueError: Jeśli pozycja jest poza siatką
            
        Note:
            Jeśli pole jest zajęte, zwraca False.
            Jeśli jednostka już jest na siatce, najpierw ją usuwa.
        """
        if not self.is_valid(pos):
            raise ValueError(f"Position {pos} is outside grid bounds")
        
        if self.is_occupied(pos):
            return False
        
        # Usuń jednostkę z poprzedniej pozycji jeśli istnieje
        if unit.id in self._unit_positions:
            old_pos = self._unit_positions[unit.id]
            del self._occupancy[old_pos]
        
        # Umieść na nowej pozycji
        self._occupancy[pos] = unit
        self._unit_positions[unit.id] = pos
        
        return True
    
    def move_unit(self, unit: "Unit", new_pos: HexCoord) -> bool:
        """
        Przesuwa jednostkę na nową pozycję.
        
        Args:
            unit: Jednostka do przesunięcia
            new_pos: Nowa pozycja
            
        Returns:
            bool: True jeśli ruch się powiódł
            
        Note:
            Zwraca False jeśli:
            - Nowa pozycja jest poza siatką
            - Nowa pozycja jest zajęta
            - Jednostka nie jest na siatce
        """
        if unit.id not in self._unit_positions:
            return False
        
        if not self.is_walkable(new_pos):
            return False
        
        old_pos = self._unit_positions[unit.id]
        del self._occupancy[old_pos]
        
        self._occupancy[new_pos] = unit
        self._unit_positions[unit.id] = new_pos
        
        return True
    
    def remove_unit(self, unit: "Unit") -> bool:
        """
        Usuwa jednostkę z siatki.
        
        Args:
            unit: Jednostka do usunięcia
            
        Returns:
            bool: True jeśli jednostka była na siatce i została usunięta
        """
        if unit.id not in self._unit_positions:
            return False
        
        pos = self._unit_positions[unit.id]
        del self._occupancy[pos]
        del self._unit_positions[unit.id]
        
        return True
    
    # ─────────────────────────────────────────────────────────────────────────
    # ZAPYTANIA
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_all_units(self) -> List["Unit"]:
        """
        Zwraca listę wszystkich jednostek na siatce.
        
        Returns:
            List[Unit]: Lista jednostek
        """
        return list(self._occupancy.values())
    
    def get_walkable_neighbors(
        self, 
        pos: HexCoord, 
        ignore_units: Optional[Set[str]] = None
    ) -> List[HexCoord]:
        """
        Zwraca listę sąsiednich pól, na które można wejść.
        
        Args:
            pos: Pozycja bazowa
            ignore_units: Opcjonalny set unit_id do ignorowania przy sprawdzaniu zajętości
            
        Returns:
            List[HexCoord]: Lista dostępnych sąsiadów
        """
        ignore = ignore_units or set()
        result = []
        
        for neighbor in pos.neighbors():
            if not self.is_valid(neighbor):
                continue
            
            unit = self._occupancy.get(neighbor)
            if unit is None or unit.id in ignore:
                result.append(neighbor)
        
        return result
    
    def get_all_valid_positions(self) -> List[HexCoord]:
        """
        Zwraca wszystkie prawidłowe pozycje na siatce.
        
        Returns:
            List[HexCoord]: Lista wszystkich hexów w siatce
        """
        positions = []
        for y in range(self.height):
            for x in range(self.width):
                pos = self._offset_to_axial(x, y)
                positions.append(pos)
        return positions
    
    def get_empty_positions(self) -> List[HexCoord]:
        """
        Zwraca wszystkie puste pozycje na siatce.
        
        Returns:
            List[HexCoord]: Lista pustych hexów
        """
        return [pos for pos in self.get_all_valid_positions() 
                if pos not in self._occupancy]
    
    # ─────────────────────────────────────────────────────────────────────────
    # KONWERSJA WSPÓŁRZĘDNYCH
    # ─────────────────────────────────────────────────────────────────────────
    
    @staticmethod
    def _axial_to_offset(pos: HexCoord) -> tuple[int, int]:
        """
        Konwertuje axial (q, r) na offset (x, y) - układ odd-r.
        
        Wzór:
            x = q + (r // 2)
            y = r
            
        Args:
            pos: Współrzędne axial
            
        Returns:
            Tuple[int, int]: Współrzędne offset (x, y)
        """
        x = pos.q + (pos.r // 2)
        y = pos.r
        return (x, y)
    
    @staticmethod
    def _offset_to_axial(x: int, y: int) -> HexCoord:
        """
        Konwertuje offset (x, y) na axial (q, r) - układ odd-r.
        
        Wzór:
            q = x - (y // 2)
            r = y
            
        Args:
            x, y: Współrzędne offset
            
        Returns:
            HexCoord: Współrzędne axial
        """
        q = x - (y // 2)
        r = y
        return HexCoord(q, r)
    
    # ─────────────────────────────────────────────────────────────────────────
    # DEBUG / VISUALIZACJA
    # ─────────────────────────────────────────────────────────────────────────
    
    def debug_print(self) -> str:
        """
        Zwraca tekstową reprezentację siatki do debugowania.
        
        Legenda:
            . = puste pole
            X = zajęte pole
            
        Returns:
            str: Tekstowa wizualizacja siatki
        """
        lines = []
        for y in range(self.height):
            indent = " " if y % 2 == 1 else ""
            row = []
            for x in range(self.width):
                pos = self._offset_to_axial(x, y)
                if pos in self._occupancy:
                    row.append("X")
                else:
                    row.append(".")
            lines.append(indent + " ".join(row))
        return "\n".join(lines)
