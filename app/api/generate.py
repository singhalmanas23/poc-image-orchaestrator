from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.graph.workflow import orchestrator
from app.storage.store import save_result

router = APIRouter()


class GenerateRequest(BaseModel):
    prompt: str
    priority: Literal["quality", "speed", "cost"] = "quality"
    transparent_background: bool = True


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
    error: Optional[str] = None


@router.post("/generate", response_model=OrchestratorResponse)
async def generate_image(req: GenerateRequest):
    """Generate an image. The orchestrator analyzes your prompt and picks the best model."""

    initial_state = {
        "user_prompt": req.prompt,
        "input_image_url": None,
        "priority": req.priority,
        "transparent_background": req.transparent_background,
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
    )
