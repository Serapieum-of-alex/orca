from __future__ import annotations

from typing import Any

# Optional stub: Only define adapter functions if langgraph/langchain is available.


def wrap_orca_graph_as_langgraph(graph: Any) -> Any:
    """Return a stub that represents a LangGraph-compatible wrapper.

    This is a placeholder to satisfy API surface; real integration requires langgraph.
    """
    return graph


def wrap_langgraph_as_orca(langgraph_flow: Any) -> Any:
    """Return a stub that represents an Orca Graph wrapper around a LangGraph flow."""
    return langgraph_flow


__all__ = ["wrap_orca_graph_as_langgraph", "wrap_langgraph_as_orca"]
