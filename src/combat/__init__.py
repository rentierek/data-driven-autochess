"""
Combat module - obliczanie obrażeń i logika walki.

Zawiera:
- DamageType: Typy obrażeń (PHYSICAL, MAGICAL, TRUE)
- DamageResult: Wynik ataku (ilość, crit, dodge)
- calculate_damage: Funkcja obliczająca finalne obrażenia
"""

from .damage import DamageType, DamageResult, calculate_damage, calculate_reduction

__all__ = ["DamageType", "DamageResult", "calculate_damage", "calculate_reduction"]
