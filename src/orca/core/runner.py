from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, TypeAdapter

from .events import Event
from .graph import Graph
from .node import Node
from .state import RunState
from ..observability.hooks import get_event_handlers
from ..persistence.base import Persistence


@dataclass(slots=True)
class RunResult:
    run_id: str
    status: str
    output: Optional[Any]
    state: RunState


class GraphRunner:
    def __init__(self, persistence: Optional[Persistence] = None) -> None:
        self.persistence = persistence

    async def run(
        self,
        graph: Graph,
        initial_input: BaseModel,
        *,
        resume_from_checkpoint: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> RunResult:
        graph.validate()
        rid = run_id or str(uuid.uuid4())
        state = RunState(run_id=rid)

        if self.persistence:
            self.persistence.create_run(rid, metadata=state.metadata.model_dump())
        await self._emit(Event(type="run_started", run_id=rid))

        # For minimal implementation, support a single linear path starting at entrypoint.
        current_node_name = graph.entrypoint
        current_input = initial_input
        last_output: Optional[BaseModel] = None
        adapter_cache: dict[type[BaseModel], TypeAdapter] = {}

        def validate_to_model(model_type: type[BaseModel], value: Any) -> BaseModel:
            adapter = adapter_cache.get(model_type)
            if adapter is None:
                adapter = TypeAdapter(model_type)
                adapter_cache[model_type] = adapter
            return adapter.validate_python(value)

        steps = 0
        while current_node_name is not None:
            steps += 1
            if steps > 10000:
                raise RuntimeError("Iteration cap exceeded (10000)")

            node = graph.nodes[current_node_name]
            # Validate input
            current_input = validate_to_model(node.input_model, current_input)

            await self._emit(Event(type="node_started", run_id=rid, node=node.name))
            # Run node
            try:
                out = await node.run(current_input, state)
            except Exception as e:  # noqa: BLE001 - user node may raise arbitrary exceptions
                await self._emit(
                    Event(type="node_failed", run_id=rid, node=node.name, data={"error": repr(e)})
                )
                if self.persistence:
                    self.persistence.update_run_status(rid, "failed")
                raise

            # Validate output
            out = validate_to_model(node.output_model, out)
            state.node_outputs[node.name] = out.model_dump()
            await self._emit(Event(type="node_finished", run_id=rid, node=node.name))

            # Save checkpoint at node boundary
            if self.persistence:
                self.persistence.save_checkpoint(rid, node.name, state.model_dump_json())
                await self._emit(
                    Event(type="checkpoint_saved", run_id=rid, node=node.name)
                )

            last_output = out
            # Move to successor (if multiple, pick first for minimal impl)
            succ = graph.successors(node.name)
            if len(succ) == 0:
                current_node_name = None
            else:
                current_node_name = succ[0]
                current_input = out

        await self._emit(Event(type="run_finished", run_id=rid))
        if self.persistence:
            self.persistence.update_run_status(rid, "finished")
        return RunResult(run_id=rid, status="finished", output=last_output, state=state)

    async def _emit(self, event: Event) -> None:
        # Persistence
        if self.persistence:
            try:
                self.persistence.add_event(event)
            except Exception:
                pass
        # Local hooks
        for h in get_event_handlers():
            try:
                h(event)
            except Exception:
                pass


__all__ = ["GraphRunner", "RunResult"]
