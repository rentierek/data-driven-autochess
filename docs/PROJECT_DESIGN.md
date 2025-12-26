# TFT Auto-Battler Simulator

## Dokument Projektowy v1.1

**Data:** 25 Grudnia 2024  
**Status:** Aktywny Rozwój

---

## 1. Przegląd Projektu

### 1.1 Cel

Stworzenie **deterministycznego symulatora walki TFT** (Teamfight Tactics), który pozwala na:

- Symulowanie walk między drużynami jednostek
- Analizę wyników poprzez szczegółowe logi JSON
- Testowanie kompozycji i strategii
- Potencjalne wykorzystanie do treningu AI/ML

### 1.2 Kluczowe Cechy

- **Deterministyczność** - ten sam seed = identyczny wynik
- **Data-Driven** - konfiguracja przez pliki YAML
- **Modularność** - oddzielne systemy łatwe do rozbudowy
- **TFT-Accurate** - formuły zaczerpnięte z oryginalnej gry

---

## 2. Architektura Systemu

```
datadrive-autochess-simulator/
├── main.py                 # Entry point
├── data/                   # Konfiguracja YAML
│   ├── defaults.yaml       # Domyślne parametry
│   ├── units.yaml          # Definicje jednostek
│   ├── abilities.yaml      # Definicje umiejętności (11 abilities)
│   ├── items.yaml          # Definicje itemów
│   └── classes.yaml        # Champion Classes (7 klas)
├── src/
│   ├── core/               # Silnik podstawowy
│   │   ├── hex_coord.py    # Współrzędne hex
│   │   ├── hex_grid.py     # Siatka gry
│   │   ├── pathfinding.py  # Algorytm A*
│   │   ├── rng.py          # Deterministyczny RNG
│   │   ├── config_loader.py# Ładowanie YAML
│   │   └── targeting.py    # Selektory celów (11 typów)
│   ├── units/              # Jednostki
│   │   ├── unit.py         # Klasa Unit + debuff methods
│   │   ├── stats.py        # UnitStats
│   │   ├── state_machine.py# Stany jednostki + mana lock
│   │   └── champion_class.py# System klas
│   ├── abilities/          # System umiejętności ✨ NEW
│   │   ├── scaling.py      # Star values + stat scaling
│   │   ├── effect.py       # 13 typów efektów
│   │   └── ability.py      # Ability + Projectile + AoE
│   ├── combat/             # Walka
│   │   └── damage.py       # Obliczenia obrażeń
│   ├── effects/            # Efekty
│   │   └── buff.py         # System buffów
│   ├── simulation/         # Symulacja
│   │   └── simulation.py   # Główna pętla
│   └── events/             # Eventy
│       └── event_logger.py # Logger JSON
├── tests/                  # Testy jednostkowe (88 testów)
│   ├── test_targeting.py   # 18 testów
│   ├── test_mana.py        # 27 testów
│   ├── test_damage.py      # 21 testów
│   └── test_abilities.py   # 22 testów ✨ NEW
└── docs/
    ├── SYSTEMS.md          # Szczegóły systemów
    └── PROJECT_DESIGN.md   # Ten dokument
```

---

## 3. Zaimplementowane Systemy

### ✅ Faza 1: Core Systems

| System | Status | Elementy |
|--------|--------|----------|
| Hex Grid | ✅ | HexCoord, HexGrid, A* Pathfinding |
| Jednostki | ✅ | Unit, UnitStats, StateMachine, Star Levels |
| Targeting | ✅ | 11 selektorów (nearest, backline, cluster, etc.) |
| Walka | ✅ | Physical/Magical/True, Crit, Dodge, Lifesteal |
| Many | ✅ | TFT formula (1%+3%), Mana Lock, Overflow |
| Castowanie | ✅ | CAST_START → EFFECT_POINT → CAST_END |
| Champion Classes | ✅ | 7 klas z modyfikatorami |
| Eventy | ✅ | JSON Logger z replay capability |

### ✅ Faza 2: System Umiejętności (DONE)

| Komponent | Status | Opis |
|-----------|--------|------|
| Star Scaling | ✅ | `value: [100, 200, 400]` per 1★/2★/3★ |
| Stat Scaling | ✅ | `final = value × (stat/100)` |
| 13 Typów Efektów | ✅ | damage, heal, shield, stun, burn, wound, etc. |
| Debuff Methods | ✅ | add_shield, add_burn, add_wound, tick_debuffs |
| Ability Parser | ✅ | YAML → Ability objects |
| 11 Example Abilities | ✅ | fireball, backstab, heal_wave, etc. |

**Typy Efektów:**

| Kategoria | Efekty |
|-----------|--------|
| Offensive | damage, dot, burn (true/s), execute, sunder, shred |
| CC | stun, slow |
| Support | heal, shield, wound (heal reduction), buff, mana_grant |

---

## 4. Testy

| Plik | Opis | Testy |
|------|------|-------|
| test_targeting.py | 11 selektorów, max_range | 18 |
| test_mana.py | TFT formula, lock, classes | 27 |
| test_damage.py | Redukcja, crit, dodge | 21 |
| test_abilities.py | Star scaling, effects, parsing | 22 |
| **SUMA** | | **88** |

```bash
python3 -m pytest tests/ -v
```

---

## 5. Roadmap - Co Dalej?

### 🔴 Priorytet Wysoki

| Zadanie | Status | Opis |
|---------|--------|------|
| Integracja abilities z simulation | 🔜 | Abilities faktycznie wykonywane w walce |
| Projectile system | 🔜 | Travel time, homing, miss on death |
| AoE implementation | 🔜 | Circle/Cone/Line |

### 🟡 Priorytet Średni

| Zadanie | Status | Opis |
|---------|--------|------|
| System Traitów/Synergii | 📋 | 2/4/6 breakpoints |
| System Itemów | 📋 | Komponenty + completed items |
| Silence/Disarm effects | 📋 | Dodatkowe CC |
| Knockback/Pull/Dash | 📋 | Displacement |

### 🟢 Priorytet Niski

| Zadanie | Status | Opis |
|---------|--------|------|
| Augmenty | 📋 | Wybór augmentów |
| Pozycjonowanie AI | 📋 | Optymalne ustawienie |
| Wizualizacja/Replay | 📋 | Web player |

**Legenda:** ✅ Done | 🔄 In Progress | 🔜 Next | 📋 Planned

---

## 6. Przykładowa Ability (YAML)

```yaml
fireball:
  name: "Fireball"
  mana_cost: 80
  cast_time: [20, 18, 15]      # per star
  target_type: "current_target"
  delivery: "projectile"
  projectile:
    speed: 3
    homing: true
  effects:
    - type: "damage"
      damage_type: "magical"
      value: [200, 350, 600]   # 1★, 2★, 3★
      scaling: "ap"            # × AP%
    - type: "burn"
      value: [20, 35, 60]      # true dmg/s
      duration: 90             # 3s
```

---

## 7. Uruchomienie

```bash
# Symulacja
python main.py --seed 12345 --verbose

# Testy
python3 -m pytest tests/ -v

# Quick check
python3 -c "from src.abilities import EFFECT_REGISTRY; print(list(EFFECT_REGISTRY.keys()))"
```

---

*Ostatnia aktualizacja: 25.12.2024 23:00*
