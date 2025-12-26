"""
Trait/Synergy System.

System traitów pozwala jednostkom dzielić synergie. 
Traity aktywują się przy progach (2/4/6) i mogą dawać bonusy.

Eksportuje:
    - Trait, TraitThreshold, TraitEffect, TraitTrigger
    - TriggerType, EffectTarget (enums)
    - TraitManager

Przykład użycia:
    >>> from src.traits import TraitManager, Trait
    >>> 
    >>> manager = TraitManager(simulation)
    >>> manager.load_traits(traits_data)
    >>> manager.on_battle_start()
"""

from .trait import (
    Trait,
    TraitThreshold,
    TraitEffect,
    TraitTrigger,
    TriggerType,
    EffectTarget,
    ActiveTraitEffect,
)

from .trait_manager import (
    TraitManager,
    TRAIT_EFFECT_APPLICATORS,
)

__all__ = [
    # Core classes
    "Trait",
    "TraitThreshold",
    "TraitEffect",
    "TraitTrigger",
    "ActiveTraitEffect",
    
    # Enums
    "TriggerType",
    "EffectTarget",
    
    # Manager
    "TraitManager",
    "TRAIT_EFFECT_APPLICATORS",
]
