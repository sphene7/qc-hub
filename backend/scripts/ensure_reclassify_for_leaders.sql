-- 核对并补齐「跨类移动」权限（reclassify）— MySQL
-- 方案 2：内置角色「项目主管」带跨类；洪沛生账号 hps_all 挂该角色。
--
-- 用法（任选）：
--   mysql -u用户 -p qc_hub < backend/scripts/ensure_reclassify_for_leaders.sql
--   或在客户端里整份执行。
--
-- 说明：
--   1) 只改「项目主管」角色 JSON，挂该角色的人立刻有跨类
--   2) 可选段：把 hps_all 挂到变焦/抽检项目的项目主管（默认注释，需要时取消注释）
--   3) 最后 SELECT 列出谁实际有跨类，便于核对

-- ========== 1) 项目主管角色：补齐 / 打开 reclassify ==========
-- 直接写成完整布尔 JSON，避免 JSON_EXTRACT + COALESCE 把 true 写成字符串
UPDATE roles
SET permissions = JSON_OBJECT(
  'read', true,
  'create', true,
  'update', true,
  'delete', true,
  'submit', true,
  'inspect', true,
  'handle', true,
  'reclassify', true
)
WHERE name = '项目主管';

-- 其他角色若缺 reclassify 键，补 False（不按 update 推断）
UPDATE roles
SET permissions = JSON_SET(COALESCE(permissions, JSON_OBJECT()), '$.reclassify', FALSE)
WHERE name <> '项目主管'
  AND (
    permissions IS NULL
    OR JSON_EXTRACT(permissions, '$.reclassify') IS NULL
  );

-- 核对角色
SELECT id, name, JSON_EXTRACT(permissions, '$.reclassify') AS reclassify, permissions
FROM roles
ORDER BY id;


-- ========== 2)【可选】把 hps_all 设为变焦/抽检项目的「项目主管」==========
-- 需要时去掉下面这段的注释后执行。
-- 若用户/项目不存在会 0 行更新，属正常。

/*
SET @leader_role_id := (SELECT id FROM roles WHERE name = '项目主管' LIMIT 1);
SET @hps_uid := (SELECT id FROM users WHERE username = 'hps_all' LIMIT 1);

-- 已是成员：改挂项目主管 + 成员 permissions 显式开跨类
UPDATE project_members pm
JOIN projects p ON p.id = pm.project_id
SET
  pm.role_id = @leader_role_id,
  pm.role = 'entry',
  pm.permissions = JSON_SET(
    COALESCE(pm.permissions, JSON_OBJECT()),
    '$.read', true,
    '$.create', true,
    '$.update', true,
    '$.delete', true,
    '$.submit', true,
    '$.inspect', true,
    '$.handle', true,
    '$.reclassify', true,
    '$.dept', ''
  )
WHERE pm.user_id = @hps_uid
  AND p.owner_id <> @hps_uid
  AND (
    p.name LIKE '%变焦%'
    OR p.name LIKE '%抽检%'
    OR LOWER(p.name) LIKE '%oqc%'
  );

-- 还不是成员：插入（仅对匹配项目）
INSERT INTO project_members (project_id, user_id, role, role_id, permissions, created_at)
SELECT
  p.id,
  @hps_uid,
  'entry',
  @leader_role_id,
  JSON_OBJECT(
    'read', true,
    'create', true,
    'update', true,
    'delete', true,
    'submit', true,
    'inspect', true,
    'handle', true,
    'reclassify', true,
    'dept', ''
  ),
  UTC_TIMESTAMP()
FROM projects p
WHERE @hps_uid IS NOT NULL
  AND @leader_role_id IS NOT NULL
  AND p.owner_id <> @hps_uid
  AND (
    p.name LIKE '%变焦%'
    OR p.name LIKE '%抽检%'
    OR LOWER(p.name) LIKE '%oqc%'
  )
  AND NOT EXISTS (
    SELECT 1 FROM project_members pm
    WHERE pm.project_id = p.id AND pm.user_id = @hps_uid
  );
*/


-- ========== 3) 列出谁有跨类（便于确认只有洪沛生+必要主管）==========
-- 统一 COLLATE，避免 UNION 报 1271 Illegal mix of collations
-- 项目所有者（天然全开）
SELECT
  CONVERT(p.name USING utf8mb4) COLLATE utf8mb4_unicode_ci AS project_name,
  CONVERT(p.project_id USING utf8mb4) COLLATE utf8mb4_unicode_ci AS project_id,
  CONVERT(u.username USING utf8mb4) COLLATE utf8mb4_unicode_ci AS username,
  CONVERT(IFNULL(u.full_name, '') USING utf8mb4) COLLATE utf8mb4_unicode_ci AS full_name,
  CONVERT('项目所有者' USING utf8mb4) COLLATE utf8mb4_unicode_ci AS how
FROM projects p
JOIN users u ON u.id = p.owner_id

UNION ALL

-- 成员：挂了带 reclassify 的角色，或成员 JSON 显式开了跨类
SELECT
  CONVERT(p.name USING utf8mb4) COLLATE utf8mb4_unicode_ci AS project_name,
  CONVERT(p.project_id USING utf8mb4) COLLATE utf8mb4_unicode_ci AS project_id,
  CONVERT(u.username USING utf8mb4) COLLATE utf8mb4_unicode_ci AS username,
  CONVERT(IFNULL(u.full_name, '') USING utf8mb4) COLLATE utf8mb4_unicode_ci AS full_name,
  CONVERT(
    CASE
      WHEN r.name IS NOT NULL THEN CONCAT('角色 ', r.name)
      ELSE CONCAT('成员 ', pm.role)
    END
    USING utf8mb4
  ) COLLATE utf8mb4_unicode_ci AS how
FROM project_members pm
JOIN projects p ON p.id = pm.project_id
JOIN users u ON u.id = pm.user_id
LEFT JOIN roles r ON r.id = pm.role_id
WHERE p.owner_id <> pm.user_id
  AND (
    COALESCE(JSON_EXTRACT(r.permissions, '$.reclassify'), CAST('false' AS JSON)) = CAST('true' AS JSON)
    OR COALESCE(JSON_EXTRACT(pm.permissions, '$.reclassify'), CAST('false' AS JSON)) = CAST('true' AS JSON)
  )

ORDER BY project_name, username;
