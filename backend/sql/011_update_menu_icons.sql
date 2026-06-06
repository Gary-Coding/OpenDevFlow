-- 更新可见目录和菜单图标，避免侧边栏图标重复并增强语义。

WITH desired(menu_name, permission, icon) AS (
  VALUES
    ('首页', 'dashboard:view', 'House'),
    ('系统管理', NULL, 'Setting'),
    ('公司管理', 'system:company:list', 'Briefcase'),
    ('组织架构', 'system:department:list', 'Share'),
    ('用户管理', 'system:user:list', 'User'),
    ('角色管理', 'system:role:list', 'UserFilled'),
    ('菜单管理', 'system:menu:list', 'Menu'),
    ('审计日志', 'system:audit:list', 'DocumentChecked'),
    ('工作台', NULL, 'Files'),
    ('需求工作台', NULL, 'Files'),
    ('需求管理', 'demand:list', 'Document')
)
UPDATE menus
SET icon = desired.icon,
    updated_at = now()
FROM desired
WHERE menus.menu_name = desired.menu_name
  AND COALESCE(menus.permission, '') = COALESCE(desired.permission, '');
