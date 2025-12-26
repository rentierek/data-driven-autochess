#!/usr/bin/env python3
"""
8v8 Battle Test - Test wszystkich systemów.

Testuje:
- 16 jednostek (8 na team)
- Różne archetypy z różnymi abilities
- Ability execution (damage, heal, stun, burn, etc.)
- Projectiles i AoE
- Debuffs (burn, wound, slow, etc.)
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.hex_coord import HexCoord
from src.core.config_loader import ConfigLoader
from src.simulation.simulation import Simulation, SimulationConfig


def run_8v8_battle(seed: int = 12345, verbose: bool = True) -> dict:
    """
    Uruchamia 8v8 walkę testową.
    
    Team 0 (Blue): Guardian, Warrior, Fire Mage, Ice Mage, Archer, Healer, Assassin, Berserker
    Team 1 (Red):  Guardian, Warrior, Fire Mage, Necromancer, Sniper, Healer, Duelist, Battlemage
    """
    
    # Setup
    loader = ConfigLoader("data/")
    config = SimulationConfig(
        ticks_per_second=30,
        max_ticks=3000,  # 100s max
        grid_width=7,
        grid_height=8,
    )
    
    sim = Simulation(seed=seed, config=config)
    sim.set_config_loader(loader)
    
    # Load traits
    traits_data = loader.load_all_traits()
    sim.set_trait_manager(traits_data)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEAM 0 (BLUE) - Pozycje: dolna część mapy (r=0,1,2)
    # ═══════════════════════════════════════════════════════════════════════════
    
    team0_units = [
        # Frontline
        ("guardian", HexCoord(2, 2), 2),  # Tank 2★
        ("warrior", HexCoord(4, 2), 2),   # OT 2★
        
        # Mid
        ("fire_mage", HexCoord(1, 1), 1),   # Burst mage
        ("ice_mage", HexCoord(5, 1), 1),    # Control mage
        
        # Backline
        ("archer", HexCoord(0, 0), 2),      # Ranged DPS 2★
        ("healer", HexCoord(3, 0), 1),      # Support
        ("assassin", HexCoord(6, 0), 2),    # Backline dive 2★
        ("berserker", HexCoord(3, 2), 1),   # Melee DPS
    ]
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TEAM 1 (RED) - Pozycje: górna część mapy (r=5,6,7)
    # Grid is 7x8, offset x = q + (r//2) < 7
    # r=5: q_max = 7 - 2 - 1 = 4
    # r=6: q_max = 7 - 3 - 1 = 3
    # r=7: q_max = 7 - 3 - 1 = 3
    # ═══════════════════════════════════════════════════════════════════════════
    
    team1_units = [
        # Frontline (r=5, q_max=4, valid q: -2..4)
        ("guardian", HexCoord(0, 5), 2),      # offset: (2, 5)
        ("warrior", HexCoord(2, 5), 2),       # offset: (4, 5)
        
        # Mid (r=6, q_max=3, valid q: -3..3)
        ("fire_mage", HexCoord(-1, 6), 1),    # offset: (2, 6)
        ("necromancer", HexCoord(1, 6), 1),   # offset: (4, 6)
        
        # Backline (r=7, q_max=3, valid q: -3..3)
        ("sniper", HexCoord(-2, 7), 2),       # offset: (1, 7)
        ("healer", HexCoord(0, 7), 1),        # offset: (3, 7)
        ("duelist", HexCoord(2, 7), 1),       # offset: (5, 7)
        ("battlemage", HexCoord(4, 5), 1),    # offset: (6, 5)
    ]
    
    # Spawn Team 0
    if verbose:
        print("=" * 60)
        print("TEAM 0 (BLUE)")
        print("=" * 60)
    
    for unit_id, pos, star in team0_units:
        unit_config = loader.load_unit(unit_id)
        unit = sim.add_unit_from_config(unit_config, team=0, position=pos, star_level=star)
        if unit and verbose:
            print(f"  {unit.name} ({star}★) @ {pos} - ability: {unit.abilities}")
    
    # Spawn Team 1
    if verbose:
        print()
        print("=" * 60)
        print("TEAM 1 (RED)")
        print("=" * 60)
    
    for unit_id, pos, star in team1_units:
        unit_config = loader.load_unit(unit_id)
        unit = sim.add_unit_from_config(unit_config, team=1, position=pos, star_level=star)
        if unit and verbose:
            print(f"  {unit.name} ({star}★) @ {pos} - ability: {unit.abilities}")
    
    # Run simulation
    if verbose:
        print()
        print("=" * 60)
        print("BATTLE START!")
        print("=" * 60)
    
    result = sim.run()
    
    # Print results
    if verbose:
        print()
        print("=" * 60)
        print("BATTLE RESULT")
        print("=" * 60)
        
        winner = result.get("winner_team")
        if winner is not None:
            winner_name = "BLUE" if winner == 0 else "RED"
            print(f"  Winner: Team {winner} ({winner_name})")
        else:
            print("  Result: DRAW")
        
        print(f"  Duration: {result['total_ticks']} ticks ({result['duration_seconds']:.1f}s)")
        print(f"  Survivors: {len(result['survivors'])}")
        
        for surv in result['survivors']:
            print(f"    - {surv['name']} (Team {surv['team']}) - {surv['hp']:.0f} HP")
        
        # Analyze log for ability usage
        log = sim.get_log()
        events = log.get("events", [])
        
        ability_casts = [e for e in events if e.get("type") == "ABILITY_CAST"]
        ability_effects = [e for e in events if e.get("type") == "ABILITY_EFFECT"]
        deaths = [e for e in events if e.get("type") == "UNIT_DEATH"]
        
        print()
        print("=" * 60)
        print("STATISTICS")
        print("=" * 60)
        print(f"  Total ability casts: {len(ability_casts)}")
        print(f"  Total ability effects: {len(ability_effects)}")
        print(f"  Total deaths: {len(deaths)}")
        
        # Effect breakdown
        effect_types = {}
        for e in ability_effects:
            etype = e.get("data", {}).get("effect_type", "unknown")
            effect_types[etype] = effect_types.get(etype, 0) + 1
        
        if effect_types:
            print()
            print("  Effect breakdown:")
            for etype, count in sorted(effect_types.items(), key=lambda x: -x[1]):
                print(f"    - {etype}: {count}")
    
    # Save log
    output_path = f"output/battle_8v8_{seed}.json"
    sim.save_log(output_path)
    if verbose:
        print()
        print(f"Log saved to: {output_path}")
    
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="8v8 Battle Test")
    parser.add_argument("--seed", type=int, default=12345, help="Random seed")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    
    args = parser.parse_args()
    
    result = run_8v8_battle(seed=args.seed, verbose=not args.quiet)
