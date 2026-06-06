-- 插入默认公司
INSERT INTO companies (name, code, status)
VALUES ('默认公司', 'default', 'active')
ON CONFLICT (code) DO NOTHING;

-- 插入默认部门
INSERT INTO departments (company_id, parent_id, ancestors, org_type, name, order_num, status)
SELECT companies.id, NULL, '', 'department', '默认部门', 0, 'active'
FROM companies
WHERE companies.code = 'default'
  AND NOT EXISTS (
    SELECT 1
    FROM departments
    WHERE departments.company_id = companies.id
      AND departments.parent_id IS NULL
      AND departments.name = '默认部门'
  );

-- 更新现有用户归属默认公司和部门
UPDATE users
SET
  company_id = (SELECT id FROM companies WHERE code = 'default'),
  department_id = (SELECT id FROM departments WHERE name = '默认部门' AND company_id = (SELECT id FROM companies WHERE code = 'default'))
WHERE (company_id IS NULL OR department_id IS NULL)
  AND NOT EXISTS (
    SELECT 1
    FROM user_roles
    JOIN roles ON roles.id = user_roles.role_id
    WHERE user_roles.user_id = users.id
      AND roles.name = 'admin'
  );

-- 更新角色数据范围
UPDATE roles SET data_scope = 'all' WHERE name = 'admin';
UPDATE roles SET data_scope = 'self' WHERE name = 'user';

-- 超级管理员是系统级账号，不归属任何公司和组织架构。
UPDATE users
SET company_id = NULL,
    department_id = NULL,
    updated_at = now()
WHERE EXISTS (
  SELECT 1
  FROM user_roles
  JOIN roles ON roles.id = user_roles.role_id
  WHERE user_roles.user_id = users.id
    AND roles.name = 'admin'
);

-- 权限标识统一维护在 menus.permission 字段，不再单独维护权限列表。

WITH desired AS (
  SELECT *
  FROM (
    VALUES
      ('首页', 'C', NULL, '/dashboard', 'dashboard/DashboardView', 'dashboard:view', 'House', 1, true),
      ('系统管理', 'M', NULL, '/admin', NULL, NULL, 'Setting', 10, true),
      ('公司管理', 'C', '系统管理', '/admin/company', 'admin/CompanyView', 'system:company:list', 'Briefcase', 5, true),
      ('公司新增', 'F', '公司管理', NULL, NULL, 'system:company:create', NULL, 6, false),
      ('公司修改', 'F', '公司管理', NULL, NULL, 'system:company:update', NULL, 7, false),
      ('公司删除', 'F', '公司管理', NULL, NULL, 'system:company:delete', NULL, 8, false),
      ('组织架构', 'C', '系统管理', '/admin/organizations', 'organization/DepartmentView', 'system:department:list', 'Share', 10, true),
      ('组织新增', 'F', '组织架构', NULL, NULL, 'system:department:create', NULL, 11, false),
      ('组织修改', 'F', '组织架构', NULL, NULL, 'system:department:update', NULL, 12, false),
      ('组织删除', 'F', '组织架构', NULL, NULL, 'system:department:delete', NULL, 13, false),
      ('用户管理', 'C', '系统管理', '/admin/users', 'admin/AdminView:users', 'system:user:list', 'User', 20, true),
      ('用户新增', 'F', '用户管理', NULL, NULL, 'system:user:create', NULL, 21, false),
      ('用户修改', 'F', '用户管理', NULL, NULL, 'system:user:update', NULL, 22, false),
      ('用户删除', 'F', '用户管理', NULL, NULL, 'system:user:delete', NULL, 23, false),
      ('重置密码', 'F', '用户管理', NULL, NULL, 'system:user:reset-password', NULL, 24, false),
      ('角色管理', 'C', '系统管理', '/admin/roles', 'admin/AdminView:roles', 'system:role:list', 'UserFilled', 30, true),
      ('角色新增', 'F', '角色管理', NULL, NULL, 'system:role:create', NULL, 31, false),
      ('角色修改', 'F', '角色管理', NULL, NULL, 'system:role:update', NULL, 32, false),
      ('角色删除', 'F', '角色管理', NULL, NULL, 'system:role:delete', NULL, 33, false),
      ('角色授权', 'F', '角色管理', NULL, NULL, 'system:role:grant', NULL, 34, false),
      ('菜单管理', 'C', '系统管理', '/admin/menus', 'admin/AdminView:menus', 'system:menu:list', 'Menu', 40, true),
      ('菜单新增', 'F', '菜单管理', NULL, NULL, 'system:menu:create', NULL, 41, false),
      ('菜单修改', 'F', '菜单管理', NULL, NULL, 'system:menu:update', NULL, 42, false),
      ('菜单删除', 'F', '菜单管理', NULL, NULL, 'system:menu:delete', NULL, 43, false),
      ('审计日志', 'C', '系统管理', '/admin/audit-logs', 'admin/AdminView:audit', 'system:audit:list', 'DocumentChecked', 60, true),

      ('需求工作台', 'M', NULL, '/demands', NULL, NULL, 'Files', 20, true),
      ('需求管理', 'C', '需求工作台', '/demands', 'demand/DemandView', 'demand:list', 'Document', 10, true),
      ('新增需求', 'F', '需求管理', NULL, NULL, 'demand:create', NULL, 11, false),
      ('修改需求', 'F', '需求管理', NULL, NULL, 'demand:update', NULL, 12, false),
      ('删除需求', 'F', '需求管理', NULL, NULL, 'demand:delete', NULL, 13, false),
      ('归档需求', 'F', '需求管理', NULL, NULL, 'demand:archive', NULL, 14, false),
      ('查看工作流', 'F', '需求管理', NULL, NULL, 'workflow:view', NULL, 20, false),
      ('新建工作流', 'F', '需求管理', NULL, NULL, 'workflow:create', NULL, 21, false),
      ('推进阶段', 'F', '需求管理', NULL, NULL, 'workflow:advance', NULL, 22, false),
      ('阻塞阶段', 'F', '需求管理', NULL, NULL, 'workflow:block', NULL, 23, false),
      ('查看仓库', 'F', '需求管理', NULL, NULL, 'repository:list', NULL, 30, false),
      ('查看产物', 'F', '需求管理', NULL, NULL, 'artifact:list', NULL, 31, false),
      ('查看 Agent Run', 'F', '需求管理', NULL, NULL, 'agent_run:list', NULL, 32, false),
      ('查看 Review', 'F', '需求管理', NULL, NULL, 'review:list', NULL, 33, false)
  ) AS item(menu_name, menu_type, parent_name, path, component, permission, icon, order_num, visible)
),
roots AS (
  INSERT INTO menus (menu_name, menu_type, path, component, permission, icon, order_num, visible, status)
  SELECT d.menu_name, d.menu_type, d.path, d.component, d.permission, d.icon, d.order_num, d.visible, 'active'
  FROM desired d
  WHERE d.parent_name IS NULL
    AND NOT EXISTS (
      SELECT 1 FROM menus m
      WHERE m.parent_id IS NULL
        AND m.menu_name = d.menu_name
        AND COALESCE(m.permission, '') = COALESCE(d.permission, '')
        AND COALESCE(m.path, '') = COALESCE(d.path, '')
    )
  RETURNING id
),
updated_roots AS (
  UPDATE menus m
  SET path = d.path,
      component = d.component,
      permission = d.permission,
      icon = d.icon,
      order_num = d.order_num,
      visible = d.visible,
      status = 'active'
  FROM desired d
  WHERE d.parent_name IS NULL
  AND m.parent_id IS NULL
    AND m.menu_name = d.menu_name
    AND COALESCE(m.permission, '') = COALESCE(d.permission, '')
    AND COALESCE(m.path, '') = COALESCE(d.path, '')
  RETURNING m.id
),
children AS (
  INSERT INTO menus (parent_id, menu_name, menu_type, path, component, permission, icon, order_num, visible, status)
  SELECT parent.id, d.menu_name, d.menu_type, d.path, d.component, d.permission, d.icon, d.order_num, d.visible, 'active'
  FROM desired d
  JOIN menus parent ON parent.menu_name = d.parent_name
  WHERE d.parent_name IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM menus m
      WHERE COALESCE(m.permission, '') = COALESCE(d.permission, '')
        AND m.menu_name = d.menu_name
    )
  RETURNING id
)
UPDATE menus m
SET parent_id = parent.id,
    menu_type = d.menu_type,
    path = d.path,
    component = d.component,
    permission = d.permission,
    icon = d.icon,
    order_num = d.order_num,
    visible = d.visible,
    status = 'active'
FROM desired d
JOIN menus parent ON parent.menu_name = d.parent_name
WHERE d.parent_name IS NOT NULL
  AND COALESCE(m.permission, '') = COALESCE(d.permission, '')
  AND m.menu_name = d.menu_name;

INSERT INTO role_menus (role_id, menu_id)
SELECT roles.id, menus.id
FROM roles
CROSS JOIN menus
WHERE roles.name = 'admin'
  AND menus.status = 'active'
ON CONFLICT DO NOTHING;

UPDATE menus
SET menu_name = '组织架构',
    path = '/admin/organizations',
    updated_at = now()
WHERE permission = 'system:department:list';

INSERT INTO role_menus (role_id, menu_id)
SELECT roles.id, menus.id
FROM roles
CROSS JOIN menus
WHERE roles.name = 'user'
  AND menus.permission IN (
    'dashboard:view',
    'system:user:list',
    'system:role:list',
    'system:department:list'
  )
ON CONFLICT DO NOTHING;
