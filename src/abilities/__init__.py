"""
Abilities module - system umiejętności.

Zawiera:
- Ability: Główna klasa umiejętności
- Effect: Bazowa klasa efektów + 19 typów
- ScalingCalculator: Obliczenia skalowania
- Projectile: System projektili
- AoE: Obliczenia obszarowych efektów

TYPY EFEKTÓW (19):
══════════════════════════════════════════════════════════════════

    OFFENSIVE:    damage, dot, burn, execute, sunder, shred
    CC:           stun, slow, silence, disarm
    SUPPORT:      heal, shield, wound, buff, mana_grant, cleanse
    DISPLACEMENT: knockback, pull, dash
"""

from .ability import Ability, ProjectileConfig, AoEConfig
from .effect import (
    Effect, EffectResult, EffectTarget, DamageType,
    # Offensive
    DamageEffect, DoTEffect, BurnEffect, ExecuteEffect, SunderEffect, ShredEffect,
    # CC
    StunEffect, SlowEffect, SilenceEffect, DisarmEffect,
    # Support
    HealEffect, ShieldEffect, WoundEffect, BuffEffect, ManaGrantEffect, CleanseEffect,
    # Displacement
    KnockbackEffect, PullEffect, DashEffect,
    # Registry
    EFFECT_REGISTRY, create_effect, parse_effects,
)
from .scaling import (
    StarValue, get_star_value, get_stat_for_scaling,
    calculate_scaled_value, ScalingConfig,
)
from .projectile import Projectile, ProjectileManager
from .aoe import (
    get_units_in_circle, get_units_in_cone, get_units_in_line,
    AoECalculator,
)

__all__ = [
    # Ability
    "Ability", "ProjectileConfig", "AoEConfig",
    
    # Effects - 19 types
    "Effect", "EffectResult", "EffectTarget", "DamageType",
    "DamageEffect", "DoTEffect", "BurnEffect", "ExecuteEffect", 
    "SunderEffect", "ShredEffect",
    "StunEffect", "SlowEffect", "SilenceEffect", "DisarmEffect",
    "HealEffect", "ShieldEffect", "WoundEffect", "BuffEffect", 
    "ManaGrantEffect", "CleanseEffect",
    "KnockbackEffect", "PullEffect", "DashEffect",
    "EFFECT_REGISTRY", "create_effect", "parse_effects",
    
    # Scaling
    "StarValue", "get_star_value", "get_stat_for_scaling",
    "calculate_scaled_value", "ScalingConfig",
    
    # Projectile
    "Projectile", "ProjectileManager",
    
    # AoE
    "get_units_in_circle", "get_units_in_cone", "get_units_in_line",
    "AoECalculator",
]
