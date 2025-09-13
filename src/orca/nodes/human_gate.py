from __future__ import annotations

from typing import Generic, Type, TypeVar

from pydantic import BaseModel

from ..core.events import Event
from ..core.node import Node
from ..core.state import RunState

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


class HumanGateNode(Node[I, O], Generic[I, O]):
    """Minimal stub of a HumanGate that currently passes input through.

    In a full implementation, this would pause execution and await external approval.
    """

    def __init__(self, name: str, model: Type[I]) -> None:
        super().__init__(name=name, input_model=model, output_model=model)

    async def run(self, input: I, state: RunState) -> O:  # type: ignore[override]
        # Emit an event that a human gate was encountered; pass-through for now
        e = Event(type="human_gate_pending", run_id=state.run_id, node=self.name)
        state.events.append(e)
        return input  # type: ignore[return-value]


__all__ = ["HumanGateNode", "I", "O"]
