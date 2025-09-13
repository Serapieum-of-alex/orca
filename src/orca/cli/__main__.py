from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from typing import Any, Optional

import click
from pydantic import BaseModel, TypeAdapter

from ..core.graph import Graph
from ..core.runner import GraphRunner
from ..persistence.sqlite import DEFAULT_DB_PATH, SQLitePersistence


def _load_module_from_path(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build_graph_from_file(path: Path) -> tuple[Graph, type[BaseModel]]:
    mod = _load_module_from_path(path)
    # Conventions supported (first match wins):
    # - function build_graph() -> Graph and attribute InputModel: Type[BaseModel]
    # - function build() -> tuple[Graph, Type[BaseModel]]
    if hasattr(mod, "build_graph") and hasattr(mod, "InputModel"):
        graph: Graph = mod.build_graph()  # type: ignore[assignment]
        input_model: type[BaseModel] = mod.InputModel  # type: ignore[assignment]
        return graph, input_model
    if hasattr(mod, "build"):
        g, im = mod.build()
        if isinstance(g, Graph) and isinstance(im, type) and issubclass(im, BaseModel):
            return g, im
    raise RuntimeError(
        "Module must expose build_graph() + InputModel, or build() -> (Graph, InputModel)"
    )


def _demo_graph() -> tuple[Graph, type[BaseModel]]:
    # Inline simple demo graph using PythonFunctionNode
    from pydantic import BaseModel

    from ..nodes.python_function import PythonFunctionNode

    class In(BaseModel):
        text: str

    class Mid(BaseModel):
        text: str
        length: int

    class Out(BaseModel):
        summary: str

    def step_len(inp: In, _state) -> Mid:
        return Mid(text=inp.text, length=len(inp.text))

    def step_summary(inp: Mid, _state) -> Out:
        return Out(summary=f"{inp.text.upper()} ({inp.length} chars)")

    g = Graph()
    n1 = PythonFunctionNode("length", In, Mid, step_len)
    n2 = PythonFunctionNode("summary", Mid, Out, step_summary)
    g.add_node(n1)
    g.add_node(n2)
    g.connect("length", "summary")
    g.set_entry("length")
    return g, In


@click.group()
@click.option(
    "--db", "db_path", type=click.Path(dir_okay=False, path_type=Path), default=DEFAULT_DB_PATH, show_default=True,
    help="Path to SQLite DB file for runs/persistence.",
)
@click.pass_context
def main(ctx: click.Context, db_path: Path) -> None:
    """Agentic Workflow CLI (awf)."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path


@main.command()
@click.argument("graph_path", required=False, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--demo", is_flag=True, help="Run built-in demo graph.")
@click.option("--input-json", type=str, default=None, help="JSON for initial input model.")
@click.option(
    "--input-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to JSON file for initial input model.",
)
@click.pass_context
def run(ctx: click.Context, graph_path: Optional[Path], demo: bool, input_json: Optional[str], input_file: Optional[Path]) -> None:
    """Run a graph. Provide GRAPH_PATH (Python file) or use --demo."""
    db_path: Path = ctx.obj["db_path"]
    persistence = SQLitePersistence(db_path)

    if demo:
        graph, input_model = _demo_graph()
    else:
        if not graph_path:
            raise click.UsageError("Provide GRAPH_PATH or use --demo")
        graph, input_model = _build_graph_from_file(graph_path)

    # Load initial input
    data: dict[str, Any]
    if input_file:
        data = json.loads(Path(input_file).read_text(encoding="utf-8"))
    elif input_json:
        data = json.loads(input_json)
    else:
        # Best-effort default for demo
        data = {"text": "hello orca"}

    adapter = TypeAdapter(input_model)
    initial = adapter.validate_python(data)

    async def _do_run() -> None:
        runner = GraphRunner(persistence=persistence)
        result = await runner.run(graph, initial)
        click.echo(json.dumps({
            "run_id": result.run_id,
            "status": result.status,
            "output": result.output.model_dump() if isinstance(result.output, BaseModel) else None,
        }, indent=2))

    asyncio.run(_do_run())


@main.command("ls")
@click.pass_context
def ls_cmd(ctx: click.Context) -> None:
    """List recent runs."""
    db_path: Path = ctx.obj["db_path"]
    persistence = SQLitePersistence(db_path)
    rows = list(persistence.list_runs())
    if not rows:
        click.echo("No runs.")
        return
    for r in rows:
        click.echo(f"{r.run_id}\t{r.status}")


@main.command()
@click.argument("run_id")
@click.pass_context
def view(ctx: click.Context, run_id: str) -> None:
    """View timeline of a run."""
    db_path: Path = ctx.obj["db_path"]
    persistence = SQLitePersistence(db_path)
    for e in persistence.get_events(run_id):
        node = e.node or "-"
        click.echo(f"{e.time}\t{e.type}\t{node}\t{json.dumps(e.data)}")


@main.command()
@click.argument("run_id")
@click.option("--format", "fmt", type=click.Choice(["json"]) , default="json")
@click.pass_context
def export(ctx: click.Context, run_id: str, fmt: str) -> None:  # noqa: ARG001 - reserved for future
    """Export the final checkpoint state as JSON."""
    db_path: Path = ctx.obj["db_path"]
    persistence = SQLitePersistence(db_path)
    latest = persistence.load_latest_checkpoint(run_id)
    if not latest:
        click.echo("{}")
        return
    _node, state_json = latest
    click.echo(state_json)


@main.command()
@click.argument("run_id")
@click.argument("gate_id")
@click.option("--data", "data_json", type=str, default="{}", help="JSON payload for approval event.")
@click.pass_context
def approve(ctx: click.Context, run_id: str, gate_id: str, data_json: str) -> None:
    """Record a human approval event for a gate node.

    Note: Minimal implementation only records the event; it does not resume a paused run.
    """
    db_path: Path = ctx.obj["db_path"]
    persistence = SQLitePersistence(db_path)
    # Create a synthetic event
    from ..core.events import Event

    try:
        data = json.loads(data_json)
    except json.JSONDecodeError as e:
        raise click.UsageError(f"Invalid JSON for --data: {e}") from e

    persistence.add_event(Event(type="human_gate_approved", run_id=run_id, node=gate_id, data=data))
    click.echo("OK")


if __name__ == "__main__":
    main()
