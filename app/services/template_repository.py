from __future__ import annotations

import json
import uuid
from typing import Any

from app.schemas.template import WorkflowTemplateCreate
from app.schemas.workflow import WorkflowCreate, WorkflowVersionCreate
from app.services.db import get_db_cursor
from app.services.workflow_repository import WorkflowRepository
from app.services.workflow_version_repository import WorkflowVersionRepository


def _graph(template_key: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    start_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"workflow-template:{template_key}:start"))
    nodes = [{"id": start_id, "kind": "start", "position": {"x": 80, "y": 160}}]
    edges = []
    previous = start_id
    for index, step in enumerate(steps):
        node_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"workflow-template:{template_key}:node:{index}"))
        edge_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"workflow-template:{template_key}:edge:{index}"))
        nodes.append({"id": node_id, "kind": "step", "step_type": step["type"], "args": step["args"], "position": {"x": 360 + index * 280, "y": 160}})
        edges.append({"id": edge_id, "source": previous, "target": node_id})
        previous = node_id
    return {"schema_version": 2, "graph": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 1}}}


DEFAULT_TEMPLATES = [
    {
        "key": "generic_login_flow_v2",
        "name": "Generic Login Flow v2",
        "category": "generic",
        "definition_json": _graph("generic_login_flow_v2", [
                {"type": "goto_url", "args": {"url": "{{inputs.base_url}}"}},
                {
                    "type": "fill_input",
                    "args": {
                        "target": {"strategy": "css", "selector": "{{inputs.username_selector}}"},
                        "value": "{{inputs.username}}",
                    },
                },
                {
                    "type": "fill_input",
                    "args": {
                        "target": {"strategy": "css", "selector": "{{inputs.password_selector}}"},
                        "value": "{{inputs.password}}",
                    },
                },
                {"type": "click", "args": {"target": {"strategy": "css", "selector": "{{inputs.submit_selector}}"}}},
            ]),
    },
    {
        "key": "call_platform_create_ticket_v2",
        "name": "Call Platform Create Ticket v2",
        "category": "ticketing",
        "definition_json": _graph("call_platform_create_ticket_v2", [
                {"type": "goto_url", "args": {"url": "{{inputs.base_url}}"}},
                {
                    "type": "fill_input",
                    "args": {
                        "target": {"strategy": "css", "selector": "{{inputs.username_selector}}"},
                        "value": "{{inputs.username}}",
                    },
                },
                {
                    "type": "fill_input",
                    "args": {
                        "target": {"strategy": "css", "selector": "{{inputs.password_selector}}"},
                        "value": "{{inputs.password}}",
                    },
                },
                {"type": "click", "args": {"target": {"strategy": "css", "selector": "{{inputs.login_button_selector}}"}}},
                {"type": "click", "args": {"target": {"strategy": "css", "selector": "{{inputs.call_platform_selector}}"}}},
                {
                    "type": "fill_input",
                    "args": {
                        "target": {"strategy": "css", "selector": "{{inputs.caller_number_selector}}"},
                        "value": "{{inputs.caller_number}}",
                    },
                },
                {
                    "type": "select_option",
                    "args": {
                        "target": {"strategy": "css", "selector": "{{inputs.ivr_language_selector}}"},
                        "option": {"by": "label", "value": "{{inputs.ivr_language}}"},
                    },
                },
                {"type": "click", "args": {"target": {"strategy": "css", "selector": "{{inputs.search_button_selector}}"}}},
                {
                    "type": "wait_for_element",
                    "args": {"target": {"strategy": "css", "selector": "{{inputs.scenario_dropdown_selector}}"}},
                },
                {
                    "type": "ticket_select_scenario",
                    "args": {
                        "scenario_name": "{{inputs.scenario_name}}",
                    },
                },
                {"type": "ticket_create_new_ticket", "args": {}},
                {"type": "ticket_fill_fields", "args": {"fields": [{"target": {"strategy": "label", "label": "Subject"}, "control_type": "text", "value": "{{inputs.subject}}"}]}},
                {"type": "ticket_submit", "args": {}},
            ]),
    },
]


class TemplateRepository:
    @staticmethod
    def ensure_default_template() -> None:
        with get_db_cursor() as (_, cursor):
            for template in DEFAULT_TEMPLATES:
                cursor.execute(
                    "SELECT id FROM workflow_templates WHERE `key` = %s",
                    (template["key"],),
                )
                if cursor.fetchone() is not None:
                    continue
                cursor.execute(
                    """
                    INSERT INTO workflow_templates (`key`, name, category, definition_json)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        template["key"],
                        template["name"],
                        template["category"],
                        json.dumps(template["definition_json"]),
                    ),
                )

    @staticmethod
    def create_template(payload: WorkflowTemplateCreate) -> dict:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO workflow_templates (`key`, name, category, definition_json)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    payload.key,
                    payload.name,
                    payload.category,
                    json.dumps(payload.definition_json),
                ),
            )
            template_id = int(cursor.lastrowid)
            cursor.execute(
                """
                SELECT id, `key`, name, category, definition_json, created_at, updated_at
                FROM workflow_templates
                WHERE id = %s
                """,
                (template_id,),
            )
            row = cursor.fetchone()
            if isinstance(row.get("definition_json"), str):
                row["definition_json"] = json.loads(row["definition_json"])
            return row

    @staticmethod
    def list_templates() -> list[dict]:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, `key`, name, category, definition_json, created_at, updated_at
                FROM workflow_templates
                ORDER BY created_at DESC
                """
            )
            rows = list(cursor.fetchall())
            for row in rows:
                if isinstance(row.get("definition_json"), str):
                    row["definition_json"] = json.loads(row["definition_json"])
            return rows

    @staticmethod
    def get_template(template_id: int) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, `key`, name, category, definition_json, created_at, updated_at
                FROM workflow_templates
                WHERE id = %s
                """,
                (template_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            if isinstance(row.get("definition_json"), str):
                row["definition_json"] = json.loads(row["definition_json"])
            return row

    @staticmethod
    def import_template_to_workflow(
        template_id: int,
        workflow_name: str,
        workflow_description: str | None,
        workflow_status: str,
        version_number: int,
        is_published: bool,
    ) -> dict[str, Any]:
        template = TemplateRepository.get_template(template_id)
        if template is None:
            raise ValueError("template_not_found")

        workflow = WorkflowRepository.create_workflow(
            WorkflowCreate(
                name=workflow_name,
                description=workflow_description,
                status=workflow_status,
            )
        )
        version = WorkflowVersionRepository.create(
            int(workflow["id"]),
            WorkflowVersionCreate(
                definition_json=template["definition_json"],
            ),
        )
        if is_published:
            version = WorkflowVersionRepository.set_published(int(version["id"]), int(version["lock_version"]), True)
        return {"workflow": workflow, "version": version}
