-- 清理 017 在已运行环境中可能产生的重复按钮权限。

WITH duplicates AS (
  SELECT
    id,
    permission,
    row_number() OVER (
      PARTITION BY permission
      ORDER BY order_num ASC NULLS LAST, created_at ASC, id ASC
    ) AS rn
  FROM menus
  WHERE permission IN ('skill_run:view', 'artifact:view')
    AND status = 'active'
)
DELETE FROM role_menus
WHERE menu_id IN (
  SELECT id FROM duplicates WHERE rn > 1
);

WITH duplicates AS (
  SELECT
    id,
    permission,
    row_number() OVER (
      PARTITION BY permission
      ORDER BY order_num ASC NULLS LAST, created_at ASC, id ASC
    ) AS rn
  FROM menus
  WHERE permission IN ('skill_run:view', 'artifact:view')
    AND status = 'active'
)
DELETE FROM menus
WHERE id IN (
  SELECT id FROM duplicates WHERE rn > 1
);
