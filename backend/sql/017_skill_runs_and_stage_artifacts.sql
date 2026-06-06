-- Skill Run + 阶段产物 MVP。

ALTER TABLE workflow_artifacts
  ADD COLUMN IF NOT EXISTS workflow_stage_id UUID REFERENCES workflow_stages(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_workflow_stage_id
  ON workflow_artifacts(workflow_stage_id);

CREATE TABLE IF NOT EXISTS skill_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demand_id UUID NOT NULL REFERENCES demands(id) ON DELETE CASCADE,
  workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
  workflow_stage_id UUID REFERENCES workflow_stages(id) ON DELETE SET NULL,
  stage VARCHAR(50) NOT NULL,
  skill_key VARCHAR(80) NOT NULL,
  skill_name VARCHAR(120) NOT NULL,
  skill_role VARCHAR(40),
  skill_source VARCHAR(40),
  status VARCHAR(20) NOT NULL DEFAULT 'success',
  input_summary TEXT,
  output_summary TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skill_runs_demand_id ON skill_runs(demand_id);
CREATE INDEX IF NOT EXISTS idx_skill_runs_workflow_id ON skill_runs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_skill_runs_workflow_stage_id ON skill_runs(workflow_stage_id);
CREATE INDEX IF NOT EXISTS idx_skill_runs_stage ON skill_runs(stage);
CREATE INDEX IF NOT EXISTS idx_skill_runs_skill_key ON skill_runs(skill_key);

UPDATE menus
SET menu_name = '查看 Skill Run',
    permission = 'skill_run:view'
WHERE permission = 'agent_run:list';

UPDATE menus
SET menu_name = '查看阶段产物',
    permission = 'artifact:view'
WHERE permission = 'artifact:list';

WITH demand_menu AS (
  SELECT id FROM menus WHERE permission = 'demand:list' LIMIT 1
),
desired AS (
  SELECT *
  FROM (
    VALUES
      ('查看 Skill Run', 'skill_run:view', 40),
      ('新建 Skill Run', 'skill_run:create', 41),
      ('查看阶段产物', 'artifact:view', 42),
      ('新建阶段产物', 'artifact:create', 43),
      ('修改阶段产物', 'artifact:update', 44)
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
  'skill_run:view',
  'skill_run:create',
  'artifact:view',
  'artifact:create',
  'artifact:update'
)
WHERE roles.name = 'user'
ON CONFLICT DO NOTHING;
