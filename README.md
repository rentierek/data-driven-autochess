# TFT Auto-Battler Simulator

Modularny, headless symulator walki w stylu TFT (Auto-Battler).

## Instalacja

```bash
pip install -r requirements.txt
```

## Uruchomienie

```bash
python main.py --seed 12345
```

## Struktura projektu

```
src/
├── core/          # Hex grid, pathfinding, RNG
├── units/         # Unit, Stats, State Machine
├── combat/        # Damage calculation, crit
├── simulation/    # Main game loop
├── effects/       # Buffs, abilities
└── events/        # Event logging

data/              # YAML configurations
output/            # Battle logs (JSON)
```

## Dokumentacja

Szczegółowa dokumentacja znajduje się w docstringach każdego modułu.
