from typing import Optional
import json

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import get_settings

router = APIRouter()


class QAPair(BaseModel):
    question: str
    answer: str


MIN_ROUNDS = 5
MAX_ROUNDS = 8


class ClarifyRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Original user prompt")
    qa: list[QAPair] = Field(
        default_factory=list,
        description="Clarifying questions asked so far, paired with the user's answers",
    )
    max_questions: int = Field(default=1, ge=1, le=5)
    min_rounds: int = Field(default=MIN_ROUNDS, ge=1, le=12)
    max_rounds: int = Field(default=MAX_ROUNDS, ge=1, le=15)


class ClarifyResponse(BaseModel):
    success: bool
    questions: list[str]
    done: bool
    rounds_done: int = 0
    min_rounds: int = MIN_ROUNDS
    max_rounds: int = MAX_ROUNDS
    reasoning: Optional[str] = None
    error: Optional[str] = None


CLARIFY_SYSTEM_PROMPT = (
    "You are a product-image briefing assistant running a step-by-step "
    "drill-down interview. The user wants an image of a product; your job "
    "is to extract the precise visual brief by asking ONE focused question "
    "per round and DRILLING INTO each answer before moving on.\n\n"
    "Drill-down rule (most important):\n"
    "- If the user's most recent answer is broad (e.g. ‘red’, ‘leather’, "
    "‘running shoes’, ‘studio’), the NEXT question MUST narrow that exact "
    "attribute further (e.g. red → ‘which red — fire-engine, burgundy, "
    "terracotta, or neon?’; leather → ‘smooth full-grain, suede, patent, or "
    "distressed?’).\n"
    "- Only move to a NEW attribute once the current one is fully specified.\n"
    "- Each question must offer 3–5 concrete options or examples in "
    "parentheses so the user can answer in one word.\n\n"
    "Attribute order to cover (drill each before moving on):\n"
    "1. Product identity & sub-type (e.g. shoe → sneaker / loafer / boot)\n"
    "2. Primary color → exact shade\n"
    "3. Material → finish/texture\n"
    "4. Distinctive details (sole, stitching, hardware, branding)\n"
    "5. Background / scene / surface\n"
    "6. Lighting mood\n"
    "7. Camera angle & framing\n"
    "8. Output usage / aspect ratio\n\n"
    "Each round return STRICT JSON with keys:\n"
    "- questions: list of exactly {max_questions} question string(s) — "
    "single, sharp, with concrete options in parentheses.\n"
    "- done: boolean — set true ONLY after the brief is fully specified "
    "across all attributes above.\n"
    "- reasoning: short string — name which attribute you are drilling and "
    "why (e.g. ‘drilling color shade — user said red, need exact tone’).\n\n"
    "Never re-ask anything already answered. Never bulk-ask multiple "
    "attributes in a single question."
)


def _normalize_question(q: str) -> str:
    s = " ".join(str(q).split()).strip()
    if not s:
        return ""
    if not s.endswith("?"):
        s = s.rstrip(".!") + "?"
    return s


def _dedupe(items: list[str], cap: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        s = _normalize_question(raw)
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= cap:
            break
    return out


async def _llm_clarify(
    prompt: str,
    qa: list[QAPair],
    max_questions: int,
) -> tuple[list[str], bool, str]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    lines = [f"ORIGINAL PRODUCT PROMPT: {prompt}"]
    for i, pair in enumerate(qa, 1):
        lines.append(f"Q{i}: {pair.question}")
        lines.append(f"A{i}: {pair.answer}")
    if qa:
        last = qa[-1]
        lines.append("")
        lines.append(
            f"MOST RECENT ANSWER (drill into THIS unless already exhausted): "
            f"{last.answer!r} — given in response to {last.question!r}"
        )
    convo_text = "\n".join(lines)

    system = CLARIFY_SYSTEM_PROMPT.replace("{max_questions}", str(max_questions))

    body = {
        "model": settings.brain_model,
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": convo_text + "\n\nReturn JSON only."},
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
    parsed = json.loads(raw)

    questions_raw = parsed.get("questions", [])
    done = bool(parsed.get("done", False))
    reasoning = str(parsed.get("reasoning", "")).strip()

    if not isinstance(questions_raw, list):
        questions_raw = []

    questions = _dedupe([str(q) for q in questions_raw], max_questions)
    return questions, done, reasoning


_FALLBACK_LADDER: list[tuple[str, str]] = [
    ("identity", "What exact sub-type of the product is it (e.g. for shoes — sneaker, loafer, running, boot, sandal)?"),
    ("color", "What primary color should it be (e.g. red, navy, black, cream, olive)?"),
    ("shade", "Be more specific about that color — which exact shade (e.g. fire-engine red, burgundy, terracotta, dusty rose)?"),
    ("material", "What primary material is it made of (e.g. full-grain leather, suede, canvas, knit mesh, technical synthetic)?"),
    ("finish", "What finish should that material have (e.g. matte, satin, glossy, distressed, brushed, pebbled)?"),
    ("detail", "What distinctive details must be visible (e.g. stitching, hardware, sole pattern, branding placement)?"),
    ("background", "What background or surface should it sit on (e.g. seamless white studio, raw concrete, oak wood, marble, sand)?"),
    ("lighting", "What lighting mood do you want (e.g. hard studio key, soft north-window, golden-hour, dramatic side-light)?"),
    ("angle", "What camera angle and framing (e.g. 3/4 hero, profile side, top-down flat-lay, low-angle close-up)?"),
    ("usage", "Where will this image be used and what aspect ratio (e.g. 1:1 social, 16:9 web hero, 4:5 catalog)?"),
]


def _fallback_questions(
    prompt: str, qa: list[QAPair], max_questions: int
) -> tuple[list[str], bool]:
    asked_blob = " ".join(pair.question.lower() for pair in qa)
    prompt_blob = prompt.lower()

    picked: list[str] = []
    for keyword, question in _FALLBACK_LADDER:
        if keyword in asked_blob:
            continue
        if keyword in prompt_blob and keyword not in {"shade", "finish"}:
            continue
        picked.append(question)
        if len(picked) >= max_questions:
            break

    done = len(picked) == 0 and len(qa) >= MIN_ROUNDS
    return picked, done


@router.post("/clarify", response_model=ClarifyResponse)
async def clarify(req: ClarifyRequest):
    """Ask the next round of clarifying questions about the user's product prompt.

    The client keeps calling this endpoint — passing the growing Q&A history —
    until the user decides to finalize. Image generation happens separately
    via `/api/generate`, with the Q&A flattened into the prompt.
    """
    base = req.prompt.strip()
    if not base:
        return ClarifyResponse(
            success=False,
            questions=[],
            done=False,
            rounds_done=0,
            min_rounds=req.min_rounds,
            max_rounds=req.max_rounds,
            error="Prompt cannot be empty",
        )

    rounds_done = len(req.qa)
    # Clamp: never declare done before min_rounds; force done at max_rounds.
    force_continue = rounds_done < req.min_rounds
    force_stop = rounds_done >= req.max_rounds

    def finalize(
        questions: list[str], done: bool, reasoning: Optional[str], error: Optional[str] = None
    ) -> ClarifyResponse:
        if force_stop:
            return ClarifyResponse(
                success=True,
                questions=[],
                done=True,
                rounds_done=rounds_done,
                min_rounds=req.min_rounds,
                max_rounds=req.max_rounds,
                reasoning=reasoning or "Reached max rounds — finalize when ready.",
                error=error,
            )
        if force_continue and not questions:
            fq, _ = _fallback_questions(base, req.qa, req.max_questions)
            questions = fq or [
                "What is one more concrete detail about this product you want emphasized?"
            ]
            done = False
            reasoning = (
                reasoning
                or f"Min {req.min_rounds} rounds not yet reached — drilling further."
            )
        if force_continue:
            done = False
        return ClarifyResponse(
            success=True,
            questions=questions,
            done=done,
            rounds_done=rounds_done,
            min_rounds=req.min_rounds,
            max_rounds=req.max_rounds,
            reasoning=reasoning or None,
            error=error,
        )

    try:
        questions, done, reasoning = await _llm_clarify(
            prompt=base, qa=req.qa, max_questions=req.max_questions
        )
        return finalize(questions, done, reasoning)
    except PermissionError as e:
        fq, fdone = _fallback_questions(base, req.qa, req.max_questions)
        return finalize(
            fq,
            fdone,
            "Heuristic clarifying questions (upstream model access restricted).",
            str(e),
        )
    except Exception as e:
        fq, fdone = _fallback_questions(base, req.qa, req.max_questions)
        return finalize(
            fq,
            fdone,
            "Heuristic clarifying questions (upstream failure).",
            f"Clarification failed: {e}",
        )
