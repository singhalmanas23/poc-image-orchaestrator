"""
LangGraph nodes — each function is a node in the orchestration graph.
"""

import uuid

from app.brain.analyzer import analyze_intent
from app.router.model_registry import select_generation_model, select_editing_model
from app.adapters.flux_fal import FluxFalAdapter
from app.adapters.ideogram import IdeogramAdapter
from app.adapters.recraft import RecraftAdapter
from app.adapters.openai_image import OpenAIImageAdapter
from app.graph.state import OrchestratorState


# --- Node 1: Analyze Intent ---
async def analyze_intent_node(state: OrchestratorState) -> dict:
    """Brain node: uses Claude to analyze user's prompt and extract structured intent."""
    try:
        return await analyze_intent(state)
    except Exception as e:
        return {"error": f"Intent analysis failed: {str(e)}"}


# --- Node 2: Route to model ---
async def route_model_node(state: OrchestratorState) -> dict:
    """Router node: selects the best model based on analyzed intent."""
    if state.get("error"):
        return {}

    task_type = state.get("task_type", "generate")

    if task_type == "generate":
        return select_generation_model(state)
    else:
        return select_editing_model(state)


# --- Node 3a: Generate Image ---
async def generate_image_node(state: OrchestratorState) -> dict:
    """Execution node: calls the selected generation model."""
    if state.get("error"):
        return {}

    model_id = state["selected_model"]
    provider = state["selected_provider"]
    prompt = state.get("optimized_prompt", state["user_prompt"])
    transparent_bg = bool(state.get("transparent_background", False))

    adapter = _get_adapter(provider)

    try:
        result = await adapter.generate(
            prompt=prompt,
            model_id=model_id,
            transparent_background=transparent_bg,
        )

        out_url = result.image_url
        total_cost = result.cost
        total_latency = result.latency_ms
        applied_alpha = False

        # Post-process: rembg via fal for a real alpha channel.
        # Skip if the model already produced alpha (e.g. gpt-image-1 with background=transparent)
        natively_alpha = bool((result.metadata or {}).get("transparent_background"))
        if transparent_bg and not natively_alpha:
            try:
                fal = FluxFalAdapter()
                rembg = await fal.remove_background(out_url)
                out_url = rembg.image_url
                total_cost = (total_cost or 0) + (rembg.cost or 0)
                total_latency = (total_latency or 0) + (rembg.latency_ms or 0)
                applied_alpha = True
            except Exception as e:
                # Soft-fail: keep original image but mark transparent_background False
                return {
                    "output_image_url": out_url,
                    "image_id": f"img_{uuid.uuid4().hex[:12]}",
                    "cost": total_cost,
                    "latency_ms": total_latency,
                    "transparent_background": False,
                    "selection_reasoning": (
                        (state.get("selection_reasoning") or "")
                        + f" — rembg failed: {e}"
                    ),
                }

        return {
            "output_image_url": out_url,
            "image_id": f"img_{uuid.uuid4().hex[:12]}",
            "cost": total_cost,
            "latency_ms": total_latency,
            "transparent_background": applied_alpha or natively_alpha,
        }
    except Exception as e:
        return {"error": f"Generation failed ({model_id}): {str(e)}"}


# --- Node 3b: Edit Image (instruction-based) ---
async def edit_image_node(state: OrchestratorState) -> dict:
    """Execution node: calls the selected editing model (instruction-based, no mask)."""
    if state.get("error"):
        return {}

    model_id = state["selected_model"]
    provider = state["selected_provider"]
    instruction = state.get("optimized_prompt", state["user_prompt"])
    image_url = state.get("input_image_url", "")

    if not image_url:
        return {"error": "No input image provided for editing"}

    adapter = _get_adapter(provider)

    try:
        result = await adapter.edit(
            image_url=image_url,
            instruction=instruction,
            model_id=model_id,
        )
        return {
            "output_image_url": result.image_url,
            "image_id": f"img_{uuid.uuid4().hex[:12]}",
            "cost": result.cost,
            "latency_ms": result.latency_ms,
        }
    except Exception as e:
        return {"error": f"Editing failed ({model_id}): {str(e)}"}


# --- Node 3c: Mask-based Inpainting ---
async def inpaint_image_node(state: OrchestratorState) -> dict:
    """Execution node: mask-based inpainting (FLUX Fill Pro)."""
    if state.get("error"):
        return {}

    instruction = state.get("optimized_prompt", state["user_prompt"])
    image_url = state.get("input_image_url", "")

    if not image_url:
        return {"error": "No input image provided for inpainting"}

    adapter = FluxFalAdapter()

    try:
        result = await adapter.edit(
            image_url=image_url,
            instruction=instruction,
            model_id="flux-fill-pro",
            # mask_url would come from SAM or user-provided mask (future)
        )
        return {
            "output_image_url": result.image_url,
            "image_id": f"img_{uuid.uuid4().hex[:12]}",
            "cost": result.cost,
            "latency_ms": result.latency_ms,
        }
    except Exception as e:
        return {"error": f"Inpainting failed: {str(e)}"}


# --- Node 4: Return Result ---
async def return_result_node(state: OrchestratorState) -> dict:
    """Final node: formats the response. (passthrough — state already has everything)"""
    return {}


# --- Helper ---
def _get_adapter(provider: str):
    adapters = {
        "fal": FluxFalAdapter(),
        "ideogram": IdeogramAdapter(),
        "recraft": RecraftAdapter(),
        "openai": OpenAIImageAdapter(),
    }
    adapter = adapters.get(provider)
    if not adapter:
        raise ValueError(f"No adapter for provider: {provider}")
    return adapter
