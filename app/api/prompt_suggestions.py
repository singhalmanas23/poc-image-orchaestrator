from typing import Optional

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import get_settings

router = APIRouter()


class PromptSuggestionsRequest(BaseModel):
    prompt: str = Field(
        ..., min_length=3, description="User-submitted generation prompt"
    )
    count: int = Field(
        default=5,
        ge=4,
        le=5,
        description="Number of suggestions to return (allowed: 4 or 5)",
    )
    context: Optional[str] = Field(
        default=None,
        description="Optional extra context (brand/style/constraints)",
    )


class PromptSuggestionsResponse(BaseModel):
    success: bool
    base_prompt: str
    suggestions: list[str]
    reasoning: Optional[str] = None
    error: Optional[str] = None


def _sanitize_suggestions(items: list[str], max_items: int) -> list[str]:
    """Deduplicate/clean suggestions and cap length."""
    cleaned: list[str] = []
    seen: set[str] = set()

    for raw in items:
        s = " ".join((raw or "").split()).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(s)
        if len(cleaned) >= max_items:
            break

    return cleaned


def _fallback_suggestions(prompt: str, count: int) -> list[str]:
    """
    Dynamic prompt-only fallback suggestions.
    Produces varied, context-aware iterative upgrades without hardcoding product types.
    """
    p = " ".join(prompt.strip().split())
    lower = p.lower()

    # Heuristic context extraction from user prompt
    lighting_tokens = (
        "studio",
        "softbox",
        "golden hour",
        "dramatic",
        "backlit",
        "neon",
    )
    material_tokens = ("leather", "metal", "glass", "wood", "fabric", "matte", "glossy")
    composition_tokens = (
        "close-up",
        "macro",
        "top-down",
        "hero shot",
        "flat lay",
        "angle",
    )
    bg_tokens = (
        "white background",
        "dark background",
        "gradient",
        "concrete",
        "marble",
        "linen",
    )

    has_lighting = any(t in lower for t in lighting_tokens)
    has_material = any(t in lower for t in material_tokens)
    has_composition = any(t in lower for t in composition_tokens)
    has_bg = any(t in lower for t in bg_tokens)

    candidates: list[str] = []

    # Build dynamic variants based on what is missing/present
    if not has_lighting:
        candidates.append(
            f"{p}, with premium soft key light, subtle rim light, and natural shadow falloff"
        )
    else:
        candidates.append(
            f"{p}, with refined lighting contrast and cleaner highlight control for a premium look"
        )

    if not has_material:
        candidates.append(
            f"{p}, with enhanced micro-texture detail and realistic surface reflections"
        )
    else:
        candidates.append(
            f"{p}, with richer material fidelity and sharper edge definition"
        )

    if not has_composition:
        candidates.append(
            f"{p}, composed as a clean hero shot with stronger subject framing"
        )
    else:
        candidates.append(
            f"{p}, with improved framing balance and tighter composition hierarchy"
        )

    if not has_bg:
        candidates.append(
            f"{p}, on a minimal background with better subject separation and depth"
        )
    else:
        candidates.append(
            f"{p}, with a cleaner background treatment and improved foreground-background contrast"
        )

    candidates.append(
        f"{p}, with refined color grading and consistent tones while preserving product identity"
    )
    candidates.append(
        f"{p}, with subtle premium detailing and manufacturing-quality finish"
    )

    # De-duplicate and cap
    unique: list[str] = []
    seen: set[str] = set()
    for s in candidates:
        key = s.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
        if len(unique) >= count:
            break

    return unique[:count]


async def _llm_generate_suggestions(
    prompt: str,
    count: int,
    context: Optional[str],
) -> tuple[list[str], str]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    system_prompt = (
        "You generate concise iterative prompt improvements for product image generation. "
        "Given a base prompt, return STRICT JSON with keys: suggestions, reasoning. "
        "Rules for suggestions: "
        "1) Return exactly the requested number of suggestions. "
        "2) Each suggestion must be a complete prompt that preserves the original product identity. "
        "3) Each suggestion should be a practical next iteration (lighting, materials, composition, details, styling). "
        "4) Do not repeat near-duplicates. "
        "5) Keep each suggestion under 24 words."
    )

    user_text = (
        f"Base prompt: {prompt}\n"
        f"Requested suggestions: {count}\n"
        f"Optional context: {context or 'none'}\n"
        "Return JSON only."
    )

    body = {
        "model": "gpt-5.4-mini",
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )

        # Handle permission/plan restrictions explicitly so caller can degrade gracefully
        if resp.status_code in (401, 403):
            raise PermissionError(
                f"OpenAI access denied ({resp.status_code}). "
                "Check API key validity, project permissions, and model access."
            )

        resp.raise_for_status()
        data = resp.json()

    raw = data["choices"][0]["message"]["content"]

    import json

    parsed = json.loads(raw)
    suggestions = parsed.get("suggestions", [])
    reasoning = str(parsed.get("reasoning", "")).strip()

    if not isinstance(suggestions, list):
        suggestions = []

    typed = [str(x) for x in suggestions]
    typed = _sanitize_suggestions(typed, count)

    if len(typed) < count:
        # Backfill if model under-returns
        fallback = _fallback_suggestions(prompt, count)
        for s in fallback:
            if len(typed) >= count:
                break
            if s.lower() not in {x.lower() for x in typed}:
                typed.append(s)

    return typed[:count], (reasoning or "Generated from submitted prompt context.")


@router.post("/prompt-suggestions", response_model=PromptSuggestionsResponse)
async def prompt_suggestions(req: PromptSuggestionsRequest):
    """
    Generate 4-5 iterative prompt improvements from the submitted user prompt.
    """
    base_prompt = req.prompt.strip()
    if not base_prompt:
        return PromptSuggestionsResponse(
            success=False,
            base_prompt="",
            suggestions=[],
            error="Prompt cannot be empty",
        )

    try:
        suggestions, reasoning = await _llm_generate_suggestions(
            prompt=base_prompt,
            count=req.count,
            context=req.context,
        )
        return PromptSuggestionsResponse(
            success=True,
            base_prompt=base_prompt,
            suggestions=suggestions,
            reasoning=reasoning,
        )
    except PermissionError as e:
        # 401/403 path: still return dynamic prompt-driven suggestions
        return PromptSuggestionsResponse(
            success=True,
            base_prompt=base_prompt,
            suggestions=_fallback_suggestions(base_prompt, req.count),
            reasoning="Returned dynamic local suggestions because upstream model access is restricted.",
            error=str(e),
        )
    except Exception as e:
        # Any transient/network/model-shape issue still yields useful dynamic suggestions
        return PromptSuggestionsResponse(
            success=True,
            base_prompt=base_prompt,
            suggestions=_fallback_suggestions(base_prompt, req.count),
            reasoning="Returned dynamic local suggestions due to upstream generation failure.",
            error=f"Suggestion generation failed: {e}",
        )
