# 🧙 Effect System Overview

Complete documentation of the 55 modular effect types in the TFT simulator.

---

## Effect Categories

### ⚔️ Damage Effects (13)

| Effect | Description | Example Champion |
|--------|-------------|------------------|
| `damage` | Base magic/physical damage | Anivia |
| `hybrid_damage` | AD + AP combined | Caitlyn |
| `splash_damage` | Main + % splash to nearby | Kog'Maw |
| `ricochet` | Bounces between targets | Lulu |
| `multi_hit` | Multiple hits on target(s) | Sona |
| `percent_hp_damage` | % max HP damage | Illaoi |
| `dash_through` | Damage while dashing | Yone |
| `projectile_swarm` | Multiple projectiles | Xerath |
| `projectile_spread` | Fan of projectiles | Twisted Fate |
| `dot` | Damage over time | Teemo |
| `burn` | % HP burn | Leona |
| `multi_strike` | Sequential hits | Xin Zhao |
| `grab_and_slam` | Grab + slam AoE | Sett |

---

### 🛡️ CC Effects (8)

| Effect | Description | Duration |
|--------|-------------|----------|
| `stun` | Prevents all actions | Variable |
| `slow` | Reduces AS | 30% default |
| `chill` | AS reduction debuff | Stacks |
| `silence` | Prevents abilities | Variable |
| `disarm` | Prevents attacks | Variable |
| `knockback` | Push away + stun | Distance + stun |
| `pull` | Pull toward caster | Distance |
| `taunt` | Force attack caster | Duration |

---

### 💚 Support Effects (10)

| Effect | Description | Target |
|--------|-------------|--------|
| `heal` | Restore HP | Self/Ally |
| `heal_over_time` | HP per tick | Self/Ally |
| `shield` | Temporary HP | Self/Ally |
| `buff` | Stat increase | Self/Ally |
| `buff_team` | Team-wide buff | All allies |
| `decaying_buff` | Buff that decays | Self |
| `stacking_buff` | Permanent stacks | Self |
| `mana_grant` | Give mana | Ally |
| `cleanse` | Remove debuffs | Self/Ally |
| `wound` | Reduce healing | Enemy |

---

### 🎯 Movement Effects (2)

| Effect | Description | Range |
|--------|-------------|-------|
| `dash` | Move to target | Variable |
| `teleport` | Instant reposition | Map-wide |

---

### ✨ Special Effects (22)

| Effect | Description | Champion |
|--------|-------------|----------|
| `replace_attacks` | Change attacks temporarily | Jhin |
| `effect_group` | Group of effects | Cho'Gath |
| `create_zone` | Persistent area | Kennen |
| `interval_trigger` | Periodic effect | Nautilus |
| `permanent_stack` | Persistent stat gain | Sion |
| `mana_reave` | Increase enemy mana cost | Yorick |
| `sunder` | Reduce armor | Gangplank |
| `shred` | Reduce MR | Zoe |
| `percent_damage_taken` | Bonus based on dmg taken | Ekko |
| `transform` | Change form | Shyvana |
| `accumulator` | Build up stacks | Seraphine |
| `random_ability` | Random spell | Sylas |
| `suppress` | Remove from combat | Tahm Kench |
| `cycle_ability` | Rotating abilities | Aatrox |
| `channel` | Drain mana, tick effect | Fiddlesticks |
| `invulnerability_zone` | Allies can't die | Kindred |
| `stardust` | Progressive upgrades | Aurelion Sol |
| `trait_effects` | Trait-based bonuses | Ryze |
| `transform_after_casts` | Transform at threshold | Volibear |
| `escalating_ability` | Power up over time | Zaahen |
| `execute` | Kill below threshold | Darius |

---

## Star Scaling

All numeric values support star scaling:

- **1★**: Base value
- **2★**: ~150% value
- **3★**: ~225% value

```yaml
effects:
  - type: damage
    ap_value: [280, 420, 630]  # 1★, 2★, 3★
```

---

## Stat Scaling

Effects can scale with:

- `ap` - Ability Power
- `ad` - Attack Damage
- `armor` - Armor
- `mr` - Magic Resist
- `hp` - Max Health
- `as` - Attack Speed
- `souls` - Shadow Isles souls

```yaml
effects:
  - type: damage
    value: [180, 270, 405]
    scaling: "armor"
```

---

## Targeting Modes

| Mode | Description |
|------|-------------|
| `current_target` | Attack target |
| `nearest` | Closest enemy |
| `farthest` | Furthest enemy |
| `lowest_hp` | Lowest HP enemy |
| `highest_damage` | Highest DPS enemy |
| `cluster` | Largest enemy group |
| `all_enemies` | All enemies |
| `self` | Caster |
| `lowest_hp_ally` | Lowest HP ally |
| `allies` | All allies |
