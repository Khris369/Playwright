-- 008_workflow_graph_versioning.sql
-- Existing-database update: graph versioning, run snapshots, artifacts, and indexes.
-- Fresh databases already receive these objects from 001_init.sql.

USE `workflow_builder`;

ALTER TABLE `workflow_versions`
  ADD COLUMN  `lock_version` INT NOT NULL DEFAULT 0 AFTER `definition_json`,
  ADD COLUMN  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER `created_at`;

ALTER TABLE `workflow_versions`
  ADD UNIQUE KEY `uniq_workflow_versions_number` (`workflow_id`, `version_number`);

ALTER TABLE `workflow_runs`
  ADD COLUMN  `workflow_id` INT NULL AFTER `id`,
  ADD COLUMN  `trigger_source` VARCHAR(30) NOT NULL DEFAULT 'manual' AFTER `status`,
  ADD COLUMN  `resolved_definition_json` JSON NULL AFTER `inputs_json`;

UPDATE `workflow_runs` AS wr
JOIN `workflow_versions` AS wv ON wv.id = wr.workflow_version_id
SET wr.workflow_id = wv.workflow_id
WHERE wr.workflow_id IS NULL;

ALTER TABLE `workflow_runs`
  MODIFY COLUMN `workflow_id` INT NOT NULL,
  ADD KEY `idx_workflow_runs_version_created` (`workflow_version_id`, `created_at`);

ALTER TABLE `workflow_step_runs`
  ADD COLUMN  `step_id` VARCHAR(120) NULL AFTER `step_index`,
  ADD COLUMN  `duration_ms` INT NULL AFTER `finished_at`,
  ADD COLUMN  `screenshot_path` TEXT NULL AFTER `error_text`,
  ADD KEY `idx_workflow_step_runs_run_step` (`workflow_run_id`, `step_id`),
  ADD KEY `idx_workflow_step_runs_run_index` (`workflow_run_id`, `step_index`);

CREATE TABLE IF NOT EXISTS `workflow_run_artifacts` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `workflow_run_id` INT NOT NULL,
  `step_run_id` INT NULL,
  `artifact_type` VARCHAR(50) NOT NULL,
  `file_path` VARCHAR(500) NOT NULL,
  `mime_type` VARCHAR(100) NOT NULL,
  `size_bytes` BIGINT NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_workflow_run_artifacts_run_created` (`workflow_run_id`, `created_at`),
  KEY `idx_workflow_run_artifacts_step` (`step_run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
