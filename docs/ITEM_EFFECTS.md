# System Efektów Przedmiotów

## Typy Efektów

Registry efektów w `item_manager.py` zawiera 14 typów:

### Podstawowe

| Typ | Opis | Parametry |
|-----|------|-----------|
| `stat_bonus` | Dodaje bonus do statystyki | `stat`, `value`, `duration?` |
| `stacking_stat` | Stackujący bonus | `stat`, `value`, `max_stacks`, `stack_group?` |
| `mana_grant` | Daje manę | `value` |
| `heal` | Leczy flat HP | `value` |
| `shield` | Daje tarczę | `value`, `duration` |
| `damage` | Zadaje obrażenia | `value`, `damage_type` |
| `slow` | Spowalnia AS | `value`, `duration` |

### Set 16

| Typ | Opis | Parametry |
|-----|------|-----------|
| `sunder` | % redukcja Armor | `value` (0.30=30%), `duration` |
| `shred` | % redukcja MR | `value`, `duration` |
| `burn` | % max HP true DPS | `value`, `duration` |
| `wound` | Redukcja leczenia | `value` (33=33%), `duration` |
| `percent_max_hp_heal` | Heal % max HP | `value` |
| `percent_missing_hp_heal` | Heal % brakującego HP | `value` |
| `heal_lowest_ally` | Heal sojusznika z min HP | `value` (% obrażeń) |

---

## Triggery

### Format YAML

```yaml
effects:
  - triggers: ["on_hit", "on_take_damage"]  # wielokrotne!
    effects:
      - type: "stacking_stat"
        ...
```

### Dostępne triggery

| Trigger | Kiedy | Cel |
|---------|-------|-----|
| `on_hit` | Po trafieniu atakiem | `target`, `self` |
| `on_take_damage` | Po otrzymaniu obrażeń | `attacker`, `self` |
| `on_ability_cast` | Po użyciu umiejętności | `target`, `self` |
| `on_kill` | Po zabójstwie | `self` |
| `on_interval` | Co X ticków | `self` |
| `on_damage_dealt` | Po zadaniu obrażeń | `lowest_hp_ally` |
| `on_crit` | Po krytyku | `self` |

---

## Stack Groups

Dla itemów z wieloma triggerami dzielącymi wspólny limit (np. Titan's Resolve):

```yaml
effects:
  - triggers: ["on_hit", "on_take_damage"]
    effects:
      - type: "stacking_stat"
        stat: "attack_damage"
        value: 0.02
        max_stacks: 25
        stack_group: "titans_stacks"  # wspólny licznik!
```

`ItemStats.add_stack_group(group, max_stacks)` - sprawdza limit
`ItemStats.is_stack_group_full(group)` - czy pełne stacki

---

## Sunder/Shred - Refresh

**WAŻNE**: Sunder i Shred **odświeżają** duration, **nie stackują** wartości!

```python
# W unit.py:
def add_armor_reduction(self, amount, duration, is_percent=False):
    self.armor_reduction = max(self.armor_reduction, amount)  # max, nie +=
    self.armor_reduction_ticks = max(self.armor_reduction_ticks, duration)
```

---

## Conditional Effects

### Giant Slayer - sprawdza HP celu

```yaml
conditional_effects:
  - condition:
      type: "target_max_hp"
      operator: ">"
      value: 1600
    effect:
      type: "damage_amp"
      value: 0.15
```

### Steadfast Heart - sprawdza własne HP

```yaml
conditional_effects:
  - condition:
      type: "self_hp_percent"
      operator: "<"
      value: 0.50
    effect:
      type: "durability_bonus"
      value: 0.07
```

---

## Formuła Obrażeń

```
final = mitigated * (1 + damage_amp) * (1 - durability)
```

- `damage_amp` = conditional + flat (z stats)
- `durability` = redukcja obrażeń (max 90%)
