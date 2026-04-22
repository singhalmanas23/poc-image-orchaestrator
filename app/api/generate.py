from typing import Any, Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.graph.workflow import orchestrator
from app.storage.store import save_result

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str
    priority: Literal["quality", "speed", "cost"] = "quality"
    transparent_background: bool = True
    multi_view: bool = False
    num_views: int = Field(default=8, ge=1, le=8)


class ViewFrameOut(BaseModel):
    angle: Optional[str] = None
    degrees: Optional[int] = None
    image_url: Optional[str] = None
    cost: Optional[float] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None


class OrchestratorResponse(BaseModel):
    success: bool
    image_url: Optional[str] = None
    image_id: Optional[str] = None
    model_used: Optional[str] = None
    provider: Optional[str] = None
    reasoning: Optional[str] = None
    optimized_prompt: Optional[str] = None
    cost: Optional[float] = None
    latency_ms: Optional[int] = None
    transparent_background: Optional[bool] = None
    views: Optional[list[ViewFrameOut]] = None
    error: Optional[str] = None


@router.post("/generate", response_model=OrchestratorResponse)
async def generate_image(req: GenerateRequest):
    """Generate an image. The orchestrator analyzes your prompt and picks the best model.

    When `multi_view` is true, returns `views`: a parallel set of camera-angle
    renderings of the same subject for a 360° turntable viewer.
    """

    initial_state: dict[str, Any] = {
        "user_prompt": req.prompt,
        "input_image_url": None,
        "priority": req.priority,
        "transparent_background": req.transparent_background,
        "multi_view": req.multi_view,
        "num_views": req.num_views,
    }

    result = await orchestrator.ainvoke(initial_state)

    if result.get("error"):
        return OrchestratorResponse(success=False, error=result["error"])

    # Save to store for later editing
    if result.get("image_id"):
        save_result(result["image_id"], result)

    return OrchestratorResponse(
        success=True,
        image_url=result.get("output_image_url"),
        image_id=result.get("image_id"),
        model_used=result.get("selected_model"),
        provider=result.get("selected_provider"),
        reasoning=result.get("selection_reasoning"),
        optimized_prompt=result.get("optimized_prompt"),
        cost=result.get("cost"),
        latency_ms=result.get("latency_ms"),
        transparent_background=result.get("transparent_background"),
        views=result.get("views"),
    )
