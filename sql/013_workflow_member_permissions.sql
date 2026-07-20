-- 013_workflow_member_permissions.sql
-- Replace one workflow member access_level with independent permissions.

USE `workflow_builder`;

CREATE TABLE IF NOT EXISTS `workflow_member_permissions` (
  `workflow_id` INT NOT NULL,
  `user_id` INT NOT NULL,
  `permission_key` VARCHAR(100) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`workflow_id`, `user_id`, `permission_key`),
  KEY `idx_workflow_member_permissions_user` (`user_id`, `workflow_id`),
  CONSTRAINT `fk_workflow_member_permissions_member`
    FOREIGN KEY (`workflow_id`, `user_id`) REFERENCES `workflow_members` (`workflow_id`, `user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO `workflow_member_permissions` (`workflow_id`, `user_id`, `permission_key`)
SELECT workflow_id, user_id,
      CASE access_level
        WHEN 'viewer' THEN 'workflow.view'
        WHEN 'editor' THEN 'workflow.edit'
        WHEN 'runner' THEN 'workflow.run'
      END
FROM `workflow_members`
WHERE access_level IN ('viewer', 'editor', 'runner');

INSERT IGNORE INTO `workflow_member_permissions` (`workflow_id`, `user_id`, `permission_key`)
SELECT workflow_id, user_id, 'workflow.view'
FROM `workflow_members`
WHERE access_level IN ('editor', 'runner');
