import pytest
from fastapi import HTTPException

from app.api.routes import workflow_runs


def test_stop_running_workflow_run_requests_cancellation(monkeypatch) -> None:
    requested = []
    monkeypatch.setattr(
        workflow_runs.WorkflowRunRepository,
        "get_run",
        lambda run_id: {"id": run_id, "status": "running"},
    )
    monkeypatch.setattr(
        workflow_runs.WorkflowRunControl,
        "request_cancel",
        lambda run_id: requested.append(run_id),
    )

    assert workflow_runs.stop_workflow_run(15) == {"status": "stopping"}
    assert requested == [15]


def test_stop_queued_workflow_run_cancels_immediately(monkeypatch) -> None:
    cancelled = []
    requested = []
    monkeypatch.setattr(
        workflow_runs.WorkflowRunRepository,
        "get_run",
        lambda run_id: {"id": run_id, "status": "queued"},
    )
    monkeypatch.setattr(
        workflow_runs.WorkflowRunRepository,
        "cancel_queued_run",
        lambda run_id: cancelled.append(run_id) or True,
    )
    monkeypatch.setattr(
        workflow_runs.WorkflowRunControl,
        "request_cancel",
        lambda run_id: requested.append(run_id),
    )

    assert workflow_runs.stop_workflow_run(9) == {"status": "cancelled"}
    assert cancelled == [9]
    assert requested == [9]


def test_stop_completed_workflow_run_rejects_request(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_runs.WorkflowRunRepository,
        "get_run",
        lambda run_id: {"id": run_id, "status": "passed"},
    )

    with pytest.raises(HTTPException) as exc:
        workflow_runs.stop_workflow_run(3)

    assert exc.value.status_code == 409
