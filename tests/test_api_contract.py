from app.api.routes.step_types import list_step_types
from app.api.routes.workflow_definitions import validate_workflow_definition
from app.schemas.workflow_definition import WorkflowDefinitionValidate


def test_step_type_api_is_registry_backed() -> None:
    item = list_step_types()[0].model_dump()
    assert {"category", "default_args", "args_schema", "editor_schema"} <= item.keys()


def test_validate_endpoint_returns_node_keyed_errors() -> None:
    start = "00000000-0000-4000-8000-000000000001"
    step = "00000000-0000-4000-8000-000000000002"
    result = validate_workflow_definition(WorkflowDefinitionValidate(definition_json={
        "schema_version": 2,
        "graph": {
            "nodes": [
                {"id": start, "kind": "start", "position": {"x": 0, "y": 0}},
                {"id": step, "kind": "step", "step_type": "unknown", "args": {}, "position": {"x": 1, "y": 0}},
            ],
            "edges": [{"id": "00000000-0000-4000-8000-000000000003", "source": start, "target": step}],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }))
    assert result["errors"][0]["node_id"] == step
