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
    """Execution limits for a single Node invocation.

    The Budget object describes optional soft limits that an implementation of
    Node.run may use to constrain its work (e.g., LLM call durations, token
    counts, or costs). It does not enforce limits by itself; enforcement is up to
    concrete Node implementations or surrounding infrastructure.

    Attributes:
        max_seconds (Optional[float]):
            Maximum wall-clock time in seconds the node should spend producing an
            output. None means "no time limit".
        max_tokens (Optional[int]):
            Maximum number of model tokens the node should consume (useful for
            LLM-backed nodes). None means "no token limit".
        max_cost (Optional[float]):
            Maximum monetary cost allowed for the node run (if applicable). None
            means "no cost limit".

    Examples:
        - Create a budget that asks a node to finish within 2 seconds and under
          1000 tokens.
            ```python
            >>> from orca.core.node import Budget
            >>> b = Budget(max_seconds=2.0, max_tokens=1000)
            >>> print(b.max_seconds)
            2.0

            ```
        - A budget with no limits (all fields are None).
            ```python
            >>> Budget()  # doctest: +ELLIPSIS
            Budget(max_seconds=None, max_tokens=None, max_cost=None)

            ```
    """

    max_seconds: Optional[float] = None
    max_tokens: Optional[int] = None
    max_cost: Optional[float] = None


class Node(Generic[I, O], metaclass=abc.ABCMeta):
    """Abstract, typed processing unit in a Graph.

    A Node consumes a Pydantic input model ``I`` and asynchronously produces a
    Pydantic output model ``O``. Concrete subclasses implement the ``run``
    coroutine, which may interact with external systems (LLMs, tools, humans,
    etc.). Nodes can optionally honor a ``Budget`` and react to an ``ErrorPolicy``.

    Type Variables:
        I: The Pydantic model type expected as input.
        O: The Pydantic model type produced as output.

    See Also:
        - orca.core.graph.Graph: Container that wires nodes together.
        - orca.core.runner.GraphRunner: Executes a Graph of nodes.

    Examples:
        - Implement and execute a simple node that increments an integer.
            ```python
            >>> import asyncio
            >>> from pydantic import BaseModel
            >>> from orca.core.node import Node, Budget
            >>> from orca.core.state import RunState
            >>> class In(BaseModel):
            ...     x: int
            >>> class Out(BaseModel):
            ...     y: int
            >>> class AddOne(Node[In, Out]):
            ...     async def run(self, input: In, state: RunState) -> Out:  # noqa: A003
            ...         return Out(y=input.x + 1)
            >>> node = AddOne(name="adder", input_model=In, output_model=Out, budget=Budget(max_seconds=1))
            >>> res = asyncio.run(node.run(In(x=41), RunState(run_id="demo")))
            >>> print(res.y)
            42

            ```
        - Demonstrate that the node keeps its configuration (budget, models, name).
            ```python
            >>> from pydantic import BaseModel
            >>> class In(BaseModel):
            ...     x: int
            >>> class Out(BaseModel):
            ...     y: int
            >>> class Echo(Node[In, Out]):
            ...     async def run(self, input: In, state: RunState) -> Out:  # noqa: A003
            ...         return Out(y=input.x)
            >>> n = Echo(name="echo", input_model=In, output_model=Out)
            >>> print(n.name, n.input_model.__name__, n.output_model.__name__)
            echo In Out

            ```
    """

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
        """Construct a Node with its identity, IO types, and policies.

        Args:
            name (str): Unique node name within a Graph.
            input_model (Type[I]): Exact Pydantic model class expected as input.
            output_model (Type[O]): Exact Pydantic model class produced as output.
            error_policy (Optional[ErrorPolicy]): Strategy on how errors should be
                handled by the node implementation. If None, defaults to a new
                ``ErrorPolicy()`` instance.
            budget (Optional[Budget]): Optional soft limits for this node. If None,
                defaults to ``Budget()`` with no limits.

        Raises:
            ValueError: If invalid arguments are provided by a concrete Node
                subclass (this base constructor itself does not validate beyond type hints).

        Examples:
            - Create a node subclass and configure a budget.
                ```python
                >>> from pydantic import BaseModel
                >>> from orca.core.node import Node, Budget
                >>> from orca.core.state import RunState
                >>> class I(BaseModel):
                ...     x: int
                >>> class O(BaseModel):
                ...     y: int
                >>> class PlusOne(Node[I, O]):
                ...     async def run(self, input: I, state: RunState) -> O:  # noqa: A003
                ...         return O(y=input.x + 1)
                >>> n = PlusOne(name="p1", input_model=I, output_model=O, budget=Budget(max_tokens=500))
                >>> print(n.budget.max_tokens)
                500

                ```
        """
        self.name = name
        self.input_model = input_model
        self.output_model = output_model
        self.error_policy = error_policy or ErrorPolicy()
        self.budget = budget or Budget()

    @abc.abstractmethod
    async def run(self, input: I, state: RunState) -> O:  # noqa: A003 - 'input' is domain-specific term
        """Execute node logic asynchronously and return typed output.

        Implement this coroutine in subclasses. The framework validates both the
        input and the output against the declared Pydantic model classes
        (``input_model`` and ``output_model``) when running a Graph.

        Args:
            input (I): Validated input model instance for this node.
            state (RunState): Mutable run state shared across nodes in one run.

        Returns:
            O: The node's output as an instance of ``output_model``.

        Raises:
            orca.core.errors.HumanInputRequired: If the node cannot proceed without
                external input. The GraphRunner catches this and returns a
                waiting status.
            Exception: Any other exception to indicate failure; GraphRunner will
                mark the run as failed and re-raise.

        Examples:
            - Minimal subclass example that doubles an integer.
                ```python
                >>> import asyncio
                >>> from pydantic import BaseModel
                >>> from orca.core.state import RunState
                >>> class I(BaseModel):
                ...     x: int
                >>> class O(BaseModel):
                ...     y: int
                >>> class Doubler(Node[I, O]):
                ...     async def run(self, input: I, state: RunState) -> O:  # noqa: A003
                ...         return O(y=input.x * 2)
                >>> out = asyncio.run(Doubler("dbl", I, O).run(I(x=3), RunState(run_id="r")))
                >>> print(out.y)
                6

                ```
        """
        raise NotImplementedError

