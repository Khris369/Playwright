-- 012_remove_legacy_user_role.sql
-- Remove the superseded single-role column after 011_rbac.sql has migrated
-- existing accounts into user_roles.

USE `workflow_builder`;

ALTER TABLE `users` DROP COLUMN `role`;
