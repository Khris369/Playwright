-- 014_verify_element_step_type.sql
-- Add the Verify element assertion to the existing step catalogue.

USE `workflow_builder`;

INSERT INTO `step_types` (`key`, `name`, `description`, `is_active`, `sort_order`) VALUES
  ('verify_element', 'Verify Element', 'Require an element to match an expected state.', 1, 65)
ON DUPLICATE KEY UPDATE
  `name` = VALUES(`name`),
  `description` = VALUES(`description`),
  `is_active` = VALUES(`is_active`),
  `sort_order` = VALUES(`sort_order`);
