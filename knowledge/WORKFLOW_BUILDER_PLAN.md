# Workflow Builder Plan

## Overview
This project will evolve the current Playwright test suite into a workflow-builder application that lets users define, run, and monitor browser automation workflows across different websites through a UI instead of writing test code directly.

The first target is an MVP that can model the same steps currently implemented in `tests/test_call.py` as an initial template and execute them reliably.

## Why Python (Chosen Stack)
- Existing automation is already in Python (`pytest` + `Playwright`), so core logic is reusable.
- Lower integration overhead than mixing Laravel with Python automation workers.
- Strong backend options for async workflows (`FastAPI`, `Celery`, `Redis`).

## Product Goal
Enable non-developer or low-code users to:
- Build automation flows from reusable steps.
- Save and version workflows.
- Run workflows on demand.
- See run logs, pass/fail status, and step-level errors.

## MVP Scope
### In scope
- Workflow definition as JSON (stored in DB).
- Basic workflow builder UI (linear visual builder first, graph later).
- Execution engine for predefined step types.
- Run history and detailed logs.
- Parameterized inputs (e.g., `base_url`, credentials, form data, selectors, scenario values).

### Out of scope (MVP)
- Full drag-and-drop DAG with branching/parallelism.
- Multi-tenant RBAC.
- Real-time collaborative editing.
- Visual diff/merge for workflow versions.

## Current UI Capability (Implemented)
- Workflow shell create/list/load.
- Version editor with:
  - phase-1 drag-and-drop linear step cards
  - step add/remove/reorder
  - inline step args JSON editing
  - synchronized raw `definition_json` view
  - auto-load latest version for quick iteration
- Run trigger and run/step log inspection.

## Proposed Architecture
### Backend
- `FastAPI` for API layer.
- `PostgreSQL` for workflows, versions, runs, and step logs.
- `Celery` + `Redis` for async execution.
- `Playwright` worker module to execute step handlers.

### Frontend
- Web UI (React recommended) for:
  - Workflow list/create/edit
  - Run trigger
  - Run status/log viewer

### Execution model
1. User creates/edits workflow definition.
2. User triggers run with input payload.
3. API creates run record and enqueues job.
4. Worker executes steps in order.
5. Worker writes step logs + status.
6. UI shows final run result and detailed timeline.

## Initial Step Types
- `goto_url`
- `fill_input`
- `click`
- `select_option`
- `wait_for_element`
- `assert_url_not_equal`
- `assert_text_visible`
- `run_custom_action`

Call-platform-specific steps from `test_call.py` will be implemented as a starter template workflow on top of these generic primitives.

## Example Workflow Definition (Draft)
```json
{
  "name": "Create Ticket - Digi",
  "version": 1,
  "inputs": {
    "base_url": "https://example-app.com/login",
    "brand": "Digi",
    "caller_number": "601131219974",
    "scenario_name": "Enquiry about Roaming"
  },
  "steps": [
    { "type": "goto_url", "args": { "url": "{{inputs.base_url}}" } },
    { "type": "fill_input", "args": { "selector": "#username", "value": "{{secrets.username}}" } },
    { "type": "fill_input", "args": { "selector": "#password", "value": "{{secrets.password}}" } },
    { "type": "click", "args": { "selector": "button:has-text('Log In')" } },
    { "type": "wait_for_element", "args": { "selector": "text=Call Platform" } },
    { "type": "run_custom_action", "args": { "action": "create_ticket_flow", "brand": "{{inputs.brand}}" } }
  ]
}
```

## Data Model (MVP)
- `workflows`
  - `id`, `name`, `description`, `created_at`, `updated_at`
- `workflow_versions`
  - `id`, `workflow_id`, `version`, `definition_json`, `created_at`
- `workflow_runs`
  - `id`, `workflow_version_id`, `status`, `inputs_json`, `started_at`, `finished_at`, `error_summary`
- `workflow_step_runs`
  - `id`, `workflow_run_id`, `step_index`, `step_type`, `status`, `started_at`, `finished_at`, `log_text`, `error_text`

## API Endpoints (MVP Draft)
- `POST /workflows`
- `GET /workflows`
- `GET /workflows/{id}`
- `POST /workflows/{id}/versions`
- `POST /workflow-runs`
- `GET /workflow-runs/{id}`
- `GET /workflow-runs/{id}/steps`

## Implementation Phases
1. Core backend skeleton (`FastAPI`, DB models, migrations).
2. Workflow definition schema + validation.
3. Runner service + Playwright step handlers.
4. Async execution via Celery + Redis.
5. Basic UI for workflow CRUD and run monitoring.
6. Hardening: retries, timeout controls, screenshots on failure.

## Risks and Mitigations
- UI selectors are brittle:
  - Mitigation: centralize selectors and add fallback strategies.
- Long-running browser jobs:
  - Mitigation: worker timeouts + heartbeat + resumable logs.
- Debuggability:
  - Mitigation: per-step logs, screenshots, and structured errors.

## Success Criteria for MVP
- Create a workflow without writing test code.
- Execute workflow from UI/API with runtime inputs.
- Run the same workflow structure against different target URLs by changing inputs/config.
- Reproduce current `test_call.py` path as one reusable template.
- View detailed step-by-step execution logs and failure context.

## Next Step
After approval of this plan, scaffold the project structure and implement Phase 1 with a minimal runnable API and workflow-run stub.
