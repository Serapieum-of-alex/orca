from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, TypeAdapter

from orca.core.events import Event
from orca.core.graph import Graph
from orca.core.state import RunState
from orca.core.errors import HumanInputRequired
from orca.observability.hooks import get_event_handlers
from orca.persistence.base import Persistence


@dataclass(slots=True)
class RunResult:
    """Summary of a Graph execution.

    Attributes:
        run_id (str): Unique identifier of the run.
        status (str): Final status: "finished", "failed", or "waiting" (when a
            human gate pauses the run).
        output (Optional[Any]): The last node's output model instance if finished,
            otherwise None.
        state (RunState): The final run state snapshot (always provided).

    Examples:
        - Create a result manually and inspect its fields.
            ```python
            >>> from orca.core.state import RunState
            >>> rr = RunResult(run_id="r1", status="finished", output=None, state=RunState(run_id="r1"))
            >>> print(rr.run_id, rr.status)
            r1 finished

            ```
    """

    run_id: str
    status: str
    output: Optional[Any]
    state: RunState


class GraphRunner:
    """Execute a Graph node-by-node with validation, events, and checkpoints.

    The runner validates inputs/outputs at each step using Pydantic, emits
    events to observers, and optionally persists checkpoints via a configured
    ``Persistence`` backend. It currently supports a single linear successor per
    node (first successor is picked when multiple exist).

    See Also:
        - orca.core.graph.Graph: The graph to execute.
        - orca.core.node.Node: The typed processing units.
        - orca.persistence.base.Persistence: Optional persistence interface.

    Examples:
        - Successful two-node run that returns a final output.
            ```python
            >>> import asyncio
            >>> from pydantic import BaseModel
            >>> from orca.core.graph import Graph
            >>> from orca.core.node import Node
            >>> from orca.core.state import RunState
            >>> class I(BaseModel):
            ...     x: int
            >>> class M(BaseModel):
            ...     y: int
            >>> class A(Node[I, M]):
            ...     async def run(self, input: I, state: RunState) -> M:  # noqa: A003
            ...         return M(y=input.x + 1)
            >>> class B(Node[M, M]):
            ...     async def run(self, input: M, state: RunState) -> M:  # noqa: A003
            ...         return M(y=input.y * 2)
            >>> g = Graph(); g.add_node(A("A", I, M)); g.add_node(B("B", M, M)); g.connect("A", "B"); g.set_entry("A"); g.validate()
            >>> runner = GraphRunner()
            >>> res = asyncio.run(runner.run(g, I(x=1)))
            >>> print(res.status, res.output.y)
            finished 4

            ```

        - A node that requires human input makes the run return "waiting".
            ```python
            >>> import asyncio
            >>> from pydantic import BaseModel
            >>> from orca.core.errors import HumanInputRequired
            >>> from orca.core.graph import Graph
            >>> from orca.core.node import Node
            >>> from orca.core.state import RunState
            >>> class IO(BaseModel):
            ...     n: int
            >>> class Gate(Node[IO, IO]):
            ...     async def run(self, input: IO, state: RunState) -> IO:  # noqa: A003
            ...         raise HumanInputRequired("Need user confirmation")
            >>> g = Graph(); g.add_node(Gate("G", IO, IO)); g.set_entry("G"); g.validate()
            >>> rr = asyncio.run(GraphRunner().run(g, IO(n=0)))
            >>> print(rr.status in ("waiting", "finished"))  # expected waiting
            True

            ```
    """

    def __init__(self, persistence: Optional[Persistence] = None) -> None:
        """Create a runner.

        Args:
            persistence (Optional[Persistence]): Optional persistence backend used
                to store events, checkpoints, and run metadata. If None, no data
                is persisted but the API behaves the same otherwise.

        Examples:
            - Construct a runner without persistence.
                ```python
                >>> r = GraphRunner(); isinstance(r, GraphRunner)
                True

                ```
        """
        self.persistence = persistence

    async def run(
        self,
        graph: Graph,
        initial_input: BaseModel,
        *,
        resume_from_checkpoint: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> RunResult:
        """Execute the given graph starting at its entrypoint (or resume).

        The runner iterates nodes linearly by following the first successor of
        each node, validating inputs and outputs using the declared Pydantic
        model types on each node. When a node raises ``HumanInputRequired``, the
        run is paused and a waiting ``RunResult`` is returned along with a
        checkpoint (if persistence is configured). You can later resume by
        passing the previous ``run_id`` as ``resume_from_checkpoint``.

        Args:
            graph (Graph): The graph to execute. Must be validated or validatable.
            initial_input (BaseModel): The first node's input model instance.
            resume_from_checkpoint (Optional[str]): If provided and persistence is
                configured, the runner tries to resume from the latest checkpoint
                of that run_id.
            run_id (Optional[str]): Override the generated run_id when starting a
                fresh run. Ignored when resuming.

        Returns:
            RunResult: Outcome of the run including status, last output (if any),
                and final state.

        Raises:
            orca.core.errors.ValidationError: If the graph fails validation.
            RuntimeError: If resuming but no checkpoint is found, or if the
                internal iteration cap is exceeded.
            pydantic.ValidationError: If a node receives invalid input or
                produces an invalid output according to its declared models.
            Exception: Any exception raised by a node (other than
                ``HumanInputRequired``) is propagated after failure is recorded.

        See Also:
            - orca.core.node.Node
            - orca.core.graph.Graph
            - orca.core.runner.RunResult

        Examples:
            - Start a fresh run with one node and inspect the status.
                ```python
                >>> import asyncio
                >>> from pydantic import BaseModel
                >>> from orca.core.graph import Graph
                >>> from orca.core.node import Node
                >>> from orca.core.state import RunState
                >>> class I(BaseModel):
                ...     x: int
                >>> class O(BaseModel):
                ...     y: int
                >>> class Inc(Node[I, O]):
                ...     async def run(self, input: I, state: RunState) -> O:  # noqa: A003
                ...         return O(y=input.x + 1)
                >>> g = Graph(); g.add_node(Inc("inc", I, O)); g.set_entry("inc")
                >>> runner = GraphRunner()
                >>> rr = asyncio.run(runner.run(g, I(x=1)))
                >>> print(rr.status, rr.output.y)
                finished 2

                ```

            - When a node requests human input, the run returns "waiting".
                ```python
                >>> import asyncio
                >>> from pydantic import BaseModel
                >>> from orca.core.errors import HumanInputRequired
                >>> from orca.core.graph import Graph
                >>> from orca.core.node import Node
                >>> from orca.core.state import RunState
                >>> class IO(BaseModel):
                ...     n: int
                >>> class Gate(Node[IO, IO]):
                ...     async def run(self, input: IO, state: RunState) -> IO:  # noqa: A003
                ...         raise HumanInputRequired()
                >>> g = Graph(); g.add_node(Gate("gate", IO, IO)); g.set_entry("gate")
                >>> rr = asyncio.run(GraphRunner().run(g, IO(n=0)))
                >>> print(rr.status)
                waiting

                ```
        """
        graph.validate()
        # Determine whether we are resuming from an existing checkpoint or starting fresh
        adapter_cache: dict[type[BaseModel], TypeAdapter] = {}

        def validate_to_model(model_type: type[BaseModel], value: Any) -> BaseModel:
            adapter = adapter_cache.get(model_type)
            if adapter is None:
                adapter = TypeAdapter(model_type)
                adapter_cache[model_type] = adapter
            return adapter.validate_python(value)

        if resume_from_checkpoint and self.persistence:
            loaded = self.persistence.load_latest_checkpoint(resume_from_checkpoint)
            if not loaded:
                raise RuntimeError(f"No checkpoint found for run_id={resume_from_checkpoint}")
            last_node_name, state_json = loaded
            # Restore state
            state = RunState.model_validate_json(state_json)
            rid = state.run_id
            # Choose successor of last checkpointed node as the next node
            succ = graph.successors(last_node_name)
            current_node_name = None if not succ else succ[0]
            # Determine current_input from either the last node's output or pending gate input
            pending_key = f"pending_input:{last_node_name}"
            if last_node_name in state.node_outputs:
                current_input = state.node_outputs[last_node_name]
            elif pending_key in state.context:
                current_input = state.context[pending_key]
            else:
                # Fall back to provided initial_input (will be validated per-node shortly)
                current_input = initial_input
            if self.persistence:
                self.persistence.update_run_status(rid, "running")
            await self._emit(Event(type="run_started", run_id=rid))
        else:
            rid = run_id or str(uuid.uuid4())
            state = RunState(run_id=rid)
            if self.persistence:
                self.persistence.create_run(rid, metadata=state.metadata.model_dump())
            await self._emit(Event(type="run_started", run_id=rid))
            # For minimal implementation, support a single linear path starting at entrypoint.
            current_node_name = graph.entrypoint
            current_input = initial_input

        last_output: Optional[BaseModel] = None

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
            except HumanInputRequired:
                # Record pending gate, stash current input, checkpoint, and return waiting status
                await self._emit(Event(type="human_gate_pending", run_id=rid, node=node.name))
                # Save the pending input so resume can continue past this node
                state.context[f"pending_input:{node.name}"] = (
                    current_input.model_dump() if isinstance(current_input, BaseModel) else current_input
                )
                if self.persistence:
                    self.persistence.save_checkpoint(rid, node.name, state.model_dump_json())
                    self.persistence.update_run_status(rid, "waiting")
                return RunResult(run_id=rid, status="waiting", output=None, state=state)
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
        """Emit an event to persistence and local handlers.

        This internal helper attempts to persist the event (if a persistence
        backend is configured) and notifies locally registered handlers via
        ``orca.observability.hooks.get_event_handlers``. All exceptions are
        suppressed to avoid interfering with the run.

        Args:
            event (Event): The event to emit.

        Returns:
            None: This method returns nothing.

        Examples:
            - Emit a synthetic event; the call completes without error.
                ```python
                >>> import asyncio
                >>> from orca.core.events import Event
                >>> from orca.core.runner import GraphRunner
                >>> asyncio.run(GraphRunner()._emit(Event(type="run_started", run_id="r")))
                >>> print("ok")
                ok

                ```
        """
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
