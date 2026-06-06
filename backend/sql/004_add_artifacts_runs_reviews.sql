-- 新增工作流产物表
CREATE TABLE IF NOT EXISTS workflow_artifacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demand_id UUID NOT NULL REFERENCES demands(id) ON DELETE CASCADE,
  workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
  stage VARCHAR(50) NOT NULL,
  artifact_type VARCHAR(50) NOT NULL,
  title VARCHAR(255) NOT NULL,
  content TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 1,
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 新增 Agent Run 表
CREATE TABLE IF NOT EXISTS agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demand_id UUID NOT NULL REFERENCES demands(id) ON DELETE CASCADE,
  workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
  stage VARCHAR(50) NOT NULL,
  agent_type VARCHAR(50) NOT NULL DEFAULT 'manual',
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  input_summary TEXT,
  output_summary TEXT,
  logs TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  exit_code INTEGER,
  blocker_reason TEXT,
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 新增 Review 表
CREATE TABLE IF NOT EXISTS reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demand_id UUID NOT NULL REFERENCES demands(id) ON DELETE CASCADE,
  workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
  stage VARCHAR(50) NOT NULL,
  review_type VARCHAR(50) NOT NULL,
  result VARCHAR(20) NOT NULL,
  comment TEXT,
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 新增索引
CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_demand_id ON workflow_artifacts(demand_id);
CREATE INDEX IF NOT EXISTS idx_workflow_artifacts_workflow_id ON workflow_artifacts(workflow_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_demand_id ON agent_runs(demand_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_workflow_id ON agent_runs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_reviews_demand_id ON reviews(demand_id);
CREATE INDEX IF NOT EXISTS idx_reviews_workflow_id ON reviews(workflow_id);
