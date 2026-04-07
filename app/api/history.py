from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.storage.store import get_result, list_results

router = APIRouter()


@router.get("/history")
async def get_history(limit: int = 20):
    """List recent generated/edited images."""
    return {"images": list_results(limit)}


@router.get("/history/{image_id}")
async def get_image(image_id: str):
    """Get details of a specific image by ID."""
    result = get_result(image_id)
    if not result:
        return {"error": f"Image '{image_id}' not found"}
    return result
