"""
Conditional edge functions for the LangGraph orchestration graph.
"""

from app.graph.state import OrchestratorState


def route_after_analysis(state: OrchestratorState) -> str:
    """After intent analysis, decide: generate or edit?"""
    if state.get("error"):
        return "return_result"

    task_type = state.get("task_type", "generate")
    if task_type == "edit":
        return "route_model_edit"
    return "route_model_generate"


def route_after_edit_routing(state: OrchestratorState) -> str:
    """After model routing for edits, decide: instruction-based or mask-based?"""
    if state.get("error"):
        return "return_result"

    needs_mask = state.get("needs_mask", False)
    selected_model = state.get("selected_model", "")

    if needs_mask or selected_model == "flux-fill-pro":
        return "inpaint_image"
    return "edit_image"
