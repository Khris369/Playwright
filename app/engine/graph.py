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
    kind: Literal["start", "step", "comment"]
    position: Position
    step_type: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    text: str | None = Field(default=None, max_length=10_000)

    @field_validator("id")
    @classmethod
    def uuid_id(cls, value: str) -> str:
        uuid.UUID(value)
        return value


class Edge(GraphModel):
    id: str
    source: str
    target: str

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

    executable = {node.id for node in nodes if node.kind in {"start", "step"}}
    incoming: dict[str, list[Edge]] = {node_id: [] for node_id in executable}
    outgoing: dict[str, list[Edge]] = {node_id: [] for node_id in executable}
    for edge in edges:
        if edge.source not in by_id or edge.target not in by_id:
            issues.append(GraphIssue("missing_reference", "Edge references a missing node", edge_id=edge.id))
            continue
        if by_id[edge.source].kind == "comment" or by_id[edge.target].kind == "comment":
            issues.append(GraphIssue("comment_edge", "Comment nodes must remain disconnected", edge_id=edge.id))
            continue
        outgoing[edge.source].append(edge)
        incoming[edge.target].append(edge)
    for node_id in executable:
        if len(outgoing[node_id]) > 1:
            issues.append(GraphIssue("branch", "Execution path cannot branch", node_id=node_id))
        if len(incoming[node_id]) > 1:
            issues.append(GraphIssue("join", "Execution path cannot join", node_id=node_id))
    if starts and incoming.get(starts[0].id):
        issues.append(GraphIssue("start_incoming", "Start node cannot have incoming edges", node_id=starts[0].id))

    compiled: list[dict[str, Any]] = []
    visited: set[str] = set()
    available_state: set[str] = set()
    current = starts[0].id if len(starts) == 1 else None
    while current is not None:
        if current in visited:
            issues.append(GraphIssue("cycle", "Execution path cannot contain a cycle", node_id=current))
            break
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
                    compiled.append({"id": node.id, "type": node.step_type, "args": validated_args.model_dump(mode="json")})
                except ValidationError as exc:
                    message = exc.errors(include_url=False, include_context=False)[0]["msg"]
                    issues.append(GraphIssue("invalid_args", f"Invalid step arguments: {message}", node_id=node.id))
        next_edges = outgoing.get(current, [])
        current = next_edges[0].target if len(next_edges) == 1 else None

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
