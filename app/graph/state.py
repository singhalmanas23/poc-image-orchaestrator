from typing import Literal, Optional
from typing_extensions import TypedDict


class OrchestratorState(TypedDict, total=False):
    # --- Input ---
    user_prompt: str
    input_image_url: Optional[str]  # For editing: URL or base64 of source image
    priority: Literal["quality", "speed", "cost"]
    transparent_background: Optional[bool]  # If True, prefer a model that outputs alpha

    # --- Brain output (intent analysis) ---
    task_type: Optional[Literal["generate", "edit"]]
    needs_text_rendering: Optional[bool]
    style: Optional[Literal["photorealistic", "artistic", "vector", "product_shot"]]
    needs_svg_vector: Optional[bool]
    edit_type: Optional[
        Literal[
            "color_change",
            "background",
            "object_modify",
            "text_edit",
            "style_transfer",
            "inpaint",
        ]
    ]
    needs_mask: Optional[bool]
    optimized_prompt: Optional[str]

    # --- Router output ---
    selected_model: Optional[str]
    selected_provider: Optional[str]
    selection_reasoning: Optional[str]

    # --- Execution output ---
    output_image_url: Optional[str]
    image_id: Optional[str]
    cost: Optional[float]
    latency_ms: Optional[int]
    error: Optional[str]
