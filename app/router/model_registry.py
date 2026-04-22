"""
Model selection logic based on the research document.
Maps intent signals → best model for the job.
"""

from app.config import get_settings
from app.graph.state import OrchestratorState

# Provider → Settings attribute holding its API key
_PROVIDER_KEY_ATTR = {
    "fal": "fal_key",
    "ideogram": "ideogram_api_key",
    "recraft": "recraft_api_key",
    "openai": "openai_api_key",
    "google": "google_cloud_project",
}

# Preference order when the selected generation model's provider has no key.
# Order reflects "best default generator" → widest fallback.
_GENERATION_FALLBACK_ORDER = ("flux-2-pro", "gpt-image-1.5", "imagen-4-fast")

# Model catalog with capabilities and metadata
MODELS = {
    # --- Generation models ---
    "flux-2-pro": {
        "provider": "fal",
        "task": "generate",
        "cost_per_image": 0.055,
        "latency_range": "5-10s",
        "strengths": ["photorealistic", "product_shot", "quality"],
        "quality_rank": 1,
        "speed_rank": 3,
        "cost_rank": 3,
    },
    "imagen-4-fast": {
        "provider": "google",
        "task": "generate",
        "cost_per_image": 0.02,
        "latency_range": "2.7s",
        "strengths": ["photorealistic", "product_shot", "speed", "cost"],
        "quality_rank": 3,
        "speed_rank": 1,
        "cost_rank": 1,
    },
    "ideogram-3": {
        "provider": "ideogram",
        "task": "generate",
        "cost_per_image": 0.06,
        "latency_range": "15-30s",
        "strengths": ["text_rendering", "artistic"],
        "quality_rank": 2,
        "speed_rank": 5,
        "cost_rank": 4,
    },
    "recraft-v4": {
        "provider": "recraft",
        "task": "generate",
        "cost_per_image": 0.04,
        "latency_range": "few secs",
        "strengths": ["vector", "text_rendering", "svg"],
        "quality_rank": 4,
        "speed_rank": 2,
        "cost_rank": 2,
    },
    "gpt-image-1.5": {
        "provider": "openai",
        "task": "generate",
        "cost_per_image": 0.034,
        "latency_range": "5-15s",
        "strengths": ["photorealistic", "product_shot"],
        "quality_rank": 1,
        "speed_rank": 3,
        "cost_rank": 3,
    },
    # --- Editing models ---
    "flux-kontext-pro": {
        "provider": "fal",
        "task": "edit",
        "cost_per_image": 0.10,
        "latency_range": "3-5s",
        "strengths": [
            "color_change",
            "background",
            "object_modify",
            "style_transfer",
            "instruction_based",
        ],
        "quality_rank": 1,
        "speed_rank": 1,
        "cost_rank": 3,
    },
    "flux-fill-pro": {
        "provider": "fal",
        "task": "edit",
        "cost_per_image": 0.05,
        "latency_range": "fast",
        "strengths": ["inpaint", "mask_based", "precision"],
        "quality_rank": 1,
        "speed_rank": 2,
        "cost_rank": 2,
    },
    "imagen-4-edit": {
        "provider": "google",
        "task": "edit",
        "cost_per_image": 0.02,
        "latency_range": "5-10s",
        "strengths": [
            "color_change",
            "background",
            "object_modify",
            "cost",
            "auto_mask",
        ],
        "quality_rank": 3,
        "speed_rank": 3,
        "cost_rank": 1,
    },
    "ideogram-3-edit": {
        "provider": "ideogram",
        "task": "edit",
        "cost_per_image": 0.05,
        "latency_range": "15-30s",
        "strengths": ["text_edit", "inpaint"],
        "quality_rank": 2,
        "speed_rank": 4,
        "cost_rank": 3,
    },
}


def select_generation_model(state: OrchestratorState) -> dict:
    """Pick the best generation model based on intent signals."""
    priority = state.get("priority", "quality")
    needs_text = state.get("needs_text_rendering", False)
    needs_vector = state.get("needs_svg_vector", False)
    transparent_bg = state.get("transparent_background", False)
    style = state.get("style", "photorealistic")

    # Rule 1: Vector/SVG → Recraft V4 (only model that outputs real SVG)
    if needs_vector:
        return _apply_generation_key_fallback(
            _pick("recraft-v4", "Needs vector/SVG output — only Recraft V4 generates real SVGs")
        )

    # Rule 2: Text on product → Ideogram 3.0 (90-95% text accuracy)
    if needs_text:
        return _apply_generation_key_fallback(
            _pick("ideogram-3", "Text rendering needed — Ideogram 3.0 has 90-95% text accuracy")
        )

    # Rule 3: Priority-based selection for photorealistic/product shots
    if priority == "cost":
        return _apply_generation_key_fallback(
            _pick("imagen-4-fast", "Cost priority — Imagen 4 Fast at $0.02/image is cheapest quality option")
        )

    if priority == "speed":
        return _apply_generation_key_fallback(
            _pick("imagen-4-fast", "Speed priority — Imagen 4 Fast has ~2.7s latency")
        )

    # Default: quality priority
    base = _pick("flux-2-pro", "Quality priority — FLUX.2 Pro has top Elo rating (1,265)")

    # Note: transparent_background is handled as a post-processing pass in
    # generate_image_node (rembg via fal). It does not change model selection here
    # because the only raster model with native alpha (gpt-image-1) requires a
    # verified OpenAI org. transparent_bg is read here only to annotate reasoning.
    if transparent_bg:
        base["selection_reasoning"] = (
            base["selection_reasoning"] + " + rembg post-processing for transparent background"
        )
    return _apply_generation_key_fallback(base)


def select_editing_model(state: OrchestratorState) -> dict:
    """Pick the best editing model based on edit type and signals."""
    priority = state.get("priority", "quality")
    edit_type = state.get("edit_type", "object_modify")
    needs_mask = state.get("needs_mask", False)
    needs_text = state.get("needs_text_rendering", False)

    # Rule 1: Text editing WITH a mask → Ideogram 3.0 (industry-leading text accuracy, mask-based)
    # Without a mask Ideogram's edit endpoint will not accept the request, so fall through
    # to FLUX Kontext which handles instruction-based text edits well enough.
    if (edit_type == "text_edit" or needs_text) and needs_mask:
        return _pick(
            "ideogram-3-edit",
            "Text editing with mask — Ideogram 3.0 has industry-leading text accuracy",
        )

    # Rule 2: Needs mask / precision inpainting → FLUX Fill Pro
    if needs_mask or edit_type == "inpaint":
        return _pick("flux-fill-pro", "Precision edit requiring mask — FLUX Fill Pro is best mask-based inpainter")

    # Rule 3: Budget editing → Imagen 4
    if priority == "cost":
        return _pick("imagen-4-edit", "Cost priority — Imagen 4 at $0.02/edit with auto-mask detection")

    # Default: instruction-based editing → FLUX Kontext Pro
    # Also handles text edits without a mask (Kontext renders text reasonably well).
    reasoning = "Instruction-based edit — FLUX Kontext Pro, no mask needed, 3-5s, best local edit precision"
    if edit_type == "text_edit" or needs_text:
        reasoning = (
            "Text edit without mask — Ideogram requires a mask, falling back to FLUX Kontext Pro for instruction-based text editing"
        )
    return _pick("flux-kontext-pro", reasoning)


def _pick(model_id: str, reasoning: str) -> dict:
    model = MODELS[model_id]
    return {
        "selected_model": model_id,
        "selected_provider": model["provider"],
        "selection_reasoning": reasoning,
        "cost": model["cost_per_image"],
    }


def _provider_has_key(provider: str) -> bool:
    attr = _PROVIDER_KEY_ATTR.get(provider)
    if not attr:
        return True
    value = getattr(get_settings(), attr, "") or ""
    return bool(value.strip())


def _apply_generation_key_fallback(pick: dict) -> dict:
    """If the selected provider has no API key, swap to the first available
    generation model in _GENERATION_FALLBACK_ORDER and explain why in reasoning."""
    if _provider_has_key(pick["selected_provider"]):
        return pick

    original_model = pick["selected_model"]
    original_provider = pick["selected_provider"]
    original_reason = pick["selection_reasoning"]

    for candidate in _GENERATION_FALLBACK_ORDER:
        if candidate == original_model:
            continue
        candidate_provider = MODELS[candidate]["provider"]
        if _provider_has_key(candidate_provider):
            fb = _pick(
                candidate,
                (
                    f"Originally selected {original_model} ({original_reason}), "
                    f"but {original_provider.upper()} API key is not configured — "
                    f"falling back to {candidate}."
                ),
            )
            fb["fallback_from"] = original_model
            return fb

    pick["selection_reasoning"] = (
        f"{original_reason} — WARNING: {original_provider.upper()} API key is not "
        f"configured and no fallback provider has a key set."
    )
    return pick
