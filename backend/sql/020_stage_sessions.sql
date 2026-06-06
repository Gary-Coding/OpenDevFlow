-- 阶段 AI 会话：用聊天和产物草稿驱动阶段完成。

CREATE TABLE IF NOT EXISTS stage_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demand_id UUID NOT NULL REFERENCES demands(id) ON DELETE CASCADE,
  workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
  workflow_stage_id UUID NOT NULL REFERENCES workflow_stages(id) ON DELETE CASCADE,
  stage VARCHAR(50) NOT NULL,
  skill_key VARCHAR(80) NOT NULL,
  skill_name VARCHAR(120) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  draft_title VARCHAR(255),
  draft_type VARCHAR(50),
  draft_content TEXT,
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stage_sessions_demand_id ON stage_sessions(demand_id);
CREATE INDEX IF NOT EXISTS idx_stage_sessions_workflow_id ON stage_sessions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_stage_sessions_workflow_stage_id ON stage_sessions(workflow_stage_id);
CREATE INDEX IF NOT EXISTS idx_stage_sessions_stage ON stage_sessions(stage);
CREATE INDEX IF NOT EXISTS idx_stage_sessions_status ON stage_sessions(status);

CREATE TABLE IF NOT EXISTS stage_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES stage_sessions(id) ON DELETE CASCADE,
  role VARCHAR(20) NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stage_messages_session_id ON stage_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_stage_messages_role ON stage_messages(role);

WITH demand_menu AS (
  SELECT id FROM menus WHERE permission = 'demand:list' LIMIT 1
),
desired AS (
  SELECT *
  FROM (
    VALUES
      ('查看阶段会话', 'stage_session:view', 45),
      ('发送阶段消息', 'stage_session:message', 46),
      ('完成阶段会话', 'stage_session:complete', 47)
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
  'stage_session:view',
  'stage_session:message',
  'stage_session:complete'
)
WHERE roles.name = 'user'
ON CONFLICT DO NOTHING;
