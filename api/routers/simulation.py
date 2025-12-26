"""
Simulation router - uruchamianie symulacji i obliczanie synergii.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import random

from src.core.config_loader import ConfigLoader
from src.core.hex_coord import HexCoord
from src.simulation.simulation import Simulation, SimulationConfig
from src.traits import TraitManager


router = APIRouter()

DATA_PATH = Path(__file__).parent.parent.parent / "data"
_loader = ConfigLoader(str(DATA_PATH))


# ═══════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════

class UnitPlacement(BaseModel):
    """Jednostka umieszczona na planszy."""
    unit_id: str
    position: List[int]  # [q, r]
    star_level: int = 1
    items: List[str] = []


class TeamComposition(BaseModel):
    """Skład drużyny."""
    units: List[UnitPlacement]


class SimulationRequest(BaseModel):
    """Request do symulacji."""
    team0: List[UnitPlacement]
    team1: List[UnitPlacement]
    seed: Optional[int] = None


class SynergyRequest(BaseModel):
    """Request do obliczenia synergii."""
    units: List[str]  # Lista unit_ids


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/synergies")
async def calculate_synergies(request: SynergyRequest) -> Dict[str, Any]:
    """
    Oblicza aktywne synergie dla podanego składu.
    
    Args:
        request.units: Lista ID jednostek
        
    Returns:
        Dict z aktywnyni traitami i ich progami
    """
    # Count traits from units
    trait_counts: Dict[str, int] = {}
    unique_units: Dict[str, set] = {}  # trait -> set of base_ids
    
    for unit_id in request.units:
        try:
            unit_data = _loader.load_unit(unit_id)
            traits = unit_data.get("traits", [])
            
            for trait in traits:
                if trait not in unique_units:
                    unique_units[trait] = set()
                
                # Count unique base_ids per trait
                unique_units[trait].add(unit_id)
        except KeyError:
            continue
    
    # Convert to counts
    for trait, base_ids in unique_units.items():
        trait_counts[trait] = len(base_ids)
    
    # Load trait definitions and check thresholds
    traits_data = _loader.load_all_traits()
    active_traits = []
    
    for trait_id, count in trait_counts.items():
        if trait_id not in traits_data:
            continue
        
        trait_def = traits_data[trait_id]
        thresholds = trait_def.get("thresholds", [])
        
        # Find active threshold
        active_threshold = None
        for thresh in sorted(thresholds, key=lambda x: x.get("count", 0), reverse=True):
            if count >= thresh.get("count", 0):
                active_threshold = thresh
                break
        
        # Get all threshold counts for display
        all_thresholds = [t.get("count", 0) for t in thresholds]
        
        active_traits.append({
            "id": trait_id,
            "name": trait_def.get("name", trait_id),
            "count": count,
            "thresholds": all_thresholds,
            "active_threshold": active_threshold.get("count") if active_threshold else None,
            "is_active": active_threshold is not None,
        })
    
    # Sort by active first, then by count
    active_traits.sort(key=lambda x: (-x["is_active"], -x["count"]))
    
    return {
        "traits": active_traits,
        "total_units": len(request.units),
    }


@router.post("/simulate")
async def run_simulation(request: SimulationRequest) -> Dict[str, Any]:
    """
    Uruchamia symulację walki.
    
    Args:
        request: Składy obu drużyn
        
    Returns:
        Wynik walki z logiem eventów
    """
    seed = request.seed if request.seed is not None else random.randint(1, 999999)
    
    # Create simulation
    config = SimulationConfig(
        ticks_per_second=30,
        max_ticks=3000,
        grid_width=7,
        grid_height=8,
    )
    sim = Simulation(seed=seed, config=config)
    sim.set_config_loader(_loader)
    
    # Load traits and items
    sim.set_trait_manager(_loader.load_all_traits())
    sim.set_item_manager(_loader.load_all_items())
    
    # Add team 0 units
    for placement in request.team0:
        try:
            unit_config = _loader.load_unit(placement.unit_id)
            pos = HexCoord(placement.position[0], placement.position[1])
            unit = sim.add_unit_from_config(
                unit_config, 
                team=0, 
                position=pos, 
                star_level=placement.star_level
            )
            
            # Equip items
            if unit:
                for item_id in placement.items[:3]:  # Max 3 items
                    sim.item_manager.equip_item(unit, item_id)
        except Exception as e:
            print(f"Error adding unit {placement.unit_id}: {e}")
    
    # Add team 1 units
    for placement in request.team1:
        try:
            unit_config = _loader.load_unit(placement.unit_id)
            pos = HexCoord(placement.position[0], placement.position[1])
            unit = sim.add_unit_from_config(
                unit_config, 
                team=1, 
                position=pos, 
                star_level=placement.star_level
            )
            
            # Equip items
            if unit:
                for item_id in placement.items[:3]:
                    sim.item_manager.equip_item(unit, item_id)
        except Exception as e:
            print(f"Error adding unit {placement.unit_id}: {e}")
    
    # Run simulation
    result = sim.run()
    
    # Get event log
    events = sim.logger.get_events()
    
    return {
        "seed": seed,
        "result": result,
        "events": events,
        "total_events": len(events),
    }


@router.get("/grid-config")
async def get_grid_config() -> Dict[str, Any]:
    """
    Zwraca konfigurację siatki hex.
    """
    return {
        "width": 7,
        "height": 8,
        "team0_rows": [0, 1, 2, 3],  # Bottom half
        "team1_rows": [4, 5, 6, 7],  # Top half
        "coordinate_system": "odd-r",
    }
