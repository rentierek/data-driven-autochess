# TFT Auto-Battler Simulator - Dokumentacja Systemów

## Spis Treści

1. [Przegląd Architektury](#przegląd-architektury)
2. [System Hex Grid](#system-hex-grid)
3. [System Jednostek](#system-jednostek)
4. [System Targetingu](#system-targetingu)
5. [System Walki](#system-walki)
6. [System Many](#system-many)
7. [System Castowania](#system-castowania)
8. [System Champion Classes](#system-champion-classes)
9. [System Buffów](#system-buffów)
10. [System Eventów](#system-eventów)
11. [System Umiejętności](#system-umiejętności)

---

## Przegląd Architektury

```
┌─────────────────────────────────────────────────────────────────┐
│                         SIMULATION                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ HexGrid  │ │  Units   │ │ Combat   │ │ Events   │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│        │           │            │             │                  │
│        ▼           ▼            ▼             ▼                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │Pathfind  │ │  Stats   │ │ Damage   │ │  Logger  │           │
│  │   A*     │ │ Machine  │ │  Calc    │ │  JSON    │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

**Przepływ ticka:**

1. `_phase_update_buffs()` - Aktualizacja buffów
2. `_phase_check_abilities()` - Check czy ktoś ma pełną manę
3. `_phase_ai_decision()` - Wybór celów i stanów
4. `_phase_execute_actions()` - Ruch/Atak/Cast
5. `_phase_check_end()` - Sprawdzenie końca walki

---

## System Hex Grid

**Pliki:** `src/core/hex_coord.py`, `src/core/hex_grid.py`, `src/core/pathfinding.py`

### HexCoord (Axial Coordinates)

```python
from src.core import HexCoord

pos = HexCoord(q=3, r=2)
distance = pos.distance(HexCoord(0, 0))  # 5 hexów
neighbors = pos.neighbors()  # 6 sąsiadów
```

**Kierunki:**

```
    NW    NE
      \ /
  W --- ● --- E
      / \
    SW    SE
```

### HexGrid

```python
grid = HexGrid(width=7, height=8)
grid.place_unit(unit, HexCoord(1, 3))
grid.is_walkable(HexCoord(2, 3))  # True/False
```

### Pathfinding (A*)

```python
from src.core.pathfinding import find_path, find_path_next_step

path = find_path(grid, start, goal)  # pełna ścieżka
next_hex = find_path_next_step(grid, start, goal)  # tylko następny krok
```

---

## System Jednostek

**Pliki:** `src/units/unit.py`, `src/units/stats.py`, `src/units/state_machine.py`

### Unit

```python
unit = Unit.from_config(loader.load_unit("warrior"), team=0, position=HexCoord(1, 3))

unit.is_alive()
unit.can_attack()
unit.in_attack_range(target)
unit.set_target(enemy)
```

### UnitStats

**Wzór efektywny:** `effective = (base + flat) * (1 + percent)`

```python
stats.get_attack_damage()  # 50 base + 20 flat * 1.1 percent = 77
stats.get_crit_chance()    # cap 0.0 - 1.0
stats.get_attack_speed()   # cap 0.2 - 5.0
```

**Modyfikatory Star Level:**

| Star | HP Mult | DMG Mult |
|------|---------|----------|
| 1★   | 1.0x    | 1.0x     |
| 2★   | 1.8x    | 1.8x     |
| 3★   | 3.24x   | 3.24x    |

### UnitStateMachine

```
        ┌─────────┐
        │  IDLE   │◄──────────────┐
        └────┬────┘               │
             │ target found       │ target died
    ┌────────┴────────┐           │
    ▼                 ▼           │
┌────────┐      ┌──────────┐      │
│ MOVING │─────▶│ATTACKING │──────┤
└────────┘      └────┬─────┘      │
   ▲ out of          │ full mana  │
   │ range           ▼            │
   │           ┌──────────┐       │
   └───────────│ CASTING  │───────┘
               └──────────┘
               
   STUNNED ← any state ← stun effect
   DEAD ← any state ← HP <= 0
```

---

## System Targetingu

**Plik:** `src/core/targeting.py`

### Dostępne Selektory

| Selektor | Opis | Parametry |
|----------|------|-----------|
| `nearest` | Najbliższy wróg | `max_range` |
| `farthest` | Najdalszy wróg | `max_range` |
| `lowest_hp_percent` | Najniższe % HP | `max_range` |
| `lowest_hp_flat` | Najniższe HP absolutne | `max_range` |
| `highest_stat` | Najwyższa statystyka | `stat`, `max_range` |
| `cluster` | Największe skupisko | `radius`, `max_range` |
| `random` | Losowy cel | `max_range` |
| `frontline` | Najbliżej mojego spawnu | `max_range` |
| `backline` | Najdalej od mojego spawnu | `max_range` |
| `current_target` | Utrzymaj cel | `max_range` |

### Użycie

```python
from src.core.targeting import get_selector, parse_target_type

# Programatycznie
selector = get_selector("backline", max_range=5)
target = selector.select(unit, enemies, grid, rng)

# Z YAML
selector = parse_target_type("nearest")
selector = parse_target_type({"selector": "cluster", "radius": 2})
```

### YAML Syntax

```yaml
# Prosty format
target_type: "nearest"

# Rozszerzony format
target_type:
  selector: "lowest_hp_percent"
  max_range: 5

# Highest stat
target_type:
  selector: "highest_stat"
  stat: "attack_damage"
```

---

## System Walki

**Plik:** `src/combat/damage.py`

### Typy Obrażeń

| Typ | Redukowany przez | Uwagi |
|-----|------------------|-------|
| PHYSICAL | Armor | Auto-attacks, niektóre skills |
| MAGICAL | Magic Resist | Większość umiejętności |
| TRUE | Nic | Przechodzi przez wszystko |

### Wzór Redukcji (TFT-style)

```
reduction = resistance / (resistance + 100)

Przykłady:
  0 armor   → 0% redukcji
  50 armor  → 33% redukcji
  100 armor → 50% redukcji
  200 armor → 67% redukcji
```

### Pipeline Obrażeń

```
1. Base Damage
   ↓
2. Crit Roll (tylko auto-attack)
   ↓ damage *= crit_multiplier (np. 1.4)
3. Dodge Roll (tylko auto-attack)
   ↓ jeśli dodge → damage = 0
4. Redukcja (armor/MR)
   ↓ damage *= (1 - reduction)
5. Final Damage
   ↓
6. Lifesteal/Spell Vamp
```

### DamageResult

```python
result = calculate_damage(attacker, defender, 100, DamageType.PHYSICAL, rng)
result.raw_damage           # przed redukcją
result.pre_mitigation_damage # = raw (dla mana calc)
result.final_damage         # po redukcji
result.is_crit              # True/False
result.was_dodged           # True/False
result.lifesteal_amount     # HP do oddania
```

---

## System Many

**Pliki:** `src/units/unit.py`, `src/units/stats.py`, `data/defaults.yaml`

### Źródła Many

| Źródło | Wzór | Domyślnie |
|--------|------|-----------|
| Atak | flat mana | 10 |
| Otrzymany damage | 1% pre + 3% post, cap 42.5 | TFT formula |
| Pasywna regen | mana/s (globalnie konfigurowalne) | 0 |

### TFT Formula (Mana from Damage)

```python
mana = min(cap, pre_dmg * pre_percent + post_dmg * post_percent)
mana = min(42.5, raw_damage * 0.01 + final_damage * 0.03)
```

**Przykład:** 200 raw → 150 final

```
mana = min(42.5, 200 * 0.01 + 150 * 0.03)
     = min(42.5, 2 + 4.5)
     = 6.5
```

### Mana Overflow

Jeśli włączone (`mana_overflow.enabled: true`):

- 85/90 mana + 10 z ataku → cast → **5 mana pozostaje**

Jeśli wyłączone:

- 85/90 mana + 10 z ataku → cast → **0 mana**

### Konfiguracja (defaults.yaml)

```yaml
mana_generation:
  mana_per_attack: 10
  mana_from_damage:
    pre_mitigation_percent: 0.01
    post_mitigation_percent: 0.03
    cap: 42.5
  mana_per_second: 0
  mana_overflow:
    enabled: true
```

---

## System Castowania

**Plik:** `src/units/state_machine.py`

### Fazy Casta

```
ATTACKING ──► CAST_START ──► EFFECT_POINT ──► CAST_END ──► IDLE
                │                   │
                │ Mana Lock ON      │ Ability fires
                │ Stop attacking    │ Log ABILITY_EFFECT
                ▼                   ▼
```

### Mana Lock

- **ON** gdy `start_cast()` wywołane
- Podczas lock: `gain_mana_on_damage()` zwraca 0
- **OFF** gdy `cast_remaining <= 0` (lub `mana_lock_remaining <= 0`)

### Parametry

```python
fsm.start_cast(
    cast_time_ticks=15,      # 0.5s @ 30 TPS
    effect_delay_ticks=8,    # efekt po 0.27s
    mana_lock_duration=None  # None = tylko podczas casta
)
```

### Konfiguracja (defaults.yaml)

```yaml
casting_defaults:
  base_cast_time_ticks: 15        # 0.5s
  base_effect_delay_ticks: 0      # instant
  base_mana_lock_duration: 0      # tylko podczas casta
  mana_lock_during_cast: true
```

---

## System Champion Classes

**Pliki:** `src/units/champion_class.py`, `data/classes.yaml`

### Jak Działa

1. `defaults.yaml` → `champion_classes.enabled: true`
2. `classes.yaml` → definicje klas
3. `units.yaml` → `mana_class: "assassin"`
4. Gra przy spawnie aplikuje modyfikatory

### Dostępne Klasy

| Klasa | Mana Attack | Mana Damage | Mana/s | Targeting |
|-------|-------------|-------------|--------|-----------|
| sorcerer | 0.5x | 1.5x | +5 | - |
| assassin | 1.2x | 0.8x | 0 | backline |
| guardian | 0.8x | 1.5x | 0 | frontline |
| marksman | 1.0x | 1.0x | 0 | farthest |
| executioner | 1.1x | 1.0x | 0 | lowest_hp |
| support | 0.6x | 1.0x | +8 | - (starts locked) |
| brawler | 1.1x | 1.1x | 0 | - |

### Użycie

```python
from src.units.champion_class import ChampionClassLoader

loader = ChampionClassLoader("data/")
assassin = loader.get_class("assassin")

# Aplikuj modyfikatory
mana = base_mana * assassin.mana_per_attack_multiplier
target_selector = assassin.default_target_selector or "nearest"
```

### Konfiguracja

```yaml
# defaults.yaml
champion_classes:
  enabled: true
  classes_file: "classes.yaml"

# classes.yaml
classes:
  assassin:
    name: "Assassin"
    mana_per_attack_multiplier: 1.2
    default_target_selector: "backline"
```

---

## System Buffów

**Plik:** `src/effects/buff.py`

### Typy Buffów

- **Stat modifiers** - +AD, +AS, etc.
- **Debuffs** - -armor, slow
- **Crowd control** - stun (przez state machine)

### Stackowanie

| Typ | Zachowanie |
|-----|------------|
| NONE | Pojedyncza instancja |
| REFRESH | Reset duration |
| INTENSITY | Zwiększ wartość |
| STACKS | Wiele instancji |

### Użycie

```python
buff = Buff(
    id="attack_boost",
    flat_modifiers={"attack_damage": 20},
    percent_modifiers={"attack_speed": 0.25},
    duration_ticks=90,  # 3s @ 30 TPS
)
unit.add_buff(buff)
```

---

## System Eventów

**Plik:** `src/events/event_logger.py`

### Typy Eventów

| Event | Opis |
|-------|------|
| SIMULATION_START | Start walki |
| SIMULATION_END | Koniec walki |
| UNIT_MOVE | Jednostka się ruszyła |
| UNIT_ATTACK | Jednostka zaatakowała |
| UNIT_DAMAGE | Jednostka otrzymała obrażenia |
| UNIT_DEATH | Jednostka zginęła |
| ABILITY_CAST | Jednostka użyła umiejętności |
| BUFF_APPLY | Buff nałożony |
| BUFF_EXPIRE | Buff wygasł |
| STATE_CHANGE | Zmiana stanu jednostki |
| TARGET_ACQUIRED | Jednostka wybrała cel |

### Format Logu (JSON)

```json
{
  "metadata": {
    "seed": 12345,
    "grid": {"width": 7, "height": 8},
    "ticks_per_second": 30
  },
  "events": [
    {
      "tick": 0,
      "type": "SIMULATION_START",
      "data": {"units": [...]}
    },
    {
      "tick": 15,
      "type": "UNIT_ATTACK",
      "unit_id": "warrior_0_abc123",
      "target_id": "mage_1_def456",
      "data": {"damage": 65, "is_crit": false}
    }
  ]
}
```

### Użycie

```python
logger = EventLogger(seed=12345)
logger.log_attack(tick, unit_id, target_id, damage, is_crit, was_dodged)
logger.save("output/battle.json")
```

---

## Quick Reference

### Uruchomienie Symulacji

```bash
python main.py --seed 12345 --verbose
```

### Kluczowe Parametry (defaults.yaml)

```yaml
simulation:
  ticks_per_second: 30
  max_ticks: 3000
  grid_width: 7
  grid_height: 8

mana_generation:
  mana_per_attack: 10
  mana_from_damage: {pre: 0.01, post: 0.03, cap: 42.5}

casting_defaults:
  base_cast_time_ticks: 15

champion_classes:
  enabled: true
```

### Tworzenie Jednostki

```yaml
# units.yaml
warrior:
  name: "Warrior"
  hp: 700
  attack_damage: 60
  attack_range: 1
  traits: ["frontline"]
  ability: "shield_bash"
  mana_class: "guardian"  # opcjonalne
```
