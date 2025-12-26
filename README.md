# TFT Auto-Battler Simulator

Data-driven symulator walk auto-battler w stylu Teamfight Tactics. Headless engine z pełnym systemem umiejętności, projektili, AoE i debuffów.

## 📊 Statystyki Projektu

| Metryka | Wartość |
|---------|---------|
| **Linii kodu Python** | 10,418 |
| **Linii konfiguracji YAML** | 947 |
| **Testy** | 88 (100% pass) |
| **Moduły** | 7 |
| **Typy efektów** | 19 |
| **Archetypy jednostek** | 15 |

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

### 19 Typów Efektów

| Kategoria | Efekty |
|-----------|--------|
| **Offensive** | `damage`, `dot`, `burn`, `execute`, `sunder`, `shred` |
| **CC** | `stun`, `slow`, `silence`, `disarm` |
| **Support** | `heal`, `shield`, `wound`, `buff`, `mana_grant`, `cleanse` |
| **Displacement** | `knockback`, `pull`, `dash` |

### 15 Archetypów Jednostek

| Kategoria | Jednostki |
|-----------|-----------|
| **Tanks** | Guardian, Warrior |
| **Melee DPS** | Berserker, Assassin, Duelist |
| **Ranged DPS** | Archer, Sniper, Gunslinger |
| **Mages** | Fire Mage, Ice Mage, Necromancer, Battlemage |
| **Support** | Healer, Shaman, Executioner |

## 📁 Struktura Projektu

```
data-driven-autochess/
├── src/
│   ├── abilities/          # System umiejętności
│   │   ├── ability.py      # Ability dataclass + config
│   │   ├── effect.py       # 19 typów efektów
│   │   ├── scaling.py      # Star + stat scaling
│   │   ├── projectile.py   # Projectile system
│   │   └── aoe.py          # AoE calculations
│   │
│   ├── combat/             # System walki
│   │   └── damage.py       # Damage calculation + mitigation
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
│   ├── simulation/         # Battle engine
│   │   └── simulation.py   # Main tick loop (30 TPS)
│   │
│   └── units/              # Unit system
│       ├── unit.py         # Unit dataclass + debuffs
│       ├── stats.py        # Stats + modifiers
│       ├── state_machine.py # IDLE/MOVING/ATTACKING/CASTING/STUNNED/DEAD
│       └── champion_class.py # Mana modifiers per class
│
├── data/
│   ├── defaults.yaml       # Default values + simulation config
│   ├── units.yaml          # 15 unit definitions
│   ├── abilities.yaml      # Ability definitions
│   ├── classes.yaml        # Champion class modifiers
│   └── items.yaml          # Item definitions (placeholder)
│
├── tests/
│   ├── test_abilities.py   # 22 tests
│   ├── test_damage.py      # 21 tests
│   ├── test_mana.py        # 27 tests
│   └── test_targeting.py   # 18 tests
│
├── docs/
│   ├── PROJECT_DESIGN.md   # Architecture + roadmap
│   └── SYSTEMS.md          # Detailed system documentation
│
├── main.py                 # Entry point
├── test_8v8_battle.py      # 8v8 battle test
└── requirements.txt        # Dependencies
```

## 🚀 Quick Start

### Instalacja

```bash
git clone https://github.com/rentierek/data-driven-autochess.git
cd data-driven-autochess
pip install -r requirements.txt
```

### Uruchomienie symulacji

```bash
# Prosta walka
python main.py

# Z seedem dla determinizmu
python main.py --seed 12345

# 8v8 battle test
python test_8v8_battle.py --seed 42
```

### Uruchomienie testów

```bash
pytest tests/ -v
```

## 📖 Jak to działa?

### Pętla Ticka (30 TPS)

```
1. UPDATE_BUFFS     → Decrement buff durations
2. CHECK_ABILITIES  → Start casting if mana full
3. AI_DECISION      → Target selection, state transitions
4. EXECUTE_ACTIONS  → Move, attack, cast abilities
5. UPDATE_PROJECTILES → Move projectiles, apply on hit
6. CHECK_END        → Winner determination
```

### Skalowanie Umiejętności

```yaml
# Star scaling: [1★, 2★, 3★]
# Stat scaling: final = value × (stat/100)

fireball:
  cast_time: [20, 18, 15]
  effects:
    - type: "damage"
      damage_type: "magical"
      value: [200, 350, 600]  # per star
      scaling: "ap"           # × (AP/100)
    - type: "burn"
      value: [20, 35, 60]
      duration: 90
```

### Przykład Walki

```
Team 0 (Blue): Guardian, Warrior, Fire Mage, Ice Mage, Archer, Healer, Assassin, Berserker
Team 1 (Red):  Guardian, Warrior, Fire Mage, Necromancer, Sniper, Healer, Duelist, Battlemage

Result: Team 0 wins in 16.9s
Stats: 108 ability casts, 209 effects, 14 deaths
```

## 🗺️ Roadmap

| Faza | Status | Opis |
|------|--------|------|
| **Faza 1** | ✅ | Core systems (grid, units, combat) |
| **Faza 2** | ✅ | Ability system + 19 effects |
| **Faza 3** | ✅ | Simulation integration + 8v8 battle |
| **Faza 4** | 🔜 | Trait/Synergy system (2/4/6 breakpoints) |
| **Faza 5** | 📋 | Item system (components + combined) |
| **Faza 6** | 📋 | Database + ML integration |

## 📝 License

MIT License

## 🤝 Contributing

Pull requests welcome! Please run tests before submitting.
