from __future__ import annotations

from typing import Callable, Dict, Generic, List, Tuple, Type, TypeVar

from pydantic import BaseModel

from ..core.node import Node
from ..core.state import RunState

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


class RouterNode(Node[I, O], Generic[I, O]):
    """Route input to one of several downstreams based on a predicate.

    Minimal stub that returns the input unchanged; actual routing is handled by Graph wiring.
    """

    def __init__(self, name: str, input_model: Type[I], output_model: Type[O], predicate: Callable[[I], str]):
        super().__init__(name, input_model, output_model)
        self.predicate = predicate

    async def run(self, input: I, state: RunState) -> O:  # type: ignore[override]
        # In a full impl, we'd record the chosen route and maybe transform input.
        return input  # type: ignore[return-value]


__all__ = ["RouterNode"]
