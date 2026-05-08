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
- Migration files and ORM models.
- CRUD endpoints for workflow and version management.

### Exit criteria
- Can create and fetch versioned workflows via API.
- Validation catches malformed workflow definitions.

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
