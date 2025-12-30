# Set 16 Trait System Documentation

## Overview

| Metric | Value |
|--------|-------|
| **Total Traits** | 40 |
| **Origins** | 14 |
| **Classes** | 12 |
| **Unique** | 14 |
| **Effect Applicators** | 17 |

---

## Effect Applicators

| Applicator | Description | Used By |
|------------|-------------|---------|
| `stat_bonus` | Add flat stat | Arcanist, Defender, Darkin |
| `stat_percent` | % of base stat | Bruiser, Slayer, Shadow Isles |
| `damage_amp` | % damage increase | Longshot |
| `damage_reduction` | % DR | Juggernaut |
| `shield` | Flat shield | - |
| `shield_percent_hp` | % max HP shield | Warden |
| `heal` | Heal HP | Juggernaut (on death) |
| `mana` | Grant mana | - |
| `mana_regen` | Mana/sec | Invoker |
| `mana_generation_bonus` | +% mana gen | Invoker |
| `target_missing_hp_as` | AS vs low HP | Quickstriker |
| `distance_damage_bonus` | +% per hex | Longshot |
| `self_missing_hp_damage` | +dmg at low HP | Slayer |
| `ability_applies_debuff` | Apply dazzle | Disruptor |
| `damage_vs_debuffed` | Bonus vs debuff | Disruptor |
| `shimmer_fused` | DR + decay AS | Zaun |
| `on_attack_counter` | Every Nth hit | Gunslinger |

---

## Origins (14)

### ✅ Implemented (stat bonuses only)

| Origin | Progi | Key Effect |
|--------|-------|------------|
| **Darkin** | 1/2/3 | +15% Omnivamp |
| **Shadow Isles** | 2/3/4/5 | +18-25% AD/AP |
| **Shurima** | 2/3/4 | +20% HP, AS/heal per sec |
| **Targon** | 1 | No effect (traitless) |
| **Yordle** | 2/4/6/8 | +40 HP, +5% AS per Yordle |

### 🟡 Partial (complex triggers)

| Origin | Progi | Missing |
|--------|-------|---------|
| **Demacia** | 3/5/7/11 | Team HP rally trigger |
| **Freljord** | 3/5/7 | Tower spawn system |
| **Ionia** | 3/6/9 | Path selection |
| **Noxus** | 3/5/7/10 | Atakhan summon |
| **Void** | 3/6/9 | Random mutation |
| **Zaun** | 3/5/7 | Shimmer refresh timer |

### ⏸️ Skip (requires shop/quest UI)

| Origin | Reason |
|--------|--------|
| **Bilgewater** | Currency + Black Market |
| **Ixtal** | Quest system |
| **Piltover** | Invention module selection |

---

## Classes (12)

### ✅ Fully Implemented

| Class | Progi | Effect |
|-------|-------|--------|
| **Arcanist** | 2/4/6 | Team +18/25/40 AP, Holders +25/45/70 |
| **Bruiser** | 2/4/6 | Team +150 HP, Holders +25/45/65% HP |
| **Defender** | 2/4/6 | Team +12 Armor/MR, Holders +30/55/80 |
| **Vanquisher** | 2/3/4/5 | +15-30% Crit, abilities can crit |
| **Gunslinger** | 2/4 | +20/35% AD, every 4th hit +100/200 |
| **Invoker** | 2/4 | Team +1 mana/sec, Holders +25/45% gen |
| **Juggernaut** | 2/4/6 | 18-25% DR, +7-8% above 50% HP |
| **Longshot** | 2/3/4/5 | +18-30% DA, +2-5% per hex |
| **Quickstriker** | 2/3/4/5 | Team +15% AS, 10-80% vs low HP |
| **Slayer** | 2/4/6 | +22-44% AD, 10-20% Omnivamp, +50% at low |
| **Disruptor** | 2/4 | Dazzle debuff, +25/45% vs dazzled |
| **Warden** | 2/4/6 | 20-50% HP shield at 75%/25% |

---

## Unique Traits (14)

| Trait | Champion | Status |
|-------|----------|--------|
| `ascendant` | Xerath | Placeholder |
| `assimilator` | Kai'Sa | Done (ability) |
| `blacksmith` | Ornn | Placeholder |
| `caretaker` | Bard | Placeholder |
| `chainbreaker` | Sylas | Done (ability) |
| `chronokeeper` | Zilean | Placeholder |
| `dark_child` | Annie | Placeholder |
| `emperor` | Azir | Placeholder |
| `hexmech` | T-Hex | Placeholder |
| `riftscourge` | Baron | Placeholder |
| `rune_mage` | Ryze | Done (ability) |
| `soulbound` | Lucian/Senna | Placeholder |
| `star_forger` | ASol | Done (ability) |
| `the_boss` | Sett | Placeholder |

---

## Unit → Trait Mapping (Example)

Based on units.yaml:

| Unit | Cost | Traits |
|------|------|--------|
| Soldier | 1 | guardian, human |
| Apprentice | 1 | mage, scholar |
| Scout | 1 | ranger, nomad |
| Brawler | 1 | fighter, wild |
| Recruit | 1 | duelist, human |
| Acolyte | 1 | healer, mystic |

*Note: Need to assign Set 16 traits to units*

---

## Battle Test Results

### 8v8 Battle Simulation

Teams with different trait compositions:

| Test | Team 0 Traits | Team 1 Traits | Duration | Winner |
|------|---------------|---------------|----------|--------|
| Tank vs DPS | Bruiser/Defender | Slayer/Quickstriker | ~30s | Varies |
| Caster duel | Arcanist | Arcanist | ~25s | Tie |
| Mixed | Defender/Longshot | Bruiser/Vanquisher | ~35s | Varies |

---

## Files

| File | Description |
|------|-------------|
| `data/set16_traits.yaml` | All 40 trait definitions |
| `src/traits/trait_manager.py` | 17 effect applicators |
| `tests/test_traits.py` | Test suite |
