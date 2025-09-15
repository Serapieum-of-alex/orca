from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


__all__ = [
    "OrcaError",
    "ValidationError",
    "HumanInputRequired",
    "ErrorPolicy",
]


class OrcaError(Exception):
    """Base exception for Orca.

    This is the root of all custom exceptions raised by the Orca core. Catching
    OrcaError allows you to handle any error produced by the library.

    Examples:
    - Catch any Orca error and inspect its type

        ```python

        >>> from orca.core.errors import OrcaError, ValidationError
        >>> try:
        ...     raise ValidationError("invalid")
        ... except OrcaError as e:
        ...     print(type(e).__name__)
        ValidationError

        ```
    """


class ValidationError(OrcaError):
    """Graph or model validation error.

    Raised when the graph structure or type contracts are violated. For example,
    when connecting two nodes whose output and input models don't match.

    See Also:
        - orca.core.graph.Graph.validate: Performs static validation of a graph.

    Examples:
    - Catch a validation error during graph checks

        ```python

        >>> from pydantic import BaseModel
        >>> from orca.core.graph import Graph
        >>> from orca.nodes.python_function import PythonFunctionNode
        >>> class A(BaseModel):
        ...     x: int
        >>> class B(BaseModel):
        ...     y: int
        >>> def f(inp: A, _state) -> A:  # pass-through
        ...     return inp
        >>> def g(inp: B, _state) -> B:
        ...     return inp
        >>> gph = Graph()
        >>> n1 = PythonFunctionNode("n1", A, A, f)
        >>> n2 = PythonFunctionNode("n2", B, B, g)
        >>> gph.add_node(n1); gph.add_node(n2)
        >>> gph.connect("n1", "n2")
        >>> gph.set_entry("n1")
        >>> try:
        ...     gph.validate()
        ... except ValidationError as e:
        ...     print(type(e).__name__)
        ValidationError

        ```
    """


class HumanInputRequired(OrcaError):
    """Raised when a HumanGateNode needs input to proceed.

    Args:
        run_id: Identifier of the run that is waiting for human input.
        gate_id: Name of the HumanGate node requesting input.
        message: Optional human-readable message describing the requirement.

    Examples:
    - Construct and stringify the exception

        ```python

        >>> from orca.core.errors import HumanInputRequired
        >>> exc = HumanInputRequired(run_id="run-123", gate_id="approve")
        >>> print(str(exc))
        Human input required (run_id=run-123, gate_id=approve)

        ```
    """

    def __init__(self, run_id: str, gate_id: str, message: str = "Human input required"):
        super().__init__(message)
        self.run_id = run_id
        self.gate_id = gate_id
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.message} (run_id={self.run_id}, gate_id={self.gate_id})"


@dataclass(slots=True)
class ErrorPolicy:
    """Configuration for node-level error handling policies.

    Attributes map to common retry/backoff strategies and escalation controls.

    Attributes:
        max_retries: Maximum number of retry attempts for a failing node.
        base_backoff_seconds: Starting backoff delay between retries.
        max_backoff_seconds: Maximum backoff delay.
        jitter: Proportional random jitter to apply to backoff delays.
        fallback_node: Optional name of a node to route to upon failure.
        escalate_to_human: Whether to escalate to a human gate on repeated failure.

    Examples:
    - Create an error policy with a couple of retries

        ```python

        >>> from orca.core.errors import ErrorPolicy
        >>> p = ErrorPolicy(max_retries=2, base_backoff_seconds=0.1)
        >>> (p.max_retries, p.base_backoff_seconds)
        (2, 0.1)

        ```
    """

    max_retries: int = 0
    base_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 5.0
    jitter: float = 0.1
    fallback_node: Optional[str] = None
    escalate_to_human: bool = False
