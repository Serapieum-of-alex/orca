You are a senior Python architect. Create a production-ready open-source Python package named orca that implements an 
**agentic workflow orchestrator** based on a **typed, stateful directed graph** (DAG/graph). The package must emphasize testability, determinism, replay, human-in-the-loop, and interoperability with LangGraph (LangChain) and LlamaIndex.

## High-level goals
- Provide a small, opinionated core for building agentic workflows as graphs of **Nodes** with explicit, typed inputs/outputs and a shared **versioned State**.
- Deliver **developer ergonomics** (DX) and **observability** out of the box: step logs, timelines, run viewer JSON, cost/token metering hooks.
- Offer **durability + replay** via pluggable persistence (start with SQLite) and optional enterprise backends (Postgres/S3; plus adapters for Prefect/Temporal).
- Interoperate cleanly with **LangGraph** and **LlamaIndex Workflows** so teams can adopt gradually.

## Non-negotiable constraints
- Python 3.11+; prefer **3.12** support.
- Use **Pydantic v2** for all schemas and type-checked IO contracts.
- 100% type hints; run **mypy** in CI; style via **ruff** + **black**.
- Package with **Poetry**; wheel + sdist; semantic versioning; MIT or Apache-2.0 license.
- Cross-platform (Linux & Windows). Provide GitHub Actions CI matrix (3.10–3.12, ubuntu-latest, windows-latest).
- Include docs site (MkDocs Material) with tutorials and API reference.

## Core architecture (implement)
1. **State Model**
    - `RunState` (Pydantic v2): versioned, JSON-serializable; includes `context`, `artifacts`, `events`, per-node outputs, and metadata (model usage, token/cost).
    - Checkpointing at node boundaries; deterministic replay from checkpoints.
2. **Node Abstraction**
    - `Node[I, O]` generic with:
        - `name: str`
        - `input_model: type[I]` and `output_model: type[O]` (Pydantic models)
        - `async def run(self, input: I, state: RunState) -> O`
        - `error_policy` (max_retries, backoff, fallbacks, escalate_to_human)
        - `budget` (time/cost/token guards).
    - Built-ins:
        - `ToolNode` (sync/async tool calls), `LLMNode` (abstract over provider), `RouterNode` (branching by predicate), `MapNode` (fan-out), `ReduceNode` (fan-in),
          `HumanGateNode` (pause/resume with external input), `PythonFunctionNode`.
3. **Graph**
    - `Graph` holds nodes and **explicit typed edges**; allow general directed graphs (not just acyclic) with safeguards against infinite loops (iteration caps).
    - Static validation: edge type compatibility (producer `O` -> consumer `I`).
4. **Runner**
    - `GraphRunner` with:
        - `run(graph, initial_input, *, resume_from_checkpoint=None) -> RunResult`
        - Streaming events; hooks for telemetry; cancellation & timeouts.
    - Observability: structured logs, timeline JSON, per-node durations, retries, exceptions.
5. **Persistence**
    - `Persistence` interface with **SQLite** default:
        - tables: runs, checkpoints, events, artifacts (blob store on disk/S3).
    - Optional Postgres/S3 implementations behind feature flags.
6. **Human-in-the-loop**
    - `HumanGateNode` exposes a **pending token** in persistence; provide CLI & Python API to **submit approval/input** to resume.
7. **Error handling**
    - Per-node `ErrorPolicy`: retry/backoff, fallback node, route-to-human; graph-level defaults and overrides.
8. **Security & isolation**
    - Support **tool whitelisting** and redaction of sensitive fields in logs; mask secrets in state exports.

## Interoperability (implement adapters)
- **LangGraph Adapter**
    - Allow wrapping a `Graph` as a LangGraph subgraph and vice versa.
    - Minimal examples showing a LangGraph agent step as a `Node`, and this package’s `Graph` executed inside a LangGraph flow.
- **LlamaIndex Adapter**
    - Wrap `QueryEngine`/`AgentRunner`/Workflow as `Node`s (typed IO via Pydantic models).
    - Expose this package’s `Graph` as a LlamaIndex tool.
- **(Optional) Multi-agent bridges**
    - Thin shims to call AutoGen/CrewAI conversations as `Node`s (design for, can stub if time).

## Developer Experience (deliver)
- **CLI**: `awf` (agentic workflow)
    - `awf run path/to/graph.py --input path/to/input.json --resume <run_id>`
    - `awf ls` / `awf view <run_id>` prints timeline; `awf approve <run_id> <gate_id> --data <json>`
    - `awf export <run_id> --format json` (sanitized).
- **Testing utilities**
    - Record-and-replay fixtures; `FakeLLM` and `DeterministicTool` for unit tests.
    - Pytest plugin: `@with_recording` to capture node IO and re-use as golden tests.
- **Observability hooks**
    - Simple Python callbacks and OpenTelemetry stubs for spans/metrics.

## Reference examples (include runnable code)
1. **Doc QA With Human Approval**
    - Pipeline: retrieve → rank → summarize → **HumanGate** (approve/edit) → finalize report.
    - Show both **LlamaIndex** and **LangGraph** integrations in this example.
2. **Scientific/Simulation Workflow (hydrology flavored)**
    - Steps: load parameters → run simulation (long-running stub) → quality checks → conditional re-run → publish results.
    - Demonstrate budgeting, retries, and checkpoint resume.
3. **Multi-tool Agent**
    - Router chooses tools (web search, SQL, file ops) with typed contracts; show failure fallback to human.

## Public API design (sketch concrete signatures)
- `class Node(Generic[I, O])`
- `class Graph: add_node(node), connect(src, dst), validate()`
- `class GraphRunner: run(...), resume(...), cancel(run_id)`
- `class Persistence: save_run(...), save_checkpoint(...), load_checkpoint(...)`
- `class HumanGateNode(Node[I, O])`: waits for `submit_human_input(run_id, gate_id, data: dict)`
- `register_tool(name: str, fn: Callable[..., Any], input_model, output_model)`
- `on_event(handler: Callable[[Event], None])` for logs/metrics.

## Files & repo layout (create)
- `/src/[PACKAGE_NAME]/`
    - `core/` (`node.py`, `graph.py`, `runner.py`, `state.py`, `errors.py`, `events.py`)
    - `nodes/` (`llm.py`, `tool.py`, `router.py`, `map.py`, `reduce.py`, `human_gate.py`)
    - `io_models/` (Pydantic models for examples)
    - `persistence/` (`base.py`, `sqlite.py`, `postgres.py`, `s3.py`)
    - `adapters/` (`langgraph.py`, `llamaindex.py`, `prefect.py`, `temporal.py` [stubs ok])
    - `observability/` (`hooks.py`, `otel.py`)
    - `cli/` (`__main__.py`)
    - `version.py`
- `/examples/` (three reference workflows above; each with README, run scripts)
- `/tests/` (unit + integration; golden recordings)
- `pyproject.toml` (Poetry), `README.md`, `LICENSE`, `CONTRIBUTING.md`
- `mkdocs.yml`, `/docs/` (tutorials, API, design notes, ADRs)
- `.github/workflows/ci.yml` (lint, typecheck, tests; matrix Linux/Windows; Python 3.10–3.12)

## Implementation details to emphasize
- Use **Pydantic v2** `BaseModel` with `model_validate` for IO; exportable JSON schemas; include **schema versioning** in `RunState`.
- Deterministic behavior: offer seedable random + deterministic mock LLM/tool layers for tests.
- Budget guards: cost/time/token ceilings per node; graceful cancellation with checkpoint.
- Router semantics: predicates type-checked; support confidence thresholds; log routing decisions.
- ErrorPolicy: exponential backoff, jitter; fallback-to node; escalate to `HumanGateNode`.
- Persistence: write-ahead event log; compaction; artifact store (local folder default; S3 optional).
- Security: secret masking; allowlist of callable tools; redact PIIs from exports.
- Performance: async first; avoid thread starvation; backpressure where fan-out happens.

## Docs deliverables
- “Why typed graphs?” explainer with Observer vs DAG contrast.
- Quickstart in <10 minutes; “Bring your own LLM/tool.”
- Interop guides: “Use inside LangGraph”, “Use LlamaIndex tool wrappers”.
- Durability & replay guide; Human-in-the-loop guide.

## Acceptance tests (must pass)
- Build & tests green in CI on Linux/Windows.
- Example 1 & 2 runnable via CLI; can **pause** at human gate, **approve**, **resume**, and **export** the final run.
- Replay from a mid-graph checkpoint produces identical outputs (given deterministic mocks).
- Type mismatch on edges is caught at `graph.validate()` with a helpful error.
- LangGraph and LlamaIndex adapters compile and run their example demos.

## Nice-to-haves (if time permits)
- Minimal web UI (FastAPI + tiny JS app) to list runs and approve HumanGate steps.
- OpenTelemetry spans around node execution.
- Pluggable policy engine (e.g., YAML) for retries and routing thresholds.

Deliver the full repo with code, tests, examples, docs, and CI. Keep the core API compact and well-documented; prioritize correctness, determinism, and interoperability over features.
