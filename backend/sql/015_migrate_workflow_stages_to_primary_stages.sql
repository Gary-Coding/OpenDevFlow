-- 将旧的 10 个内部阶段迁移为 5 个对外一级阶段。

WITH mapped AS (
  SELECT
    workflows.id AS workflow_id,
    CASE
      WHEN workflows.current_stage IN ('demand_created', 'product_discovery', 'spec_authoring') THEN 'demand_planning'
      WHEN workflows.current_stage IN ('dev_planning') THEN 'product_design'
      WHEN workflows.current_stage IN ('implementation', 'dev_review', 'dev_verify') THEN 'development'
      WHEN workflows.current_stage IN ('qa_verification', 'final_review') THEN 'acceptance_review'
      WHEN workflows.current_stage IN ('archived') THEN 'delivery_archive'
      WHEN workflows.current_stage IN ('demand_planning', 'product_design', 'development', 'acceptance_review', 'delivery_archive') THEN workflows.current_stage
      ELSE 'demand_planning'
    END AS mapped_stage
  FROM workflows
)
UPDATE workflows
SET current_stage = mapped.mapped_stage
FROM mapped
WHERE workflows.id = mapped.workflow_id;

DELETE FROM workflow_stages;

INSERT INTO workflow_stages (workflow_id, stage_key, stage_name, sort_order, status, started_at, finished_at, blocked_reason)
SELECT
  workflows.id,
  stage_defs.stage_key,
  stage_defs.stage_name,
  stage_defs.sort_order,
  CASE
    WHEN workflows.status = 'archived' THEN 'passed'
    WHEN stage_defs.stage_key = workflows.current_stage AND workflows.status = 'blocked' THEN 'blocked'
    WHEN stage_defs.stage_key = workflows.current_stage THEN 'current'
    WHEN stage_defs.sort_order < current_defs.sort_order THEN 'passed'
    ELSE 'pending'
  END AS status,
  CASE
    WHEN stage_defs.sort_order <= current_defs.sort_order THEN COALESCE(workflows.created_at, now())
    ELSE NULL
  END AS started_at,
  CASE
    WHEN workflows.status = 'archived' OR stage_defs.sort_order < current_defs.sort_order THEN COALESCE(workflows.updated_at, now())
    ELSE NULL
  END AS finished_at,
  CASE
    WHEN stage_defs.stage_key = workflows.current_stage AND workflows.status = 'blocked' THEN '迁移前工作流处于阻塞状态'
    ELSE NULL
  END AS blocked_reason
FROM workflows
JOIN (
  VALUES
    ('demand_planning', '需求规划', 0),
    ('product_design', '产品设计', 1),
    ('development', '程序开发', 2),
    ('acceptance_review', '验收审查', 3),
    ('delivery_archive', '交付归档', 4)
) AS stage_defs(stage_key, stage_name, sort_order) ON true
JOIN (
  VALUES
    ('demand_planning', 0),
    ('product_design', 1),
    ('development', 2),
    ('acceptance_review', 3),
    ('delivery_archive', 4)
) AS current_defs(stage_key, sort_order) ON current_defs.stage_key = workflows.current_stage;
