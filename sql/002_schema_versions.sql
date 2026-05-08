-- 002_schema_versions.sql
-- Optional table to track applied SQL files in schema-first workflow.

CREATE TABLE IF NOT EXISTS `workflow_builder`.`schema_versions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `version` VARCHAR(100) NOT NULL,
  `applied_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
