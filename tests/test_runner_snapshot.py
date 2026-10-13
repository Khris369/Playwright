from app.services.workflow_runner import WorkflowRunnerService, _step_log_args


def test_message_text_is_redacted_from_step_history() -> None:
    args = {"value": "private message", "target": {"strategy": "text", "text": "Type a message"}}
    for step_type in ("fill_input", "type_text"):
        assert _step_log_args(step_type, args)["value"] == "[redacted]"
    assert args["value"] == "private message"


def test_run_creation_stores_compiled_snapshot(monkeypatch) -> None:
    start = "00000000-0000-4000-8000-000000000001"
    step = "00000000-0000-4000-8000-000000000002"
    definition = {"schema_version": 2, "graph": {"nodes": [
        {"id": start, "kind": "start", "position": {"x": 0, "y": 0}},
        {"id": step, "kind": "step", "step_type": "wait_timeout", "args": {"timeout_ms": 1}, "position": {"x": 1, "y": 0}},
    ], "edges": [{"id": "00000000-0000-4000-8000-000000000003", "source": start, "target": step}], "viewport": {"x": 0, "y": 0, "zoom": 1}}}
    monkeypatch.setattr("app.services.workflow_runner.WorkflowVersionRepository.get", lambda _: {"workflow_id": 9, "definition_json": definition})
    captured = {}
    def create(**kwargs): captured.update(kwargs); return 42
    monkeypatch.setattr("app.services.workflow_runner.WorkflowRunRepository.create_queued_run", create)
    assert WorkflowRunnerService.run_workflow_version(7, {}) == 42
    assert captured["resolved_definition"]["steps"][0]["id"] == step
