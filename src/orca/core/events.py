from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

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


__all__ = ["Event", "EventType"]
