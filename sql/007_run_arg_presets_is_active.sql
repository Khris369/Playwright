USE `workflow_builder`;

ALTER TABLE `workflow_builder`.`run_arg_presets`
  ADD COLUMN IF NOT EXISTS `isActive` TINYINT(1) NOT NULL DEFAULT 1
  AFTER `workflow_version_id`;

UPDATE `workflow_builder`.`run_arg_presets`
SET `isActive` = 1
WHERE `isActive` IS NULL;
