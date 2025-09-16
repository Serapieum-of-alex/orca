from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel, ValidationError as PydanticValidationError

from orca.core.graph import Graph
from orca.core.runner import GraphRunner
from orca.nodes.human_gate import HumanGateNode
from orca.nodes.python_function import PythonFunctionNode


class InModel(BaseModel):
    text: str


class MidModel(BaseModel):
    text: str
    length: int


class OutModel(BaseModel):
    summary: str


class TestGraphRunnerRun:
    def test_happy_path_linear_run(self, fake_persistence) -> None:
        """Run a simple 2-node pipeline; expect finished status, final output, checkpoints, and events sequence.

        Inputs:
        - Graph: In -> Mid (length) -> Out (summary)
        - Initial input: In(text="hello")

        Expected:
        - status == "finished"
        - output is Out with expected summary text
        - persistence contains checkpoint for each node and final status "finished"
        - events include run_started, node_started/finished for both nodes, and run_finished
        - state.node_outputs contains dict dumps for each node
        """
        g = Graph()

        def step_len(inp: InModel, _state) -> MidModel:
            return MidModel(text=inp.text, length=len(inp.text))

        def step_summary(inp: MidModel, _state) -> OutModel:
            return OutModel(summary=f"{inp.text.upper()} ({inp.length} chars)")

        n1 = PythonFunctionNode("length", InModel, MidModel, step_len)
        n2 = PythonFunctionNode("summary", MidModel, OutModel, step_summary)
        g.add_node(n1)
        g.add_node(n2)
        g.connect("length", "summary")
        g.set_entry("length")

        runner = GraphRunner(persistence=fake_persistence)
        res = asyncio.run(runner.run(g, InModel(text="hello")))

        assert res.status == "finished"
        assert isinstance(res.output, OutModel)
        assert "HELLO" in res.output.summary
        assert fake_persistence.status[res.run_id] == "finished"

        # Two checkpoints: after each node
        ck_nodes = [node for (rid, node, _js) in fake_persistence.checkpoints if rid == res.run_id]
        assert ck_nodes == ["length", "summary"]

        # Events sanity: there should be at least these types in order
        types = [e["type"] for e in fake_persistence.events if e["run_id"] == res.run_id]
        assert types[0] == "run_started"
        assert "node_started" in types and "node_finished" in types and types[-1] == "run_finished"

        # node_outputs are dicts (model_dump)
        assert "length" in res.state.node_outputs and "summary" in res.state.node_outputs
        assert isinstance(res.state.node_outputs["length"], dict)

    def test_human_gate_pause_waiting(self, fake_persistence) -> None:
        """Graph pauses at HumanGate; expect waiting status, checkpoint saved at gate, and pending input stored.

        Inputs:
        - Graph: In -> Mid(length) -> Gate(Mid) -> Out
        - Initial input: In(text="ok")

        Expected:
        - run returns RunResult with status "waiting"
        - persistence status is updated to "waiting" and a checkpoint exists at gate node
        - an event human_gate_pending is recorded
        - state.context contains key pending_input:gate with the MidModel payload
        """
        g = Graph()

        def step_len(inp: InModel, _state) -> MidModel:
            return MidModel(text=inp.text, length=len(inp.text))

        n1 = PythonFunctionNode("length", InModel, MidModel, step_len)
        gate = HumanGateNode("approve", MidModel)
        n3 = PythonFunctionNode("finish", MidModel, OutModel, lambda m, _s: OutModel(summary=m.text))
        for n in (n1, gate, n3):
            g.add_node(n)
        g.connect("length", "approve")
        g.connect("approve", "finish")
        g.set_entry("length")

        runner = GraphRunner(persistence=fake_persistence)
        res = asyncio.run(runner.run(g, InModel(text="ok")))

        assert res.status == "waiting"
        assert fake_persistence.status[res.run_id] == "waiting"
        # Last checkpoint should be at the gate
        assert fake_persistence.checkpoints[-1][1] == "approve"
        # Event contains human_gate_pending
        types = [e["type"] for e in fake_persistence.events if e["run_id"] == res.run_id]
        assert "human_gate_pending" in types
        # Pending input stored
        key = "pending_input:approve"
        assert key in res.state.context
        assert res.state.context[key]["text"] == "ok"

    def test_resume_from_checkpoint(self, fake_persistence) -> None:
        """Resume a previously paused run at a human gate; expect the run to finish.

        Procedure:
        1) Run graph until HumanGate pauses (waiting).
        2) Resume using the same persistence and run_id.

        Expected:
        - second run returns status "finished"
        - output is produced by the downstream node
        - run_started event exists twice (once per invocation)
        - status transitions from waiting -> running -> finished
        """
        g = Graph()

        def step_len(inp: InModel, _state) -> MidModel:
            return MidModel(text=inp.text, length=len(inp.text))

        n1 = PythonFunctionNode("length", InModel, MidModel, step_len)
        gate = HumanGateNode("approve", MidModel)
        n3 = PythonFunctionNode("finish", MidModel, OutModel, lambda m, _s: OutModel(summary=f"done:{m.text}"))
        for n in (n1, gate, n3):
            g.add_node(n)
        g.connect("length", "approve")
        g.connect("approve", "finish")
        g.set_entry("length")

        runner = GraphRunner(persistence=fake_persistence)
        first = asyncio.run(runner.run(g, InModel(text="resume")))
        assert first.status == "waiting"
        run_id = first.run_id

        # Now resume
        second = asyncio.run(runner.run(g, None, resume_from_checkpoint=run_id))  # type: ignore[arg-type]
        assert second.status == "finished"
        assert isinstance(second.output, OutModel) and second.output.summary == "done:resume"
        assert fake_persistence.status[run_id] == "finished"
        # Two run_started events (two invocations)
        types = [e["type"] for e in fake_persistence.events if e["run_id"] == run_id]
        assert types.count("run_started") == 2

    def test_node_failure_emits_and_raises(self, fake_persistence) -> None:
        """A node that raises should cause node_failed event, persistence status 'failed', and re-raise the error."""
        g = Graph()

        def boom(_inp: InModel, _s) -> OutModel:
            raise ValueError("nope")

        n = PythonFunctionNode("bad", InModel, OutModel, boom)
        g.add_node(n)
        g.set_entry("bad")

        runner = GraphRunner(persistence=fake_persistence)
        with pytest.raises(ValueError):
            asyncio.run(runner.run(g, InModel(text="x")))
        # node_failed recorded and status failed
        types = [e["type"] for e in fake_persistence.events]
        assert "node_failed" in types
        # Ensure the run_id matches the status map
        run_ids = {e["run_id"] for e in fake_persistence.events}
        assert any(fake_persistence.status[rid] == "failed" for rid in run_ids)

    def test_input_validation_error(self, fake_persistence) -> None:
        """If initial input doesn't conform to the entry node's input model, a Pydantic ValidationError is raised.

        Note: This happens before node execution; there is no node_failed event and run status remains 'running'.
        """
        g = Graph()
        n = PythonFunctionNode("length", InModel, MidModel, lambda i, _s: MidModel(text=i.text, length=len(i.text)))
        g.add_node(n)
        g.set_entry("length")

        class Wrong(BaseModel):
            pass

        runner = GraphRunner(persistence=fake_persistence)
        with pytest.raises(PydanticValidationError):
            asyncio.run(runner.run(g, Wrong()))
        types = [e["type"] for e in fake_persistence.events]
        assert types == ["run_started"]  # no node_started
        # Status remains 'running' because failure occurred outside node try/except
        run_ids = {e["run_id"] for e in fake_persistence.events}
        assert all(fake_persistence.status[rid] == "running" for rid in run_ids)

    def test_output_validation_error(self, fake_persistence) -> None:
        """If a node returns a value that doesn't match its output model, output validation raises.

        Expected:
        - node_started is emitted, but node_finished and checkpoint_saved are not
        - status stays 'running' because exception is thrown after try/except block
        """
        g = Graph()

        def bad_out(_i: InModel, _s):
            return {"not": "valid"}  # missing required field for OutModel

        n = PythonFunctionNode("bad_out", InModel, OutModel, bad_out)
        g.add_node(n)
        g.set_entry("bad_out")

        runner = GraphRunner(persistence=fake_persistence)
        with pytest.raises(PydanticValidationError):
            asyncio.run(runner.run(g, InModel(text="t")))

        types = [e["type"] for e in fake_persistence.events]
        assert "node_started" in types
        assert "node_finished" not in types
        assert "checkpoint_saved" not in types
