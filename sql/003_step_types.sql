USE `workflow_builder`;

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
);

INSERT IGNORE INTO `workflow_builder`.`step_types` (`key`, `name`, `description`, `is_active`, `sort_order`)
VALUES
  ('goto_url', 'Go To URL', 'Navigate browser page to a URL.', 1, 10),
  ('fill_input', 'Fill Input', 'Type or fill a value into an input element.', 1, 20),
  ('click', 'Click Element', 'Click an element using a selector.', 1, 30),
  ('select_option', 'Select Option', 'Select a value/label in a dropdown.', 1, 40),
  ('wait_for_element', 'Wait For Element', 'Wait until an element is present/visible.', 1, 50),
  ('assert_url_not_equal', 'Assert URL Not Equal', 'Assert the current URL is not equal to a given value.', 1, 60),
  ('assert_text_visible', 'Assert Text Visible', 'Assert specific text is visible on the page.', 1, 70),
  ('run_custom_action', 'Run Custom Action', 'Execute a registered custom action handler.', 1, 80);
