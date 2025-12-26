#!/usr/bin/env python3
"""
TFT Auto-Battler Simulator - Entry Point
═══════════════════════════════════════════════════════════════════════════

Uruchamia przykładową symulację walki między dwoma drużynami.

Użycie:
    python main.py                    # Domyślny seed
    python main.py --seed 12345       # Konkretny seed
    python main.py --verbose          # Szczegółowy output

Wynik:
    - Wypisuje przebieg walki na konsolę
    - Zapisuje pełny log do output/battle_{seed}.json
"""

import argparse
import sys
from pathlib import Path

# Dodaj src do path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.hex_coord import HexCoord
from src.core.config_loader import ConfigLoader
from src.simulation.simulation import Simulation, SimulationConfig


def main():
    """Główna funkcja."""
    parser = argparse.ArgumentParser(
        description="TFT Auto-Battler Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--seed", 
        type=int, 
        default=12345,
        help="Ziarno losowości (domyślnie: 12345)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Szczegółowy output"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Nie zapisuj logu do pliku"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("TFT AUTO-BATTLER SIMULATOR")
    print("=" * 60)
    print(f"Seed: {args.seed}")
    print()
    
    # Załaduj konfigurację
    loader = ConfigLoader("data/")
    
    # Konfiguracja symulacji
    sim_config = SimulationConfig(
        ticks_per_second=30,
        max_ticks=3000,
        grid_width=7,
        grid_height=8,
    )
    
    # Stwórz symulację
    sim = Simulation(seed=args.seed, config=sim_config)
    
    # ─────────────────────────────────────────────────────────────────────────
    # TEAM 0 (lewa strona)
    # ─────────────────────────────────────────────────────────────────────────
    print("Team 0:")
    
    # Warrior - front line
    warrior = loader.load_unit("warrior")
    unit1 = sim.add_unit_from_config(warrior, team=0, position=HexCoord(1, 3), star_level=1)
    print(f"  - {unit1.name} @ ({unit1.position.q}, {unit1.position.r})")
    
    # Archer - back line
    archer = loader.load_unit("archer")
    unit2 = sim.add_unit_from_config(archer, team=0, position=HexCoord(1, 1), star_level=1)
    print(f"  - {unit2.name} @ ({unit2.position.q}, {unit2.position.r})")
    
    # ─────────────────────────────────────────────────────────────────────────
    # TEAM 1 (prawa strona)
    # ─────────────────────────────────────────────────────────────────────────
    print("Team 1:")
    
    # Mage - back line
    mage = loader.load_unit("mage")
    unit3 = sim.add_unit_from_config(mage, team=1, position=HexCoord(4, 5), star_level=1)
    print(f"  - {unit3.name} @ ({unit3.position.q}, {unit3.position.r})")
    
    # Assassin - front line
    assassin = loader.load_unit("assassin")
    unit4 = sim.add_unit_from_config(assassin, team=1, position=HexCoord(4, 3), star_level=1)
    print(f"  - {unit4.name} @ ({unit4.position.q}, {unit4.position.r})")
    
    print()
    print("-" * 60)
    print("ROZPOCZYNAM WALKĘ...")
    print("-" * 60)
    print()
    
    # Uruchom symulację
    result = sim.run()
    
    # Wyniki
    print()
    print("=" * 60)
    print("WYNIKI")
    print("=" * 60)
    
    if result["winner_team"] is not None:
        print(f"🏆 ZWYCIĘZCA: Team {result['winner_team']}")
    else:
        print("🤝 REMIS!")
    
    print(f"Czas walki: {result['duration_seconds']:.1f}s ({result['total_ticks']} ticks)")
    print()
    
    print("Ocaleni:")
    for survivor in result["survivors"]:
        hp_percent = (survivor["hp"] / survivor["max_hp"]) * 100
        print(f"  - {survivor['name']} (Team {survivor['team']}): {survivor['hp']:.0f}/{survivor['max_hp']:.0f} HP ({hp_percent:.0f}%)")
    
    # Zapisz log
    if not args.no_save:
        output_path = f"output/battle_{args.seed}.json"
        sim.save_log(output_path)
        print()
        print(f"📄 Log zapisany: {output_path}")
    
    # Verbose: pokaż statystyki
    if args.verbose:
        print()
        print("-" * 60)
        print("STATYSTYKI ZDARZEŃ")
        print("-" * 60)
        
        from src.events.event_logger import EventType
        
        for event_type in EventType:
            count = len(sim.logger.get_events_by_type(event_type))
            if count > 0:
                print(f"  {event_type.name}: {count}")
    
    print()
    print("Symulacja zakończona!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
