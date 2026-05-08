# Database Design (Current)

## Overview
This document reflects the current schema-first MySQL design implemented under `sql/`.

Primary goals:
- Store workflows and immutable version definitions.
- Track runs and step-level execution logs.
- Support reusable templates and step-type catalogs.
- Support reusable run argument presets.

Database: `MySQL` (`workflow_builder` schema)

## Applied SQL Files
- `001_init.sql`
- `002_schema_versions.sql`
- `003_step_types.sql`
- `004_step_types_ticket_steps.sql`
- `005_step_types_click_by_role.sql`
- `006_run_arg_presets.sql`

## Core Tables

### 1) `workflows`
Logical workflow container.

Key columns:
- `id` INT PK
- `name` VARCHAR(200) NOT NULL
- `description` TEXT NULL
- `status` VARCHAR(30) NOT NULL default `active`
- `created_at`, `updated_at`

### 2) `workflow_versions`
Versioned definitions for each workflow.

Key columns:
- `id` INT PK
- `workflow_id` INT NOT NULL
- `version_number` INT NOT NULL
- `is_published` TINYINT(1) NOT NULL default 0
- `definition_json` JSON NOT NULL
- `created_at`

### 3) `workflow_runs`
Per-execution run records.

Key columns:
- `id` INT PK
- `workflow_id` INT NOT NULL
- `workflow_version_id` INT NOT NULL
- `status` VARCHAR(30) NOT NULL (`queued`, `running`, `passed`, `failed`)
- `trigger_source` VARCHAR(30) NOT NULL default `manual`
- `inputs_json` JSON NULL
- `resolved_definition_json` JSON NULL
- `started_at`, `finished_at`
- `error_summary` TEXT NULL
- `created_at`

### 4) `workflow_step_runs`
Per-step execution logs.

Key columns:
- `id` INT PK
- `workflow_run_id` INT NOT NULL
- `step_index` INT NOT NULL
- `step_id` VARCHAR(120) NULL
- `step_type` VARCHAR(80) NOT NULL
- `status` VARCHAR(30) NOT NULL
- `args_json` JSON NULL
- `started_at`, `finished_at`, `duration_ms`
- `log_text`, `error_text`, `screenshot_path`
- `created_at`

### 5) `workflow_templates`
Reusable workflow definitions.

Key columns:
- `id` INT PK
- `key` VARCHAR(120) NOT NULL
- `name` VARCHAR(200) NOT NULL
- `category` VARCHAR(80) NULL
- `definition_json` JSON NOT NULL
- `created_at`, `updated_at`

### 6) `step_types`
UI/API catalog for allowed step types.

Key columns:
- `id` INT PK
- `key` VARCHAR(80) UNIQUE NOT NULL
- `name` VARCHAR(120) NOT NULL
- `description` VARCHAR(500) NULL
- `is_active` TINYINT(1) NOT NULL default 1
- `sort_order` INT NOT NULL default 0
- `created_at`, `updated_at`

Includes generic and ticket-specific types, e.g.:
- `goto_url`, `fill_input`, `click`, `click_by_role`, `select_option`, `wait_for_element`
- `assert_url_not_equal`, `assert_text_visible`
- `run_custom_action`
- `ticket_select_scenario`, `ticket_create_new_ticket`, `ticket_fill_fields`, `ticket_fill_fields_from_scenario`, `ticket_submit`

### 7) `run_arg_presets`
Saved input JSON presets for runs.

Key columns:
- `id` INT PK
- `name` VARCHAR(120) NOT NULL
- `workflow_id` INT NULL
- `workflow_version_id` INT NULL
- `inputs_json` JSON NOT NULL
- `created_at`, `updated_at`

## Operational Notes
- Schema is maintained with additive SQL files; no migration framework is required.
- API and repository layers currently do not enforce foreign keys at DB level; integrity is controlled in service logic.
- For future hardening, consider:
  - adding FK constraints and secondary indexes
  - uniqueness for `(workflow_id, version_number)`
  - audit tables for workflow/version changes
