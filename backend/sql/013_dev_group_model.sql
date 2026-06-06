-- 引入开发组模型：
-- 部门下可挂部门、项目组、开发组；项目组下只能挂开发组；需求和组织成员只维护在开发组上。

UPDATE departments
SET org_type = 'project_group'
WHERE name = '来伊份项目组'
  AND org_type = 'department';

UPDATE departments
SET org_type = 'dev_group'
WHERE name IN ('交易组', '商品组')
  AND org_type = 'project_group';

DELETE FROM organization_members
USING departments
WHERE organization_members.department_id = departments.id
  AND departments.org_type <> 'dev_group';
