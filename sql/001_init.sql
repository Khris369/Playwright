-- 001_init.sql
-- Complete first-time schema bootstrap for WorkflowBuilder.

CREATE DATABASE IF NOT EXISTS `workflow_builder`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `workflow_builder`;

CREATE TABLE IF NOT EXISTS `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(255) NOT NULL,
  `email` VARCHAR(254),
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

CREATE TABLE IF NOT EXISTS `workflows` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `owner_user_id` INT NULL,
  `created_by_user_id` INT NULL,
  `updated_by_user_id` INT NULL,
  `name` VARCHAR(200) NOT NULL,
  `description` TEXT NULL,
  `status` VARCHAR(30) NOT NULL DEFAULT 'active',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_workflows_owner_status` (`owner_user_id`, `status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_versions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `workflow_id` INT NOT NULL,
  `created_by_user_id` INT NULL,
  `updated_by_user_id` INT NULL,
  `version_number` INT NOT NULL,
  `is_published` TINYINT(1) NOT NULL DEFAULT 0,
  `definition_json` JSON NOT NULL,
  `lock_version` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_workflow_versions_number` (`workflow_id`, `version_number`),
  KEY `idx_workflow_versions_created_by` (`created_by_user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_runs` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `workflow_id` INT NOT NULL,
  `workflow_version_id` INT NOT NULL,
  `created_by_user_id` INT NULL,
  `status` VARCHAR(30) NOT NULL,
  `trigger_source` VARCHAR(30) NOT NULL DEFAULT 'manual',
  `inputs_json` JSON NULL,
  `resolved_definition_json` JSON NULL,
  `started_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  `error_summary` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_workflow_runs_version_created` (`workflow_version_id`, `created_at`),
  KEY `idx_workflow_runs_user_created` (`created_by_user_id`, `created_at`),
  KEY `idx_workflow_runs_user_status` (`created_by_user_id`, `status`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_step_runs` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `workflow_run_id` INT NOT NULL,
  `step_index` INT NOT NULL,
  `step_id` VARCHAR(120) NULL,
  `step_type` VARCHAR(80) NOT NULL,
  `status` VARCHAR(30) NOT NULL,
  `args_json` JSON NULL,
  `started_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  `duration_ms` INT NULL,
  `log_text` LONGTEXT NULL,
  `error_text` LONGTEXT NULL,
  `screenshot_path` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_workflow_step_runs_run_step` (`workflow_run_id`, `step_id`),
  KEY `idx_workflow_step_runs_run_index` (`workflow_run_id`, `step_index`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

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
  KEY `idx_workflow_run_artifacts_step` (`step_run_id`),
  KEY `idx_workflow_run_artifacts_user_created` (`created_by_user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_templates` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `key` VARCHAR(120) NOT NULL,
  `name` VARCHAR(200) NOT NULL,
  `category` VARCHAR(80) NULL,
  `definition_json` JSON NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_workflow_templates_key` (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `schema_versions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `version` VARCHAR(100) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_schema_versions_version` (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `step_types` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `key` VARCHAR(80) NOT NULL,
  `name` VARCHAR(120) NOT NULL,
  `description` VARCHAR(500) NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `sort_order` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_step_types_key` (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `step_types` (`key`, `name`, `description`, `is_active`, `sort_order`) VALUES
  ('goto_url', 'Go To URL', 'Navigate browser page URL.', 1, 10),
  ('fill_input', 'Fill Input', 'Type or fill value into input element.', 1, 20),
  ('click', 'Click Element', 'Click an element using selector.', 1, 30),
  ('select_option', 'Select Option', 'Select value or label in dropdown.', 1, 40),
  ('wait_for_element', 'Wait For Element', 'Wait until element is present or visible.', 1, 50),
  ('wait_timeout', 'Wait Timeout', 'Wait for bounded duration.', 1, 55),
  ('assert_url_not_equal', 'Assert URL Not Equal', 'Assert current URL not equal value.', 1, 60),
  ('assert_text_visible', 'Assert Text Visible', 'Assert specific text visible on page.', 1, 70),
  ('ticket_select_scenario', 'Ticket Select Scenario', 'Select scenario in ticket UI scenario dropdown.', 1, 90),
  ('ticket_create_new_ticket', 'Ticket Create New Ticket', 'Click Create New Ticket and prepare ticket form scope.', 1, 100),
  ('ticket_fill_fields', 'Ticket Fill Fields', 'Fill ticket form fields from args.fields.', 1, 110),
  ('ticket_submit', 'Ticket Submit', 'Submit the current ticket form.', 1, 120)
ON DUPLICATE KEY UPDATE
  `name` = VALUES(`name`),
  `description` = VALUES(`description`),
  `is_active` = VALUES(`is_active`),
  `sort_order` = VALUES(`sort_order`);

CREATE TABLE IF NOT EXISTS `run_arg_presets` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `owner_user_id` INT NULL,
  `name` VARCHAR(120) NOT NULL,
  `workflow_id` INT NULL,
  `workflow_version_id` INT NULL,
  `isActive` TINYINT(1) NOT NULL DEFAULT 1,
  `inputs_json` JSON NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_run_arg_presets_workflow` (`workflow_id`, `workflow_version_id`, `isActive`),
  KEY `idx_run_arg_presets_owner_active` (`owner_user_id`, `isActive`, `updated_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
