from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Generic, Type, TypeVar

from pydantic import BaseModel, TypeAdapter

from orca.core.node import Node
from orca.core.state import RunState

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


class PythonFunctionNode(Node[I, O], Generic[I, O]):
    """Wrap a sync or async Python function as a Node with typed IO.

    The wrapped function signature should be either:
      - def fn(input: I, state: RunState) -> O
      - async def fn(input: I, state: RunState) -> O
    """

    def __init__(
        self,
        name: str,
        input_model: Type[I],
        output_model: Type[O],
        fn: Callable[[I, RunState], O | Awaitable[O]],
    ) -> None:
        super().__init__(name, input_model, output_model)
        self._fn = fn
        self._out_adapter: TypeAdapter[O] = TypeAdapter(output_model)

    async def run(self, input: I, state: RunState) -> O:  # noqa: A003
        res = self._fn(input, state)
        if asyncio.iscoroutine(res):
            res = await res  # type: ignore[assignment]
        # Validate output to ensure type safety
        return self._out_adapter.validate_python(res)  # type: ignore[return-value]


__all__ = ["PythonFunctionNode", "I", "O"]
