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
12. [System Traitów](#system-traitów)

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

---

## System Umiejętności

**Pliki:** `src/abilities/ability.py`, `src/abilities/effect.py`, `src/abilities/scaling.py`, `src/abilities/projectile.py`, `src/abilities/aoe.py`

### Przegląd

System umiejętności obsługuje:

- **19 typów efektów** (damage, heal, stun, burn, etc.)
- **Star scaling** - wartości per 1★/2★/3★
- **Stat scaling** - skalowanie z AD/AP/Armor/MR/HP
- **Projectiles** - homing, miss-on-death
- **AoE** - circle, cone, line

### 19 Typów Efektów

| Kategoria | Typ | Parametry | Opis |
|-----------|-----|-----------|------|
| **Offensive** | `damage` | value, damage_type, scaling | Jednorazowe obrażenia |
| | `dot` | value, duration, interval | Damage Over Time |
| | `burn` | value, duration | TRUE damage/s |
| | `execute` | threshold | Zabija poniżej % HP |
| | `sunder` | value, duration | Redukuje Armor |
| | `shred` | value, duration | Redukuje MR |
| **CC** | `stun` | duration | Całkowite wyłączenie |
| | `slow` | value, duration | Slow AS |
| | `silence` | duration | Blokada spelli |
| | `disarm` | duration | Blokada auto-ataków |
| **Support** | `heal` | value, scaling | Przywraca HP |
| | `shield` | value, duration | Tymczasowe HP |
| | `wound` | value, duration | Redukcja leczenia % |
| | `buff` | stat, value, duration | Tymczasowy bonus |
| | `mana_grant` | value | Daje manę |
| | `cleanse` | target | Usuwa debuffs |
| **Displacement** | `knockback` | distance, stun_duration | Odpycha cel |
| | `pull` | distance | Przyciąga cel |
| | `dash` | distance, direction | Dash castera |

### Skalowanie

```
final_value = value[star_level] × (caster_stat / 100)

Przykład:
  value: [200, 350, 600], scaling: "ap"
  Caster 2★ z 150 AP
  → 350 × 1.5 = 525 damage
```

**Typy skalowania:**

| Typ | Statystyka | Użycie |
|-----|------------|--------|
| `ad` | Attack Damage | Fizyczne skille |
| `ap` | Ability Power | Magiczne skille |
| `armor` | Armor | Defensive shieldy |
| `mr` | Magic Resist | Defensive heale |
| `max_hp` | Max HP celu | % HP damage |
| `missing_hp` | Brakujące HP | Execute, heale |
| `caster_hp` | HP castera | Tank skille |

### Definicja Ability (YAML)

```yaml
# abilities.yaml
fireball:
  name: "Fireball"
  mana_cost: 80
  cast_time: [20, 18, 15]    # ticks per star
  target_type: "current_target"
  delivery: "projectile"
  projectile:
    speed: 3
    homing: true
    can_miss: true
  effects:
    - type: "damage"
      damage_type: "magical"
      value: [200, 350, 600]
      scaling: "ap"
    - type: "burn"
      value: [20, 35, 60]
      duration: 90

heal_wave:
  name: "Heal Wave"
  mana_cost: 70
  target_type: "lowest_hp_ally"
  delivery: "instant"
  aoe:
    type: "circle"
    radius: 2
  effects:
    - type: "heal"
      value: [150, 250, 400]
      scaling: "ap"
    - type: "shield"
      value: [100, 175, 300]
      duration: 120
```

### Projectile System

```python
from src.abilities import Projectile, ProjectileManager

manager = ProjectileManager()

# Spawn projectile
proj = manager.spawn(source=caster, target=target, ability=ability, star_level=2)

# Each tick: update positions, get arrivals
arrived = manager.tick()
for proj in arrived:
    # Apply effects on hit
    apply_ability_effects(proj.source, proj.target, proj.ability)
```

**Atrybuty projektilu:**

| Atrybut | Typ | Opis |
|---------|-----|------|
| `speed` | float | Hexów per tick |
| `homing` | bool | Czy śledzi cel |
| `can_miss` | bool | Czy pudłuje gdy cel zginie |

### AoE System

```python
from src.abilities.aoe import get_units_in_circle, get_units_in_cone, get_units_in_line

# Circle AoE
targets = get_units_in_circle(center, radius=2, units=enemies)

# Cone AoE (60° angle)
targets = get_units_in_cone(origin, target, angle=60, range_=3, units=enemies)

# Line AoE
targets = get_units_in_line(origin, target, width=1, units=enemies)
```

### Użycie w Kodzie

```python
from src.abilities import Ability, EFFECT_REGISTRY, create_effect

# Load ability
ability = Ability.from_dict("fireball", loader.load_ability("fireball"))

# Get cast time for star level
cast_time = ability.get_cast_time(star_level=2)

# Execute ability
for effect in ability.effects:
    result = effect.apply(caster, target, star_level=2, simulation=sim)
    if result.success:
        print(f"{effect.effect_type}: {result.value}")
```

---

## Quick Reference

### Uruchomienie Symulacji

```bash
python main.py --seed 12345 --verbose
python test_8v8_battle.py --seed 42
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

### Testy

```bash
pytest tests/ -v  # 100 tests (88 core + 12 traits)
```

---

## System Traitów

**Pliki:** `src/traits/trait.py`, `src/traits/trait_manager.py`, `data/traits.yaml`

### Zasady Działania

1. **Unikalne Jednostki**
   - 2x ta sama jednostka = **1** do traitu
   - Liczymy po `base_id` (typ jednostki, nie instance)

2. **Progi Zastępują**
   - Knight 4 = 40 armor, NIE 20+40=60
   - Aktywny jest tylko najwyższy osiągnięty próg

3. **Cele Efektów**

   | Target | Opis |
   |--------|------|
   | `holders` | Tylko jednostki z traitem |
   | `team` | Cały team |
   | `self` | Jednostka która triggered |
   | `adjacent` | Sąsiedzi na hexach |
   | `enemies` | Wrogowie |

### Typy Triggerów

| Trigger | Parametry | Kiedy aktywuje? |
|---------|-----------|-----------------|
| `on_battle_start` | - | Tick 0 (start walki) |
| `on_hp_threshold` | `threshold: 0.5` | Gdy HP spadnie poniżej % |
| `on_time` | `ticks: 300` | Dokładnie po X tickach |
| `on_interval` | `interval: 120` | Co X ticków |
| `on_death` | - | Gdy sojusznik z traitem ginie |
| `on_first_cast` | - | Gdy jednostka pierwszy raz castuje |
| `on_kill` | - | Gdy jednostka zabije wroga |

### Typy Efektów

| Efekt | Parametry | Opis |
|-------|-----------|------|
| `stat_bonus` | `stat`, `value` | Dodaje statystykę |
| `shield` | `value`, `duration` | Daje tarczę |
| `damage_amp` | `value`, `duration` | +X% zadawanych obrażeń |
| `damage_reduction` | `value`, `duration` | -X% otrzymywanych obrażeń |

### Przykład Traitu (YAML)

```yaml
knight:
  name: "Knight"
  description: "Knights gain bonus armor. At 6, entire team gets armor."
  thresholds:
    2:
      trigger: "on_battle_start"
      effects:
        - type: "stat_bonus"
          stat: "armor"
          value: 20
          target: "holders"
    4:
      trigger: "on_battle_start"
      effects:
        - type: "stat_bonus"
          stat: "armor"
          value: 40
          target: "holders"
    6:
      trigger: "on_battle_start"
      effects:
        - type: "stat_bonus"
          stat: "armor"
          value: 60
          target: "team"  # Cały team!
```

### Trigger Czasowy (on_time)

```yaml
ascended:
  name: "Ascended"
  description: "After 10 seconds, deal 50% more damage."
  thresholds:
    2:
      trigger: "on_time"
      trigger_params:
        ticks: 300  # 10s @ 30 TPS
      effects:
        - type: "damage_amp"
          value: 0.5
          target: "holders"
```

### Trigger HP (on_hp_threshold)

```yaml
light:
  name: "Light"
  description: "When below 50% HP, heal for 150 HP."
  thresholds:
    2:
      trigger: "on_hp_threshold"
      trigger_params:
        threshold: 0.5
      effects:
        - type: "stat_bonus"
          stat: "hp"
          value: 150
          target: "self"  # Tylko jednostka która triggered
```

### Zdefiniowane Traity (11)

| Trait | Progi | Efekt |
|-------|-------|-------|
| `knight` | 2/4/6 | Armor (holders, team@6) |
| `sorcerer` | 2/4/6 | AP (holders) |
| `ranger` | 2/4 | Attack Speed (holders) |
| `brawler` | 2/4/6 | HP (holders) |
| `assassin` | 2/4 | Crit Chance (holders) |
| `mystic` | 2/4 | MR (team) |
| `wild` | 2/4 | AS (holders, team@4) |
| `elemental` | 2/4 | Shield (holders) |
| `ascended` | 2/4 | Damage Amp po 10s |
| `machine` | 2 | AS co 4s (stacking) |
| `light` | 2/4 | Heal przy <50% HP |

### Integracja z Simulation

```python
# Setup
loader = ConfigLoader("data/")
sim = Simulation(seed=42, config=config)
sim.set_config_loader(loader)

# Load traits
traits_data = loader.load_all_traits()
sim.set_trait_manager(traits_data)

# Run - traits are automatically applied!
result = sim.run()
```

### Flow TraitManager

```
tick 0:
  on_battle_start()
    └─> count_traits() - liczy unikalne jednostki per trait
    └─> For each active threshold:
        └─> Check if trigger == ON_BATTLE_START
        └─> Apply effects to target units

every tick:
  on_tick(tick)
    └─> Check ON_TIME triggers (if tick == target_ticks)
    └─> Check ON_INTERVAL triggers (if tick % interval == 0)

on damage:
  on_unit_damaged(unit)
    └─> Check ON_HP_THRESHOLD triggers
    └─> If hp_percent <= threshold and not already triggered:
        └─> Apply effects with target="self"

on death:
  on_unit_death(unit)
    └─> Check ON_DEATH triggers
    └─> Recount traits (unit removed)
```
