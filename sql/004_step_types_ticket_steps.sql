USE `workflow_builder`;

INSERT IGNORE INTO `workflow_builder`.`step_types` (`key`, `name`, `description`, `is_active`, `sort_order`)
VALUES
  ('ticket_select_scenario', 'Ticket Select Scenario', 'Select scenario in the ticket UI scenario dropdown.', 1, 90),
  ('ticket_create_new_ticket', 'Ticket Create New Ticket', 'Click Create New Ticket and prepare ticket form scope.', 1, 100),
  ('ticket_fill_fields', 'Ticket Fill Fields (Inline)', 'Fill ticket form fields from args.fields (ticket-scenario structure).', 1, 110),
  ('ticket_fill_fields_from_scenario', 'Ticket Fill Fields From Scenario', 'Fill ticket fields by reading scenario data from file path.', 1, 120),
  ('ticket_submit', 'Ticket Submit', 'Submit ticket and confirm dialog.', 1, 130);
