-- 轻量本地 Bridge 与需求多项目绑定。

CREATE TABLE IF NOT EXISTS local_bridge_clients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  client_name VARCHAR(120) NOT NULL,
  client_key VARCHAR(120) NOT NULL UNIQUE,
  status VARCHAR(20) NOT NULL DEFAULT 'offline',
  last_seen_at TIMESTAMPTZ,
  metadata TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_local_bridge_clients_user_id ON local_bridge_clients(user_id);
CREATE INDEX IF NOT EXISTS idx_local_bridge_clients_client_key ON local_bridge_clients(client_key);
CREATE INDEX IF NOT EXISTS idx_local_bridge_clients_status ON local_bridge_clients(status);

CREATE TABLE IF NOT EXISTS demand_local_projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demand_id UUID NOT NULL REFERENCES demands(id) ON DELETE CASCADE,
  bridge_client_id UUID REFERENCES local_bridge_clients(id) ON DELETE SET NULL,
  project_key VARCHAR(80) NOT NULL,
  project_name VARCHAR(120) NOT NULL,
  local_path TEXT NOT NULL,
  project_type VARCHAR(50) NOT NULL DEFAULT 'service',
  branch_name VARCHAR(120),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  order_num INTEGER NOT NULL DEFAULT 0,
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_demand_local_project_key UNIQUE (demand_id, project_key)
);

CREATE INDEX IF NOT EXISTS idx_demand_local_projects_demand_id ON demand_local_projects(demand_id);
CREATE INDEX IF NOT EXISTS idx_demand_local_projects_bridge_client_id ON demand_local_projects(bridge_client_id);
CREATE INDEX IF NOT EXISTS idx_demand_local_projects_project_key ON demand_local_projects(project_key);
CREATE INDEX IF NOT EXISTS idx_demand_local_projects_project_type ON demand_local_projects(project_type);
CREATE INDEX IF NOT EXISTS idx_demand_local_projects_status ON demand_local_projects(status);

CREATE TABLE IF NOT EXISTS local_bridge_commands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demand_id UUID NOT NULL REFERENCES demands(id) ON DELETE CASCADE,
  workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
  local_project_id UUID REFERENCES demand_local_projects(id) ON DELETE SET NULL,
  bridge_client_id UUID REFERENCES local_bridge_clients(id) ON DELETE SET NULL,
  command_type VARCHAR(50) NOT NULL,
  command_text TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  output_summary TEXT,
  exit_code INTEGER,
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_local_bridge_commands_demand_id ON local_bridge_commands(demand_id);
CREATE INDEX IF NOT EXISTS idx_local_bridge_commands_workflow_id ON local_bridge_commands(workflow_id);
CREATE INDEX IF NOT EXISTS idx_local_bridge_commands_local_project_id ON local_bridge_commands(local_project_id);
CREATE INDEX IF NOT EXISTS idx_local_bridge_commands_bridge_client_id ON local_bridge_commands(bridge_client_id);
CREATE INDEX IF NOT EXISTS idx_local_bridge_commands_command_type ON local_bridge_commands(command_type);
CREATE INDEX IF NOT EXISTS idx_local_bridge_commands_status ON local_bridge_commands(status);

WITH demand_menu AS (
  SELECT id FROM menus WHERE permission = 'demand:list' LIMIT 1
),
desired AS (
  SELECT *
  FROM (
    VALUES
      ('查看本地项目', 'local_project:view', 52),
      ('维护本地项目', 'local_project:manage', 53),
      ('查看本地 Bridge', 'local_bridge:view', 54),
      ('维护本地 Bridge', 'local_bridge:manage', 55),
      ('执行本地命令', 'local_bridge:command', 56)
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
  'local_project:view',
  'local_project:manage',
  'local_bridge:view',
  'local_bridge:manage',
  'local_bridge:command'
)
WHERE roles.name = 'user'
ON CONFLICT DO NOTHING;
