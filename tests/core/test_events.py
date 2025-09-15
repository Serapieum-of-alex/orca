from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from orca.core.events import Event


class TestEventModel:
    def test_default_time_and_fields(self) -> None:
        """Create an Event with minimal fields; ensure utc timestamp is set and defaults are correct."""
        e = Event(type="run_started", run_id="rid")
        assert e.type == "run_started"
        assert e.run_id == "rid"
        assert e.node is None
        assert isinstance(e.time, datetime)
        assert e.time.tzinfo is not None and e.time.tzinfo.utcoffset(e.time) == timezone.utc.utcoffset(e.time)
        assert e.data == {}

    def test_invalid_type_raises(self) -> None:
        """Provide an invalid type literal; expect Pydantic to raise validation error."""
        with pytest.raises(PydanticValidationError):
            Event(type="definitely-not-valid", run_id="rid")  # type: ignore[arg-type]

    def test_serialization_roundtrip(self) -> None:
        """Roundtrip an Event through JSON; resulting object should be equivalent in important fields."""
        e1 = Event(type="node_finished", run_id="r", node="n", data={"ok": True})
        js = e1.model_dump_json()
        e2 = Event.model_validate_json(js)
        assert (e2.type, e2.run_id, e2.node, e2.data) == (e1.type, e1.run_id, e1.node, e1.data)

    def test_all_event_types_constructible(self) -> None:
        """Construct one instance of each allowed event type to ensure the union is covered."""
        types = [
            "run_started",
            "run_finished",
            "node_started",
            "node_finished",
            "node_failed",
            "checkpoint_saved",
            "human_gate_pending",
            "human_gate_approved",
        ]
        for t in types:
            e = Event(type=t, run_id="r")
            assert e.type == t
