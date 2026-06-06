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
