from __future__ import annotations

from typing import Generic, Type, TypeVar

from pydantic import BaseModel

from ..core.node import Node
from ..core.state import RunState

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


class LLMNode(Node[I, O], Generic[I, O]):
    """Minimal LLM abstraction stub. Currently acts as identity.

    In real usage, it would call an LLM provider; for tests we keep deterministic.
    """

    def __init__(self, name: str, input_model: Type[I], output_model: Type[O]):
        super().__init__(name, input_model, output_model)

    async def run(self, input: I, state: RunState) -> O:  # type: ignore[override]
        return input  # type: ignore[return-value]


__all__ = ["LLMNode"]
