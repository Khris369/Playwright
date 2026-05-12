# Allure Integration Guide

## Purpose
Define how to integrate Allure reporting into the current workflow-builder stack without breaking the existing UI/API behavior.

Current stack context:
- API/UI: FastAPI (`/ui`, `/workflows`, `/workflow-runs`, etc.)
- Execution: Playwright-driven workflow engine (step-based)
- Persistence: MySQL (`workflow_runs`, `workflow_step_runs`, etc.)

## Goals
- Generate readable test-style reports for workflow runs.
- Preserve current DB-backed run/step logs as source of truth.
- Keep integration optional (can be disabled in local/dev).

## Non-Goals (Initial)
- Replacing the existing run monitor UI.
- Rewriting step execution to pytest-native tests.
- Hard dependency on Allure for run success/failure.

## Integration Options

### Option A (Recommended): Direct Allure Result Writer from Runner
Write Allure result JSON/artifacts during workflow execution.

Pros:
- Works with existing run model.
- No pytest migration required.
- Fine-grained mapping from `workflow_step_runs` to Allure steps.

Cons:
- Need to implement result file generation and attachments manually.

### Option B: Pytest Wrapper Per Workflow Run
Wrap each run in a synthetic pytest test and use `allure-pytest`.

Pros:
- Uses standard allure plugin behavior.

Cons:
- Architectural overhead.
- Harder to map async/background execution and run IDs cleanly.

Use Option A first.

## Recommended Architecture (Option A)

### 1) Output Structure
- Allure results directory per environment (example): `artifacts/allure-results/`
- Optional grouped subfolder per run: `artifacts/allure-results/run_{run_id}/`

### 2) Mapping Model
- Allure "test case" = one workflow run
  - Name: `Workflow #{workflow_id} - Version #{workflow_version_id} - Run #{run_id}`
  - Status: mapped from run status (`passed`, `failed`, etc.)
- Allure "steps" = each workflow step run
  - Step name: `[{step_index}] {step_type}`
  - Status: mapped from step status
  - Attachments:
    - `log_text`
    - `error_text` (if present)
    - screenshot file (if present)

### 3) Metadata
- Labels:
  - `feature=workflow-builder`
  - `suite=workflow-runner`
  - `workflow_id`, `workflow_version_id`
- Parameters:
  - selected inputs keys (mask secrets)

### 4) Trigger Point
Integrate after run execution finalization:
- At the end of `execute_run(run_id)` (or equivalent run-complete path), emit/update Allure result.

### 5) Serving Reports
- CI/local command:
  - `allure generate artifacts/allure-results --clean -o artifacts/allure-report`
  - `allure open artifacts/allure-report`
- Optional FastAPI static mount for generated HTML report.

## Configuration
Add env flags:
- `ALLURE_ENABLED=true|false`
- `ALLURE_RESULTS_DIR=artifacts/allure-results`
- `ALLURE_MASK_INPUT_KEYS=password,token,secret,api_key`

Behavior:
- If disabled, no-op.
- If enabled but write fails, log warning and continue run flow.

## Data and Security Notes
- Do not include raw secrets in parameters/attachments.
- Redact known sensitive keys before writing attachments.
- Keep Allure artifacts out of public static hosting unless access-controlled.

## Implementation Plan

### Phase 1: Minimal Reporting
- Add `app/services/allure_reporter.py`:
  - `emit_workflow_run(run, step_runs, workflow, version)` entrypoint
  - status mapping
  - basic JSON result file output
- Hook into run completion path.
- Add env config and guarded no-op behavior.

Exit criteria:
- One report file generated per run.
- Report status reflects run status.

### Phase 2: Step Details + Attachments
- Add step blocks for each `workflow_step_runs` row.
- Attach log/error text and screenshots.
- Add input redaction logic.

Exit criteria:
- Step-level details visible in Allure report.

### Phase 3: CI + Developer UX
- Add make/script commands:
  - `report:allure:generate`
  - `report:allure:open`
- Optionally publish report artifact in CI.

Exit criteria:
- Team can generate/open report with one command.

## Suggested File Changes
- `app/core/settings.py`
  - add Allure-related settings
- `app/services/allure_reporter.py`
  - new reporter service
- `app/services/workflow_runner.py` (or completion path)
  - call reporter on run completion
- `knowledge/LAUNCH.md`
  - add optional Allure commands

## Validation Checklist
- Run pass case:
  - report shows passed status and all steps passed.
- Run fail case:
  - report shows failed step, error text attachment.
- Redaction:
  - masked input keys are not exposed.
- Resilience:
  - reporting failure does not fail workflow run completion path.
