"""
Units router - lista dostępnych jednostek.
"""

from fastapi import APIRouter
from typing import List, Dict, Any
from pathlib import Path

from src.core.config_loader import ConfigLoader


router = APIRouter()

# Initialize config loader
DATA_PATH = Path(__file__).parent.parent.parent / "data"
_loader = ConfigLoader(str(DATA_PATH))


@router.get("/units")
async def get_units() -> List[Dict[str, Any]]:
    """
    Zwraca listę wszystkich dostępnych jednostek.
    
    Returns:
        Lista jednostek z ich statystykami, traitami i abilities.
    """
    units_data = _loader.load_all_units()
    
    result = []
    for unit_id, data in units_data.items():
        unit_info = {
            "id": unit_id,
            "name": data.get("name", unit_id),
            "traits": data.get("traits", []),
            "abilities": data.get("abilities", []),
            "attack_range": data.get("attack_range", 1),
            "stats": {
                "hp": data.get("stats", {}).get("base_hp", 500),
                "attack_damage": data.get("stats", {}).get("base_attack_damage", 50),
                "ability_power": data.get("stats", {}).get("base_ability_power", 0),
                "armor": data.get("stats", {}).get("base_armor", 20),
                "magic_resist": data.get("stats", {}).get("base_magic_resist", 20),
                "attack_speed": data.get("stats", {}).get("base_attack_speed", 0.7),
                "crit_chance": data.get("stats", {}).get("base_crit_chance", 0.25),
                "mana": data.get("stats", {}).get("base_mana", 0),
                "max_mana": data.get("stats", {}).get("base_max_mana", 100),
            },
            "cost": data.get("cost", 1),
        }
        result.append(unit_info)
    
    return result


@router.get("/units/{unit_id}")
async def get_unit(unit_id: str) -> Dict[str, Any]:
    """
    Zwraca szczegóły jednostki.
    
    Args:
        unit_id: ID jednostki
        
    Returns:
        Pełne dane jednostki
    """
    try:
        data = _loader.load_unit(unit_id)
        return {
            "id": unit_id,
            "name": data.get("name", unit_id),
            "traits": data.get("traits", []),
            "abilities": data.get("abilities", []),
            "attack_range": data.get("attack_range", 1),
            "stats": data.get("stats", {}),
            "cost": data.get("cost", 1),
        }
    except KeyError:
        return {"error": f"Unit '{unit_id}' not found"}
