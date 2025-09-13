from __future__ import annotations

from typing import Generic, Iterable, List, Sequence, Type, TypeVar

from pydantic import BaseModel

from ..core.node import Node
from ..core.state import RunState

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


class MapNode(Node[I, O], Generic[I, O]):
    """Fan-out stub: returns input unchanged. Real impl would map over a collection."""

    def __init__(self, name: str, input_model: Type[I], output_model: Type[O]):
        super().__init__(name, input_model, output_model)

    async def run(self, input: I, state: RunState) -> O:  # type: ignore[override]
        return input  # type: ignore[return-value]


__all__ = ["MapNode"]
