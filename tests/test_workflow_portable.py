from contextlib import contextmanager
import asyncio

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.routes.workflows import upload_workflow
from app.schemas.workflow_portable import PortableWorkflow
from app.services import workflow_portable


START = {"schema_version": 2, "graph": {"nodes": [
    {"id": "00000000-0000-4000-8000-000000000001", "kind": "start", "position": {"x": 0, "y": 0}}
], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}}}


def test_import_validates_every_version_before_database_write(monkeypatch):
    @contextmanager
    def fail_if_database_opened():
        raise AssertionError("database opened before validation")
        yield

    monkeypatch.setattr(workflow_portable, "get_db_cursor", fail_if_database_opened)
    payload = PortableWorkflow(format="workflow-builder", format_version=1, name="Example", versions=[
        {"definition_json": START}, {"definition_json": {"schema_version": 2, "graph": {"nodes": [], "edges": []}}},
    ])
    with pytest.raises(ValueError):
        workflow_portable.import_workflow(payload, 7)


def test_export_omits_database_ids_and_imports_drafts(monkeypatch):
    class Cursor:
        lastrowid = 41
        def __init__(self):
            self.calls = []
        def execute(self, query, params):
            self.calls.append((query, params))
        def fetchone(self):
            return {"name": "Example", "description": "Shared"}
        def fetchall(self):
            return [{"definition_json": START}]

    cursor = Cursor()

    @contextmanager
    def db():
        yield None, cursor

    monkeypatch.setattr(workflow_portable, "get_db_cursor", db)
    exported = workflow_portable.export_workflow(9)
    assert exported.model_dump() == {
        "format": "workflow-builder", "format_version": 1, "name": "Example",
        "description": "Shared", "versions": [{"definition_json": START}],
    }
    assert workflow_portable.import_workflow(exported, 7) == 41
    inserts = [(sql, params) for sql, params in cursor.calls if "INSERT INTO" in sql]
    assert len(inserts) == 2
    assert inserts[0][1][:3] == (7, 7, 7)
    assert inserts[1][1][:4] == (41, 7, 7, 1)
    assert "VALUES (%s, %s, %s, %s, 0, %s, 0)" in inserts[1][0]


def test_import_endpoint_rejects_invalid_file():
    class Request:
        async def stream(self):
            yield b'{"format":"workflow-builder","format_version":99}'

    with pytest.raises(HTTPException) as error:
        asyncio.run(upload_workflow(Request(), {"id": 7}))
    assert error.value.status_code == 422
    assert error.value.detail == "Invalid workflow export file"


def test_portable_schema_rejects_database_metadata():
    with pytest.raises(ValidationError):
        PortableWorkflow.model_validate({
            "format": "workflow-builder", "format_version": 1,
            "name": "Example", "versions": [{"definition_json": START}],
            "owner_user_id": 12,
        })


def test_import_endpoint_limits_stream_size():
    class Request:
        async def stream(self):
            yield b"x" * (10 * 1024 * 1024 + 1)

    with pytest.raises(HTTPException) as error:
        asyncio.run(upload_workflow(Request(), {"id": 7}))
    assert error.value.status_code == 413
