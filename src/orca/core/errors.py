from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class OrcaError(Exception):
    """Base exception for Orca."""


class ValidationError(OrcaError):
    """Graph or model validation error."""


class HumanInputRequired(OrcaError):
    """Raised when a HumanGateNode needs input to proceed."""

    def __init__(self, run_id: str, gate_id: str, message: str = "Human input required"):
        super().__init__(message)
        self.run_id = run_id
        self.gate_id = gate_id
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.message} (run_id={self.run_id}, gate_id={self.gate_id})"


@dataclass(slots=True)
class ErrorPolicy:
    max_retries: int = 0
    base_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 5.0
    jitter: float = 0.1
    fallback_node: Optional[str] = None
    escalate_to_human: bool = False


__all__ = [
    "OrcaError",
    "ValidationError",
    "HumanInputRequired",
    "ErrorPolicy",
]
