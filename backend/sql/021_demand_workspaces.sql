-- 需求服务端工作空间：主存储使用挂载盘，数据库只保存空间元数据和权限按钮。

CREATE TABLE IF NOT EXISTS demand_workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demand_id UUID NOT NULL UNIQUE REFERENCES demands(id) ON DELETE CASCADE,
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  root_path TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_demand_workspaces_demand_id ON demand_workspaces(demand_id);
CREATE INDEX IF NOT EXISTS idx_demand_workspaces_company_id ON demand_workspaces(company_id);
CREATE INDEX IF NOT EXISTS idx_demand_workspaces_status ON demand_workspaces(status);

WITH demand_menu AS (
  SELECT id FROM menus WHERE permission = 'demand:list' LIMIT 1
),
desired AS (
  SELECT *
  FROM (
    VALUES
      ('查看需求空间', 'workspace:view', 48),
      ('保存需求空间文件', 'workspace:file:update', 49)
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
JOIN menus ON menus.permission IN ('workspace:view', 'workspace:file:update')
WHERE roles.name = 'user'
ON CONFLICT DO NOTHING;
