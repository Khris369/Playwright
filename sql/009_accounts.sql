-- 009_accounts.sql
-- Existing-database update: users and nullable account ownership columns.
-- Authentication/session enforcement is intentionally implemented separately.
-- Fresh databases already receive these objects from 001_init.sql.

USE `workflow_builder`;

CREATE TABLE IF NOT EXISTS `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(255) NOT NULL,
  `email` VARCHAR(254) NOT NULL,
  `display_name` VARCHAR(120) NOT NULL,
  `password_hash` VARCHAR(255) NULL,
  `role` VARCHAR(30) NOT NULL DEFAULT 'user',
  `status` VARCHAR(30) NOT NULL DEFAULT 'active',
  `last_login_at` DATETIME NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_users_email` (`email`),
  KEY `idx_users_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `user_sessions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT NOT NULL,
  `token_hash` CHAR(64) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `expires_at` DATETIME NOT NULL,
  `last_seen_at` DATETIME NULL,
  `revoked_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_user_sessions_token_hash` (`token_hash`),
  KEY `idx_user_sessions_user` (`user_id`, `expires_at`),
  KEY `idx_user_sessions_expiry` (`expires_at`, `revoked_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `workflows`
  ADD COLUMN  `owner_user_id` INT NULL AFTER `id`,
  ADD COLUMN  `created_by_user_id` INT NULL AFTER `owner_user_id`,
  ADD KEY `idx_workflows_owner_status` (`owner_user_id`, `status`, `created_at`);

ALTER TABLE `workflow_versions`
  ADD COLUMN  `created_by_user_id` INT NULL AFTER `workflow_id`,
  ADD COLUMN  `updated_by_user_id` INT NULL AFTER `created_by_user_id`,
  ADD KEY `idx_workflow_versions_created_by` (`created_by_user_id`, `created_at`);

ALTER TABLE `workflow_runs`
  ADD COLUMN  `created_by_user_id` INT NULL AFTER `workflow_version_id`,
  ADD KEY `idx_workflow_runs_user_created` (`created_by_user_id`, `created_at`),
  ADD KEY `idx_workflow_runs_user_status` (`created_by_user_id`, `status`, `created_at`);

CREATE TABLE IF NOT EXISTS `workflow_run_artifacts` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `workflow_run_id` INT NOT NULL,
  `created_by_user_id` INT NULL,
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

ALTER TABLE `workflow_run_artifacts`
  ADD COLUMN  `created_by_user_id` INT NULL AFTER `workflow_run_id`,
  ADD KEY `idx_workflow_run_artifacts_user_created` (`created_by_user_id`, `created_at`);

ALTER TABLE `run_arg_presets`
  ADD COLUMN  `owner_user_id` INT NULL AFTER `id`,
  ADD KEY `idx_run_arg_presets_owner_active` (`owner_user_id`, `isActive`, `updated_at`);
