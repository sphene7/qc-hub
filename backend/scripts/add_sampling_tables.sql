-- ============================================================
-- 质控通 · 抽检业务表重构（关系型存储 + 乐观锁 + 审计）
-- 适用：MySQL 8.0+ / utf8mb4
-- 说明：后端启动会自动建表；本脚本供手工执行（Navicat / 生产库）
-- 顺序：先 departments（见 add_departments.sql），再执行本脚本
-- ============================================================
SET NAMES utf8mb4;

-- 1) 送检单
CREATE TABLE IF NOT EXISTS `sampling_submissions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `project_id` int NOT NULL,
  `code` varchar(40) NOT NULL COMMENT '送检单号 SJ20260827-001',
  `submit_date` date NOT NULL,
  `month_label` varchar(20) DEFAULT NULL,
  `model` varchar(100) DEFAULT NULL COMMENT '机种',
  `series` varchar(50) DEFAULT NULL COMMENT '系列',
  `department` varchar(100) DEFAULT NULL COMMENT '送检单位/课室',
  `submit_type` varchar(50) DEFAULT NULL COMMENT '送检类型',
  `qty` int DEFAULT NULL COMMENT '送检数量',
  `batch_seq` int DEFAULT NULL COMMENT '同批送检次数',
  `urgent` varchar(10) DEFAULT NULL,
  `remark` text,
  `confirmer` varchar(50) DEFAULT NULL,
  `room_owner` varchar(50) DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL COMMENT '完成日期（判定OK后自动写入）',
  `version` int NOT NULL DEFAULT 1 COMMENT '乐观锁版本',
  `created_by` int DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `deleted_at` datetime DEFAULT NULL COMMENT '软删除',
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_sampling_submissions_code` (`code`),
  KEY `ix_sampling_submissions_project_id` (`project_id`),
  KEY `ix_sampling_submissions_submit_date` (`submit_date`),
  KEY `ix_sampling_submissions_department` (`department`),
  KEY `created_by` (`created_by`),
  CONSTRAINT `sampling_submissions_ibfk_1` FOREIGN KEY (`project_id`) REFERENCES `projects` (`id`),
  CONSTRAINT `sampling_submissions_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='送检单';

-- 2) 抽检记录（每检验员一条）
CREATE TABLE IF NOT EXISTS `sampling_inspections` (
  `id` int NOT NULL AUTO_INCREMENT,
  `submission_id` int NOT NULL,
  `code` varchar(50) NOT NULL COMMENT '抽检单号 SJ20260827-001-C01',
  `inspector` varchar(50) DEFAULT NULL,
  `appearance_qty` int DEFAULT NULL,
  `function_qty` int DEFAULT NULL,
  `defect_qty` int DEFAULT NULL,
  `defect_rate` varchar(20) DEFAULT NULL,
  `batch_sent` int DEFAULT NULL,
  `batch_pass` int DEFAULT NULL,
  `batch_rate` varchar(20) DEFAULT NULL,
  `verdict` varchar(20) DEFAULT NULL COMMENT 'OK / NG / NG×N',
  `version` int NOT NULL DEFAULT 1,
  `created_by` int DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_sampling_inspections_code` (`code`),
  KEY `ix_sampling_inspections_submission_id` (`submission_id`),
  KEY `ix_sampling_inspections_inspector` (`inspector`),
  KEY `created_by` (`created_by`),
  CONSTRAINT `sampling_inspections_ibfk_1` FOREIGN KEY (`submission_id`) REFERENCES `sampling_submissions` (`id`),
  CONSTRAINT `sampling_inspections_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='抽检记录';

-- 3) 不良明细（一条一种不良，替代「；」拼接）
CREATE TABLE IF NOT EXISTS `sampling_defects` (
  `id` int NOT NULL AUTO_INCREMENT,
  `inspection_id` int NOT NULL,
  `attr` varchar(20) DEFAULT NULL COMMENT '外观不良/性能不良',
  `location` varchar(100) DEFAULT NULL,
  `phenomenon` varchar(100) DEFAULT NULL,
  `qty` int DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_sampling_defects_inspection_id` (`inspection_id`),
  CONSTRAINT `sampling_defects_ibfk_1` FOREIGN KEY (`inspection_id`) REFERENCES `sampling_inspections` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='不良明细';

-- 4) 异常处理（每条抽检最多一条）
CREATE TABLE IF NOT EXISTS `sampling_exceptions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `inspection_id` int NOT NULL,
  `oa_no` varchar(50) DEFAULT NULL,
  `qc_company` varchar(100) DEFAULT NULL,
  `owner_dept` varchar(100) DEFAULT NULL,
  `owner` varchar(50) DEFAULT NULL,
  `temp_action` text,
  `root_cause` text,
  `perm_action` text,
  `verify` text,
  `close_date` date DEFAULT NULL,
  `close_days` int DEFAULT NULL,
  `created_by` int DEFAULT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_sampling_exceptions_inspection_id` (`inspection_id`),
  KEY `created_by` (`created_by`),
  CONSTRAINT `sampling_exceptions_ibfk_1` FOREIGN KEY (`inspection_id`) REFERENCES `sampling_inspections` (`id`),
  CONSTRAINT `sampling_exceptions_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='异常处理';

-- 5) 审计日志
CREATE TABLE IF NOT EXISTS `audit_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `entity` varchar(40) NOT NULL COMMENT 'sampling_submission / sampling_inspection ...',
  `entity_id` varchar(50) NOT NULL,
  `action` varchar(20) NOT NULL COMMENT 'create/update/delete/upsert',
  `changes` json DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_audit_logs_entity` (`entity`),
  KEY `ix_audit_logs_entity_id` (`entity_id`),
  KEY `ix_audit_logs_created_at` (`created_at`),
  KEY `ix_audit_logs_user_id` (`user_id`),
  CONSTRAINT `audit_logs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='审计日志';

-- 6) 可选：清理已经废弃的三张 JSON 登记表（确认不再需要旧数据再执行）
-- DELETE FROM `sheet_data` WHERE `sheet_name` IN ('送检登记', '抽检登记', '异常登记');

-- 7) 验证
SELECT COUNT(*) AS submissions FROM `sampling_submissions`;
SELECT COUNT(*) AS inspections FROM `sampling_inspections`;
SELECT COUNT(*) AS defects FROM `sampling_defects`;
SELECT COUNT(*) AS exceptions FROM `sampling_exceptions`;
SELECT COUNT(*) AS audit_rows FROM `audit_logs`;
