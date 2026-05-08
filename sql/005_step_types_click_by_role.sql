USE `workflow_builder`;

INSERT IGNORE INTO `workflow_builder`.`step_types` (`key`, `name`, `description`, `is_active`, `sort_order`)
VALUES
  ('click_by_role', 'Click By Role', 'Click an element by role and accessible name (with optional scope).', 1, 35);
