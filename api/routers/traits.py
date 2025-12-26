"""
Traits router - lista traitów/synergii.
"""

from fastapi import APIRouter
from typing import List, Dict, Any
from pathlib import Path

from src.core.config_loader import ConfigLoader


router = APIRouter()

DATA_PATH = Path(__file__).parent.parent.parent / "data"
_loader = ConfigLoader(str(DATA_PATH))


@router.get("/traits")
async def get_traits() -> List[Dict[str, Any]]:
    """
    Zwraca listę wszystkich traitów.
    """
    traits_data = _loader.load_all_traits()
    
    result = []
    for trait_id, data in traits_data.items():
        thresholds = []
        for thresh in data.get("thresholds", []):
            thresholds.append({
                "count": thresh.get("count", 0),
                "effects": thresh.get("effects", []),
            })
        
        trait_info = {
            "id": trait_id,
            "name": data.get("name", trait_id),
            "description": data.get("description", ""),
            "thresholds": thresholds,
        }
        result.append(trait_info)
    
    return sorted(result, key=lambda x: x["name"])


@router.get("/traits/{trait_id}")
async def get_trait(trait_id: str) -> Dict[str, Any]:
    """
    Zwraca szczegóły traitu.
    """
    try:
        data = _loader.load_trait(trait_id)
        return {
            "id": trait_id,
            "name": data.get("name", trait_id),
            "description": data.get("description", ""),
            "thresholds": data.get("thresholds", []),
        }
    except KeyError:
        return {"error": f"Trait '{trait_id}' not found"}
