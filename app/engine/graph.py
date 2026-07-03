from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.engine.registry import STEP_REGISTRY

MAX_DEFINITION_BYTES = 2 * 1024 * 1024
MAX_NODES = 500
MAX_COORDINATE = 1_000_000.0


class GraphModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Position(GraphModel):
    x: float
    y: float

    @field_validator("x", "y")
    @classmethod
    def finite_bounded(cls, value: float) -> float:
        if not math.isfinite(value) or abs(value) > MAX_COORDINATE:
            raise ValueError("coordinate must be finite and bounded")
        return value


class Viewport(Position):
    zoom: float = Field(ge=0.05, le=8)


class Node(GraphModel):
    id: str
    kind: Literal["start", "step", "if", "loop", "comment"]
    position: Position
    step_type: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    text: str | None = Field(default=None, max_length=10_000)
    source_handle: Literal["top", "right", "bottom", "left"] | None = None
    target_handle: Literal["top", "right", "bottom", "left"] | None = None

    @field_validator("id")
    @classmethod
    def uuid_id(cls, value: str) -> str:
        uuid.UUID(value)
        return value


class Edge(GraphModel):
    id: str
    source: str
    target: str
    branch: Literal["true", "false", "body", "done"] | None = None

    @field_validator("id", "source", "target")
    @classmethod
    def uuid_id(cls, value: str) -> str:
        uuid.UUID(value)
        return value


class Graph(GraphModel):
    nodes: list[Node]
    edges: list[Edge]
    viewport: Viewport = Field(default_factory=lambda: Viewport(x=0, y=0, zoom=1))


class Definition(GraphModel):
    schema_version: Literal[2]
    graph: Graph


@dataclass(frozen=True)
class GraphIssue:
    code: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None

    def as_dict(self) -> dict[str, str]:
        result = {"code": self.code, "message": self.message}
        if self.node_id:
            result["node_id"] = self.node_id
        if self.edge_id:
            result["edge_id"] = self.edge_id
        return result


class GraphValidationError(ValueError):
    def __init__(self, issues: list[GraphIssue]):
        super().__init__("invalid_workflow_definition")
        self.issues = issues


def _shape_issue(exc: ValidationError) -> GraphIssue:
    first = exc.errors(include_url=False, include_context=False)[0]
    location = ".".join(str(part) for part in first.get("loc", ()))
    return GraphIssue("invalid_shape", f"Invalid definition at {location}: {first['msg']}")


def compile_definition(raw: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        encoded = json.dumps(raw, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GraphValidationError([GraphIssue("invalid_json", "Definition must be JSON serializable")]) from exc
    if len(encoded) > MAX_DEFINITION_BYTES:
        raise GraphValidationError([GraphIssue("definition_too_large", "Definition exceeds 2 MiB")])
    try:
        definition = Definition.model_validate(raw)
    except ValidationError as exc:
        raise GraphValidationError([_shape_issue(exc)]) from exc

    nodes = definition.graph.nodes
    edges = definition.graph.edges
    issues: list[GraphIssue] = []
    if len(nodes) > MAX_NODES:
        issues.append(GraphIssue("too_many_nodes", f"Definition exceeds {MAX_NODES} nodes"))
    node_ids = [node.id for node in nodes]
    edge_ids = [edge.id for edge in edges]
    for duplicated in {value for value in node_ids if node_ids.count(value) > 1}:
        issues.append(GraphIssue("duplicate_node_id", "Node ID must be unique", node_id=duplicated))
    for duplicated in {value for value in edge_ids if edge_ids.count(value) > 1}:
        issues.append(GraphIssue("duplicate_edge_id", "Edge ID must be unique", edge_id=duplicated))
    by_id = {node.id: node for node in nodes}
    starts = [node for node in nodes if node.kind == "start"]
    if len(starts) != 1:
        issues.append(GraphIssue("start_count", "Definition requires exactly one start node"))

    executable = {node.id for node in nodes if node.kind in {"start", "step", "if", "loop"}}
    incoming: dict[str, list[Edge]] = {node_id: [] for node_id in executable}
    outgoing: dict[str, list[Edge]] = {node_id: [] for node_id in executable}
    for edge in edges:
        if edge.source not in by_id or edge.target not in by_id:
            issues.append(GraphIssue("missing_reference", "Edge references a missing node", edge_id=edge.id))
            continue
        if by_id[edge.source].kind == "comment" or by_id[edge.target].kind == "comment":
            issues.append(GraphIssue("comment_edge", "Comment nodes must remain disconnected", edge_id=edge.id))
            continue
        if edge.source == edge.target:
            issues.append(GraphIssue("self_connection", "A node cannot connect to itself", node_id=edge.source, edge_id=edge.id))
            continue
        outgoing[edge.source].append(edge)
        incoming[edge.target].append(edge)
    for node_id in executable:
        node = by_id[node_id]
        if node.kind in {"start", "step"} and len(outgoing[node_id]) > 1:
            issues.append(GraphIssue("branch", "Execution path cannot branch", node_id=node_id))
        if node.kind != "loop" and len(incoming[node_id]) > 1:
            issues.append(GraphIssue("join", "Execution paths cannot join", node_id=node_id))
        if node.kind == "if":
            labels = [edge.branch for edge in outgoing[node_id]]
            if sorted(str(label) for label in labels) != ["false", "true"]:
                issues.append(GraphIssue("if_branches", "If requires exactly one true and one false connection", node_id=node_id))
        if node.kind == "loop":
            labels = [edge.branch for edge in outgoing[node_id]]
            if sorted(str(label) for label in labels) != ["body", "done"]:
                issues.append(GraphIssue("loop_branches", "Loop requires exactly one body and one done connection", node_id=node_id))
    if starts and incoming.get(starts[0].id):
        issues.append(GraphIssue("start_incoming", "Start node cannot have incoming edges", node_id=starts[0].id))

    compiled: list[dict[str, Any]] = []
    visited: set[str] = set()
    available_state: set[str] = set()
    visiting: set[str] = set()

    def visit(current: str) -> None:
        if current in visiting:
            if by_id[current].kind != "loop":
                issues.append(GraphIssue("cycle", "Cycles must return to a Loop node", node_id=current))
            return
        if current in visited:
            return
        visiting.add(current)
        visited.add(current)
        node = by_id[current]
        if node.kind == "step":
            definition_item = STEP_REGISTRY.get(node.step_type or "")
            if definition_item is None:
                issues.append(GraphIssue("unknown_step_type", "Unknown step type", node_id=node.id))
            else:
                try:
                    validated_args = definition_item.args_model.model_validate(node.args)
                    missing_state = definition_item.requires - available_state
                    if missing_state:
                        issues.append(GraphIssue("missing_state", f"Step requires state: {', '.join(sorted(missing_state))}", node_id=node.id))
                    available_state.update(definition_item.provides)
                    compiled.append({"id": node.id, "type": node.step_type, "args": validated_args.model_dump(mode="json"), "next": outgoing[node.id][0].target if len(outgoing[node.id]) == 1 else None})
                except ValidationError as exc:
                    message = exc.errors(include_url=False, include_context=False)[0]["msg"]
                    issues.append(GraphIssue("invalid_args", f"Invalid step arguments: {message}", node_id=node.id))
        elif node.kind in {"if", "loop"}:
            state_key = node.args.get("state_key")
            operator = node.args.get("operator")
            if not isinstance(state_key, str) or len(state_key) > 200 or operator not in {"equals", "not_equals", "contains", "truthy", "falsy"}:
                issues.append(GraphIssue("invalid_args", "Control node requires a valid state_key and operator", node_id=node.id))
            max_iterations = node.args.get("max_iterations", 10)
            if node.kind == "loop" and (not isinstance(max_iterations, int) or isinstance(max_iterations, bool) or not 1 <= max_iterations <= 1000):
                issues.append(GraphIssue("invalid_args", "Loop max_iterations must be between 1 and 1000", node_id=node.id))
            compiled.append({"id": node.id, "type": f"__{node.kind}__", "args": node.args, "branches": {str(edge.branch): edge.target for edge in outgoing[node.id]}})
        for next_edge in outgoing.get(current, []):
            visit(next_edge.target)
        visiting.remove(current)

    if len(starts) == 1:
        visit(starts[0].id)

    disconnected = executable - visited
    for node_id in sorted(disconnected):
        issues.append(GraphIssue("disconnected", "Executable node is disconnected from Start", node_id=node_id))
    for node in nodes:
        if node.kind == "start" and (node.step_type is not None or node.args):
            issues.append(GraphIssue("invalid_start", "Start node cannot contain step arguments", node_id=node.id))
        if node.kind == "step" and not node.step_type:
            issues.append(GraphIssue("missing_step_type", "Step node requires step_type", node_id=node.id))
    if issues:
        raise GraphValidationError(issues)
    return compiled


def validate_definition(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        steps = compile_definition(raw)
        return {"valid": True, "compiled_steps": steps, "compiled_order": [step["id"] for step in steps], "errors": []}
    except GraphValidationError as exc:
        return {"valid": False, "compiled_steps": [], "compiled_order": [], "errors": [issue.as_dict() for issue in exc.issues]}
