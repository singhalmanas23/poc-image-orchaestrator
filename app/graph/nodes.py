"""
LangGraph nodes — each function is a node in the orchestration graph.
"""

import asyncio
import uuid

from app.brain.analyzer import analyze_intent
from app.router.model_registry import select_generation_model, select_editing_model
from app.adapters.flux_fal import FluxFalAdapter
from app.adapters.ideogram import IdeogramAdapter
from app.adapters.recraft import RecraftAdapter
from app.adapters.openai_image import OpenAIImageAdapter
from app.graph.state import OrchestratorState, ViewFrame


# Default camera yaws around the subject, counter-clockwise from front.
# Paired with a human label that we splice into the prompt.
DEFAULT_VIEW_ANGLES: list[tuple[int, str]] = [
    (0,   "front view, camera directly facing the subject"),
    (45,  "three-quarter view from the front-right, 45° around the subject"),
    (90,  "right side profile view, camera 90° to the right of the subject"),
    (135, "three-quarter view from the back-right, 135° around the subject"),
    (180, "rear view, camera directly behind the subject"),
    (225, "three-quarter view from the back-left, 225° around the subject"),
    (270, "left side profile view, camera 90° to the left of the subject"),
    (315, "three-quarter view from the front-left, 315° around the subject"),
]


def _pick_angles(num_views: int) -> list[tuple[int, str]]:
    """Return `num_views` evenly-spaced angles, sampled from DEFAULT_VIEW_ANGLES."""
    n = max(1, min(num_views, len(DEFAULT_VIEW_ANGLES)))
    if n == len(DEFAULT_VIEW_ANGLES):
        return DEFAULT_VIEW_ANGLES
    step = len(DEFAULT_VIEW_ANGLES) / n
    return [DEFAULT_VIEW_ANGLES[int(i * step)] for i in range(n)]


def _view_prompt(base_prompt: str, angle_clause: str) -> str:
    return (
        f"{base_prompt}. {angle_clause}. "
        "Keep the exact same subject, identical design, materials, proportions, "
        "and colour palette as other views; plain neutral studio background, "
        "even soft lighting, sharp focus, product photography reference sheet."
    )


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
    """Execution node: calls the selected generation model.

    When `multi_view` is True, fans out N parallel generations — one per camera
    angle — and returns a `views` array alongside the primary `output_image_url`
    (which is always the 0° / front view).
    """
    if state.get("error"):
        return {}

    model_id = state["selected_model"]
    provider = state["selected_provider"]
    base_prompt = state.get("optimized_prompt", state["user_prompt"])
    transparent_bg = bool(state.get("transparent_background", False))
    multi_view = bool(state.get("multi_view", False))

    if multi_view:
        num_views = int(state.get("num_views") or 8)
        return await _run_multi_view(
            base_prompt=base_prompt,
            model_id=model_id,
            provider=provider,
            transparent_bg=transparent_bg,
            num_views=num_views,
        )

    # --- Single-view path ---
    try:
        single = await _run_single_view(
            prompt=base_prompt,
            model_id=model_id,
            provider=provider,
            transparent_bg=transparent_bg,
        )
    except Exception as e:
        return {"error": f"Generation failed ({model_id}): {str(e)}"}

    return {
        "output_image_url": single["image_url"],
        "image_id": f"img_{uuid.uuid4().hex[:12]}",
        "cost": single["cost"],
        "latency_ms": single["latency_ms"],
        "transparent_background": single["transparent_background"],
    }


async def _run_single_view(
    *,
    prompt: str,
    model_id: str,
    provider: str,
    transparent_bg: bool,
) -> dict:
    """Generate one image and optionally strip its background.

    Returns a dict with image_url / cost / latency_ms / transparent_background.
    Raises on the underlying adapter failure.
    """
    adapter = _get_adapter(provider)
    result = await adapter.generate(
        prompt=prompt,
        model_id=model_id,
        transparent_background=transparent_bg,
    )

    out_url = result.image_url
    total_cost = result.cost or 0
    total_latency = result.latency_ms or 0

    natively_alpha = bool((result.metadata or {}).get("transparent_background"))
    applied_alpha = False
    if transparent_bg and not natively_alpha:
        try:
            fal = FluxFalAdapter()
            rembg = await fal.remove_background(out_url)
            out_url = rembg.image_url
            total_cost += rembg.cost or 0
            total_latency += rembg.latency_ms or 0
            applied_alpha = True
        except Exception:
            # Soft-fail: keep original image, caller will see transparent_background False
            applied_alpha = False

    return {
        "image_url": out_url,
        "cost": total_cost,
        "latency_ms": total_latency,
        "transparent_background": applied_alpha or natively_alpha,
    }


async def _run_multi_view(
    *,
    base_prompt: str,
    model_id: str,
    provider: str,
    transparent_bg: bool,
    num_views: int,
) -> dict:
    """Generate a base front view, then derive the other angles by feeding that
    base image into FLUX Kontext with rotate-camera instructions.

    Re-prompting text-to-image from scratch per angle produces a *different
    object* each time — Kontext edits keep the same subject and only move the
    camera, which is what users actually want from a turntable view.
    """
    angles = _pick_angles(num_views)

    # 1) Base front view — normal text-to-image with the routed generation model
    front_deg, front_clause = angles[0]
    try:
        base = await _run_single_view(
            prompt=_view_prompt(base_prompt, front_clause),
            model_id=model_id,
            provider=provider,
            transparent_bg=transparent_bg,
        )
    except Exception as e:
        return {"error": f"Base view generation failed ({model_id}): {str(e)}"}

    base_frame: ViewFrame = {
        "angle": front_clause.split(",")[0],
        "degrees": front_deg,
        "image_url": base["image_url"],
        "cost": base["cost"],
        "latency_ms": base["latency_ms"],
    }

    # 2) Derive the remaining angles in parallel via Kontext edits on the base.
    # Kontext preserves subject identity — it just rotates the camera.
    fal = FluxFalAdapter()

    async def derive(deg: int, clause: str) -> ViewFrame:
        instruction = (
            f"Show this exact same subject from a different camera angle: {clause}. "
            "Keep the subject identical — same object, same materials, same colours, "
            "same proportions, same lighting, same background. Do not redesign or "
            "substitute the subject. Only rotate the camera around it."
        )
        try:
            res = await fal.edit(
                image_url=base["image_url"],
                instruction=instruction,
                model_id="flux-kontext-pro",
            )
            return {
                "angle": clause.split(",")[0],
                "degrees": deg,
                "image_url": res.image_url,
                "cost": res.cost,
                "latency_ms": res.latency_ms,
            }
        except Exception as e:
            return {
                "angle": clause.split(",")[0],
                "degrees": deg,
                "image_url": "",
                "error": str(e),
            }

    derived: list[ViewFrame] = await asyncio.gather(
        *(derive(deg, clause) for (deg, clause) in angles[1:])
    )

    frames: list[ViewFrame] = [base_frame, *derived]
    successful = [f for f in frames if f.get("image_url") and not f.get("error")]
    if not successful:
        first_err = next((f.get("error") for f in frames if f.get("error")), "unknown error")
        return {"error": f"Multi-view generation failed: {first_err}"}

    total_cost = sum((f.get("cost") or 0) for f in frames)
    # Perceived latency = base gen + slowest Kontext edit (edits run in parallel)
    max_edit_latency = max(
        ((f.get("latency_ms") or 0) for f in derived if not f.get("error")),
        default=0,
    )
    total_latency = (base_frame.get("latency_ms") or 0) + max_edit_latency

    return {
        "output_image_url": base["image_url"],
        "image_id": f"img_{uuid.uuid4().hex[:12]}",
        "cost": total_cost,
        "latency_ms": total_latency,
        "transparent_background": base["transparent_background"],
        "views": frames,
    }


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
