from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Protocol

from ..core.events import Event


@dataclass(slots=True)
class RunRecord:
    run_id: str
    status: str


class Persistence(Protocol):
    """Persistence protocol for runs, checkpoints, and events."""

    def init(self) -> None:
        ...

    def create_run(self, run_id: str, metadata: Dict[str, Any]) -> None:
        ...

    def update_run_status(self, run_id: str, status: str) -> None:
        ...

    def list_runs(self) -> Iterable[RunRecord]:
        ...

    def save_checkpoint(self, run_id: str, node: str, state_json: str) -> None:
        ...

    def load_latest_checkpoint(self, run_id: str) -> Optional[tuple[str, str]]:
        """Return (node_name, state_json) for latest checkpoint, if any."""
        ...

    def add_event(self, event: Event) -> None:
        ...

    def get_events(self, run_id: str) -> Iterable[Event]:
        ...


__all__ = ["Persistence", "RunRecord"]
