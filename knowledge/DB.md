# Database Design (MVP)

## Overview
This document defines the core tables required for the workflow builder backend.

Primary goals:
- Store workflows and versions.
- Track workflow runs and step-level execution.
- Support reusable templates.
- Keep room for future auth/secrets features.

## Database Choice
Recommended: `PostgreSQL`

## Core Tables

## 1) `workflows`
Stores logical workflow identities.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK, default gen_random_uuid() | Workflow ID |
| name | VARCHAR(200) | NOT NULL | Human-readable name |
| description | TEXT | NULL | Optional description |
| status | VARCHAR(30) | NOT NULL default 'active' | `active`, `archived` |
| created_at | TIMESTAMPTZ | NOT NULL default now() | Created timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL default now() | Updated timestamp |

Indexes:
- `idx_workflows_name` on `(name)`
- `idx_workflows_status` on `(status)`

## 2) `workflow_versions`
Stores immutable versioned workflow definitions.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK, default gen_random_uuid() | Version row ID |
| workflow_id | UUID | NOT NULL, FK -> workflows(id) ON DELETE CASCADE | Parent workflow |
| version_number | INT | NOT NULL | Starts at 1 |
| is_published | BOOLEAN | NOT NULL default false | Optional publish flag |
| definition_json | JSONB | NOT NULL | Full workflow JSON definition |
| created_at | TIMESTAMPTZ | NOT NULL default now() | Created timestamp |

Constraints:
- Unique: `(workflow_id, version_number)`

Indexes:
- `idx_workflow_versions_workflow_id` on `(workflow_id)`
- `idx_workflow_versions_published` on `(workflow_id, is_published)`

## 3) `workflow_runs`
Stores each execution attempt of a workflow version.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK, default gen_random_uuid() | Run ID |
| workflow_id | UUID | NOT NULL, FK -> workflows(id) ON DELETE RESTRICT | Snapshot linkage |
| workflow_version_id | UUID | NOT NULL, FK -> workflow_versions(id) ON DELETE RESTRICT | Exact version run |
| status | VARCHAR(30) | NOT NULL | `queued`, `running`, `passed`, `failed`, `cancelled`, `timed_out` |
| trigger_source | VARCHAR(30) | NOT NULL default 'manual' | `manual`, `api`, `schedule` |
| inputs_json | JSONB | NULL | Runtime inputs |
| resolved_definition_json | JSONB | NULL | Optional resolved copy at run start |
| started_at | TIMESTAMPTZ | NULL | Start timestamp |
| finished_at | TIMESTAMPTZ | NULL | End timestamp |
| error_summary | TEXT | NULL | Run-level error summary |
| created_at | TIMESTAMPTZ | NOT NULL default now() | Enqueue timestamp |

Indexes:
- `idx_workflow_runs_workflow_id` on `(workflow_id)`
- `idx_workflow_runs_version_id` on `(workflow_version_id)`
- `idx_workflow_runs_status` on `(status)`
- `idx_workflow_runs_created_at` on `(created_at DESC)`

## 4) `workflow_step_runs`
Stores per-step execution details for each run.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK, default gen_random_uuid() | Step run ID |
| workflow_run_id | UUID | NOT NULL, FK -> workflow_runs(id) ON DELETE CASCADE | Parent run |
| step_index | INT | NOT NULL | Zero-based step order |
| step_id | VARCHAR(120) | NULL | Optional workflow-defined step id |
| step_type | VARCHAR(80) | NOT NULL | E.g., `goto_url`, `click` |
| status | VARCHAR(30) | NOT NULL | `queued`, `running`, `passed`, `failed`, `skipped` |
| args_json | JSONB | NULL | Resolved args used at execution time |
| started_at | TIMESTAMPTZ | NULL | Start timestamp |
| finished_at | TIMESTAMPTZ | NULL | End timestamp |
| duration_ms | INT | NULL | Derived or persisted duration |
| log_text | TEXT | NULL | Human-readable log chunk |
| error_text | TEXT | NULL | Error detail |
| screenshot_path | TEXT | NULL | Optional artifact path |
| created_at | TIMESTAMPTZ | NOT NULL default now() | Created timestamp |

Constraints:
- Unique: `(workflow_run_id, step_index)`

Indexes:
- `idx_workflow_step_runs_run_id` on `(workflow_run_id)`
- `idx_workflow_step_runs_status` on `(status)`

## 5) `workflow_templates` (Recommended for Phase 6)
Reusable starter definitions, including current call-flow example.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK, default gen_random_uuid() | Template ID |
| key | VARCHAR(120) | NOT NULL UNIQUE | Stable identifier |
| name | VARCHAR(200) | NOT NULL | Template name |
| category | VARCHAR(80) | NULL | E.g., `crm`, `ticketing`, `generic` |
| definition_json | JSONB | NOT NULL | Template workflow JSON |
| created_at | TIMESTAMPTZ | NOT NULL default now() | Created timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL default now() | Updated timestamp |

## Optional Future Tables (Not MVP)

## 6) `secrets`
For secure runtime secret references (Phase 8).

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | UUID | PK | Secret ID |
| name | VARCHAR(150) | NOT NULL UNIQUE | Secret key name |
| provider | VARCHAR(50) | NOT NULL | `vault`, `aws_sm`, etc. |
| reference | TEXT | NOT NULL | External secret reference |
| created_at | TIMESTAMPTZ | NOT NULL default now() | Created timestamp |

## 7) `users`, `roles`, `user_roles`, `audit_logs`
For authz and audit (Phase 8+).

## Relationships Summary
- `workflows (1) -> (many) workflow_versions`
- `workflows (1) -> (many) workflow_runs`
- `workflow_versions (1) -> (many) workflow_runs`
- `workflow_runs (1) -> (many) workflow_step_runs`

## Status Enum Recommendation
Use DB enums or strict check constraints for statuses.

- Workflow status: `active`, `archived`
- Run status: `queued`, `running`, `passed`, `failed`, `cancelled`, `timed_out`
- Step status: `queued`, `running`, `passed`, `failed`, `skipped`

## Notes for Implementation
- Keep `definition_json` immutable per version.
- Persist resolved step arguments in `workflow_step_runs.args_json` for debugging.
- Prefer UUID PKs to simplify distributed execution and API exposure.
- Add `updated_at` trigger for mutable tables (`workflows`, `workflow_templates`).
