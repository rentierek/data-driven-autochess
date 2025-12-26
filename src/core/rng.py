"""
Deterministyczny generator liczb losowych (RNG).

W symulacji TFT potrzebujemy determinizmu - ten sam seed
musi zawsze dawać ten sam wynik walki. To pozwala na:
- Replay/odtwarzanie walk
- Debugowanie
- Testy jednostkowe

GameRNG opakowuje Pythonowy random.Random z dodatkowymi
metodami przydatnymi w grze.

Jak używać:
    - Każda symulacja powinna mieć WŁASNĄ instancję GameRNG
    - NIE używaj globalnego random - jest współdzielony
    - Seed podawany przy tworzeniu symulacji

Przykład użycia:
    >>> rng = GameRNG(seed=12345)
    >>> rng.random()  # zawsze to samo dla seed=12345
    0.41661987254534116
    >>> rng.roll_crit(0.25)  # 25% szansy na crit
    False
    >>> rng.randint(1, 6)  # rzut kostką
    3

Ważne:
    NIGDY nie używaj random.random() bezpośrednio w symulacji!
    Zawsze używaj instancji GameRNG przekazanej do symulacji.
"""

from __future__ import annotations
import random
from typing import List, TypeVar, Sequence, Optional

T = TypeVar('T')


class GameRNG:
    """
    Deterministyczny generator losowości dla symulacji.
    
    Opakowuje random.Random z konkretrym seedem.
    Używaj jednej instancji per symulacja.
    
    Attributes:
        seed (int): Ziarno użyte do inicjalizacji
        _rng (random.Random): Wewnętrzny generator
        
    Example:
        >>> rng1 = GameRNG(42)
        >>> rng2 = GameRNG(42)
        >>> rng1.random() == rng2.random()  # ten sam seed = te same wyniki
        True
    """
    
    def __init__(self, seed: int):
        """
        Tworzy nowy generator z podanym seedem.
        
        Args:
            seed: Ziarno losowości. Ten sam seed = te same wyniki.
        """
        self.seed = seed
        self._rng = random.Random(seed)
    
    # ─────────────────────────────────────────────────────────────────────────
    # PODSTAWOWE METODY
    # ─────────────────────────────────────────────────────────────────────────
    
    def random(self) -> float:
        """
        Zwraca losową liczbę z przedziału [0.0, 1.0).
        
        Returns:
            float: Liczba losowa
        """
        return self._rng.random()
    
    def randint(self, a: int, b: int) -> int:
        """
        Zwraca losową liczbę całkowitą z przedziału [a, b] (włącznie).
        
        Args:
            a: Dolna granica (włącznie)
            b: Górna granica (włącznie)
            
        Returns:
            int: Losowa liczba całkowita
        """
        return self._rng.randint(a, b)
    
    def uniform(self, a: float, b: float) -> float:
        """
        Zwraca losową liczbę z przedziału [a, b].
        
        Args:
            a: Dolna granica
            b: Górna granica
            
        Returns:
            float: Losowa liczba
        """
        return self._rng.uniform(a, b)
    
    def choice(self, seq: Sequence[T]) -> T:
        """
        Wybiera losowy element z sekwencji.
        
        Args:
            seq: Sekwencja do wyboru z
            
        Returns:
            T: Losowy element
            
        Raises:
            IndexError: Jeśli sekwencja jest pusta
        """
        return self._rng.choice(seq)
    
    def choices(self, seq: Sequence[T], k: int = 1) -> List[T]:
        """
        Wybiera k losowych elementów z sekwencji (z powtórzeniami).
        
        Args:
            seq: Sekwencja do wyboru z
            k: Ile elementów wybrać
            
        Returns:
            List[T]: Lista wybranych elementów
        """
        return self._rng.choices(seq, k=k)
    
    def sample(self, seq: Sequence[T], k: int) -> List[T]:
        """
        Wybiera k unikalnych losowych elementów z sekwencji.
        
        Args:
            seq: Sekwencja do wyboru z
            k: Ile elementów wybrać (k <= len(seq))
            
        Returns:
            List[T]: Lista unikalnych elementów
            
        Raises:
            ValueError: Jeśli k > len(seq)
        """
        return self._rng.sample(list(seq), k)
    
    def shuffle(self, seq: List[T]) -> None:
        """
        Tasuje listę w miejscu (modyfikuje oryginalną).
        
        Args:
            seq: Lista do przetasowania
        """
        self._rng.shuffle(seq)
    
    # ─────────────────────────────────────────────────────────────────────────
    # METODY SPECYFICZNE DLA GRY
    # ─────────────────────────────────────────────────────────────────────────
    
    def roll_chance(self, chance: float) -> bool:
        """
        Rzuca kością na szansę (0.0 - 1.0).
        
        Args:
            chance: Szansa na sukces (0.0 = 0%, 1.0 = 100%)
            
        Returns:
            bool: True jeśli sukces
            
        Example:
            >>> rng.roll_chance(0.25)  # 25% szansy
            True  # lub False
        """
        return self.random() < chance
    
    def roll_crit(self, crit_chance: float) -> bool:
        """
        Sprawdza czy atak jest krytyczny.
        
        Args:
            crit_chance: Szansa na crit (0.0 - 1.0)
            
        Returns:
            bool: True jeśli crit
            
        Note:
            To jest alias dla roll_chance(), ale nazwany
            bardziej intuicyjnie dla kontekstu walki.
        """
        return self.roll_chance(crit_chance)
    
    def roll_dodge(self, dodge_chance: float) -> bool:
        """
        Sprawdza czy atak został uniknięty.
        
        Args:
            dodge_chance: Szansa na unik (0.0 - 1.0)
            
        Returns:
            bool: True jeśli unik
        """
        return self.roll_chance(dodge_chance)
    
    def weighted_choice(
        self, 
        options: Sequence[T], 
        weights: Sequence[float]
    ) -> T:
        """
        Wybiera element z wagami.
        
        Args:
            options: Lista opcji
            weights: Lista wag (nie muszą sumować się do 1)
            
        Returns:
            T: Wybrany element
            
        Example:
            >>> rng.weighted_choice(['common', 'rare', 'epic'], [70, 25, 5])
            'common'  # najczęściej
        """
        return self._rng.choices(list(options), weights=list(weights), k=1)[0]
    
    def variance(self, base: float, percent: float) -> float:
        """
        Dodaje losową wariancję do wartości bazowej.
        
        Args:
            base: Wartość bazowa
            percent: Procent wariancji (np. 0.1 = ±10%)
            
        Returns:
            float: Wartość z wariancją
            
        Example:
            >>> rng.variance(100, 0.1)  # 100 ± 10%
            95.5  # coś między 90 a 110
        """
        multiplier = self.uniform(1 - percent, 1 + percent)
        return base * multiplier
    
    # ─────────────────────────────────────────────────────────────────────────
    # STAN
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_state(self) -> tuple:
        """
        Zwraca aktualny stan RNG (do zapisania/odtworzenia).
        
        Returns:
            tuple: Stan wewnętrzny generatora
        """
        return self._rng.getstate()
    
    def set_state(self, state: tuple) -> None:
        """
        Ustawia stan RNG (do odtworzenia z zapisanego stanu).
        
        Args:
            state: Stan z get_state()
        """
        self._rng.setstate(state)
    
    def fork(self) -> "GameRNG":
        """
        Tworzy nowy RNG z seedem bazowanym na aktualnym stanie.
        
        Przydatne gdy chcesz stworzyć pod-generator dla
        izolowanego systemu (np. loot drops), który nie
        wpływa na główną sekwencję losowości.
        
        Returns:
            GameRNG: Nowy generator
        """
        new_seed = self.randint(0, 2**31 - 1)
        return GameRNG(new_seed)
    
    def __repr__(self) -> str:
        return f"GameRNG(seed={self.seed})"
