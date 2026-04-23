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


class ProbeOption(BaseModel):
    label: str = Field(description="Short display label shown in the dropdown")
    instruction: str = Field(description="Full edit instruction sent to the API when selected")


class ProbeCategory(BaseModel):
    title: str = Field(description="Category title, e.g. 'adjust wallet shape'")
    options: list[ProbeOption] = Field(
        description="3–4 specific options for this category"
    )


class EditProbesRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=3,
        description="Original generation prompt / description of the product in the image",
    )
    count: int = Field(
        default=4,
        ge=3,
        le=6,
        description="Number of probe categories to return (3–6)",
    )


class EditProbesResponse(BaseModel):
    success: bool
    base_prompt: str
    probes: list[ProbeCategory]
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
        fallback = _fallback_suggestions(prompt, count)
        for s in fallback:
            if len(typed) >= count:
                break
            if s.lower() not in {x.lower() for x in typed}:
                typed.append(s)

    return typed[:count], (reasoning or "Generated from submitted prompt context.")


_GENERIC_EDIT_CATEGORIES: list[dict] = [
    {
        "title": "shift background",
        "options": [
            {"label": "dusk gradient", "instruction": "shift the background to a warm dusk gradient"},
            {"label": "clean white", "instruction": "replace the background with a clean white studio backdrop"},
            {"label": "dark studio", "instruction": "change the background to a dark moody studio setting"},
            {"label": "natural light", "instruction": "set the background to soft natural window light"},
        ],
    },
    {
        "title": "adjust material finish",
        "options": [
            {"label": "matte", "instruction": "apply a matte finish to the main material"},
            {"label": "glossy", "instruction": "apply a glossy finish to the main material"},
            {"label": "brushed texture", "instruction": "add a brushed texture to the surface"},
        ],
    },
    {
        "title": "change accent tone",
        "options": [
            {"label": "brass accents", "instruction": "swap hardware and accent details to a warm brass tone"},
            {"label": "matte black", "instruction": "change metal and accent details to matte black"},
            {"label": "chrome", "instruction": "swap accents to a polished chrome finish"},
        ],
    },
    {
        "title": "remove distractions",
        "options": [
            {"label": "remove logo", "instruction": "remove any visible logo or branding from the product"},
            {"label": "remove watermark", "instruction": "remove any watermark or overlay text from the image"},
            {"label": "clean shadows", "instruction": "clean up stray shadows and reflections for a neater look"},
        ],
    },
]

_NOUN_HINT_CATEGORIES: list[tuple[str, dict]] = [
    ("wheel", {"title": "change wheel style", "options": [
        {"label": "matte black", "instruction": "change the wheel finish to matte black"},
        {"label": "chrome", "instruction": "swap the wheels for a polished chrome finish"},
        {"label": "brushed alloy", "instruction": "change the wheels to a brushed alloy look"},
    ]}),
    ("tyre", {"title": "adjust tyre", "options": [
        {"label": "all-terrain", "instruction": "swap the tyre tread for an all-terrain pattern"},
        {"label": "slick", "instruction": "change the tyre to a smooth slick profile"},
        {"label": "wider stance", "instruction": "widen the tyre for a more aggressive stance"},
    ]}),
    ("tire", {"title": "adjust tire", "options": [
        {"label": "all-terrain", "instruction": "swap the tire tread for an all-terrain pattern"},
        {"label": "slick", "instruction": "change the tire to a smooth slick profile"},
        {"label": "wider stance", "instruction": "widen the tire for a more aggressive stance"},
    ]}),
    ("handle", {"title": "change handle", "options": [
        {"label": "leather wrap", "instruction": "add a leather wrap to the handle"},
        {"label": "matte black", "instruction": "change the handle finish to matte black"},
        {"label": "brushed steel", "instruction": "swap the handle to brushed steel"},
    ]}),
    ("strap", {"title": "adjust strap", "options": [
        {"label": "leather", "instruction": "change the strap to smooth leather"},
        {"label": "canvas", "instruction": "swap the strap material to canvas"},
        {"label": "darker tone", "instruction": "darken the strap color"},
    ]}),
    ("leather", {"title": "adjust leather", "options": [
        {"label": "matte", "instruction": "apply a matte finish to the leather"},
        {"label": "glossy", "instruction": "give the leather a glossy polished finish"},
        {"label": "distressed", "instruction": "add a distressed vintage texture to the leather"},
        {"label": "darker tone", "instruction": "darken the leather to a richer tone"},
    ]}),
    ("zip", {"title": "change zip", "options": [
        {"label": "matte brass", "instruction": "swap the zip hardware for matte brass"},
        {"label": "black", "instruction": "change the zip to a discreet black finish"},
        {"label": "chrome", "instruction": "swap the zip for polished chrome"},
    ]}),
    ("buckle", {"title": "adjust buckle", "options": [
        {"label": "brushed steel", "instruction": "change the buckle to brushed steel"},
        {"label": "matte black", "instruction": "swap the buckle for matte black"},
        {"label": "brass", "instruction": "change the buckle to warm brass"},
    ]}),
    ("fabric", {"title": "adjust fabric", "options": [
        {"label": "linen texture", "instruction": "add a fine linen texture to the fabric"},
        {"label": "darker weave", "instruction": "darken the fabric weave"},
        {"label": "satin finish", "instruction": "give the fabric a smooth satin finish"},
    ]}),
    ("wood", {"title": "refinish wood", "options": [
        {"label": "walnut", "instruction": "change the wood grain to rich walnut"},
        {"label": "oak", "instruction": "swap the wood finish to light oak"},
        {"label": "dark stain", "instruction": "apply a dark stain to the wood"},
    ]}),
    ("metal", {"title": "change metal finish", "options": [
        {"label": "matte black", "instruction": "swap metal accents for matte black"},
        {"label": "brushed", "instruction": "give the metal a brushed finish"},
        {"label": "polished chrome", "instruction": "change metal details to polished chrome"},
    ]}),
    ("glass", {"title": "adjust glass", "options": [
        {"label": "reduce glare", "instruction": "reduce reflections and glare on the glass"},
        {"label": "frosted", "instruction": "apply a frosted effect to the glass surface"},
        {"label": "tinted", "instruction": "add a subtle tint to the glass"},
    ]}),
    ("logo", {"title": "adjust logo", "options": [
        {"label": "remove", "instruction": "remove the visible logo from the product"},
        {"label": "emboss", "instruction": "change the logo to a subtle embossed style"},
        {"label": "reposition", "instruction": "move the logo position on the product"},
    ]}),
    ("label", {"title": "adjust label", "options": [
        {"label": "remove", "instruction": "remove the product label"},
        {"label": "minimalist", "instruction": "simplify the label to a minimalist design"},
        {"label": "reposition", "instruction": "move the label to a different position"},
    ]}),
    ("lens", {"title": "adjust lens", "options": [
        {"label": "darker tint", "instruction": "tint the lens darker"},
        {"label": "gradient", "instruction": "add a gradient tint to the lens"},
        {"label": "clear", "instruction": "make the lens fully clear and transparent"},
    ]}),
    ("frame", {"title": "change frame style", "options": [
        {"label": "matte black", "instruction": "change the frame finish to matte black"},
        {"label": "gold", "instruction": "swap the frame to a gold tone"},
        {"label": "tortoiseshell", "instruction": "change the frame to a tortoiseshell pattern"},
    ]}),
    ("sole", {"title": "adjust sole", "options": [
        {"label": "darker", "instruction": "darken the sole color"},
        {"label": "white", "instruction": "change the sole to clean white"},
        {"label": "contrast", "instruction": "add a contrast color pop to the sole"},
    ]}),
]


def _fallback_edit_probes(prompt: str, count: int) -> list[ProbeCategory]:
    """Heuristic structured probes if the LLM is unavailable."""
    lower = prompt.lower()
    categories: list[ProbeCategory] = []

    for token, cat_data in _NOUN_HINT_CATEGORIES:
        if token in lower:
            categories.append(ProbeCategory(
                title=cat_data["title"],
                options=[ProbeOption(**o) for o in cat_data["options"]],
            ))
        if len(categories) >= count:
            break

    for cat_data in _GENERIC_EDIT_CATEGORIES:
        if len(categories) >= count:
            break
        if cat_data["title"].lower() not in {c.title.lower() for c in categories}:
            categories.append(ProbeCategory(
                title=cat_data["title"],
                options=[ProbeOption(**o) for o in cat_data["options"]],
            ))

    return categories[:count]


async def _llm_generate_edit_probes(
    prompt: str,
    count: int,
) -> tuple[list[ProbeCategory], str]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    system_prompt = (
        "You generate structured edit-probe categories for an image-editing UI. "
        "Given a description of the product in the image, return STRICT JSON with "
        "keys: probes, reasoning. "
        "Each probe is an object with 'title' (a short category label, 2–5 words, "
        "e.g. 'adjust wallet shape') and 'options' — an array of 3–4 objects, each "
        "with 'label' (a short value shown in a dropdown, 1–3 words, e.g. 'rectangle') "
        "and 'instruction' (the full edit instruction sent to the model, e.g. "
        "'change the wallet shape to a sleek rectangle'). "
        "Rules for probes: "
        "1) Return exactly the requested number of probe categories. "
        "2) Each category title should name a specific part, material, or attribute of "
        "the product — infer parts from the product type. For a suitcase: wheels, handle, "
        "zip, shell color. For shoes: laces, sole, upper material. "
        "3) Each option's 'label' must be short (1–3 words) and the 'instruction' must be "
        "a complete imperative edit sentence (5–12 words). "
        "4) No duplicate categories. No generic 'improve the image' phrasing. "
        "5) Categories should cover different aspects: material, color, shape, background, "
        "details — not just color changes. "
        "6) Lowercase titles, no trailing punctuation on labels."
    )

    user_text = (
        f"Product prompt: {prompt}\n"
        f"Requested probe categories: {count}\n"
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
    probes_raw = parsed.get("probes", [])
    reasoning = str(parsed.get("reasoning", "")).strip()

    categories: list[ProbeCategory] = []
    seen_titles: set[str] = set()

    if isinstance(probes_raw, list):
        for item in probes_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())

            options_raw = item.get("options", [])
            options: list[ProbeOption] = []
            if isinstance(options_raw, list):
                for opt in options_raw:
                    if isinstance(opt, dict):
                        label = str(opt.get("label", "")).strip()
                        instruction = str(opt.get("instruction", "")).strip()
                        if label and instruction:
                            options.append(ProbeOption(label=label, instruction=instruction))

            if not options:
                continue
            categories.append(ProbeCategory(title=title, options=options))
            if len(categories) >= count:
                break

    if len(categories) < count:
        for cat in _fallback_edit_probes(prompt, count):
            if cat.title.lower() not in seen_titles:
                seen_titles.add(cat.title.lower())
                categories.append(cat)
            if len(categories) >= count:
                break

    return categories[:count], (
        reasoning or "Structured probes derived from product parts inferred from the prompt."
    )


@router.post("/edit-probes", response_model=EditProbesResponse)
async def edit_probes(req: EditProbesRequest):
    """Generate 3–6 structured edit-probe categories with dropdown options specific to the product."""
    base_prompt = req.prompt.strip()
    if not base_prompt:
        return EditProbesResponse(
            success=False,
            base_prompt="",
            probes=[],
            error="Prompt cannot be empty",
        )

    try:
        probes, reasoning = await _llm_generate_edit_probes(base_prompt, req.count)
        return EditProbesResponse(
            success=True,
            base_prompt=base_prompt,
            probes=probes,
            reasoning=reasoning,
        )
    except PermissionError as e:
        return EditProbesResponse(
            success=True,
            base_prompt=base_prompt,
            probes=_fallback_edit_probes(base_prompt, req.count),
            reasoning="Returned local probes because upstream model access is restricted.",
            error=str(e),
        )
    except Exception as e:
        return EditProbesResponse(
            success=True,
            base_prompt=base_prompt,
            probes=_fallback_edit_probes(base_prompt, req.count),
            reasoning="Returned local probes due to upstream failure.",
            error=f"Probe generation failed: {e}",
        )


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
