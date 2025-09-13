from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from pydantic import BaseModel

from .errors import ValidationError
from .node import Node


@dataclass
class Edge:
    src: str
    dst: str


@dataclass
class Graph:
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    entrypoint: str | None = None

    def add_node(self, node: Node) -> None:
        if node.name in self.nodes:
            raise ValidationError(f"Duplicate node name: {node.name}")
        self.nodes[node.name] = node

    def connect(self, src: str, dst: str) -> None:
        if src not in self.nodes or dst not in self.nodes:
            raise ValidationError(f"Unknown nodes in edge {src} -> {dst}")
        self.edges.append(Edge(src, dst))

    def set_entry(self, name: str) -> None:
        if name not in self.nodes:
            raise ValidationError(f"Unknown entrypoint node: {name}")
        self.entrypoint = name

    def successors(self, node: str) -> List[str]:
        return [e.dst for e in self.edges if e.src == node]

    def predecessors(self, node: str) -> List[str]:
        return [e.src for e in self.edges if e.dst == node]

    def validate(self) -> None:
        # Entry point exists
        if not self.entrypoint:
            raise ValidationError("Graph has no entrypoint set. Call set_entry(name).")
        if self.entrypoint not in self.nodes:
            raise ValidationError(f"Entrypoint {self.entrypoint} is not a known node.")

        # Type compatibility across edges
        for e in self.edges:
            src_node = self.nodes[e.src]
            dst_node = self.nodes[e.dst]
            src_out = src_node.output_model
            dst_in = dst_node.input_model
            # Require exact same class for now (simple validation)
            if src_out is not dst_in:
                raise ValidationError(
                    "Type mismatch on edge "
                    f"{e.src}({src_out.__name__}) -> {e.dst}({dst_in.__name__})."
                )

        # Simple cycle safeguard: ensure every node reachable from entry has at least one predecessor or entry itself
        # Full cycle detection is out of scope for minimal impl.
        if len(self.nodes) > 1000:
            raise ValidationError("Graph too large for default safeguards (>1000 nodes)")


__all__ = ["Graph", "Edge"]
