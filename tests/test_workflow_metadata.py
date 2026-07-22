from app.api.routes import workflows
from app.schemas.workflow import WorkflowVersionLockRequest, WorkflowVersionUpdate
from app.services.workflow_version_repository import WorkflowVersionRepository


def test_update_workflow_version_passes_user_id(monkeypatch) -> None:
    captured = {}

    def fake_update(version_id, payload, user_id=None):
        captured["version_id"] = version_id
        captured["payload"] = payload
        captured["user_id"] = user_id
        return {
            "id": version_id,
            "workflow_id": 3,
            "version_number": 2,
            "is_published": False,
            "definition_json": payload.definition_json,
            "created_by_user_id": 4,
            "updated_by_user_id": user_id,
            "lock_version": payload.expected_lock_version + 1,
            "created_at": None,
            "updated_at": None,
        }

    monkeypatch.setattr(WorkflowVersionRepository, "update", fake_update)

    payload = WorkflowVersionUpdate(
        definition_json={"schema_version": 2, "graph": {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}},
        expected_lock_version=7,
    )
    response = workflows.update_workflow_version(9, payload, {"id": 12})

    assert captured == {"version_id": 9, "payload": payload, "user_id": 12}
    assert response.updated_by_user_id == 12


def test_publish_workflow_version_passes_user_id(monkeypatch) -> None:
    captured = {}

    def fake_set_published(version_id, expected_lock_version, published, user_id=None):
        captured["version_id"] = version_id
        captured["expected_lock_version"] = expected_lock_version
        captured["published"] = published
        captured["user_id"] = user_id
        return {
            "id": version_id,
            "workflow_id": 3,
            "version_number": 2,
            "is_published": published,
            "definition_json": {"schema_version": 2, "graph": {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}},
            "created_by_user_id": 4,
            "updated_by_user_id": user_id,
            "lock_version": expected_lock_version + 1,
            "created_at": None,
            "updated_at": None,
        }

    monkeypatch.setattr(WorkflowVersionRepository, "set_published", fake_set_published)

    response = workflows.publish_workflow_version(11, WorkflowVersionLockRequest(expected_lock_version=5), {"id": 18})

    assert captured == {
        "version_id": 11,
        "expected_lock_version": 5,
        "published": True,
        "user_id": 18,
    }
    assert response.updated_by_user_id == 18
