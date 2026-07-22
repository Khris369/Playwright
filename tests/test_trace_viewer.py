import pytest
from fastapi import HTTPException

from app.api.routes import workflow_runs


class FakeTracePath:
    suffix = ".zip"

    def exists(self) -> bool:
        return True

    def is_file(self) -> bool:
        return True


def test_open_trace_launches_playwright_for_trace_artifact(monkeypatch) -> None:
    trace = FakeTracePath()
    launched = []

    monkeypatch.setattr(
        workflow_runs.WorkflowRunRepository,
        "get_artifact",
        lambda run_id, artifact_id: {
            "id": artifact_id,
            "workflow_run_id": run_id,
            "artifact_type": "trace",
            "file_path": "workflow-runs/1/trace.zip",
        },
    )
    monkeypatch.setattr(workflow_runs, "resolve_artifact_path", lambda _: trace)
    monkeypatch.setattr(workflow_runs, "_open_trace_viewer", lambda path: launched.append(path))

    assert workflow_runs.open_workflow_run_trace(1, 2) == {"status": "opened"}
    assert launched == [trace]


def test_open_trace_rejects_non_trace_artifact(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_runs.WorkflowRunRepository,
        "get_artifact",
        lambda run_id, artifact_id: {
            "id": artifact_id,
            "workflow_run_id": run_id,
            "artifact_type": "failure_screenshot",
            "file_path": "workflow-runs/1/failure.png",
        },
    )

    with pytest.raises(HTTPException) as exc:
        workflow_runs.open_workflow_run_trace(1, 2)

    assert exc.value.status_code == 404
