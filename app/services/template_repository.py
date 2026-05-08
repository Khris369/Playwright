from __future__ import annotations

import json
from typing import Any

from app.schemas.template import WorkflowTemplateCreate
from app.schemas.workflow import WorkflowCreate, WorkflowVersionCreate
from app.services.db import get_db_cursor
from app.services.workflow_repository import WorkflowRepository


DEFAULT_TEMPLATES = [
    {
        "key": "generic_login_flow_v1",
        "name": "Generic Login Flow",
        "category": "generic",
        "definition_json": {
            "steps": [
                {"type": "goto_url", "args": {"url": "{{inputs.base_url}}"}},
                {
                    "type": "fill_input",
                    "args": {
                        "selector": "{{inputs.username_selector}}",
                        "value": "{{inputs.username}}",
                    },
                },
                {
                    "type": "fill_input",
                    "args": {
                        "selector": "{{inputs.password_selector}}",
                        "value": "{{inputs.password}}",
                    },
                },
                {"type": "click", "args": {"selector": "{{inputs.submit_selector}}"}},
            ]
        },
    },
    {
        "key": "call_platform_create_ticket_v1",
        "name": "Call Platform Create Ticket v1",
        "category": "ticketing",
        "definition_json": {
            "steps": [
                {"type": "goto_url", "args": {"url": "{{inputs.base_url}}"}},
                {
                    "type": "fill_input",
                    "args": {
                        "selector": "{{inputs.username_selector}}",
                        "value": "{{inputs.username}}",
                    },
                },
                {
                    "type": "fill_input",
                    "args": {
                        "selector": "{{inputs.password_selector}}",
                        "value": "{{inputs.password}}",
                    },
                },
                {"type": "click", "args": {"selector": "{{inputs.login_button_selector}}"}},
                {"type": "click", "args": {"selector": "{{inputs.call_platform_selector}}"}},
                {
                    "type": "fill_input",
                    "args": {
                        "selector": "{{inputs.caller_number_selector}}",
                        "value": "{{inputs.caller_number}}",
                    },
                },
                {
                    "type": "select_option",
                    "args": {
                        "selector": "{{inputs.ivr_language_selector}}",
                        "value": "{{inputs.ivr_language}}",
                    },
                },
                {"type": "click", "args": {"selector": "{{inputs.search_button_selector}}"}},
                {
                    "type": "wait_for_element",
                    "args": {"selector": "{{inputs.scenario_dropdown_selector}}"},
                },
                {
                    "type": "run_custom_action",
                    "args": {
                        "action": "create_ticket_flow",
                        "scenario_name": "{{inputs.scenario_name}}",
                        "brand": "{{inputs.brand}}",
                        "ticket_data_path": "{{inputs.ticket_data_path}}",
                    },
                },
            ]
        },
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
        version = WorkflowRepository.create_workflow_version(
            int(workflow["id"]),
            WorkflowVersionCreate(
                version_number=version_number,
                is_published=is_published,
                definition_json=template["definition_json"],
            ),
        )
        return {"workflow": workflow, "version": version}
