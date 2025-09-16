from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import pytest
from pydantic import BaseModel

from orca.persistence.base import Persistence, RunRecord


class FakePersistence(Persistence):
    """In-memory Persistence test double used to observe runner behavior.

    Stores runs, checkpoints, and events in Python data structures for assertions.
    """

    def __init__(self) -> None:
        self.runs: Dict[str, Dict[str, Any]] = {}
        self.status: Dict[str, str] = {}
        self.checkpoints: List[tuple[str, str, str]] = []  # (run_id, node, state_json)
        self.events: List[dict] = []  # store raw dict for simplicity

    def init(self) -> None:  # pragma: no cover - not used directly
        pass

    def create_run(self, run_id: str, metadata: Dict[str, Any]) -> None:
        self.runs[run_id] = metadata
        self.status[run_id] = "running"

    def update_run_status(self, run_id: str, status: str) -> None:
        self.status[run_id] = status

    def list_runs(self) -> Iterable[RunRecord]:  # pragma: no cover - unused in unit tests
        for rid, st in self.status.items():
            yield RunRecord(run_id=rid, status=st)

    def save_checkpoint(self, run_id: str, node: str, state_json: str) -> None:
        self.checkpoints.append((run_id, node, state_json))

    def load_latest_checkpoint(self, run_id: str) -> Optional[tuple[str, str]]:
        for rid, node, state_json in reversed(self.checkpoints):
            if rid == run_id:
                return (node, state_json)
        return None

    def add_event(self, event) -> None:
        # Store a small JSON-serializable snapshot
        self.events.append({
            "run_id": event.run_id,
            "node": event.node,
            "type": event.type,
            "time": event.time,
            "data": event.data,
        })

    def get_events(self, run_id: str) -> Iterable[Any]:  # pragma: no cover - not needed here
        for e in self.events:
            if e["run_id"] == run_id:
                yield e


class InModel(BaseModel):
    text: str


class MidModel(BaseModel):
    text: str
    length: int


class OutModel(BaseModel):
    summary: str


@pytest.fixture
def fake_persistence() -> FakePersistence:
    return FakePersistence()
