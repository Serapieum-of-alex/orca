from __future__ import annotations

from typing import Any


def wrap_llamaindex_as_node(obj: Any) -> Any:
    """Stub: wrap a LlamaIndex object as a Node. Returns the object unchanged."""
    return obj


def expose_graph_as_llamaindex_tool(graph: Any) -> Any:
    """Stub: expose an Orca graph as a LlamaIndex tool. Returns the graph unchanged."""
    return graph


__all__ = ["wrap_llamaindex_as_node", "expose_graph_as_llamaindex_tool"]
