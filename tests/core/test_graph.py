from __future__ import annotations

import pytest
from pydantic import BaseModel

from orca.core.errors import ValidationError
from orca.core.graph import Graph
from orca.core.node import Node
from orca.core.state import RunState


class A(BaseModel):
    a: int


class B(BaseModel):
    b: int


class EchoNode(Node[A, A]):
    async def run(self, input: A, state: RunState) -> A:
        return input


class EchoNodeB(Node[B, B]):
    async def run(self, input: B, state: RunState) -> B:
        return input


class TestGraphAddNode:
    def test_add_node_success(self) -> None:
        """Add a node with a unique name; expect it to appear in graph.nodes."""
        g = Graph()
        n = EchoNode("n1", A, A)
        g.add_node(n)
        assert "n1" in g.nodes and g.nodes["n1"] is n

    def test_duplicate_node_raises(self) -> None:
        """Add two nodes with the same name; expect ValidationError about duplicate name."""
        g = Graph()
        n1 = EchoNode("dup", A, A)
        g.add_node(n1)
        with pytest.raises(ValidationError) as ei:
            g.add_node(EchoNode("dup", A, A))
        assert "Duplicate node name" in str(ei.value)


class TestGraphConnect:
    def test_connect_unknown_nodes_raises(self) -> None:
        """Connect where src or dst isn't in graph.nodes; expect ValidationError identifying unknown nodes."""
        g = Graph()
        with pytest.raises(ValidationError) as ei:
            g.connect("a", "b")
        assert "Unknown nodes in edge" in str(ei.value)

    def test_connect_success(self) -> None:
        """Connect two existing nodes; edge list should contain the new edge."""
        g = Graph()
        n1, n2 = EchoNode("n1", A, A), EchoNode("n2", A, A)
        g.add_node(n1)
        g.add_node(n2)
        g.connect("n1", "n2")
        assert len(g.edges) == 1 and g.edges[0].src == "n1" and g.edges[0].dst == "n2"


class TestGraphSetEntry:
    def test_set_entry_success(self) -> None:
        """Set entrypoint to an existing node; property should reflect the assignment."""
        g = Graph()
        n = EchoNode("start", A, A)
        g.add_node(n)
        g.set_entry("start")
        assert g.entrypoint == "start"

    def test_set_entry_unknown_raises(self) -> None:
        """Set entrypoint to a name not in nodes; expect ValidationError mentioning the name."""
        g = Graph()
        with pytest.raises(ValidationError) as ei:
            g.set_entry("nope")
        assert "Unknown entrypoint node" in str(ei.value)


class TestGraphSuccessorsPredecessors:
    def test_lists(self) -> None:
        """Create a small chain n1->n2->n3 and verify successors and predecessors lists for each node."""
        g = Graph()
        n1, n2, n3 = EchoNode("n1", A, A), EchoNode("n2", A, A), EchoNode("n3", A, A)
        for n in (n1, n2, n3):
            g.add_node(n)
        g.connect("n1", "n2")
        g.connect("n2", "n3")
        assert g.successors("n1") == ["n2"]
        assert g.successors("n2") == ["n3"]
        assert g.successors("n3") == []
        assert g.predecessors("n1") == []
        assert g.predecessors("n2") == ["n1"]
        assert g.predecessors("n3") == ["n2"]


class TestGraphValidate:
    def test_no_entrypoint_raises(self) -> None:
        """Graph without entrypoint should fail validation with a helpful message about set_entry."""
        g = Graph()
        g.add_node(EchoNode("n1", A, A))
        with pytest.raises(ValidationError) as ei:
            g.validate()
        assert "Graph has no entrypoint" in str(ei.value)

    def test_unknown_entrypoint_raises(self) -> None:
        """Entrypoint set to a name not present should raise with that name in the message."""
        g = Graph()
        g.entrypoint = "ghost"
        with pytest.raises(ValidationError) as ei:
            g.validate()
        assert "Entrypoint ghost is not a known node" in str(ei.value)

    def test_type_mismatch_edge_raises(self) -> None:
        """Connect A->B where types differ; expect ValidationError that includes both type names and node names."""
        g = Graph()
        n1 = EchoNode("a", A, A)
        n2 = EchoNodeB("b", B, B)
        g.add_node(n1)
        g.add_node(n2)
        g.connect("a", "b")
        g.set_entry("a")
        with pytest.raises(ValidationError) as ei:
            g.validate()
        msg = str(ei.value)
        assert "Type mismatch on edge" in msg and "a(A)" in msg and "b(B)" in msg

    def test_valid_graph_passes(self) -> None:
        """Simple 1-edge graph with matching types should validate without errors."""
        g = Graph()
        n1, n2 = EchoNode("n1", A, A), EchoNode("n2", A, A)
        g.add_node(n1)
        g.add_node(n2)
        g.connect("n1", "n2")
        g.set_entry("n1")
        g.validate()  # no exception

    def test_size_safeguard(self) -> None:
        """Graphs with >1000 nodes should fail validation due to safeguard, even if otherwise valid."""
        g = Graph()
        # Add 1001 nodes of the same type
        for i in range(1001):
            g.add_node(EchoNode(f"n{i}", A, A))
        g.set_entry("n0")
        with pytest.raises(ValidationError) as ei:
            g.validate()
        assert "Graph too large" in str(ei.value)
