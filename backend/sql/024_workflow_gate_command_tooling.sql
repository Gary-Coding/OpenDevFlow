-- 工作流 Gate、命令、工具调用和产物版本。

ALTER TABLE workflow_artifacts
  ADD COLUMN IF NOT EXISTS version_no INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS is_current BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS source_session_id UUID REFERENCES stage_sessions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_is_current ON workflow_artifacts(is_current);
CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_source_session_id ON workflow_artifacts(source_session_id);

UPDATE workflow_artifacts
SET version_no = version
WHERE version_no IS NULL OR version_no < 1;

CREATE TABLE IF NOT EXISTS stage_gate_checks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES stage_sessions(id) ON DELETE CASCADE,
  demand_id UUID NOT NULL REFERENCES demands(id) ON DELETE CASCADE,
  workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
  workflow_stage_id UUID NOT NULL REFERENCES workflow_stages(id) ON DELETE CASCADE,
  stage VARCHAR(50) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  summary TEXT NOT NULL DEFAULT '',
  details TEXT,
  checked_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stage_gate_checks_session_id ON stage_gate_checks(session_id);
CREATE INDEX IF NOT EXISTS idx_stage_gate_checks_demand_id ON stage_gate_checks(demand_id);
CREATE INDEX IF NOT EXISTS idx_stage_gate_checks_workflow_id ON stage_gate_checks(workflow_id);
CREATE INDEX IF NOT EXISTS idx_stage_gate_checks_stage ON stage_gate_checks(stage);
CREATE INDEX IF NOT EXISTS idx_stage_gate_checks_status ON stage_gate_checks(status);

CREATE TABLE IF NOT EXISTS stage_commands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES stage_sessions(id) ON DELETE CASCADE,
  command VARCHAR(80) NOT NULL,
  prompt TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'running',
  result_summary TEXT,
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stage_commands_session_id ON stage_commands(session_id);
CREATE INDEX IF NOT EXISTS idx_stage_commands_command ON stage_commands(command);
CREATE INDEX IF NOT EXISTS idx_stage_commands_status ON stage_commands(status);

CREATE TABLE IF NOT EXISTS stage_tool_calls (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES stage_sessions(id) ON DELETE CASCADE,
  tool_name VARCHAR(80) NOT NULL,
  input_summary TEXT,
  output_summary TEXT,
  status VARCHAR(20) NOT NULL DEFAULT 'success',
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stage_tool_calls_session_id ON stage_tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_stage_tool_calls_tool_name ON stage_tool_calls(tool_name);
CREATE INDEX IF NOT EXISTS idx_stage_tool_calls_status ON stage_tool_calls(status);

WITH demand_menu AS (
  SELECT id FROM menus WHERE permission = 'demand:list' LIMIT 1
),
desired AS (
  SELECT *
  FROM (
    VALUES
      ('查看阶段 Gate', 'stage_gate:view', 48),
      ('校验阶段 Gate', 'stage_gate:check', 49),
      ('查看阶段命令', 'stage_command:view', 50),
      ('查看工具调用', 'stage_tool:view', 51)
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
  'stage_gate:view',
  'stage_gate:check',
  'stage_command:view',
  'stage_tool:view'
)
WHERE roles.name = 'user'
ON CONFLICT DO NOTHING;
