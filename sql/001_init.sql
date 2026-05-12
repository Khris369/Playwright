-- 001_init.sql
-- Minimal schema bootstrap (primary keys only, no foreign keys)

USE `workflow_builder`;

CREATE TABLE IF NOT EXISTS `workflow_builder`.`workflows` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(200) NOT NULL,
  `description` TEXT NULL,
  `status` VARCHAR(30) NOT NULL DEFAULT 'active',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_builder`.`workflow_versions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `workflow_id` INT NOT NULL,
  `version_number` INT NOT NULL,
  `is_published` TINYINT(1) NOT NULL DEFAULT 0,
  `definition_json` JSON NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_builder`.`workflow_runs` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `workflow_id` INT NOT NULL,
  `workflow_version_id` INT NOT NULL,
  `status` VARCHAR(30) NOT NULL,
  `trigger_source` VARCHAR(30) NOT NULL DEFAULT 'manual',
  `inputs_json` JSON NULL,
  `resolved_definition_json` JSON NULL,
  `started_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  `error_summary` TEXT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_builder`.`workflow_step_runs` (
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
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_builder`.`workflow_templates` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `key` VARCHAR(120) NOT NULL,
  `name` VARCHAR(200) NOT NULL,
  `category` VARCHAR(80) NULL,
  `definition_json` JSON NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_builder`.`schema_versions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `version` VARCHAR(100) NOT NULL,
  `applied_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_builder`.`step_types` (
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

INSERT IGNORE INTO `workflow_builder`.`step_types` (`key`, `name`, `description`, `is_active`, `sort_order`)
VALUES
  ('goto_url', 'Go To URL', 'Navigate browser page to a URL.', 1, 10),
  ('fill_input', 'Fill Input', 'Type or fill a value into an input element.', 1, 20),
  ('click', 'Click Element', 'Click an element using a selector.', 1, 30),
  ('click_by_role', 'Click By Role', 'Click an element by role and accessible name (with optional scope).', 1, 35),
  ('select_option', 'Select Option', 'Select a value/label in a dropdown.', 1, 40),
  ('wait_for_element', 'Wait For Element', 'Wait until an element is present/visible.', 1, 50),
  ('assert_url_not_equal', 'Assert URL Not Equal', 'Assert the current URL is not equal to a given value.', 1, 60),
  ('assert_text_visible', 'Assert Text Visible', 'Assert specific text is visible on the page.', 1, 70),
  ('run_custom_action', 'Run Custom Action', 'Execute a registered custom action handler.', 1, 80),
  ('ticket_select_scenario', 'Ticket Select Scenario', 'Select scenario in the ticket UI scenario dropdown.', 1, 90),
  ('ticket_create_new_ticket', 'Ticket Create New Ticket', 'Click Create New Ticket and prepare ticket form scope.', 1, 100),
  ('ticket_fill_fields', 'Ticket Fill Fields (Inline)', 'Fill ticket form fields from args.fields (ticket-scenario structure).', 1, 110),
  ('ticket_fill_fields_from_scenario', 'Ticket Fill Fields From Scenario', 'Fill ticket fields by reading scenario data from file path.', 1, 120),
  ('ticket_submit', 'Ticket Submit', 'Submit ticket and confirm dialog.', 1, 130);

CREATE TABLE IF NOT EXISTS `workflow_builder`.`run_arg_presets` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(120) NOT NULL,
  `workflow_id` INT NULL,
  `workflow_version_id` INT NULL,
  `isActive` TINYINT(1) NOT NULL DEFAULT 1,
  `inputs_json` JSON NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
