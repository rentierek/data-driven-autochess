# TFT Auto-Battler Simulator

## Kompletna Dokumentacja Projektu

---

# 📊 Przegląd

| Metryka | Wartość |
|---------|---------|
| **Wersja** | 1.0.0 |
| **Linii Python** | ~11,000 |
| **Linii YAML** | ~1,350 |
| **Testy** | 120 (100% pass) |
| **Moduły** | 10 |
| **Jednostki** | 15 archetypów |
| **Traity** | 11 synergii |
| **Itemy** | 15 przedmiotów |
| **Efekty** | 19 typów |

**Cel projektu:** Data-driven, headless symulator walk auto-battler w stylu TFT. Wszystkie mechaniki definiowane w YAML, symulacja deterministyczna.

---

# 📁 Struktura Projektu

```
datadrive-autochess-simulator/
│
├── src/                              # CORE ENGINE (~11k LOC)
│   │
│   ├── core/                         # ═══ FUNDAMENTY ═══
│   │   ├── hex_coord.py              # Axial hex coordinates (q, r)
│   │   ├── hex_grid.py               # Grid 7x8, occupancy tracking
│   │   ├── pathfinding.py            # A* algorithm z kolizjami
│   │   ├── targeting.py              # 11 target selectors
│   │   ├── config_loader.py          # YAML loading + merging
│   │   └── rng.py                    # Seeded deterministic RNG
│   │
│   ├── units/                        # ═══ JEDNOSTKI ═══
│   │   ├── unit.py                   # Unit dataclass, HP, mana, debuffs
│   │   ├── stats.py                  # BaseStats, StatModifiers, omnivamp
│   │   ├── state_machine.py          # 6 stanów (IDLE→DEAD)
│   │   └── champion_class.py         # Mana modifiers per class
│   │
│   ├── combat/                       # ═══ WALKA ═══
│   │   └── damage.py                 # Physical/Magic/True, crit, dodge, lifesteal
│   │
│   ├── abilities/                    # ═══ UMIEJĘTNOŚCI ═══
│   │   ├── ability.py                # Ability dataclass + config
│   │   ├── effect.py                 # 19 typów efektów
│   │   ├── scaling.py                # Star scaling + stat scaling
│   │   ├── projectile.py             # Homing projectiles, travel time
│   │   └── aoe.py                    # Circle, Cone, Line calculations
│   │
│   ├── traits/                       # ═══ SYNERGIE ═══
│   │   ├── trait.py                  # Trait, TraitThreshold dataclass
│   │   └── trait_manager.py          # Counting, activation, effects
│   │
│   ├── items/                        # ═══ PRZEDMIOTY ═══
│   │   ├── item.py                   # Item, ItemStats (% bonuses)
│   │   ├── item_effect.py            # ConditionalEffect, triggers
│   │   └── item_manager.py           # Equip, on_hit, on_ability_cast
│   │
│   ├── effects/                      # ═══ BUFFY ═══
│   │   └── buff.py                   # Temporary stat modifiers
│   │
│   ├── events/                       # ═══ LOGGING ═══
│   │   └── event_logger.py           # JSON event log dla replay
│   │
│   └── simulation/                   # ═══ SILNIK ═══
│       └── simulation.py             # Main tick loop @ 30 TPS
│
├── api/                              # REST API (FastAPI)
│   ├── main.py                       # Server + CORS + static
│   └── routers/                      # /api/units, items, traits, simulate
│
├── frontend/                         # Web UI
│   └── index.html                    # Hex board, drag-drop, battle
│
├── data/                             # YAML CONFIG (~1.3k LOC)
│   ├── defaults.yaml                 # Global simulation config
│   ├── units.yaml                    # 15 unit definitions
│   ├── abilities.yaml                # Ability definitions
│   ├── traits.yaml                   # 11 trait definitions
│   ├── items.yaml                    # 15 item definitions
│   └── classes.yaml                  # 7 champion classes
│
├── tests/                            # 120 TESTÓW
│   ├── test_abilities.py             # 22 tests
│   ├── test_damage.py                # 28 tests
│   ├── test_mana.py                  # 20 tests
│   ├── test_targeting.py             # 18 tests
│   ├── test_traits.py                # 12 tests
│   └── test_items.py                 # 20 tests
│
└── docs/
    └── SYSTEMS.md                    # Szczegółowa dokumentacja
```

---

# ✅ Zaimplementowane Systemy

## 1. Hex Grid & Pathfinding

```python
# Axial coordinates (odd-r offset)
class HexCoord:
    q: int  # kolumna
    r: int  # wiersz
    
# Siatka 7x8
grid = HexGrid(width=7, height=8)

# A* pathfinding z kolizjami
path = grid.find_path(start, goal, blocked_hexes)
```

**Funkcje:**

- `distance(a, b)` - odległość hexowa
- `neighbors(hex)` - 6 sąsiadów
- `line_of_sight(a, b)` - sprawdzenie linii
- `get_hexes_in_range(center, range)` - hexes w zasięgu

---

## 2. Unit System

### Stany (State Machine)

```
IDLE → MOVING → ATTACKING → CASTING → STUNNED → DEAD
         ↑          ↓           ↓
         └──────────┴───────────┘
```

### Statystyki

| Stat | Opis | Bazowa |
|------|------|--------|
| HP | Punkty życia | 500-1200 |
| Mana | Do ability | 0/100 |
| AD | Attack Damage | 40-80 |
| AP | Ability Power | 0-100 |
| Armor | Redukcja physical | 20-60 |
| MR | Redukcja magic | 20-40 |
| AS | Attack Speed | 0.6-1.2 |
| Crit% | Szansa na crit | 25% |
| Range | Zasięg ataku | 1-4 |

### Star Levels

```yaml
star_scaling:
  1: { hp: 1.0, damage: 1.0 }
  2: { hp: 1.8, damage: 1.8 }
  3: { hp: 3.24, damage: 3.24 }
```

---

## 3. Combat System

### Tick System

- **30 TPS** (ticks per second)
- Każdy tick: buffs → abilities → AI → actions → projectiles
- Deterministyczny (seed-based RNG)

### Damage Types

| Typ | Mitigacja | Przykład |
|-----|-----------|----------|
| Physical | Armor | Auto-attacks |
| Magical | Magic Resist | Abilities |
| True | Brak | Execute effects |

### Formuły

```python
# Damage reduction
reduction = armor / (armor + 100)
final_damage = raw_damage * (1 - reduction)

# Crit
if random() < crit_chance:
    damage *= (1 + crit_damage)  # default: 1.5x

# Lifesteal
heal = physical_damage * lifesteal_percent

# Omnivamp
heal = all_damage * omnivamp_percent
```

---

## 4. Mana System

### Gain Sources

| Źródło | Formuła |
|--------|---------|
| Auto-attack | `10 * attack_speed_ratio` |
| Taking damage | `mana_per_percent_hp_lost` (default 1%) |
| On-hit effects | Flat bonus |
| Blue Buff | +10 after cast |

### Ability Cast Flow

```
1. Mana reaches max_mana
2. State → CASTING
3. Cast time ticks
4. Ability executes
5. Mana → 0 (or overflow)
6. State → IDLE
```

---

## 5. Ability System

### 19 Effect Types

| Kategoria | Efekty |
|-----------|--------|
| **Damage** | `damage`, `dot`, `burn`, `execute` |
| **Defense** | `sunder` (armor shred), `shred` (mr) |
| **CC** | `stun`, `slow`, `silence`, `disarm` |
| **Support** | `heal`, `shield`, `wound`, `mana_grant`, `cleanse` |
| **Buff** | `buff` (stat modifier) |
| **Movement** | `knockback`, `pull`, `dash` |

### Targeting Selectors

```yaml
# 11 selektorów
targeting:
  type: nearest          # najbliższy wróg
  type: furthest         # najdalszy
  type: lowest_hp        # najniższe HP
  type: highest_hp       # najwyższe HP
  type: lowest_hp_percent
  type: backline         # ostatni rząd
  type: frontline        # pierwszy rząd
  type: random           # losowy
  type: cluster          # największa grupa
  type: splash           # AoE around target
  type: self             # sam siebie
```

### Projectiles

```python
# Homing projectile
projectile = Projectile(
    source=caster,
    target=enemy,
    speed=10,           # hexes per second
    on_hit=effect,
    miss_on_death=True  # miss jeśli target umrze
)
```

### AoE Shapes

```python
# Circle
targets = get_units_in_circle(center, radius=2)

# Cone
targets = get_units_in_cone(origin, direction, angle=60, range=3)

# Line
targets = get_units_in_line(start, end, width=1)
```

---

## 6. Trait System

### Mechanika

- **Unique counting**: 2× ten sam unit = 1 do traitu
- **Thresholds**: 2/4/6 progression
- **Replace, not stack**: Próg 4 zastępuje 2, nie sumuje

### Triggers

| Trigger | Kiedy |
|---------|-------|
| `on_battle_start` | Start walki |
| `on_hp_threshold` | HP poniżej % |
| `on_time` | Po X tickach |
| `on_interval` | Co X ticków |
| `on_death` | Po śmierci ally |

### Przykład (Knight)

```yaml
knight:
  thresholds:
    2:
      trigger: on_battle_start
      effects:
        - type: stat_bonus
          stat: armor
          value: 20
          target: holders
    4:
      effects:
        - type: stat_bonus
          stat: armor
          value: 40
          target: holders
    6:
      effects:
        - type: stat_bonus
          stat: armor
          value: 60
          target: team  # cały team!
```

### 11 Traitów

| Trait | Efekt |
|-------|-------|
| Knight | +Armor |
| Sorcerer | +AP |
| Ranger | +AS |
| Brawler | +HP |
| Assassin | +Crit |
| Mystic | +MR (team) |
| Wild | +AS (team@4) |
| Elemental | Shield |
| Ascended | +Damage @10s |
| Machine | Stacking AS |
| Light | Heal @50% HP |

---

## 7. Item System

### Stat Types

```yaml
# Flat bonus
attack_damage: 10      # +10 AD

# Percent bonus (z bazy!)
ad_percent: 0.35       # +35% bazowego AD
ap_percent: 0.50       # +50% bazowego AP

# Special
omnivamp: 0.25         # 25% heal z WSZYSTKICH obrażeń
```

**Formuła:** `effective = (base * (1 + percent)) + flat`

### Flagi

| Flaga | Efekt |
|-------|-------|
| `ability_crit: true` | Ability może krytować |
| `unique: true` | Max 1 per unit |

### Conditional Effects

```yaml
giant_slayer:
  conditional_effects:
    - condition:
        type: target_max_hp
        operator: ">"
        value: 1600
      effect:
        type: damage_amp
        value: 0.20  # +20% vs tanki
```

### 15 Itemów

**Komponenty (8):**

- B.F. Sword (+10% AD)
- Rod (+10% AP)
- Chain Vest (+20 Armor)
- Negatron (+20 MR)
- Giant's Belt (+150 HP)
- Recurve Bow (+10% AS)
- Tear (+15 Starting Mana)
- Sparring Gloves (+10% Crit/Dodge)

**Combined (7):**

- Infinity Edge (ability crit)
- Rabadon's (+50% AP)
- Giant Slayer (+20% vs tanks)
- Bloodthirster (omnivamp)
- Blue Buff (+mana after cast)
- Titan's Resolve (stacking AD)
- Frozen Heart (grants Mystic)

---

## 8. Event Logging

### Format JSON

```json
{
  "metadata": {
    "seed": 12345,
    "ticks_per_second": 30,
    "grid": {"width": 7, "height": 8}
  },
  "events": [
    {"tick": 0, "type": "SIMULATION_START", "data": {...}},
    {"tick": 15, "type": "UNIT_ATTACK", "unit_id": "...", "target_id": "..."},
    {"tick": 16, "type": "UNIT_DAMAGE", "data": {"damage": 50, "type": "physical"}}
  ]
}
```

### Event Types

- SIMULATION_START/END
- UNIT_SPAWN, MOVE, ATTACK, DAMAGE, HEAL, DEATH
- ABILITY_CAST, ABILITY_EFFECT
- BUFF_APPLY, BUFF_EXPIRE
- STATE_CHANGE, TARGET_ACQUIRED

---

## 9. Visualization (Web UI)

### Uruchomienie

```bash
python3 -m uvicorn api.main:app --port 8000
# Otwórz: http://localhost:8000
```

### Funkcje

- Hex board (7x8)
- Drag & drop units
- Live synergy display
- Battle simulation
- Result modal

---

# ❌ Brakujące Systemy

## Priorytet 1: Economy 🔴 KRYTYCZNE

```
[ ] Gold income (5 base + interest + streak)
[ ] Shop system (roll 2g, buy, sell)
[ ] Champion pool (shared odds)
[ ] XP & Leveling (1-10)
[ ] Unit cap per level
[ ] Bench (max 9 units)
```

## Priorytet 2: Game Loop 🔴

```
[ ] Stage/Round system (1-1 → 6-5)
[ ] PvE encounters (Krugs, Wolves, etc.)
[ ] Carousel rounds
[ ] Player HP (100 start)
[ ] Matchmaking (who fights who)
[ ] 8 player lobby
```

## Priorytet 3: Combat Polish 🟡

```
[ ] Mana lock during cast animation
[ ] Assassin backline jump
[ ] Taunt/Aggro mechanics
[ ] Untargetable states (Zed clone)
[ ] Revive mechanics
[ ] Shield breaking
```

## Priorytet 4: Items 🟡

```
[ ] Component + Component = Combined
[ ] Item removal (reforger)
[ ] Radiant items
[ ] Shadow items
[ ] Crafting UI
```

## Priorytet 5: Augments 🟢

```
[ ] Augment definitions
[ ] 3-choice selection
[ ] Silver/Gold/Prismatic tiers
[ ] Round 2-1, 3-2, 4-2 triggers
```

---

# 🚀 Roadmap

## Faza 1: Core Economy (~4-6h)

```python
# src/economy/
├── gold.py          # Income calculation
├── shop.py          # Roll, buy, sell
├── pool.py          # Champion pool, odds
└── player.py        # HP, level, bench
```

## Faza 2: Game State (~3-4h)

```python
# src/game/
├── game.py          # 8-player game controller
├── stage.py         # Stage 1-6 progression
├── round.py         # PvP/PvE rounds
└── player_state.py  # Individual player data
```

## Faza 3: Content Expansion

- Więcej unitów (30+)
- Więcej traitów (20+)
- Więcej itemów (30+)
- PvE encounters

## Faza 4: Balancing Tools

```python
# tools/
├── batch_simulator.py    # Run 1000+ games
├── balance_analyzer.py   # Win rates
└── meta_report.py        # Top comps
```

---

# 🔧 Jak Używać

## CLI Simulation

```python
from src.simulation.simulation import Simulation, SimulationConfig
from src.core.config_loader import ConfigLoader

loader = ConfigLoader("data/")
sim = Simulation(seed=42)
sim.set_config_loader(loader)
sim.set_trait_manager(loader.load_all_traits())
sim.set_item_manager(loader.load_all_items())

# Add units
unit = sim.add_unit_from_config(
    loader.load_unit("archer"),
    team=0, position=HexCoord(0, 0), star_level=2
)
sim.item_manager.equip_item(unit, "infinity_edge")

# Run
result = sim.run()
print(f"Winner: Team {result['winner_team']}")
```

## Run Tests

```bash
pytest tests/ -v
# 120 passed
```

## Start Visualization

```bash
python3 -m uvicorn api.main:app --port 8000
# http://localhost:8000
```

---

# 📄 Pliki Konfiguracyjne

## defaults.yaml

```yaml
simulation:
  ticks_per_second: 30
  max_ticks: 3000
  grid_width: 7
  grid_height: 8

combat:
  base_crit_damage: 0.5
  armor_formula_constant: 100

mana:
  on_attack_base: 10
  on_damage_percent: 0.01
  overflow_percent: 0.10
```

## units.yaml

```yaml
archer:
  name: "Archer"
  traits: [ranger, elf]
  attack_range: 4
  stats:
    base_hp: 550
    base_attack_damage: 55
    base_attack_speed: 0.8
  abilities: [volley]
```

---

# 🎯 Decyzje Projektowe

1. **Determinism**: Seed-based RNG = replay możliwy
2. **Data-driven**: Wszystko w YAML, zero hardcode
3. **Tick-based**: 30 TPS jak prawdziwe TFT
4. **Event logging**: JSON dla wizualizacji
5. **Modular**: Każdy system osobny moduł
6. **Testable**: 120 unit testów

---

**GitHub:** github.com/rentierek/data-driven-autochess
