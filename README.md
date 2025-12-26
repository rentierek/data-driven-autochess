# TFT Auto-Battler Simulator

Data-driven symulator walk auto-battler w stylu Teamfight Tactics. Headless engine z pełnym systemem umiejętności, traitów, przedmiotów i projektili.

## 📊 Statystyki Projektu

| Metryka | Wartość |
|---------|---------|
| **Linii kodu Python** | ~12,000 |
| **Linii konfiguracji YAML** | ~1,200 |
| **Testy** | 120 (100% pass) |
| **Moduły** | 9 |
| **Typy efektów** | 19 |
| **Archetypy jednostek** | 15 |
| **Traity** | 11 |
| **Przedmioty** | 15 |

## 🎮 Features

### Zaimplementowane Systemy

| System | Status | Opis |
|--------|--------|------|
| **Hex Grid** | ✅ | Siatka 7x8, axial coordinates, odd-r offset |
| **Pathfinding** | ✅ | A* z obsługą kolizji |
| **Units** | ✅ | Stats, Star Levels (1★/2★/3★), State Machine |
| **Combat** | ✅ | Physical/Magical/True damage, Crit, Dodge |
| **Mana** | ✅ | TFT formula (1%+3%, cap 42.5), Overflow |
| **Abilities** | ✅ | 19 effect types, star scaling, stat scaling |
| **Projectiles** | ✅ | Homing, miss-on-death, travel time |
| **AoE** | ✅ | Circle, Cone, Line calculations |
| **Debuffs** | ✅ | Burn, Wound, Slow, Silence, Disarm |
| **Events** | ✅ | JSON logging for replay |
| **Champion Classes** | ✅ | 7 klas z modyfikatorami many |
| **Targeting** | ✅ | 11 selektorów (nearest, backline, cluster...) |
| **Traits** | ✅ | Synergy system, unique unit counting, triggers |
| **Items** | ✅ | Percent stats, ability crit, omnivamp, conditionals |

### 19 Typów Efektów

| Kategoria | Efekty |
|-----------|--------|
| **Offensive** | `damage`, `dot`, `burn`, `execute`, `sunder`, `shred` |
| **CC** | `stun`, `slow`, `silence`, `disarm` |
| **Support** | `heal`, `shield`, `wound`, `buff`, `mana_grant`, `cleanse` |
| **Displacement** | `knockback`, `pull`, `dash` |

### Przedmioty (15)

**Komponenty (wszystkie dają % bonusy):**

- B.F. Sword (+10% AD), Rod (+10% AP), Chain Vest (+20% Armor)
- Negatron (+20% MR), Giant's Belt (+10% HP), Recurve Bow (+10% AS)
- Tear (+15 Starting Mana), Sparring Gloves (+10% Crit/Dodge)

**Combined Items:**

- Infinity Edge (+35% AD, ability crit)
- Rabadon's Deathcap (+50% AP)
- Giant Slayer (+20% dmg vs >1600 HP)
- Bloodthirster (+25% omnivamp)
- Blue Buff (+10 mana po cascie)
- Frozen Heart (grants Mystic trait)

## 📁 Struktura Projektu

```
datadrive-autochess-simulator/
├── src/
│   ├── abilities/          # System umiejętności
│   │   ├── ability.py      # Ability dataclass + config
│   │   ├── effect.py       # 19 typów efektów
│   │   ├── scaling.py      # Star + stat scaling
│   │   ├── projectile.py   # Projectile system
│   │   └── aoe.py          # AoE calculations
│   │
│   ├── combat/             # System walki
│   │   └── damage.py       # Damage calc + omnivamp + ability crit
│   │
│   ├── core/               # Fundamenty
│   │   ├── hex_coord.py    # Axial hex coordinates
│   │   ├── hex_grid.py     # Grid z occupancy
│   │   ├── pathfinding.py  # A* algorithm
│   │   ├── targeting.py    # 11 target selectors
│   │   ├── config_loader.py # YAML loading + merge
│   │   └── rng.py          # Deterministic RNG
│   │
│   ├── effects/            # Buff system
│   │   └── buff.py         # Temporary stat modifiers
│   │
│   ├── events/             # Logging
│   │   └── event_logger.py # JSON event log for replay
│   │
│   ├── items/              # System przedmiotów (NEW)
│   │   ├── item.py         # Item, ItemStats dataclasses
│   │   ├── item_effect.py  # ItemEffect, ConditionalEffect
│   │   └── item_manager.py # Equip, triggers, effects
│   │
│   ├── simulation/         # Battle engine
│   │   └── simulation.py   # Main tick loop (30 TPS)
│   │
│   ├── traits/             # System traitów (NEW)
│   │   ├── trait.py        # Trait, TraitThreshold dataclasses
│   │   └── trait_manager.py # Counting, activation, effects
│   │
│   └── units/              # Unit system
│       ├── unit.py         # Unit dataclass + debuffs
│       ├── stats.py        # Stats + modifiers + omnivamp
│       ├── state_machine.py # IDLE/MOVING/ATTACKING/CASTING/STUNNED/DEAD
│       └── champion_class.py # Mana modifiers per class
│
├── data/
│   ├── defaults.yaml       # Default values + simulation config
│   ├── units.yaml          # 15 unit definitions
│   ├── abilities.yaml      # Ability definitions
│   ├── classes.yaml        # Champion class modifiers
│   ├── traits.yaml         # 11 trait definitions
│   └── items.yaml          # 15 item definitions
│
├── docs/
│   └── SYSTEMS.md          # Detailed system documentation
│
├── tests/                  # 120 tests
│   ├── test_abilities.py
│   ├── test_items.py       # 20 tests
│   ├── test_traits.py      # 12 tests
│   └── ...
│
├── test_8v8_battle.py      # Full integration test
├── main.py                 # Entry point
└── requirements.txt
```

## 🚀 Quick Start

```bash
# Clone
git clone <repo>
cd datadrive-autochess-simulator

# Install
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Run 8v8 battle
python test_8v8_battle.py --seed 42

# Run main
python main.py
```

## 🎯 Przykład użycia

```python
from src.simulation.simulation import Simulation, SimulationConfig
from src.core.config_loader import ConfigLoader

# Setup
loader = ConfigLoader("data/")
sim = Simulation(seed=42)
sim.set_config_loader(loader)

# Load systems
sim.set_trait_manager(loader.load_all_traits())
sim.set_item_manager(loader.load_all_items())

# Add units
unit = sim.add_unit_from_config(
    loader.load_unit("archer"),
    team=0,
    position=HexCoord(0, 0),
    star_level=2
)

# Equip items
sim.item_manager.equip_item(unit, "infinity_edge")
sim.item_manager.equip_item(unit, "bloodthirster")

# Run
result = sim.run()
print(f"Winner: Team {result['winner_team']}")
```

## 📈 Następne kroki

1. **Economy System** - Gold, shop, XP, levels
2. **Stage/Round System** - PvE, PvP rounds, carousel
3. **Augments** - Special abilities chosen during game
4. **UI/Visualization** - Web or PyGame frontend
5. **AI Player** - Monte Carlo Tree Search / RL
6. **Replay System** - Playback from JSON logs

## 📄 Dokumentacja

Szczegółowa dokumentacja systemów: [docs/SYSTEMS.md](docs/SYSTEMS.md)

## 📃 License

MIT
