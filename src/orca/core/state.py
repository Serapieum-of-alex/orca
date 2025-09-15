from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from orca.core.events import Event

__all__ = ["RunState", "RunMetadata"]


class RunMetadata(BaseModel):
    """Metadata about a run used for observability and reproducibility.

    Attributes:
        schema_version: Version of the RunState schema for forwards/backwards compatibility.
        seed: Optional seed used for deterministic behavior.
        total_tokens: Aggregate token usage across nodes.
        total_cost: Aggregate cost in your chosen currency units.

    Examples:
        - Construct metadata with a custom seed
            ```python
            >>> from orca.core.state import RunMetadata
            >>> m = RunMetadata(seed=123)
            >>> (m.schema_version, m.seed)
            ('1.0', 123)

            ```
    """

    schema_version: str = "1.0"
    seed: Optional[int] = None
    total_tokens: int = 0
    total_cost: float = 0.0


class RunState(BaseModel):
    """Versioned, JSON-serializable run state.

    RunState is passed to every node and persisted in checkpoints. It collects
    per-node outputs, events, context variables, and artifacts.

    Attributes:
        run_id: Unique identifier of the run.
        context: Arbitrary JSON-serializable auxiliary data, used by nodes.
        artifacts: User-defined artifacts produced during a run.
        events: Event log collected during the run.
        node_outputs: Mapping of node name to its last output (as plain dicts).
        metadata: High-level metadata including schema version and accounting.

    Examples:
        - Create a fresh state and add a value to context
            ```python
            >>> from orca.core.state import RunState
            >>> s = RunState(run_id="r1")
            >>> s.context["greeting"] = "hello"
            >>> (s.run_id, s.context["greeting"])  # check stored values
            ('r1', 'hello')

            ```
        - Serialize to and from JSON (round-trip)
            ```python
            >>> json_str = s.model_dump_json()
            >>> s2 = RunState.model_validate_json(json_str)
            >>> s2.run_id
            'r1'

            ```

    See Also:
        - orca.core.runner.GraphRunner: Produces and consumes RunState during execution.
    """

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
