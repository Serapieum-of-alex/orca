from __future__ import annotations

from typing import Awaitable, Callable, Generic, Type, TypeVar

from pydantic import BaseModel, TypeAdapter

from orca.core.node import Node
from orca.core.state import RunState

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


class ToolNode(Node[I, O], Generic[I, O]):
    """Wrap a whitelisted tool function as a Node (minimal stub)."""

    def __init__(
        self,
        name: str,
        input_model: Type[I],
        output_model: Type[O],
        tool_fn: Callable[[I, RunState], O | Awaitable[O]],
    ) -> None:
        super().__init__(name, input_model, output_model)
        self._tool = tool_fn
        self._out_adapter: TypeAdapter[O] = TypeAdapter(output_model)

    async def run(self, input: I, state: RunState) -> O:  # noqa: A003
        res = self._tool(input, state)
        if hasattr(res, "__await__"):
            res = await res  # type: ignore[assignment]
        return self._out_adapter.validate_python(res)  # type: ignore[return-value]


__all__ = ["ToolNode"]
