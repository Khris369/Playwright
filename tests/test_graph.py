from __future__ import annotations

import uuid

import pytest

from app.engine.graph import GraphValidationError, compile_definition, validate_definition


def node(kind: str, *, step_type: str | None = None, args: dict | None = None) -> dict:
    value = {"id": str(uuid.uuid4()), "kind": kind, "position": {"x": 0, "y": 0}}
    if step_type:
        value.update(step_type=step_type, args=args or {})
    elif args is not None:
        value["args"] = args
    return value


def edge(source: dict, target: dict) -> dict:
    return {"id": str(uuid.uuid4()), "source": source["id"], "target": target["id"]}


def definition(nodes: list[dict], edges: list[dict]) -> dict:
    return {"schema_version": 2, "graph": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 1}}}


def test_compile_linear_graph_preserves_node_ids_and_order() -> None:
    start = node("start")
    first = node("step", step_type="goto_url", args={"url": "https://example.com"})
    second = node("step", step_type="wait_timeout", args={"timeout_ms": 10})
    compiled = compile_definition(definition([second, start, first], [edge(start, first), edge(first, second)]))
    assert [item["id"] for item in compiled] == [first["id"], second["id"]]


@pytest.mark.parametrize("mutation,code", [
    ("branch", "branch"), ("join", "join"), ("cycle", "cycle"),
    ("disconnected", "disconnected"), ("missing", "missing_reference"),
])
def test_rejects_non_linear_graphs(mutation: str, code: str) -> None:
    start = node("start"); one = node("step", step_type="wait_timeout", args={}); two = node("step", step_type="wait_timeout", args={})
    edges = [edge(start, one), edge(one, two)]
    if mutation == "branch": edges.append(edge(start, two))
    elif mutation == "join": edges.append(edge(start, two))
    elif mutation == "cycle": edges.append(edge(two, one))
    elif mutation == "disconnected": edges = [edge(start, one)]
    elif mutation == "missing": edges.append({"id": str(uuid.uuid4()), "source": two["id"], "target": str(uuid.uuid4())})
    result = validate_definition(definition([start, one, two], edges))
    assert not result["valid"]
    assert code in {item["code"] for item in result["errors"]}


def test_comments_may_be_disconnected_but_executable_nodes_may_not() -> None:
    start = node("start"); comment = node("comment")
    assert compile_definition(definition([start, comment], [])) == []


def test_duplicate_and_unknown_step_ids_are_rejected() -> None:
    start = node("start"); bad = node("step", step_type="not_allowed")
    duplicate = {**bad}
    result = validate_definition(definition([start, bad, duplicate], [edge(start, bad)]))
    codes = {item["code"] for item in result["errors"]}
    assert {"duplicate_node_id", "unknown_step_type"} <= codes


def test_ticket_state_contract_is_checked_in_compiled_order() -> None:
    start = node("start")
    fill = node("step", step_type="ticket_fill_fields", args={"fields": [{"target": {"strategy": "label", "label": "Subject"}, "control_type": "text", "value": "x"}]})
    result = validate_definition(definition([start, fill], [edge(start, fill)]))
    assert any(item["code"] == "missing_state" and item["node_id"] == fill["id"] for item in result["errors"])


def test_definition_size_limit() -> None:
    start = node("start"); comment = node("comment"); comment["text"] = "x" * (2 * 1024 * 1024)
    with pytest.raises(GraphValidationError) as exc:
        compile_definition(definition([start, comment], []))
    assert exc.value.issues[0].code == "definition_too_large"


def test_rejects_self_connections() -> None:
    start = node("start")
    result = validate_definition(definition([start], [edge(start, start)]))
    assert any(item["code"] == "self_connection" for item in result["errors"])


def test_compiles_if_and_bounded_loop_control_flow() -> None:
    start = node("start")
    conditional = node("if", args={"state_key": "current_url", "operator": "contains", "value": "example"})
    loop = node("loop", args={"state_key": "finished", "operator": "truthy", "max_iterations": 3})
    body = node("step", step_type="wait_timeout", args={"timeout_ms": 1})
    done = node("step", step_type="wait_timeout", args={"timeout_ms": 1})
    false_done = node("step", step_type="wait_timeout", args={"timeout_ms": 1})
    links = [edge(start, conditional), edge(conditional, loop), edge(conditional, false_done), edge(loop, body), edge(loop, done), edge(body, loop)]
    links[1]["branch"] = "true"; links[2]["branch"] = "false"
    links[3]["branch"] = "body"; links[4]["branch"] = "done"
    compiled = compile_definition(definition([start, conditional, loop, body, done, false_done], links))
    controls = {item["type"] for item in compiled if item["type"].startswith("__")}
    assert controls == {"__if__", "__loop__"}


def test_scalar_run_input_template_survives_compile_time_type_validation() -> None:
    start = node("start")
    wait = node("step", step_type="wait_timeout", args={"timeout_ms": "{{ inputs.delay_ms }}"})
    compiled = compile_definition(definition([start, wait], [edge(start, wait)]))
    assert compiled[0]["args"]["timeout_ms"] == "{{ inputs.delay_ms }}"


def test_verify_element_compiles_with_a_run_input_timeout() -> None:
    start = node("start")
    verify = node("step", step_type="verify_element", args={
        "target": {"strategy": "text", "text": "Invalid username or password"},
        "expected_state": "visible",
        "timeout_ms": "{{ inputs.verify_timeout_ms }}",
    })
    compiled = compile_definition(definition([start, verify], [edge(start, verify)]))
    assert compiled[0]["type"] == "verify_element"
    assert compiled[0]["args"]["timeout_ms"] == "{{ inputs.verify_timeout_ms }}"
