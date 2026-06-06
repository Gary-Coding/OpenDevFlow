-- 工作流模板化：标准需求、缺陷修复、小需求/小优化。

CREATE TABLE IF NOT EXISTS workflow_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key VARCHAR(50) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  workflow_type VARCHAR(30) NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  order_num INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow_template_stages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  template_key VARCHAR(50) NOT NULL REFERENCES workflow_templates(key) ON DELETE CASCADE,
  stage_key VARCHAR(50) NOT NULL,
  stage_name VARCHAR(120) NOT NULL,
  sort_order INTEGER NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_workflow_template_stage UNIQUE (template_key, stage_key)
);

CREATE INDEX IF NOT EXISTS idx_workflow_templates_key ON workflow_templates(key);
CREATE INDEX IF NOT EXISTS idx_workflow_templates_status ON workflow_templates(status);
CREATE INDEX IF NOT EXISTS idx_workflow_template_stages_template_key ON workflow_template_stages(template_key);
CREATE INDEX IF NOT EXISTS idx_workflow_template_stages_stage_key ON workflow_template_stages(stage_key);

ALTER TABLE workflows
  ADD COLUMN IF NOT EXISTS template_key VARCHAR(50) NOT NULL DEFAULT 'full',
  ADD COLUMN IF NOT EXISTS workflow_type VARCHAR(30) NOT NULL DEFAULT 'full';

CREATE INDEX IF NOT EXISTS idx_workflows_template_key ON workflows(template_key);
CREATE INDEX IF NOT EXISTS idx_workflows_workflow_type ON workflows(workflow_type);

ALTER TABLE workflow_stage_skill_bindings
  ADD COLUMN IF NOT EXISTS template_key VARCHAR(50) NOT NULL DEFAULT 'full';

DROP INDEX IF EXISTS idx_workflow_stage_skill_bindings_stage_key;
CREATE INDEX IF NOT EXISTS idx_workflow_stage_skill_bindings_stage_key ON workflow_stage_skill_bindings(stage_key);
CREATE INDEX IF NOT EXISTS idx_workflow_stage_skill_bindings_template_key ON workflow_stage_skill_bindings(template_key);

ALTER TABLE workflow_stage_skill_bindings
  DROP CONSTRAINT IF EXISTS uq_workflow_stage_skill_binding;

ALTER TABLE workflow_stage_skill_bindings
  ADD CONSTRAINT uq_workflow_stage_skill_binding UNIQUE (template_key, stage_key, skill_key);

INSERT INTO workflow_templates (key, name, workflow_type, description, status, order_num)
VALUES
  ('full', '标准需求流程', 'full', '适用于新业务、新项目、复杂优化和需要完整需求设计验收的交付。', 'active', 10),
  ('hotfix', '缺陷修复流程', 'hotfix', '适用于影响范围清晰的 bugfix 或热修，跳过完整产品设计。', 'active', 20),
  ('tweak', '小需求/小优化流程', 'tweak', '适用于小范围优化、配置、文案、轻量改动和开发自测。', 'active', 30)
ON CONFLICT (key) DO UPDATE
SET name = EXCLUDED.name,
    workflow_type = EXCLUDED.workflow_type,
    description = EXCLUDED.description,
    status = EXCLUDED.status,
    order_num = EXCLUDED.order_num,
    updated_at = now();

INSERT INTO workflow_template_stages (template_key, stage_key, stage_name, sort_order, description, status)
VALUES
  ('full', 'demand_planning', '需求规划', 0, '澄清需求背景、目标、范围和验收标准，形成可交付的需求输入。', 'active'),
  ('full', 'product_design', '产品设计', 1, '沉淀页面、交互、字段、状态和 OpenSpec 变更设计。', 'active'),
  ('full', 'development', '程序开发', 2, '基于设计产出开发计划，完成代码实施、编译验证和结果记录。', 'active'),
  ('full', 'acceptance_review', '验收审查', 3, '对代码变更和需求达成情况进行审查、测试和验收。', 'active'),
  ('full', 'delivery_archive', '交付归档', 4, '汇总交付范围、产物、验证结论和后续事项，完成归档。', 'active'),

  ('hotfix', 'issue_confirm', '问题确认', 0, '确认缺陷现象、影响范围、复现路径和修复边界。', 'active'),
  ('hotfix', 'fix_implementation', '修复实施', 1, '定位根因、完成代码修复和必要自测。', 'active'),
  ('hotfix', 'regression_verify', '回归验证', 2, '执行回归验证，确认缺陷关闭且没有明显副作用。', 'active'),
  ('hotfix', 'delivery_archive', '交付归档', 3, '记录修复范围、验证结果和交付说明。', 'active'),

  ('tweak', 'change_confirm', '变更确认', 0, '确认小需求或小优化的目标、范围和验收口径。', 'active'),
  ('tweak', 'self_test', '实施自测', 1, '完成轻量实施、自测和结果记录。', 'active'),
  ('tweak', 'delivery_archive', '交付归档', 2, '记录变更内容、验证结论和交付说明。', 'active')
ON CONFLICT (template_key, stage_key) DO UPDATE
SET stage_name = EXCLUDED.stage_name,
    sort_order = EXCLUDED.sort_order,
    description = EXCLUDED.description,
    status = EXCLUDED.status,
    updated_at = now();

UPDATE workflows
SET template_key = COALESCE(NULLIF(template_key, ''), 'full'),
    workflow_type = COALESCE(NULLIF(workflow_type, ''), 'full');

INSERT INTO workflow_stage_skill_bindings (template_key, stage_key, skill_key, is_default, order_num, status)
VALUES
  ('hotfix', 'issue_confirm', 'product-discovery', true, 10, 'active'),
  ('hotfix', 'fix_implementation', 'developer-delivery', true, 10, 'active'),
  ('hotfix', 'regression_verify', 'code-review', true, 10, 'active'),
  ('hotfix', 'regression_verify', 'qa-verification', false, 20, 'active'),
  ('hotfix', 'delivery_archive', 'delivery-summary', true, 10, 'active'),

  ('tweak', 'change_confirm', 'prd-authoring', true, 10, 'active'),
  ('tweak', 'self_test', 'developer-delivery', true, 10, 'active'),
  ('tweak', 'delivery_archive', 'delivery-summary', true, 10, 'active')
ON CONFLICT (template_key, stage_key, skill_key) DO UPDATE
SET is_default = EXCLUDED.is_default,
    order_num = EXCLUDED.order_num,
    status = EXCLUDED.status,
    updated_at = now();
