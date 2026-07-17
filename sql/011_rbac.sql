-- 011_rbac.sql
-- Multi-role RBAC and future workflow-sharing assignments.

USE `workflow_builder`;

CREATE TABLE IF NOT EXISTS `roles` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(50) NOT NULL,
  `description` VARCHAR(255) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_roles_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `permissions` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `permission_key` VARCHAR(100) NOT NULL,
  `description` VARCHAR(255) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_permissions_key` (`permission_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `user_roles` (
  `user_id` INT NOT NULL,
  `role_id` INT NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`, `role_id`),
  KEY `idx_user_roles_role` (`role_id`),
  CONSTRAINT `fk_user_roles_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_user_roles_role` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `role_permissions` (
  `role_id` INT NOT NULL,
  `permission_id` INT NOT NULL,
  PRIMARY KEY (`role_id`, `permission_id`),
  KEY `idx_role_permissions_permission` (`permission_id`),
  CONSTRAINT `fk_role_permissions_role` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_role_permissions_permission` FOREIGN KEY (`permission_id`) REFERENCES `permissions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workflow_members` (
  `workflow_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `access_level` VARCHAR(30) NOT NULL DEFAULT 'viewer',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`workflow_id`, `user_id`),
  KEY `idx_workflow_members_user` (`user_id`, `workflow_id`),
  CONSTRAINT `fk_workflow_members_workflow` FOREIGN KEY (`workflow_id`) REFERENCES `workflows` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_workflow_members_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `roles` (`name`, `description`) VALUES
  ('viewer', 'Read permitted workflow resources.'),
  ('editor', 'Create and edit workflows and versions.'),
  ('runner', 'Trigger and cancel workflow runs.'),
  ('admin', 'Global administration and all permissions.')
ON DUPLICATE KEY UPDATE `description` = VALUES(`description`);

INSERT INTO `permissions` (`permission_key`, `description`) VALUES
  ('workflow.view', 'View workflows, versions, runs, and artifacts.'),
  ('workflow.edit', 'Create and edit workflows and versions.'),
  ('workflow.run', 'Trigger and cancel workflow runs.'),
  ('workflow.delete', 'Deactivate workflows and delete presets.'),
  ('user.manage', 'Manage users and role assignments.'),
  ('audit.view', 'View governance audit events.')
ON DUPLICATE KEY UPDATE `description` = VALUES(`description`);

INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r CROSS JOIN `permissions` p WHERE r.name = 'admin';
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r JOIN `permissions` p ON p.permission_key = 'workflow.view' WHERE r.name IN ('viewer', 'editor', 'runner');
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r JOIN `permissions` p ON p.permission_key = 'workflow.edit' WHERE r.name = 'editor';
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r JOIN `permissions` p ON p.permission_key = 'workflow.run' WHERE r.name = 'runner';
INSERT IGNORE INTO `role_permissions` (`role_id`, `permission_id`)
SELECT r.id, p.id FROM `roles` r JOIN `permissions` p ON p.permission_key = 'workflow.delete' WHERE r.name = 'editor';

INSERT IGNORE INTO `user_roles` (`user_id`, `role_id`)
SELECT u.id, r.id FROM `users` u JOIN `roles` r ON r.name = CASE
  WHEN u.role IN ('admin', 'viewer', 'editor', 'runner') THEN u.role
  ELSE 'viewer'
END;
