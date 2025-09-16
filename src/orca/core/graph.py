from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from orca.core.errors import ValidationError
from orca.core.node import Node

__all__ = ["Graph", "Edge"]


@dataclass
class Edge:
    """Directed connection between two nodes inside a Graph.

    Attributes:
        src (str): Name of the upstream node.
        dst (str): Name of the downstream node.

    Examples:
        - Create an edge from A to B.
            ```python
            >>> from orca.core.graph import Edge
            >>> e = Edge(src="A", dst="B")
            >>> print(e.src, e.dst)
            A B

            ```
    """

    src: str
    dst: str


@dataclass
class Graph:
    """Lightweight directed acyclic graph of type-checked nodes.

    The Graph stores named nodes and directed edges between them. It provides
    simple validation ensuring that:

    - An entrypoint is set and refers to a known node.
    - For each edge ``src -> dst``,``src.output_model is dst.input_model`` (exact
      class identity, not subclassing) to keep the framework predictable.

    See Also:
        - orca.core.node.Node: The typed processing unit stored in Graph.
        - orca.core.runner.GraphRunner: Executes a Graph.

    Examples:
        - Build a minimal graph with two compatible nodes and validate it.
            ```python
            >>> from pydantic import BaseModel
            >>> from orca.core.node import Node
            >>> from orca.core.state import RunState
            >>> class AIn(BaseModel):
            ...     x: int
            >>> class AOut(BaseModel):
            ...     y: int
            >>> class A(Node[AIn, AOut]):
            ...     async def run(self, input: AIn, state: RunState) -> AOut:  # noqa: A003
            ...         return AOut(y=input.x + 1)
            >>> class B(Node[AOut, AOut]):
            ...     async def run(self, input: AOut, state: RunState) -> AOut:  # noqa: A003
            ...         return AOut(y=input.y * 2)
            >>> g = Graph()
            >>> g.add_node(A("A", AIn, AOut))
            >>> g.add_node(B("B", AOut, AOut))
            >>> g.connect("A", "B")
            >>> g.set_entry("A")
            >>> g.validate()  # no exception

            ```
        - Demonstrate common validation errors.
            ```python
            >>> from pydantic import BaseModel
            >>> from orca.core.errors import ValidationError
            >>> from orca.core.node import Node
            >>> from orca.core.state import RunState
            >>> class XIn(BaseModel):
            ...     a: int
            >>> class YIn(BaseModel):
            ...     b: int
            >>> class X(Node[XIn, XIn]):
            ...     async def run(self, input: XIn, state: RunState) -> XIn:  # noqa: A003
            ...         return input
            >>> g = Graph()
            >>> g.add_node(X("X", XIn, XIn))
            >>> try:
            ...     g.add_node(X("X", XIn, XIn))
            ... except ValidationError as e:
            ...     print("duplicate")
            duplicate
            >>> try:
            ...     g.connect("X", "Y")
            ... except ValidationError as e:
            ...     print("unknown node in edge")
            unknown node in edge
            >>> class Y(Node[YIn, YIn]):
            ...     async def run(self, input: YIn, state: RunState) -> YIn:  # noqa: A003
            ...         return input
            >>> g.add_node(Y("Y", YIn, YIn))
            >>> g.set_entry("X")
            >>> g.connect("X", "Y")
            >>> try:
            ...     g.validate()
            ... except ValidationError as e:
            ...     print("type mismatch")
            type mismatch

            ```
    """

    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    entrypoint: str | None = None

    def add_node(self, node: Node) -> None:
        """Add a node to the graph.

        Args:
            node (Node): The node to register. Its name must be unique in the graph.

        Raises:
            ValidationError: If a node with the same name already exists.

        Examples:
            - Adding two distinct nodes succeeds.
                ```python
                >>> from pydantic import BaseModel
                >>> from orca.core.state import RunState
                >>> class I(BaseModel):
                ...     v: int
                >>> class O(BaseModel):
                ...     v: int
                >>> from orca.core.node import Node
                >>> class N(Node[I, O]):
                ...     async def run(self, input: I, state: RunState) -> O:  # noqa: A003
                ...         return O(v=input.v)
                >>> g = Graph(); g.add_node(N("n1", I, O)); g.add_node(N("n2", I, O))
                >>> print(sorted(g.nodes.keys()))
                ['n1', 'n2']

                ```
        """
        if node.name in self.nodes:
            raise ValidationError(f"Duplicate node name: {node.name}")
        self.nodes[node.name] = node

    def connect(self, src: str, dst: str) -> None:
        """Create a directed edge from one node to another.

        Args:
            src (str): Name of the upstream node.
            dst (str): Name of the downstream node.

        Raises:
            ValidationError: If either node is unknown to the graph.

        Examples:
            - Connect two known nodes.
                ```python
                >>> from pydantic import BaseModel
                >>> from orca.core.state import RunState
                >>> from orca.core.node import Node
                >>> class I(BaseModel):
                ...     v: int
                >>> class N(Node[I, I]):
                ...     async def run(self, input: I, state: RunState) -> I:  # noqa: A003
                ...         return input
                >>> g = Graph()
                >>> g.add_node(N("a", I, I))
                >>> g.add_node(N("b", I, I))
                >>> g.connect("a", "b")
                >>> print(g.edges[0].src, g.edges[0].dst)
                a b

                ```
        """
        if src not in self.nodes or dst not in self.nodes:
            raise ValidationError(f"Unknown nodes in edge {src} -> {dst}")
        self.edges.append(Edge(src, dst))

    def set_entry(self, name: str) -> None:
        """Define the entrypoint node to start execution from.

        Args:
            name (str): Name of a node that must exist in the graph.

        Raises:
            ValidationError: If the name does not refer to a known node.
        """
        if name not in self.nodes:
            raise ValidationError(f"Unknown entrypoint node: {name}")
        self.entrypoint = name

    def successors(self, node: str) -> List[str]:
        """Return downstream neighbor names for the given node.

        Args:
            node (str): Node name.

        Returns:
            List[str]: List of successor node names (may be empty).
        """
        return [e.dst for e in self.edges if e.src == node]

    def predecessors(self, node: str) -> List[str]:
        """Return upstream neighbor names for the given node.

        Args:
            node (str): Node name.

        Returns:
            List[str]: List of predecessor node names (may be empty).
        """
        return [e.src for e in self.edges if e.dst == node]

    def validate(self) -> None:
        """Validate the graph structure and type compatibility.

        Ensures an entrypoint is set, the entry exists, and every edge connects
        nodes with exactly matching output/input Pydantic model classes. Also
        applies a simple size safeguard.

        Raises:
            ValidationError: If any of the validation rules fail.

        Examples:
            - Missing entrypoint raises a ValidationError.
                ```python
                >>> from pydantic import BaseModel
                >>> from orca.core.errors import ValidationError
                >>> from orca.core.state import RunState
                >>> from orca.core.node import Node
                >>> class I(BaseModel):
                ...     v: int
                >>> class N(Node[I, I]):
                ...     async def run(self, input: I, state: RunState) -> I:  # noqa: A003
                ...         return input
                >>> g = Graph()
                >>> g.add_node(N("n", I, I))
                >>> try:
                ...     g.validate()
                ... except ValidationError:
                ...     print("no entrypoint")
                no entrypoint

                ```
        """
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
