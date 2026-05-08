-- 001_init.sql
-- Minimal schema bootstrap (primary keys only, no foreign keys)

CREATE TABLE IF NOT EXISTS `workflow_builder`.`workflows` (
  `id` INT NOT NULL,
  `name` VARCHAR(200) NOT NULL,
  `description` TEXT NULL,
  `status` VARCHAR(30) NOT NULL DEFAULT 'active',
  `created_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_builder`.`workflow_versions` (
  `id` INT NOT NULL,
  `workflow_id` INT NOT NULL,
  `version_number` INT NOT NULL,
  `is_published` TINYINT(1) NOT NULL DEFAULT 0,
  `definition_json` JSON NOT NULL,
  `created_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_builder`.`workflow_runs` (
  `id` INT NOT NULL,
  `workflow_id` INT NOT NULL,
  `workflow_version_id` INT NOT NULL,
  `status` VARCHAR(30) NOT NULL,
  `trigger_source` VARCHAR(30) NOT NULL DEFAULT 'manual',
  `inputs_json` JSON NULL,
  `resolved_definition_json` JSON NULL,
  `started_at` DATETIME NULL DEFAULT NULL,
  `finished_at` DATETIME NULL DEFAULT NULL,
  `error_summary` TEXT NULL,
  `created_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_builder`.`workflow_step_runs` (
  `id` INT NOT NULL,
  `workflow_run_id` INT NOT NULL,
  `step_index` INT NOT NULL,
  `step_id` VARCHAR(120) NULL,
  `step_type` VARCHAR(80) NOT NULL,
  `status` VARCHAR(30) NOT NULL,
  `args_json` JSON NULL,
  `started_at` DATETIME NULL DEFAULT NULL,
  `finished_at` DATETIME NULL DEFAULT NULL,
  `duration_ms` INT NULL,
  `log_text` LONGTEXT NULL,
  `error_text` LONGTEXT NULL,
  `screenshot_path` TEXT NULL,
  `created_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_builder`.`workflow_templates` (
  `id` INT NOT NULL,
  `key` VARCHAR(120) NOT NULL,
  `name` VARCHAR(200) NOT NULL,
  `category` VARCHAR(80) NULL,
  `definition_json` JSON NOT NULL,
  `created_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
