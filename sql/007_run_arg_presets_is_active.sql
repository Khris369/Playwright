-- 007_run_arg_presets_is_active.sql
-- Existing-database update: add soft-delete support to run argument presets.

USE `workflow_builder`;

ALTER TABLE `run_arg_presets`
  ADD COLUMN `isActive` TINYINT(1) NOT NULL DEFAULT 1 AFTER `workflow_version_id`;

UPDATE `run_arg_presets`
SET `isActive` = 1
WHERE `isActive` IS NULL;
