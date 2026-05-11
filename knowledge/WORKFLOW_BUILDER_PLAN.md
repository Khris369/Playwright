# Workflow Builder Plan

## Overview
This project will evolve the current Playwright test suite into a workflow-builder application that lets users define, run, and monitor browser automation workflows across different websites through a UI instead of writing test code directly.

The first target is an MVP that can model the same steps currently implemented in `tests/test_call.py` as an initial template and execute them reliably.

## Why Python (Chosen Stack)
- Existing automation is already in Python (`pytest` + `Playwright`), so core logic is reusable.
- Lower integration overhead than mixing Laravel with Python automation workers.
- Strong backend options for API-driven workflow execution with extensible worker support.

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
- Dedicated workflow editor page (`/ui/editor`) for focused step editing.
- DB-backed run input presets for repeated runs.

### Out of scope (MVP)
- Full drag-and-drop DAG with branching/parallelism.
- Multi-tenant RBAC.
- Real-time collaborative editing.
- Visual diff/merge for workflow versions.

## Current UI Capability (Implemented)
- Dashboard page (`/ui`) for workflow/template/run operations.
- Dedicated editor page (`/ui/editor`) focused on one workflow at a time.
- Workflow viewing and editing are now unified in a single primary editor card on dashboard.
- Version editor with:
  - phase-1 drag-and-drop linear step cards
  - step add/remove/reorder
  - default args generation per step type
  - inline step args JSON editing
  - synchronized raw `definition_json` view via JSON sidebar drawer
  - save current version (in-place) and create next version
  - sticky editor header for top controls
  - collapsible create-workflow panel
  - revision dropdown selector (per-workflow version list)
  - collapsible step cards with summary-first display
  - per-step action menu (insert above/below, duplicate) + remove
- Runs experience with:
  - workflow dropdown + version dropdown
  - generated run-input template from `{{inputs.*}}`
  - DB-backed run-arg presets (save/load/delete)
  - run monitor and step logs

## Proposed Architecture
### Backend
- `FastAPI` for API layer.
- `MySQL` for workflows, versions, runs, templates, step types, and run-arg presets.
- `Playwright` worker module to execute step handlers.

### Frontend
- Server-served HTML/CSS/JS UI for:
  - Dashboard (`/ui`)
  - Dedicated editor (`/ui/editor`)
  - Run trigger and run status/log viewer

### Execution model
1. User creates/edits workflow definition.
2. User triggers run with input payload.
3. API creates run record and executes run inline (current default behavior).
4. Runner executes steps in order using Playwright.
5. Runner writes step logs + status.
6. UI shows final run result and detailed timeline.

## Initial Step Types
- `goto_url`
- `fill_input`
- `click`
- `click_by_role`
- `select_option`
- `wait_for_element`
- `assert_url_not_equal`
- `assert_text_visible`
- `run_custom_action`
- `ticket_select_scenario`
- `ticket_create_new_ticket`
- `ticket_fill_fields` (inline scenario-shaped fields)
- `ticket_fill_fields_from_scenario` (file-backed)
- `ticket_submit`

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

## Data Model (Current)
- `workflows`
  - `id`, `name`, `description`, `status`, `created_at`, `updated_at`
- `workflow_versions`
  - `id`, `workflow_id`, `version_number`, `is_published`, `definition_json`, `created_at`
- `workflow_runs`
  - `id`, `workflow_version_id`, `status`, `inputs_json`, `started_at`, `finished_at`, `error_summary`
- `workflow_step_runs`
  - `id`, `workflow_run_id`, `step_index`, `step_type`, `status`, `started_at`, `finished_at`, `log_text`, `error_text`
- `workflow_templates`
  - `id`, `key`, `name`, `category`, `definition_json`, timestamps
- `step_types`
  - `id`, `key`, `name`, `description`, `is_active`, `sort_order`, timestamps
- `run_arg_presets`
  - `id`, `name`, `workflow_id`, `workflow_version_id`, `inputs_json`, timestamps

## API Endpoints (Current Highlights)
- `POST /workflows`
- `GET /workflows` (supports `active_only` filter)
- `GET /workflows/{id}`
- `DELETE /workflows/{id}` (soft delete to inactive)
- `POST /workflows/{id}/versions`
- `GET /workflows/{id}/versions`
- `GET /workflows/versions/{version_id}`
- `PUT /workflows/versions/{version_id}`
- `POST /workflow-runs`
- `GET /workflow-runs/{id}`
- `GET /workflow-runs/{id}/steps`
- `GET /step-types`
- `POST /workflow-templates/seed-defaults`
- `POST /workflow-templates`
- `GET /workflow-templates`
- `POST /workflow-templates/{template_id}/import`
- `POST /run-arg-presets`
- `GET /run-arg-presets`
- `PUT /run-arg-presets/{preset_id}`
- `DELETE /run-arg-presets/{preset_id}`

Behavioral notes:
- Run-arg presets are soft-deleted (`isActive=0`) and active-filtered in reads/updates.

## Implementation Status
Completed:
1. Core backend skeleton and schema-first SQL model.
2. Workflow/version persistence and APIs.
3. Runner service + step engine + template interpolation.
4. UI dashboard + dedicated editor + run monitoring.
5. Template library, step-type catalog, and ticket step coverage.
6. In-place version save and DB-backed run-arg presets.

In progress / next:
1. Hardening: retries, timeout controls, screenshot artifacts.
2. Optional queue mode toggle for async execution.
3. Security/governance phase (auth, secrets, audit trails).

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
Stabilize current UX and execution reliability:
- add validation guardrails for workflow/input mismatches
- add failure artifacts and richer diagnostics
- introduce opt-in queued execution mode for non-interactive environments
