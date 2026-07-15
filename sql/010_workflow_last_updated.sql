-- 010_workflow_last_updated.sql
-- Persist workflow-level last save metadata so the dashboard reflects version saves.

ALTER TABLE `workflows`
  ADD COLUMN `updated_by_user_id` INT NULL AFTER `created_by_user_id`,
  ADD KEY `idx_workflows_updated_at` (`updated_at`);
