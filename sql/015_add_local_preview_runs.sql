-- Phase 1 local-preview metadata. Preview sessions remain in memory; this
-- migration intentionally does not add a persistent agent/device identity.
ALTER TABLE workflow_runs
  ADD COLUMN execution_mode VARCHAR(30) NOT NULL DEFAULT 'server' AFTER trigger_source,
  ADD COLUMN target_step_id VARCHAR(120) NULL AFTER execution_mode,
  ADD COLUMN definition_hash CHAR(64) NULL AFTER target_step_id,
  ADD COLUMN error_code VARCHAR(50) NULL AFTER error_summary,
  ADD KEY idx_workflow_runs_mode_user_status (execution_mode, created_by_user_id, status, created_at);
