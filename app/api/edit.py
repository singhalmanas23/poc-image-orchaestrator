from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.graph.workflow import orchestrator
from app.storage.store import save_result, get_result

router = APIRouter()


class EditRequest(BaseModel):
    instruction: str
    image_url: Optional[str] = None  # Direct URL to image
    image_id: Optional[str] = None   # Or reference a previously generated image
    priority: Literal["quality", "speed", "cost"] = "quality"
    probe_title: Optional[str] = None
    selected_option: Optional[str] = None


class EditResponse(BaseModel):
    success: bool
    image_url: Optional[str] = None
    image_id: Optional[str] = None
    model_used: Optional[str] = None
    provider: Optional[str] = None
    reasoning: Optional[str] = None
    optimized_prompt: Optional[str] = None
    cost: Optional[float] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None


@router.post("/edit", response_model=EditResponse)
async def edit_image(req: EditRequest):
    """Edit an existing image. Provide either image_url or image_id from a previous generation."""

    # Compose instruction from probe selection if provided
    instruction = req.instruction
    if req.probe_title and req.selected_option:
        instruction = f"{req.probe_title}: {req.selected_option}"

    # Resolve image URL
    image_url = req.image_url
    if not image_url and req.image_id:
        prev = get_result(req.image_id)
        if prev:
            image_url = prev.get("output_image_url")
        else:
            return EditResponse(success=False, error=f"Image ID '{req.image_id}' not found")

    if not image_url:
        return EditResponse(success=False, error="Provide either image_url or image_id")

    initial_state = {
        "user_prompt": instruction,
        "input_image_url": image_url,
        "priority": req.priority,
    }

    result = await orchestrator.ainvoke(initial_state)

    if result.get("error"):
        return EditResponse(success=False, error=result["error"])

    if result.get("image_id"):
        save_result(result["image_id"], result)

    return EditResponse(
        success=True,
        image_url=result.get("output_image_url"),
        image_id=result.get("image_id"),
        model_used=result.get("selected_model"),
        provider=result.get("selected_provider"),
        reasoning=result.get("selection_reasoning"),
        optimized_prompt=result.get("optimized_prompt"),
        cost=result.get("cost"),
        latency_ms=result.get("latency_ms"),
    )
