-- ============================================================
-- 质控通 · 部门/课室管理 数据库变更（可重复执行，幂等）
-- 适用：MySQL 8.0+ / utf8mb4
-- 说明：后端启动时也会自动建表、自动加列；本脚本用于手工执行（Navicat / 生产库）
-- 执行前建议备份：mysqldump -uroot -p qc_hub > qc_hub_backup.sql
-- ============================================================

SET NAMES utf8mb4;

-- 1) 部门表（不存在才建）
CREATE TABLE IF NOT EXISTS `departments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL COMMENT '部门/课室名称',
  `leader` varchar(100) DEFAULT NULL COMMENT '负责人',
  `sort_order` int NOT NULL DEFAULT 0 COMMENT '排序',
  `active` tinyint(1) NOT NULL DEFAULT 1 COMMENT '1启用 0停用',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_departments_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='部门/课室';

-- 2) users 增加 department_id（已存在则跳过）
SET @sql = (
  SELECT IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'department_id') = 0,
    'ALTER TABLE `users` ADD COLUMN `department_id` int DEFAULT NULL COMMENT ''所属部门'' AFTER `role`',
    'SELECT ''users.department_id 已存在，跳过'''
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3) 索引（已存在则跳过）
SET @sql = (
  SELECT IF(
    (SELECT COUNT(*) FROM information_schema.STATISTICS
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND INDEX_NAME = 'ix_users_department_id') = 0,
    'ALTER TABLE `users` ADD INDEX `ix_users_department_id` (`department_id`)',
    'SELECT ''users.ix_users_department_id 已存在，跳过'''
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4) 从现有数据自动提取课室（代码表的 课室/课室_2、送检登记的 送检单位）
INSERT IGNORE INTO `departments` (`name`, `sort_order`, `active`, `created_at`)
SELECT `name`, 0, 1, NOW() FROM (
  SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(`row_data`, '$."课室"')) AS `name`
    FROM `sheet_data` WHERE `sheet_name` = '代码'
  UNION
  SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(`row_data`, '$."课室_2"'))
    FROM `sheet_data` WHERE `sheet_name` = '代码'
  UNION
  SELECT DISTINCT JSON_UNQUOTE(JSON_EXTRACT(`row_data`, '$."送检单位"'))
    FROM `sheet_data` WHERE `sheet_name` = '送检登记'
) t
WHERE `name` IS NOT NULL AND `name` <> '' AND `name` <> 'null';

-- 5) 若库里没有可提取的数据，用固定清单兜底（按需取消注释）
-- INSERT IGNORE INTO `departments` (`name`, `sort_order`, `active`, `created_at`) VALUES
--   ('变焦一课', 0, 1, NOW()), ('变焦二课', 1, 1, NOW()), ('变焦三课', 2, 1, NOW()),
--   ('试做课', 3, 1, NOW()), ('试验课', 4, 1, NOW()), ('红外', 5, 1, NOW()),
--   ('消费三课', 6, 1, NOW());

-- 6) 可选：加外键（确认 department_id 里的值都存在后再执行）
-- ALTER TABLE `users`
--   ADD CONSTRAINT `fk_users_department` FOREIGN KEY (`department_id`)
--   REFERENCES `departments` (`id`) ON DELETE SET NULL;

-- 7) 验证
SELECT id, name, leader, active, sort_order FROM `departments` ORDER BY `sort_order`, `name`;
SHOW COLUMNS FROM `users` LIKE 'department_id';

-- 8) 回滚（谨慎）
-- ALTER TABLE `users` DROP INDEX `ix_users_department_id`, DROP COLUMN `department_id`;
-- DROP TABLE IF EXISTS `departments`;
