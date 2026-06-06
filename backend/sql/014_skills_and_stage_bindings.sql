CREATE TABLE IF NOT EXISTS skills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key VARCHAR(80) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  role VARCHAR(40) NOT NULL,
  stage VARCHAR(50) NOT NULL,
  source VARCHAR(40) NOT NULL,
  version VARCHAR(40) NOT NULL DEFAULT '0.1.0',
  description TEXT NOT NULL DEFAULT '',
  git_url TEXT,
  git_ref VARCHAR(120),
  sub_path TEXT,
  entry_file VARCHAR(120) NOT NULL DEFAULT 'SKILL.md',
  checksum VARCHAR(128),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow_stage_skill_bindings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stage_key VARCHAR(50) NOT NULL,
  skill_key VARCHAR(80) NOT NULL,
  is_default BOOLEAN NOT NULL DEFAULT false,
  order_num INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_workflow_stage_skill_binding UNIQUE (stage_key, skill_key)
);

CREATE INDEX IF NOT EXISTS idx_skills_key ON skills(key);
CREATE INDEX IF NOT EXISTS idx_skills_stage ON skills(stage);
CREATE INDEX IF NOT EXISTS idx_skills_role ON skills(role);
CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
CREATE INDEX IF NOT EXISTS idx_workflow_stage_skill_bindings_stage_key ON workflow_stage_skill_bindings(stage_key);
CREATE INDEX IF NOT EXISTS idx_workflow_stage_skill_bindings_skill_key ON workflow_stage_skill_bindings(skill_key);
CREATE INDEX IF NOT EXISTS idx_workflow_stage_skill_bindings_status ON workflow_stage_skill_bindings(status);

INSERT INTO skills (key, name, role, stage, source, version, description, git_url, git_ref, sub_path, entry_file, status)
VALUES
  ('opendevflow-guide', 'OpenDevFlow 流程引导', 'guide', 'all', 'opendevflow', '0.1.0', '引导完整需求交付流程，判断当前阶段，检查输入输出，路由到对应阶段 Skill。', 'https://github.com/Gary-Coding/opendevflow-skills.git', 'main', 'skills/opendevflow-guide', 'SKILL.md', 'active'),
  ('product-discovery', '需求发现', 'product', 'demand_planning', 'superpowers', '0.1.0', '通过对话澄清需求背景、目标、边界和待确认问题。', 'https://github.com/Gary-Coding/opendevflow-skills.git', 'main', 'skills/product-discovery', 'SKILL.md', 'active'),
  ('prd-authoring', 'PRD 编写', 'product', 'demand_planning', 'mixed', '0.1.0', '将需求发现结果固化为 PRD、用户故事和验收标准。', 'https://github.com/Gary-Coding/opendevflow-skills.git', 'main', 'skills/prd-authoring', 'SKILL.md', 'active'),
  ('product-design', '产品设计', 'design', 'product_design', 'comet', '0.1.0', '面向页面、交互、字段、状态和权限的产品设计阶段 Skill。', 'https://github.com/Gary-Coding/opendevflow-skills.git', 'main', 'skills/product-design', 'SKILL.md', 'active'),
  ('openspec-design', 'OpenSpec 变更设计', 'architect', 'product_design', 'openspec', '0.1.0', '将产品需求转为可实施变更规格。', 'https://github.com/Gary-Coding/opendevflow-skills.git', 'main', 'skills/openspec-design', 'SKILL.md', 'active'),
  ('developer-planning', '开发计划', 'developer', 'development', 'superpowers', '0.1.0', '生成文件级、步骤级、可验证的开发计划。', 'https://github.com/Gary-Coding/opendevflow-skills.git', 'main', 'skills/developer-planning', 'SKILL.md', 'active'),
  ('developer-delivery', '开发交付', 'developer', 'development', 'opendevflow', '0.1.0', '代码实施、验证、报告和交付闭环能力。', 'https://github.com/Gary-Coding/opendevflow-skills.git', 'main', 'skills/developer-delivery', 'SKILL.md', 'active'),
  ('code-review', '代码审查', 'reviewer', 'acceptance_review', 'superpowers', '0.1.0', '对 diff、风险和测试缺口进行审查。', 'https://github.com/Gary-Coding/opendevflow-skills.git', 'main', 'skills/code-review', 'SKILL.md', 'active'),
  ('qa-verification', 'QA 验收', 'qa', 'acceptance_review', 'mixed', '0.1.0', '生成测试计划、测试用例和验收结论。', 'https://github.com/Gary-Coding/opendevflow-skills.git', 'main', 'skills/qa-verification', 'SKILL.md', 'active'),
  ('delivery-summary', '交付归档', 'delivery', 'delivery_archive', 'mixed', '0.1.0', '形成交付说明和归档结论。', 'https://github.com/Gary-Coding/opendevflow-skills.git', 'main', 'skills/delivery-summary', 'SKILL.md', 'active')
ON CONFLICT (key) DO UPDATE
SET name = EXCLUDED.name,
    role = EXCLUDED.role,
    stage = EXCLUDED.stage,
    source = EXCLUDED.source,
    version = EXCLUDED.version,
    description = EXCLUDED.description,
    git_url = EXCLUDED.git_url,
    git_ref = EXCLUDED.git_ref,
    sub_path = EXCLUDED.sub_path,
    entry_file = EXCLUDED.entry_file,
    status = EXCLUDED.status,
    updated_at = now();

INSERT INTO workflow_stage_skill_bindings (stage_key, skill_key, is_default, order_num, status)
VALUES
  ('demand_planning', 'product-discovery', true, 10, 'active'),
  ('demand_planning', 'prd-authoring', false, 20, 'active'),
  ('product_design', 'product-design', true, 10, 'active'),
  ('product_design', 'openspec-design', false, 20, 'active'),
  ('development', 'developer-planning', true, 10, 'active'),
  ('development', 'developer-delivery', false, 20, 'active'),
  ('acceptance_review', 'code-review', true, 10, 'active'),
  ('acceptance_review', 'qa-verification', false, 20, 'active'),
  ('delivery_archive', 'delivery-summary', true, 10, 'active')
ON CONFLICT (stage_key, skill_key) DO UPDATE
SET is_default = EXCLUDED.is_default,
    order_num = EXCLUDED.order_num,
    status = EXCLUDED.status,
    updated_at = now();
