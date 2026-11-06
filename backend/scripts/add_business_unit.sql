-- ============================================================
-- 质控通 · 事业部 / 部番（抽检专用）
-- 适用：MySQL 8.0+ / utf8mb4
-- 说明：后端启动会自动建表/加列；本脚本供手工执行
-- 数据导入：python backend/scripts/seed_model_bu.py "D:/CODE/QE/OQC  表格对应表(1).xls"
-- ============================================================
SET NAMES utf8mb4;

-- 1) 部番 → 事业部 对照表
CREATE TABLE IF NOT EXISTS `model_bu_map` (
  `id` int NOT NULL AUTO_INCREMENT,
  `model` varchar(100) NOT NULL COMMENT '部番（完整机种）',
  `base_model` varchar(50) DEFAULT NULL COMMENT '基型（- 前，即机种）',
  `business_unit` varchar(50) NOT NULL COMMENT '事业部',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_model_bu_map_model` (`model`),
  KEY `ix_model_bu_map_base_model` (`base_model`),
  KEY `ix_model_bu_map_business_unit` (`business_unit`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='部番-事业部对照';

-- 2) 送检单增加事业部
SET @sql = (
  SELECT IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sampling_submissions'
        AND COLUMN_NAME = 'business_unit') = 0,
    'ALTER TABLE `sampling_submissions` ADD COLUMN `business_unit` varchar(50) DEFAULT NULL COMMENT ''事业部'', ADD INDEX `ix_sampling_submissions_business_unit` (`business_unit`)',
    'SELECT ''sampling_submissions.business_unit 已存在，跳过'''
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 3) 送检单拆出「部番」（完整，含 -）；机种 = 部番 - 前
SET @sql = (
  SELECT IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'sampling_submissions'
        AND COLUMN_NAME = 'part_no') = 0,
    'ALTER TABLE `sampling_submissions` ADD COLUMN `part_no` varchar(100) DEFAULT NULL COMMENT ''部番（完整）'', ADD INDEX `ix_sampling_submissions_part_no` (`part_no`)',
    'SELECT ''sampling_submissions.part_no 已存在，跳过'''
  )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 4) 旧数据：model 存的是完整部番，拆成 part_no + model(机种)
UPDATE `sampling_submissions` SET `part_no` = `model` WHERE `part_no` IS NULL;
UPDATE `sampling_submissions` SET `model` = SUBSTRING_INDEX(`model`, '-', 1) WHERE `model` LIKE '%-%';
UPDATE `sampling_submissions` SET `series` = `model`;

-- 5) 验证
SELECT COUNT(*) AS mapped_models FROM `model_bu_map`;
SHOW COLUMNS FROM `sampling_submissions` LIKE 'part_no';
SHOW COLUMNS FROM `sampling_submissions` LIKE 'business_unit';
