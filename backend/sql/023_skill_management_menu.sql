-- 系统管理 / Skill 管理：只读查看平台 Skill 资产和阶段绑定。
WITH system_menu AS (
  SELECT id
  FROM menus
  WHERE menu_name = '系统管理'
    AND parent_id IS NULL
  LIMIT 1
),
desired AS (
  SELECT *
  FROM (
    VALUES
      ('Skill 管理', 'C', '/admin/skills', 'admin/SkillManagementView', 'system:skill:list', 'Collection', 55, true)
  ) AS item(menu_name, menu_type, path, component, permission, icon, order_num, visible)
),
inserted AS (
  INSERT INTO menus (parent_id, menu_name, menu_type, path, component, permission, icon, order_num, visible, status)
  SELECT system_menu.id, d.menu_name, d.menu_type, d.path, d.component, d.permission, d.icon, d.order_num, d.visible, 'active'
  FROM desired d
  CROSS JOIN system_menu
  WHERE NOT EXISTS (SELECT 1 FROM menus WHERE permission = d.permission)
  RETURNING id
)
UPDATE menus m
SET parent_id = system_menu.id,
    menu_name = d.menu_name,
    menu_type = d.menu_type,
    path = d.path,
    component = d.component,
    icon = d.icon,
    order_num = d.order_num,
    visible = d.visible,
    status = 'active',
    updated_at = now()
FROM desired d
CROSS JOIN system_menu
WHERE m.permission = d.permission;

INSERT INTO role_menus (role_id, menu_id)
SELECT roles.id, menus.id
FROM roles
CROSS JOIN menus
WHERE roles.name = 'admin'
  AND menus.permission = 'system:skill:list'
ON CONFLICT DO NOTHING;
