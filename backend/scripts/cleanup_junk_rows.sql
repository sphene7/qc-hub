-- 清理 qc_hub 中「问题清单」无序号且内容为空的脏行
-- 使用前请先备份数据库！
-- Navicat 请确认左侧选中的是 qc_hub（不是 excel_to_web）

USE qc_hub;

-- 统一会话字符集，避免 1267 collation 冲突
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

SET @project_id = CONVERT('c1764218cdff' USING utf8mb4) COLLATE utf8mb4_unicode_ci;
SET @sheet_like  = CONVERT('问题清单%' USING utf8mb4) COLLATE utf8mb4_unicode_ci;

-- 1) 预览：无「序号」的行
SELECT
  sd.id,
  sd.sheet_name,
  JSON_UNQUOTE(JSON_EXTRACT(sd.row_data, '$."序号"')) AS 序号,
  JSON_UNQUOTE(JSON_EXTRACT(sd.row_data, '$."日期"')) AS 日期,
  JSON_UNQUOTE(JSON_EXTRACT(sd.row_data, '$."问题点描述"')) AS 问题点描述,
  sd.row_data
FROM sheet_data sd
JOIN projects p ON p.id = sd.project_id
WHERE p.project_id COLLATE utf8mb4_unicode_ci = @project_id
  AND sd.sheet_name COLLATE utf8mb4_unicode_ci LIKE @sheet_like
  AND (
    JSON_EXTRACT(sd.row_data, '$."序号"') IS NULL
    OR JSON_UNQUOTE(JSON_EXTRACT(sd.row_data, '$."序号"')) COLLATE utf8mb4_unicode_ci
       IN ('', 'null', 'None')
  )
ORDER BY sd.id;

-- 2) 删除：无序号 + 日期/问题描述/模块/工位 均为空的完全空行
DELETE sd
FROM sheet_data sd
JOIN projects p ON p.id = sd.project_id
WHERE p.project_id COLLATE utf8mb4_unicode_ci = @project_id
  AND sd.sheet_name COLLATE utf8mb4_unicode_ci LIKE @sheet_like
  AND (
    JSON_EXTRACT(sd.row_data, '$."序号"') IS NULL
    OR JSON_UNQUOTE(JSON_EXTRACT(sd.row_data, '$."序号"')) COLLATE utf8mb4_unicode_ci
       IN ('', 'null', 'None')
  )
  AND (
    JSON_EXTRACT(sd.row_data, '$."日期"') IS NULL
    OR JSON_UNQUOTE(JSON_EXTRACT(sd.row_data, '$."日期"')) COLLATE utf8mb4_unicode_ci
       IN ('', 'null', 'None', '-', '－')
  )
  AND (
    JSON_EXTRACT(sd.row_data, '$."问题点描述"') IS NULL
    OR JSON_UNQUOTE(JSON_EXTRACT(sd.row_data, '$."问题点描述"')) COLLATE utf8mb4_unicode_ci
       IN ('', 'null', 'None', '-', '－')
  )
  AND (
    JSON_EXTRACT(sd.row_data, '$."模块"') IS NULL
    OR JSON_UNQUOTE(JSON_EXTRACT(sd.row_data, '$."模块"')) COLLATE utf8mb4_unicode_ci
       IN ('', 'null', 'None', '-', '－')
  )
  AND (
    JSON_EXTRACT(sd.row_data, '$."工位"') IS NULL
    OR JSON_UNQUOTE(JSON_EXTRACT(sd.row_data, '$."工位"')) COLLATE utf8mb4_unicode_ci
       IN ('', 'null', 'None', '-', '－')
  );

-- 3) 可选：删除所有无序号行（更激进）
-- 取消注释前请先跑完第 1 步预览
/*
DELETE sd
FROM sheet_data sd
JOIN projects p ON p.id = sd.project_id
WHERE p.project_id COLLATE utf8mb4_unicode_ci = @project_id
  AND sd.sheet_name COLLATE utf8mb4_unicode_ci LIKE @sheet_like
  AND (
    JSON_EXTRACT(sd.row_data, '$."序号"') IS NULL
    OR JSON_UNQUOTE(JSON_EXTRACT(sd.row_data, '$."序号"')) COLLATE utf8mb4_unicode_ci
       IN ('', 'null', 'None')
  );
*/

-- 4) 验证剩余行数
SELECT sd.sheet_name, COUNT(*) AS row_count
FROM sheet_data sd
JOIN projects p ON p.id = sd.project_id
WHERE p.project_id COLLATE utf8mb4_unicode_ci = @project_id
  AND sd.sheet_name COLLATE utf8mb4_unicode_ci LIKE @sheet_like
GROUP BY sd.sheet_name;
