# TFT Auto-Battler Simulator

Data-driven symulator walk auto-battler w stylu Teamfight Tactics. Headless engine z pełnym systemem umiejętności, traitów, przedmiotów i projektili.

## 📊 Statystyki Projektu

| Metryka | Wartość |
|---------|---------|
| **Linii kodu Python** | ~15,000 |
| **Linii konfiguracji YAML** | ~2,500 |
| **Testy** | 150+ |
| **Moduły** | 10 |
| **Typy efektów** | 42 |
| **Set 16 Abilities** | 51 (1-3 cost) |
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
| **Abilities** | ✅ | 42 effect types, star scaling, stat scaling |
| **Projectiles** | ✅ | Homing, miss-on-death, travel time |
| **AoE** | ✅ | Circle, Cone, Line calculations |
| **Debuffs** | ✅ | Burn, Wound, Slow, Silence, Disarm |
| **Events** | ✅ | JSON logging for replay |
| **Champion Classes** | ✅ | 7 klas z modyfikatorami many |
| **Targeting** | ✅ | 11+ selektorów (nearest, backline, cluster...) |
| **Traits** | ✅ | Synergy system, unique unit counting, triggers |
| **Items** | ✅ | Percent stats, ability crit, omnivamp, conditionals |

---

## 🏆 Set 16 Champion Implementation

### Progress

| Cost | Champions | Abilities | Status |
|------|-----------|-----------|--------|
| **1-Cost** | 14 | 14/14 | ✅ Complete |
| **2-Cost** | 19 | 19/19 | ✅ Complete |
| **3-Cost** | 18 | 18/18 | ✅ Complete |
| **4-Cost** | - | 0/? | ⏳ Pending |
| **5-Cost** | - | 0/? | ⏳ Pending |

**Total: 51 abilities implemented and tested**

### 1-Cost Champions (14)

Lissandra, Blitzcrank, Warwick, Caitlyn, Illaoi, Jarvan IV, Jhin, Kog'Maw, Lulu, Maddie, Rumble, Shen, Sona, Viego

### 2-Cost Champions (19)

Tristana, Twitch, Twisted Fate, Sion, Graves, Ashe, Seraphine, Yone, Rek'Sai, Cho'Gath, Vi, Poppy, Tryndamere, Corki, Lee Sin, Yorick, Orianna, Ekko, Bard

### 3-Cost Champions (18)

Nautilus, Gangplank, Draven, Zoe, Leona, Milio, Jinx, Ahri, Malzahar, Sejuani, Darius, LeBlanc, Gwen, Dr. Mundo, Kobuko & Yuumi, Loris, Vayne, Kennen

---

## 42 Effect Types

| Kategoria | Efekty |
|-----------|--------|
| **Offensive** | `damage`, `dot`, `burn`, `execute`, `sunder`, `shred`, `splash_damage`, `ricochet`, `multi_hit`, `percent_hp_damage`, `dash_through`, `hybrid_damage`, `projectile_swarm` |
| **CC** | `stun`, `slow`, `chill`, `silence`, `disarm`, `knockback`, `pull`, `taunt` |
| **Support** | `heal`, `shield`, `shield_self`, `wound`, `buff`, `buff_team`, `mana_grant`, `cleanse`, `decaying_buff`, `stacking_buff`, `heal_over_time` |
| **Displacement** | `dash` |
| **Special** | `replace_attacks`, `effect_group`, `mana_reave`, `projectile_spread`, `multi_strike`, `create_zone`, `permanent_stack`, `interval_trigger` |

---

## 📁 Struktura Projektu

```
datadrive-autochess-simulator/
├── src/
│   ├── abilities/          # System umiejętności (42 effect types)
│   │   ├── ability.py      # Ability dataclass + config
│   │   ├── effect.py       # All effect implementations (~3000 LoC)
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
│   │   ├── targeting.py    # Target selectors
│   │   └── config_loader.py # YAML loading + merge
│   │
│   ├── events/             # Logging
│   │   └── event_logger.py # JSON event log for replay
│   │
│   ├── items/              # System przedmiotów
│   │   ├── item.py         # Item dataclasses
│   │   └── item_manager.py # Equip, triggers, effects
│   │
│   ├── simulation/         # Battle engine
│   │   └── simulation.py   # Main tick loop (30 TPS)
│   │
│   ├── traits/             # System traitów
│   │   └── trait_manager.py # Counting, activation, effects
│   │
│   └── units/              # Unit system
│       ├── unit.py         # Unit dataclass + debuffs
│       ├── stats.py        # Stats + modifiers
│       └── state_machine.py # State machine
│
├── data/
│   ├── defaults.yaml       # Default values + simulation config
│   ├── abilities.yaml      # 51 Set 16 ability definitions
│   ├── set16_abilities.yaml # Backup of Set 16 abilities
│   ├── set16_champions.yaml # Set 16 champion stats
│   ├── traits.yaml         # Trait definitions
│   └── items.yaml          # Item definitions
│
├── tests/                  # Unit tests
├── test_set16_1cost.py     # 1-cost ability tests
├── test_set16_2cost.py     # 2-cost ability tests
├── test_set16_3cost.py     # 3-cost ability tests
├── test_8v8_battle.py      # Integration test
│
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
pytest test_set16_*.py -v

# Run 8v8 battle
python test_8v8_battle.py --seed 42

# Run main
python main.py
```

## 🎯 Przykład użycia

```python
from src.simulation.simulation import Simulation
from src.core.config_loader import ConfigLoader
from src.core.hex_coord import HexCoord

# Setup
loader = ConfigLoader("data/")
sim = Simulation(seed=42)
sim._config_loader = loader

# Add units with Set 16 abilities
unit = sim.add_unit_from_config({
    'id': 'jinx_1', 'name': 'Jinx',
    'hp': 800, 'attack_damage': 65, 'attack_speed': 0.85,
    'range': 4, 'armor': 20, 'magic_resist': 20,
    'mana': 50, 'mana_start': 0,
    'ability': 'switcheroo',
}, team=0, position=HexCoord(0, 0), star_level=2)

# Run battle
result = sim.run()
print(f"Winner: Team {result['winner_team']}")
print(f"Duration: {result['total_ticks']} ticks")
```

## 📈 Następne kroki

1. ~~**1-Cost Abilities**~~ ✅
2. ~~**2-Cost Abilities**~~ ✅
3. ~~**3-Cost Abilities**~~ ✅
4. **4-Cost Abilities** ⏳
5. **5-Cost Abilities** ⏳
6. **Economy System** - Gold, shop, XP, levels
7. **Stage/Round System** - PvE, PvP rounds
8. **UI/Visualization** - Web frontend
9. **AI Player** - Monte Carlo Tree Search / RL

## 📄 Dokumentacja

- [docs/SYSTEMS.md](docs/SYSTEMS.md) - Detailed system documentation
- [data/set16_abilities.yaml](data/set16_abilities.yaml) - All 51 ability definitions

## 📃 License

MIT
