-- 需求作为唯一入口：支持一个需求下多轮工作流，并物理删除旧的独立菜单入口。

ALTER TABLE workflows DROP CONSTRAINT IF EXISTS workflows_demand_id_key;

DELETE FROM menus
WHERE menu_name IN ('工作流', '交付资产', '仓库管理', '产物管理', 'Agent Run', 'Review')
   OR path IN ('/workflows', '/repositories', '/artifacts', '/agent-runs', '/reviews')
   OR component LIKE 'workspace/PlaceholderView%';

WITH demand_menu AS (
  SELECT id FROM menus WHERE menu_name = '需求管理' AND permission = 'demand:list' LIMIT 1
),
desired AS (
  SELECT *
  FROM (
    VALUES
      ('查看工作流', 'workflow:view', 20),
      ('新建工作流', 'workflow:create', 21),
      ('推进阶段', 'workflow:advance', 22),
      ('阻塞阶段', 'workflow:block', 23),
      ('查看仓库', 'repository:list', 30),
      ('查看产物', 'artifact:list', 31),
      ('查看 Agent Run', 'agent_run:list', 32),
      ('查看 Review', 'review:list', 33)
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
