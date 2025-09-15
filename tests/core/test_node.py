from __future__ import annotations

import asyncio
import pytest
from pydantic import BaseModel

from orca.core.node import Budget, Node
from orca.core.state import RunState


class TestBudget:
    def test_defaults(self) -> None:
        """Instantiate Budget without args; expect all limits to be None by default."""
        b = Budget()
        assert b.max_seconds is None
        assert b.max_tokens is None
        assert b.max_cost is None

    def test_custom_values(self) -> None:
        """Set all budget limits explicitly; verify they are stored precisely."""
        b = Budget(max_seconds=1.5, max_tokens=100, max_cost=0.25)
        assert (b.max_seconds, b.max_tokens, b.max_cost) == (1.5, 100, 0.25)


class _In(BaseModel):
    x: int


class _Out(BaseModel):
    y: int


class _EchoNode(Node[_In, _In]):
    """Minimal Node subclass that passes input through for testing Node mechanics."""

    async def run(self, input: _In, state: RunState) -> _In:
        return input


class TestNodeAbstract:
    def test_cannot_instantiate_abstract(self) -> None:
        """Attempting to instantiate abstract Node should raise TypeError because run() is abstract."""
        with pytest.raises(TypeError):
            Node("n", _In, _Out)  # type: ignore[abstract]

    def test_subclass_has_attributes_and_run(self) -> None:
        """Subclass of Node should expose name/input_model/output_model and run returns typed output."""
        n = _EchoNode("echo", _In, _In)
        assert n.name == "echo" and n.input_model is _In and n.output_model is _In
        state = RunState(run_id="rid")
        res = asyncio.run(n.run(_In(x=1), state))
        assert isinstance(res, _In) and res.x == 1
