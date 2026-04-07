"""
LangGraph workflow assembly — builds the full orchestration graph.
"""

from langgraph.graph import StateGraph, START, END

from app.graph.state import OrchestratorState
from app.graph.nodes import (
    analyze_intent_node,
    route_model_node,
    generate_image_node,
    edit_image_node,
    inpaint_image_node,
    return_result_node,
)
from app.graph.edges import route_after_analysis, route_after_edit_routing


def build_workflow():
    """Build and compile the LangGraph orchestration workflow."""

    graph = StateGraph(OrchestratorState)

    # --- Add nodes ---
    graph.add_node("analyze_intent", analyze_intent_node)
    graph.add_node("route_model_generate", route_model_node)
    graph.add_node("route_model_edit", route_model_node)
    graph.add_node("generate_image", generate_image_node)
    graph.add_node("edit_image", edit_image_node)
    graph.add_node("inpaint_image", inpaint_image_node)
    graph.add_node("return_result", return_result_node)

    # --- Add edges ---

    # START → analyze intent
    graph.add_edge(START, "analyze_intent")

    # analyze_intent → conditional: generate path or edit path
    graph.add_conditional_edges(
        "analyze_intent",
        route_after_analysis,
        {
            "route_model_generate": "route_model_generate",
            "route_model_edit": "route_model_edit",
            "return_result": "return_result",  # error case
        },
    )

    # Generation path: route → generate → result
    graph.add_edge("route_model_generate", "generate_image")
    graph.add_edge("generate_image", "return_result")

    # Edit path: route → conditional (instruction vs mask)
    graph.add_conditional_edges(
        "route_model_edit",
        route_after_edit_routing,
        {
            "edit_image": "edit_image",
            "inpaint_image": "inpaint_image",
            "return_result": "return_result",  # error case
        },
    )
    graph.add_edge("edit_image", "return_result")
    graph.add_edge("inpaint_image", "return_result")

    # return_result → END
    graph.add_edge("return_result", END)

    return graph.compile()


# Singleton compiled workflow
orchestrator = build_workflow()
