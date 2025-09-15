from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

__all__ = ["Event", "EventType"]

EventType = Literal[
    "run_started",
    "run_finished",
    "node_started",
    "node_finished",
    "node_failed",
    "checkpoint_saved",
    "human_gate_pending",
    "human_gate_approved",
]


class Event(BaseModel):
    """A single structured occurrence in a run's timeline.

    Events are emitted by the runner and persisted via the configured
    persistence backend. They are useful for observability, debugging, and
    building timelines in UIs.

    Attributes:
        type: The category of event (e.g., "node_started").
        time: UTC timestamp when the event was created.
        run_id: Associated run identifier, if any.
        node: Node name this event pertains to, if any.
        data: Arbitrary JSON-serializable payload with event-specific details.

    Examples:
        - Create and inspect a simple event
            ```python
            >>> from orca.core.events import Event
            >>> e = Event(type="run_started", run_id="r1")
            >>> (e.type, e.run_id, isinstance(e.time, datetime))
            ('run_started', 'r1', True)

            ```
        - Serialize and deserialize an event
            ```python
            >>> payload = e.model_dump()
            >>> isinstance(payload, dict)
            True

            ```

    See Also:
        - orca.core.runner.GraphRunner: Emits events during graph execution.
    """

    type: EventType
    time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: Optional[str] = None
    node: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "frozen": False,
        "extra": "ignore",
        "ser_json_timedelta": "float",
        "ser_json_bytes": "base64",
    }
