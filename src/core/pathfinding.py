"""
Algorytm A* (A-star) dla siatki hexagonalnej.

A* znajduje najkrótszą ścieżkę między dwoma punktami,
uwzględniając przeszkody (zajęte pola).

Jak działa A*:
    1. Utrzymuj dwie listy: open (do sprawdzenia) i closed (sprawdzone)
    2. Dla każdego node'a oblicz:
       - g_cost: koszt od startu do tego node'a
       - h_cost: heurystyka (szacowany koszt do celu)
       - f_cost: g_cost + h_cost
    3. Zawsze eksploruj node z najniższym f_cost
    4. Gdy dotrzesz do celu, odtwórz ścieżkę
    
Heurystyka dla hex grid:
    Używamy odległości Manhattan na siatce hex (HexCoord.distance).
    Jest to heurystyka dopuszczalna (admissible) - nigdy nie przeszacowuje.

Koszt ruchu:
    Każdy ruch na sąsiedni hex kosztuje 1.
    W przyszłości można dodać różne koszty terenu.

Przykład użycia:
    >>> grid = HexGrid(7, 8)
    >>> grid.place_unit(obstacle_unit, HexCoord(1, 1))
    >>> path = find_path(grid, HexCoord(0, 0), HexCoord(2, 2))
    >>> path
    [HexCoord(0, 0), HexCoord(0, 1), HexCoord(0, 2), HexCoord(1, 2), HexCoord(2, 2)]
    
Edge cases:
    - Start == Goal: zwraca [start]
    - Brak ścieżki: zwraca pustą listę []
    - Start lub Goal poza siatką: zwraca []
"""

from __future__ import annotations
from typing import List, Optional, Dict, Set
from dataclasses import dataclass, field
import heapq

from .hex_coord import HexCoord
from .hex_grid import HexGrid


@dataclass(order=True)
class _PathNode:
    """
    Węzeł w algorytmie A*.
    
    Sortowanie jest po f_cost (suma g + h), co pozwala
    używać heapq jako priority queue.
    
    Attributes:
        f_cost: Całkowity szacowany koszt (g + h)
        g_cost: Koszt od startu
        position: Pozycja hexa (nie używana w sortowaniu)
        parent: Poprzedni węzeł na ścieżce
    """
    f_cost: float
    g_cost: float = field(compare=False)
    position: HexCoord = field(compare=False)
    parent: Optional["_PathNode"] = field(compare=False, default=None)


def find_path(
    grid: HexGrid,
    start: HexCoord,
    goal: HexCoord,
    ignore_units: Optional[Set[str]] = None,
    max_iterations: int = 1000
) -> List[HexCoord]:
    """
    Znajduje najkrótszą ścieżkę między dwoma hexami.
    
    Używa algorytmu A* z heurystyką hex distance.
    
    Args:
        grid: Siatka hexagonalna z informacją o zajętości
        start: Pozycja startowa
        goal: Pozycja docelowa
        ignore_units: Set unit_id do ignorowania (np. cel ataku)
        max_iterations: Maksymalna liczba iteracji (zabezpieczenie)
        
    Returns:
        List[HexCoord]: Ścieżka od start do goal (włącznie z oboma).
                        Pusta lista jeśli ścieżka nie istnieje.
    
    Algorithm:
        1. Waliduj start i goal
        2. Inicjalizuj open_set z nodem startowym
        3. Dopóki open_set nie jest pusty:
           a. Weź node z najniższym f_cost
           b. Jeśli to goal - odtwórz i zwróć ścieżkę
           c. Dla każdego walkable sąsiada:
              - Oblicz tentative_g (g_cost przez ten node)
              - Jeśli lepszy niż dotychczasowy - aktualizuj
        4. Jeśli open_set pusty - brak ścieżki
        
    Complexity:
        Time: O(n log n) gdzie n = liczba hexów do przeszukania
        Space: O(n) dla słowników g_costs i parents
        
    Example:
        >>> path = find_path(grid, HexCoord(0, 0), HexCoord(3, 3))
        >>> len(path)
        7  # start + 6 kroków
    """
    ignore = ignore_units or set()
    
    # Walidacja
    if not grid.is_valid(start) or not grid.is_valid(goal):
        return []
    
    # Przypadek trywialny
    if start == goal:
        return [start]
    
    # Sprawdź czy cel jest osiągalny (nie jest zajęty lub jest ignorowany)
    goal_unit = grid.get_unit_at(goal)
    if goal_unit is not None and goal_unit.id not in ignore:
        # Cel zajęty - znajdź ścieżkę do najbliższego sąsiada celu
        # To jest typowe zachowanie - podejdź do przeciwnika, nie wejdź na niego
        adjacent_goals = [
            n for n in goal.neighbors() 
            if grid.is_walkable(n) or (grid.get_unit_at(n) and grid.get_unit_at(n).id in ignore)
        ]
        if not adjacent_goals:
            return []
        # Znajdź najbliższego sąsiada do startu
        adjacent_goals.sort(key=lambda pos: start.distance(pos))
        goal = adjacent_goals[0]
        
        if start == goal:
            return [start]
    
    # Struktury A*
    open_set: List[_PathNode] = []
    g_costs: Dict[HexCoord, float] = {start: 0}
    closed_set: Set[HexCoord] = set()
    parents: Dict[HexCoord, HexCoord] = {}
    
    # Inicjalizacja
    start_h = start.distance(goal)
    start_node = _PathNode(f_cost=start_h, g_cost=0, position=start)
    heapq.heappush(open_set, start_node)
    
    iterations = 0
    
    while open_set and iterations < max_iterations:
        iterations += 1
        
        # Weź node z najniższym f_cost
        current = heapq.heappop(open_set)
        
        # Jeśli już przetworzony - pomiń
        if current.position in closed_set:
            continue
        
        # Oznacz jako przetworzony
        closed_set.add(current.position)
        
        # Cel osiągnięty?
        if current.position == goal:
            return _reconstruct_path(parents, start, goal)
        
        # Eksploruj sąsiadów
        for neighbor in grid.get_walkable_neighbors(current.position, ignore):
            if neighbor in closed_set:
                continue
            
            # Koszt ruchu = 1 (można zmodyfikować dla różnych terenów)
            tentative_g = current.g_cost + 1
            
            # Czy to lepsza ścieżka?
            if neighbor not in g_costs or tentative_g < g_costs[neighbor]:
                g_costs[neighbor] = tentative_g
                parents[neighbor] = current.position
                
                h_cost = neighbor.distance(goal)
                f_cost = tentative_g + h_cost
                
                new_node = _PathNode(
                    f_cost=f_cost,
                    g_cost=tentative_g,
                    position=neighbor
                )
                heapq.heappush(open_set, new_node)
    
    # Brak ścieżki
    return []


def _reconstruct_path(
    parents: Dict[HexCoord, HexCoord],
    start: HexCoord,
    goal: HexCoord
) -> List[HexCoord]:
    """
    Odtwarza ścieżkę od goal do start używając mapy rodziców.
    
    Args:
        parents: Słownik child -> parent
        start: Pozycja startowa
        goal: Pozycja końcowa
        
    Returns:
        List[HexCoord]: Ścieżka od start do goal
    """
    path = [goal]
    current = goal
    
    while current != start:
        current = parents[current]
        path.append(current)
    
    path.reverse()
    return path


def find_path_next_step(
    grid: HexGrid,
    start: HexCoord,
    goal: HexCoord,
    ignore_units: Optional[Set[str]] = None
) -> Optional[HexCoord]:
    """
    Znajduje tylko następny krok na ścieżce do celu.
    
    Przydatne gdy jednostka porusza się tick po ticku
    i nie potrzebujemy całej ścieżki.
    
    Args:
        grid: Siatka hexagonalna
        start: Aktualna pozycja
        goal: Cel
        ignore_units: Unit IDs do ignorowania
        
    Returns:
        Optional[HexCoord]: Następny hex lub None jeśli brak ścieżki/jesteśmy w celu
        
    Example:
        >>> next_pos = find_path_next_step(grid, unit.position, target.position)
        >>> if next_pos:
        ...     grid.move_unit(unit, next_pos)
    """
    path = find_path(grid, start, goal, ignore_units)
    
    if len(path) < 2:
        return None
    
    return path[1]


def get_hexes_in_range(
    center: HexCoord,
    range_: int,
    grid: Optional[HexGrid] = None
) -> List[HexCoord]:
    """
    Zwraca wszystkie hexy w określonym zasięgu od centrum.
    
    Args:
        center: Pozycja centralna
        range_: Zasięg (w krokach hex)
        grid: Opcjonalnie - filtruj tylko prawidłowe pozycje
        
    Returns:
        List[HexCoord]: Lista hexów w zasięgu
        
    Note:
        Zawiera centrum (odległość 0).
        Dla range_=1 zwraca 7 hexów (centrum + 6 sąsiadów).
    """
    result = []
    
    for dq in range(-range_, range_ + 1):
        for dr in range(max(-range_, -dq - range_), min(range_, -dq + range_) + 1):
            pos = HexCoord(center.q + dq, center.r + dr)
            
            if grid is None or grid.is_valid(pos):
                result.append(pos)
    
    return result
