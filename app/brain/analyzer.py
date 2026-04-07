import json

import httpx

from app.config import get_settings
from app.brain.prompts import INTENT_ANALYSIS_SYSTEM_PROMPT
from app.graph.state import OrchestratorState

ANALYSIS_FUNCTION = {
    "name": "task_analysis",
    "description": "Structured analysis of the user's image generation or editing request",
    "parameters": {
        "type": "object",
        "properties": {
            "task_type": {
                "type": "string",
                "enum": ["generate", "edit"],
            },
            "needs_text_rendering": {"type": "boolean"},
            "style": {
                "type": "string",
                "enum": ["photorealistic", "artistic", "vector", "product_shot"],
            },
            "needs_svg_vector": {"type": "boolean"},
            "edit_type": {
                "type": "string",
                "enum": [
                    "color_change",
                    "background",
                    "object_modify",
                    "text_edit",
                    "style_transfer",
                    "inpaint",
                ],
                "nullable": True,
            },
            "needs_mask": {"type": "boolean"},
            "optimized_prompt": {"type": "string"},
        },
        "required": [
            "task_type",
            "needs_text_rendering",
            "style",
            "needs_svg_vector",
            "needs_mask",
            "optimized_prompt",
        ],
    },
}


async def analyze_intent(state: OrchestratorState) -> dict:
    """LLM brain node: uses OpenAI GPT-4o to analyze user prompt and extract structured intent."""
    settings = get_settings()

    user_message = state["user_prompt"]
    if state.get("input_image_url"):
        user_message += "\n\n[User has provided an existing image for editing]"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.brain_model,
                "messages": [
                    {"role": "system", "content": INTENT_ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": ANALYSIS_FUNCTION,
                    }
                ],
                "tool_choice": {
                    "type": "function",
                    "function": {"name": "task_analysis"},
                },
            },
        )
        response.raise_for_status()
        data = response.json()

    # Extract function call result
    tool_calls = data["choices"][0]["message"].get("tool_calls", [])
    if tool_calls:
        analysis = json.loads(tool_calls[0]["function"]["arguments"])
        return {
            "task_type": analysis["task_type"],
            "needs_text_rendering": analysis["needs_text_rendering"],
            "style": analysis["style"],
            "needs_svg_vector": analysis["needs_svg_vector"],
            "edit_type": analysis.get("edit_type"),
            "needs_mask": analysis["needs_mask"],
            "optimized_prompt": analysis["optimized_prompt"],
        }

    return {"error": "Brain failed to produce structured analysis"}
