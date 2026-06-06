-- 代码上下文快照。统一承载 Bridge / Git / 云端 workspace 的代码事实摘要。

CREATE TABLE IF NOT EXISTS code_context_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demand_id UUID NOT NULL REFERENCES demands(id) ON DELETE CASCADE,
  source_type VARCHAR(40) NOT NULL DEFAULT 'bridge',
  source_ref TEXT,
  root_path TEXT,
  project_count INTEGER NOT NULL DEFAULT 0,
  snapshot_content TEXT NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT TRUE,
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_code_context_snapshots_demand_id ON code_context_snapshots(demand_id);
CREATE INDEX IF NOT EXISTS idx_code_context_snapshots_source_type ON code_context_snapshots(source_type);
CREATE INDEX IF NOT EXISTS idx_code_context_snapshots_is_current ON code_context_snapshots(is_current);

WITH demand_menu AS (
  SELECT id FROM menus WHERE permission = 'demand:list' LIMIT 1
),
desired AS (
  SELECT *
  FROM (
    VALUES
      ('查看代码上下文', 'code_context:view', 57),
      ('生成代码上下文', 'code_context:create', 58)
  ) AS item(menu_name, permission, order_num)
)
INSERT INTO menus (parent_id, menu_name, menu_type, path, component, permission, icon, order_num, visible, status)
SELECT demand_menu.id, desired.menu_name, 'F', NULL, NULL, desired.permission, NULL, desired.order_num, false, 'active'
FROM desired
CROSS JOIN demand_menu
WHERE NOT EXISTS (
  SELECT 1 FROM menus m
  WHERE m.permission = desired.permission
    AND m.status = 'active'
);

INSERT INTO role_menus (role_id, menu_id)
SELECT roles.id, menus.id
FROM roles
CROSS JOIN menus
WHERE roles.name = 'admin'
  AND menus.status = 'active'
ON CONFLICT DO NOTHING;

INSERT INTO role_menus (role_id, menu_id)
SELECT roles.id, menus.id
FROM roles
JOIN menus ON menus.permission IN (
  'code_context:view',
  'code_context:create'
)
WHERE roles.name = 'user'
ON CONFLICT DO NOTHING;
