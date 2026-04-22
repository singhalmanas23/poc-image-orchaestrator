from typing import Literal, Optional
from typing_extensions import TypedDict


class ViewFrame(TypedDict, total=False):
    angle: str          # human label, e.g. "front", "three-quarter right"
    degrees: int        # 0..315, yaw around the subject
    image_url: str
    cost: Optional[float]
    latency_ms: Optional[int]
    error: Optional[str]


class OrchestratorState(TypedDict, total=False):
    # --- Input ---
    user_prompt: str
    input_image_url: Optional[str]  # For editing: URL or base64 of source image
    priority: Literal["quality", "speed", "cost"]
    transparent_background: Optional[bool]  # If True, prefer a model that outputs alpha
    multi_view: Optional[bool]   # If True, generate a 360° set of angles
    num_views: Optional[int]     # How many angles to generate (default 8)

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
    views: Optional[list[ViewFrame]]   # Populated when multi_view was requested
    error: Optional[str]
