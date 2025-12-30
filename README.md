# 🎮 TFT Auto-Battler Simulator

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white)
![Set 16](https://img.shields.io/badge/TFT-Set%2016-gold?style=for-the-badge)
![Abilities](https://img.shields.io/badge/Abilities-101-green?style=for-the-badge)
![Effects](https://img.shields.io/badge/Effect%20Types-55-purple?style=for-the-badge)

**A comprehensive, data-driven headless simulator for TFT (Teamfight Tactics) auto-battler mechanics.**

[Features](#-features) • [Getting Started](#-getting-started) • [Architecture](#-architecture) • [Documentation](#-documentation)

</div>

---

## ✨ Features

### 🎯 Complete Combat System

- **Tick-based simulation** (30 ticks/second)
- **Hexagonal grid** with proper distance calculations
- **Projectile system** with homing, travel time, and miss-on-death
- **AoE calculations** (Circle, Cone, Line)

### 🧙 Modular Ability System

| Category | Count | Examples |
|----------|-------|----------|
| **Damage** | 13 | `damage`, `splash_damage`, `percent_hp_damage`, `multi_strike` |
| **CC** | 8 | `stun`, `knockback`, `taunt`, `suppress` |
| **Support** | 10 | `heal`, `shield`, `buff_team`, `cleanse` |
| **Special** | 24 | `teleport`, `stardust`, `trait_effects`, `transform` |

### 📊 Full Set 16 Implementation

| Cost | Champions | Status |
|------|-----------|--------|
| ⭐ 1-cost | 14 | ✅ Complete |
| ⭐⭐ 2-cost | 19 | ✅ Complete |
| ⭐⭐⭐ 3-cost | 18 | ✅ Complete |
| ⭐⭐⭐⭐ 4-cost | 26 | ✅ Complete |
| ⭐⭐⭐⭐⭐ 5-cost | 24 | ✅ Complete |

**Total: 101 abilities implemented and tested!**

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- PyYAML

### Installation

```bash
git clone https://github.com/rentierek/data-driven-autochess.git
cd data-driven-autochess
pip install -r requirements.txt
```

### Quick Example

```python
from src.simulation.simulation import Simulation
from src.core.hex_coord import HexCoord
from src.core.config_loader import ConfigLoader

# Create simulation
sim = Simulation(seed=42)
sim._config_loader = ConfigLoader()

# Add units with abilities
sim.add_unit_from_config({
    'id': 'unit_1', 'name': 'Anivia',
    'hp': 1000, 'attack_damage': 80, 'attack_speed': 0.75,
    'mana': 45, 'ability': 'frostbite',
}, team=0, position=HexCoord(0, 0), star_level=2)

# Run battle
result = sim.run()
print(f"Winner: Team {result['winner']} in {result['total_ticks']} ticks")
```

---

## 🏗 Architecture

```
data-driven-autochess/
├── src/
│   ├── abilities/          # Effect system (55 types)
│   │   ├── effect.py       # All effect classes
│   │   ├── scaling.py      # Star/AP/AD scaling
│   │   └── ability.py      # Ability wrapper
│   ├── combat/             # Damage & targeting
│   │   ├── damage.py       # Damage calculations
│   │   └── targeting.py    # 11+ targeting modes
│   ├── core/               # Core systems
│   │   ├── hex_coord.py    # Hexagonal math
│   │   ├── hex_grid.py     # Grid management
│   │   └── config_loader.py
│   ├── simulation/         # Battle simulation
│   │   └── simulation.py   # Main engine
│   └── traits/             # Trait system (51 traits)
├── data/
│   ├── abilities.yaml      # 101 ability definitions
│   ├── units.yaml          # Champion stats
│   └── traits.yaml         # Trait definitions
└── docs/
    ├── SYSTEMS.md          # Detailed mechanics
    └── PROJECT_CARD.md     # This file
```

---

## 📖 Documentation

### Key Systems

| System | Description |
|--------|-------------|
| **Mana** | TFT formula: `1% + 3%` per attack, max 42.5 mana/attack |
| **Damage** | Full armor/MR reduction, crit multipliers, true damage |
| **Scaling** | Star levels (1★/2★/3★), AP/AD ratios |
| **Debuffs** | Burn, Wound, Chill, Sunder, Shred |
| **Buffs** | Stat buffs, Attack Speed, Damage Reduction |

### Unique 5-Cost Mechanics

| Champion | Effect | Description |
|----------|--------|-------------|
| **Kindred** | `invulnerability_zone` | Allies can't die (HP→1) |
| **Aurelion Sol** | `stardust` | 8 upgrade thresholds |
| **Ryze** | `trait_effects` | Bonuses from active traits |
| **Volibear** | `transform_after_casts` | Transform after 5 uses |
| **Zaahen** | `escalating_ability` | Execute after 25 uses |

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Quick ability test
python -c "
from src.abilities.effect import EFFECT_REGISTRY
print(f'Effect types: {len(EFFECT_REGISTRY)}')
"
```

### Test Results

- ✅ 101/101 abilities functional
- ✅ Star scaling verified
- ✅ Item scaling verified
- ✅ 4v4 battles working

---

## 📈 Stats

| Metric | Value |
|--------|-------|
| Effect Types | 55 |
| Abilities | 101 |
| Champions | 60+ |
| Traits | 51 |
| Items | 40+ |
| Lines of Code | ~15,000 |

---

## 🔮 Roadmap

- [ ] 7-cost champion abilities
- [ ] Advanced trait interactions
- [ ] Web visualization API
- [ ] Monte Carlo simulations

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**Made with ❤️ for TFT theorycrafters**

[![GitHub](https://img.shields.io/badge/GitHub-rentierek-black?style=flat-square&logo=github)](https://github.com/rentierek/data-driven-autochess)

</div>
