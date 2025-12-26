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
        thresholds_raw = data.get("thresholds", {})
        thresholds = []
        
        # Thresholds are dict with numeric keys (2, 4, 6)
        if isinstance(thresholds_raw, dict):
            for count, thresh_data in sorted(thresholds_raw.items()):
                thresholds.append({
                    "count": int(count),
                    "effects": thresh_data.get("effects", []) if isinstance(thresh_data, dict) else [],
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
