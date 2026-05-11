# Planned Phases

## Phase 0 - Product and Technical Definition
### Objective
Lock down scope, architecture, and delivery sequence before code scaffolding.

### Planned work
- Finalize workflow-builder requirements and MVP boundaries.
- Confirm generic site-automation model (not tied to one app).
- Define initial JSON workflow contract and variable interpolation rules.
- Decide stack and local dev topology.

### Deliverables
- `WORKFLOW_BUILDER_PLAN.md` (approved).
- Agreed MVP feature list and out-of-scope list.

### Exit criteria
- No open architectural blockers.
- MVP scope accepted.

## Phase 1 - Backend Skeleton
### Objective
Establish a runnable backend foundation.

### Planned work
- Scaffold `FastAPI` project structure.
- Add config management (`.env`, settings module).
- Set up DB connection and schema-first SQL workflow.
- Implement health check and base API routing.

### Deliverables
- Running API service with `/health` endpoint.
- Base project layout for API, models, services, workers.

### Exit criteria
- App boots locally without manual patching.
- Health endpoint returns success.

### Progress
- Status: `completed`
- Last updated: `2026-05-08`
- Completed:
  - Added API entrypoint at `app/main.py`.
  - Added API router at `app/api/router.py`.
  - Added health route at `app/api/routes/health.py` (`GET /health`).
  - Added app settings layer at `app/core/settings.py` using existing `.env` config loader.
  - Added dependency manifest at `requirements.txt` (`fastapi`, `uvicorn[standard]`, `pymysql`).
  - Kept DB workflow schema-first with ordered SQL files in `sql/`.
- Verification completed:
  - Local API boot confirmed.
  - `GET /` returns expected app message.
  - `GET /health` returns HTTP 200 with status `ok`.

## Phase 2 - Data Model and Persistence
### Objective
Persist workflow definitions, versions, runs, and step logs.

### Planned work
- Implement DB schemas:
  - workflows
  - workflow_versions
  - workflow_runs
  - workflow_step_runs
- Add create/read APIs for workflows and versions.
- Add validation for payload structure.

### Deliverables
- Schema-first SQL files and persistence services.
- CRUD endpoints for workflow and version management.

### Exit criteria
- Can create and fetch versioned workflows via API.
- Validation catches malformed workflow definitions.

### Progress
- Status: `completed`
- Last updated: `2026-05-08`
- Completed:
  - Added workflow schemas with request validation:
    - `app/schemas/workflow.py`
  - Added DB transaction helper:
    - `app/services/db.py`
  - Added repository layer for workflow/workflow_version persistence:
    - `app/services/workflow_repository.py`
  - Added workflow/version routes:
    - `POST /workflows`
    - `GET /workflows`
    - `GET /workflows/{workflow_id}`
    - `POST /workflows/{workflow_id}/versions`
    - `GET /workflows/{workflow_id}/versions`
    - route file: `app/api/routes/workflows.py`
  - Wired routes into main router:
    - `app/api/router.py`
- Verification completed:
  - API smoke test passed for create/read workflow and create/read workflow versions against live MySQL DB.
  - `GET /health` remains successful after integration.

## Phase 3 - Workflow Execution Engine (Synchronous Core)
### Objective
Execute workflow steps in order with structured runtime context.

### Planned work
- Build step-runner abstraction.
- Implement first generic step types:
  - `goto_url`
  - `fill_input`
  - `click`
  - `select_option`
  - `wait_for_element`
  - assertion steps
- Add input/template resolution (e.g., `{{inputs.base_url}}`).
- Record per-step status and errors.

### Deliverables
- In-process execution service callable from API.
- Step-level logs and run summary states.

### Exit criteria
- A simple workflow can run end-to-end and produce logs.

### Progress
- Status: `completed`
- Last updated: `2026-05-08`
- Completed:
  - Added template interpolation helper for runtime inputs:
    - `app/engine/template.py`
    - Supports `{{inputs.*}}` and nested path resolution.
  - Added synchronous step engine and handler registry:
    - `app/engine/steps.py`
    - Implemented generic step types:
      - `goto_url`
      - `fill_input`
      - `click`
      - `select_option`
      - `wait_for_element`
      - `assert_url_not_equal`
      - `assert_text_visible`
      - `run_custom_action`
  - Added workflow runner service:
    - `app/services/workflow_runner.py`
    - Executes steps sequentially and records pass/fail at step level.
  - Added run persistence repository:
    - `app/services/workflow_run_repository.py`
    - Writes `workflow_runs` and `workflow_step_runs`.
  - Extended workflow repository with version lookup:
    - `app/services/workflow_repository.py` (`get_workflow_version`)
  - Added run schemas:
    - `app/schemas/workflow_run.py`
  - Added run APIs:
    - `POST /workflow-runs`
    - `GET /workflow-runs/{run_id}`
    - `GET /workflow-runs/{run_id}/steps`
    - route file: `app/api/routes/workflow_runs.py`
  - Wired run routes into API router:
    - `app/api/router.py`
- Verification completed:
  - Smoke test created workflow + version, executed run synchronously, and fetched run + step logs.
  - Verified result: run status `passed`, step statuses persisted as `passed`.
- Note:
  - Current Phase 3 step execution is state-driven and synchronous (engine core).
  - Real browser-backed execution with Playwright handlers will be layered in next implementation steps.

## Phase 4 - Async Worker and Queue
### Objective
Run workflows asynchronously and reliably.

### Planned work
- Integrate `Celery` + `Redis`.
- Move execution to worker tasks.
- Add run state transitions (`queued`, `running`, `passed`, `failed`).
- Add timeout and cancellation hooks (MVP-safe baseline).

### Deliverables
- `POST /workflow-runs` enqueues runs.
- Worker updates run and step records during execution.

### Exit criteria
- Workflow runs survive API process restarts.
- Run status is queryable until completion.

### Progress
- Status: `completed`
- Last updated: `2026-05-08`
- Completed:
  - Added Celery app wiring:
    - `app/worker/celery_app.py`
  - Added workflow run task:
    - `app/worker/tasks.py` (`workflow_runs.execute`)
  - Added worker package export:
    - `app/worker/__init__.py`
  - Updated run creation flow to queue-first:
    - `POST /workflow-runs` now creates run as `queued` and enqueues task.
    - on enqueue failure, run is finalized as `failed` with queue error summary.
  - Updated runner service split:
    - `run_workflow_version(...)` now creates queued run only.
    - `execute_run(run_id)` executes and transitions `running` -> `passed/failed`.
  - Updated run repository transitions:
    - `create_queued_run(...)`
    - `mark_run_running(...)`
  - Added queue configuration keys in `.env.example`:
    - `CELERY_BROKER_URL`
    - `CELERY_RESULT_BACKEND`
    - `CELERY_TASK_ALWAYS_EAGER`
  - Updated dependencies:
    - `requirements.txt` now includes `celery` and `redis`.
- Verification completed:
  - Eager-mode smoke test (`CELERY_TASK_ALWAYS_EAGER=true`) passed end-to-end:
    - create workflow/version
    - `POST /workflow-runs`
    - `GET /workflow-runs/{id}`
    - `GET /workflow-runs/{id}/steps`
    - observed run status `passed`
  - Non-eager mode validation passed with real worker + broker:
    - Celery worker started and consumed queued tasks.
    - API returned run records, and run/step status endpoints confirmed completion.

## Phase 5 - Frontend MVP
### Objective
Provide usable workflow management and run monitoring UI.

### Planned work
- Build pages for:
  - workflow list
  - workflow create/edit (JSON or simple form builder)
  - run trigger with input payload
  - run details with step timeline/logs
- Add API integration for core endpoints.

### Deliverables
- Web UI for core workflow lifecycle.

### Exit criteria
- User can create, run, and inspect a workflow without touching code.

### Progress
- Status: `completed`
- Last updated: `2026-05-08`
- Completed:
  - Added browser UI page served by FastAPI:
    - `app/web/index.html`
  - Added frontend logic for API integration:
    - `app/web/static/app.js`
  - Added frontend styles:
    - `app/web/static/styles.css`
  - Wired UI serving into app:
    - `app/main.py`
    - `GET /ui`
    - static assets under `/ui/static/*`
  - Implemented UI flows:
    - create workflow
    - list/refresh workflows
    - create workflow version with JSON definition
    - trigger run
    - inspect run and step logs
  - Added phase-1 visual workflow editor (linear drag-sort):
    - Step palette for supported step types
    - Add/remove step cards
    - Drag-and-drop step reordering
    - Inline step `args` JSON editing
    - Two-way sync between visual cards and `definition_json`
    - Auto-load latest workflow version into editor for faster edits
- Verification completed:
  - Smoke check passed for:
    - `GET /ui`
    - `GET /ui/static/app.js`
    - `GET /ui/static/styles.css`
  - Existing API endpoints (`/`, `/health`) remained healthy after UI integration.
  - Visual editor sync verified:
    - loading a workflow populates step cards from latest version JSON
    - reordering cards updates serialized `definition_json.steps`
    - creating a new version persists visual-editor changes

## Phase 6 - Template Library and Reusability
### Objective
Ship reusable starter templates, including existing call-flow behavior.

### Planned work
- Convert current `test_call.py` flow into template workflow(s).
- Add template metadata and import endpoint.
- Ensure templates work with configurable `base_url` and inputs.

### Deliverables
- Starter templates (including current business flow).
- Documentation on adapting templates to other websites.

### Exit criteria
- Template can be imported and run with minimal edits.

### Progress
- Status: `completed`
- Last updated: `2026-05-08`
- Completed:
  - Added template schemas:
    - `app/schemas/template.py`
  - Added template repository service:
    - `app/services/template_repository.py`
  - Added default starter template seeding:
    - `generic_login_flow_v1`
  - Added template APIs:
    - `POST /workflow-templates/seed-defaults`
    - `POST /workflow-templates`
    - `GET /workflow-templates`
    - `POST /workflow-templates/{template_id}/import`
  - Wired template routes into API:
    - `app/api/routes/templates.py`
    - `app/api/router.py`
  - Import endpoint behavior:
    - Creates a new workflow from template metadata.
    - Creates version 1 using template `definition_json`.
- Verification completed:
  - Seed default template succeeded.
  - Template listing succeeded.
  - Template import created workflow + version.
  - Imported version was accepted by run trigger endpoint (`POST /workflow-runs` returned `queued`).

## Phase 7 - Hardening and Observability
### Objective
Improve reliability, debuggability, and operational safety.

### Planned work
- Add retries for transient step failures.
- Capture screenshots/video on failure.
- Improve structured logging and correlation IDs.
- Add rate limits/guardrails for concurrent browser sessions.

### Deliverables
- Better diagnostics and safer execution controls.

### Exit criteria
- Failures are diagnosable from UI/API logs.
- System remains stable under concurrent runs.

### Progress
- Status: `in_progress`
- Last updated: `2026-05-08`
- Completed so far:
  - Added more actionable run-step error surfacing through API/UI flow.
  - Added guided run-input generation from workflow `{{inputs.*}}` placeholders.
  - Added DB-backed run-arg presets for repeatable executions.
- Remaining:
  - retries/backoff strategies
  - screenshot/video artifacts on failure
  - structured correlation IDs and richer observability outputs

## Phase 8 - Security and Governance
### Objective
Protect secrets and control access.

### Planned work
- Add secret storage strategy (not raw in workflow JSON).
- Add authentication and role-based authorization.
- Add audit trail for workflow changes and run triggers.

### Deliverables
- Auth-enabled API and protected run actions.
- Secret reference mechanism (`{{secrets.*}}`).

### Exit criteria
- Sensitive values are no longer embedded in plain definitions.
- Access controls enforced for workflow operations.

## Phase 9 - Production Readiness
### Objective
Prepare deployment, operations, and handover.

### Planned work
- Containerization and environment configs.
- CI pipeline for lint/tests/build.
- Deployment docs and runbook.
- Backup and recovery plan for workflow metadata.

### Deliverables
- Deployable artifacts and operational documentation.

### Exit criteria
- System can be deployed repeatably.
- Team has clear run/maintain procedures.

## Milestone Summary
1. Foundation: Phases 0-2
2. Execution Core: Phases 3-4
3. Usability: Phases 5-6
4. Reliability and Security: Phases 7-8
5. Go-live: Phase 9

## Post-Phase Delivery Notes (Completed)
- Dedicated editor routing and focused editing:
  - Added `/ui/editor` page for single-workflow editing.
  - Dashboard `/ui` keeps workflow/version viewing and routes into editor.
- Editor UX improvements:
  - Workflow dropdown in editor.
  - Active workflow indicator.
  - Drag handle-only reordering to avoid text-input cursor conflicts.
  - Side-by-side visual editor + JSON panel.
- Version lifecycle updates:
  - Added in-place save (`PUT /workflows/versions/{version_id}`) via "Save Current Version".
  - Kept "Create New Version" for immutable progression when needed.
- Step type catalog and extensibility:
  - Added `step_types` table and API (`GET /step-types`).
  - Added general step `click_by_role`.
  - Added ticket-specific step chain:
    - `ticket_select_scenario`
    - `ticket_create_new_ticket`
    - `ticket_fill_fields` (inline fields)
    - `ticket_fill_fields_from_scenario`
    - `ticket_submit`
- Run UX improvements:
  - Workflow/version dropdowns in Runs tab.
  - Auto-select latest version and auto-generate inputs template.
  - DB-backed run-arg presets (save/load/delete).
- Execution mode note:
  - Current default run path executes inline from API process to support headed browser visibility during interactive use.

## Post-Phase Delivery Notes (Latest UI/Behavior Updates)
- Workflow lifecycle updates:
  - Added workflow soft delete endpoint behavior (`DELETE /workflows/{id}` -> `status='inactive'`).
  - Added active-only workflow listing support via query filter.
- Run arg preset lifecycle updates:
  - Switched to soft delete (`isActive=0`) and active-only retrieval/update behavior.
- Editor consolidation and UX:
  - Combined workflow selector + editor into one card in dashboard and dedicated editor.
  - Added collapsible create-workflow panel.
  - Added sticky editor header section with top-row save action.
  - Replaced freeform revision number with revision dropdown tied to selected workflow versions.
  - "Create Next Version" now creates next revision from current editor state and switches to it.
  - Added JSON drawer sidebar for definition preview/edit.
- Step builder UX:
  - Added step summary block (title, target, value, sentence summary).
  - Added collapsible step cards showing summary when collapsed.
  - Preserved drag-and-drop and per-step menu actions while collapsed.
  - Added three-dot action menu: Insert Above, Insert Below, Duplicate.
  - Kept Remove as explicit visible action.
