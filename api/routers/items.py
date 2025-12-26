"""
Items router - lista przedmiotów.
"""

from fastapi import APIRouter
from typing import List, Dict, Any
from pathlib import Path

from src.core.config_loader import ConfigLoader


router = APIRouter()

DATA_PATH = Path(__file__).parent.parent.parent / "data"
_loader = ConfigLoader(str(DATA_PATH))


@router.get("/items")
async def get_items() -> List[Dict[str, Any]]:
    """
    Zwraca listę wszystkich przedmiotów.
    """
    items_data = _loader.load_all_items()
    
    result = []
    for item_id, data in items_data.items():
        is_component = "components" not in data or len(data.get("components", [])) == 0
        
        item_info = {
            "id": item_id,
            "name": data.get("name", item_id),
            "description": data.get("description", ""),
            "stats": data.get("stats", {}),
            "is_component": is_component,
            "components": data.get("components", []),
            "unique": data.get("unique", False),
            "grants_traits": data.get("grants_traits", []),
        }
        result.append(item_info)
    
    # Sort: components first, then combined
    result.sort(key=lambda x: (not x["is_component"], x["name"]))
    
    return result


@router.get("/items/{item_id}")
async def get_item(item_id: str) -> Dict[str, Any]:
    """
    Zwraca szczegóły przedmiotu.
    """
    try:
        data = _loader.load_item(item_id)
        return {
            "id": item_id,
            "name": data.get("name", item_id),
            "description": data.get("description", ""),
            "stats": data.get("stats", {}),
            "effects": data.get("effects", []),
            "conditional_effects": data.get("conditional_effects", []),
            "flags": data.get("flags", {}),
            "grants_traits": data.get("grants_traits", []),
        }
    except KeyError:
        return {"error": f"Item '{item_id}' not found"}
