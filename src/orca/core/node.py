from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Generic, Optional, Type, TypeVar

from pydantic import BaseModel

from orca.core.errors import ErrorPolicy
from orca.core.state import RunState

__all__ = ["Node", "Budget", "I", "O"]


I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


@dataclass(slots=True)
class Budget:
    max_seconds: Optional[float] = None
    max_tokens: Optional[int] = None
    max_cost: Optional[float] = None


class Node(Generic[I, O], metaclass=abc.ABCMeta):
    name: str
    input_model: Type[I]
    output_model: Type[O]
    error_policy: ErrorPolicy
    budget: Budget

    def __init__(
        self,
        name: str,
        input_model: Type[I],
        output_model: Type[O],
        *,
        error_policy: Optional[ErrorPolicy] = None,
        budget: Optional[Budget] = None,
    ) -> None:
        self.name = name
        self.input_model = input_model
        self.output_model = output_model
        self.error_policy = error_policy or ErrorPolicy()
        self.budget = budget or Budget()

    @abc.abstractmethod
    async def run(self, input: I, state: RunState) -> O:  # noqa: A003 - 'input' is domain-specific term
        """Execute node logic asynchronously and return typed output."""

