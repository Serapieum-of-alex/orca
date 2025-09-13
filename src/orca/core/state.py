from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .events import Event


class RunMetadata(BaseModel):
    schema_version: str = "1.0"
    seed: Optional[int] = None
    total_tokens: int = 0
    total_cost: float = 0.0


class RunState(BaseModel):
    """Versioned, JSON-serializable run state."""

    run_id: str
    context: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    events: List[Event] = Field(default_factory=list)
    node_outputs: Dict[str, Any] = Field(default_factory=dict)
    metadata: RunMetadata = Field(default_factory=RunMetadata)

    model_config = {
        "frozen": False,
        "extra": "ignore",
        "ser_json_timedelta": "float",
        "ser_json_bytes": "base64",
    }


__all__ = ["RunState", "RunMetadata"]
