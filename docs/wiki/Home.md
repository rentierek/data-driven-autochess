# 📖 Home

Welcome to the **TFT Auto-Battler Simulator** wiki!

## Quick Links

- [🧙 Effect System](Effect-System) - All 55 effect types
- [🏆 Champions](Champions) - All 101 champion abilities

## Project Stats

| Metric | Value |
|--------|-------|
| Effect Types | 55 |
| Abilities | 101 |
| Champions | 60+ |
| Traits | 51 |

## Getting Started

```bash
git clone https://github.com/rentierek/data-driven-autochess.git
cd data-driven-autochess
pip install -r requirements.txt
python -m pytest tests/
```

## Architecture

```
src/
├── abilities/     # Effect system
├── combat/        # Damage calculations
├── core/          # Hex grid, config
├── simulation/    # Battle engine
└── traits/        # Trait system
```
