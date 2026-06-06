-- 普通用户需要查看和推进自己有权限访问的需求工作流。

INSERT INTO role_menus (role_id, menu_id)
SELECT roles.id, menus.id
FROM roles
JOIN menus ON menus.permission IN ('workflow:view', 'workflow:create', 'workflow:advance', 'workflow:block')
WHERE roles.name = 'user'
ON CONFLICT DO NOTHING;
