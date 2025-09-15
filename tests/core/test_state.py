from __future__ import annotations
from orca.core.events import Event
from orca.core.state import RunMetadata, RunState


class TestRunMetadataModel:
    def test_defaults(self) -> None:
        """No inputs. Verify default schema_version, seed, and metering counters."""
        m = RunMetadata()
        assert m.schema_version == "1.0"
        assert m.seed is None
        assert m.total_tokens == 0
        assert m.total_cost == 0.0

    def test_override_values(self) -> None:
        """Construct with explicit values; ensure they are preserved in the model."""
        m = RunMetadata(schema_version="2.0", seed=123, total_tokens=10, total_cost=1.5)
        assert (m.schema_version, m.seed, m.total_tokens, m.total_cost) == ("2.0", 123, 10, 1.5)


class TestRunStateModel:
    def test_defaults_and_mutability(self) -> None:
        """Create a RunState with minimal fields; all containers default to empties and are mutable."""
        s = RunState(run_id="rid")
        assert s.run_id == "rid"
        assert s.context == {}
        assert s.artifacts == {}
        assert s.events == []
        assert s.node_outputs == {}
        # Mutate
        s.context["a"] = 1
        s.artifacts["f"] = b"bytes"
        s.node_outputs["n"] = {"k": "v"}
        assert s.context["a"] == 1 and s.artifacts["f"] == b"bytes" and s.node_outputs["n"]["k"] == "v"

    def test_extras_ignored_and_event_typing(self) -> None:
        """Supply extra fields; they should be ignored. Events list accepts Event models only."""
        e = Event(type="run_started", run_id="rid")
        s = RunState(run_id="rid", events=[e], extra_field_should_be_ignored=True)  # type: ignore[arg-type]
        assert len(s.events) == 1 and isinstance(s.events[0], Event)
        assert not hasattr(s, "extra_field_should_be_ignored")

    def test_json_roundtrip(self) -> None:
        """Roundtrip state via JSON serialization; complex nested structures should survive."""
        e = Event(type="node_finished", run_id="r", node="n", data={"ok": True})
        s1 = RunState(run_id="rid", events=[e])
        s1.context["nums"] = [1, 2, 3]
        js = s1.model_dump_json()
        s2 = RunState.model_validate_json(js)
        assert s2.run_id == s1.run_id and s2.events[0].type == "node_finished"
