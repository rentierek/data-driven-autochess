"""
Effects module - system buffów, debuffów i umiejętności.

Zawiera:
- Buff: Klasa buffa/debuffa z modyfikatorami statystyk
- (TODO) Ability: System umiejętności
"""

from .buff import Buff, StatModifier, StackBehavior

__all__ = ["Buff", "StatModifier", "StackBehavior"]
