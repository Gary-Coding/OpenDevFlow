-- Bridge 扫描结果二次确认。扫描结果先进入候选表，用户确认相关项目后再生成当前代码上下文。

CREATE TABLE IF NOT EXISTS code_context_scan_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  demand_id UUID NOT NULL REFERENCES demands(id) ON DELETE CASCADE,
  bridge_client_id UUID REFERENCES local_bridge_clients(id) ON DELETE SET NULL,
  source_ref TEXT,
  root_path TEXT,
  project_count INTEGER NOT NULL DEFAULT 0,
  snapshot_content TEXT NOT NULL,
  projects_json TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_code_context_scan_results_demand_id ON code_context_scan_results(demand_id);
CREATE INDEX IF NOT EXISTS idx_code_context_scan_results_bridge_client_id ON code_context_scan_results(bridge_client_id);
CREATE INDEX IF NOT EXISTS idx_code_context_scan_results_status ON code_context_scan_results(status);

