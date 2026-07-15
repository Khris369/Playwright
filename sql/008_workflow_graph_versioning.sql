-- 008_workflow_graph_versioning.sql
-- Prepared migration only. Apply explicitly after backing up the database.
USE `workflow_builder`;

ALTER TABLE `workflow_versions`
  ADD COLUMN `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER `created_at`,
  ADD COLUMN `lock_version` INT NOT NULL DEFAULT 0 AFTER `definition_json`,
  ADD UNIQUE KEY `uniq_workflow_versions_number` (`workflow_id`, `version_number`);

ALTER TABLE `workflow_runs`
  ADD KEY `idx_workflow_runs_version_created` (`workflow_version_id`, `created_at`);

ALTER TABLE `workflow_step_runs`
  ADD KEY `idx_workflow_step_runs_run_step` (`workflow_run_id`, `step_id`);
