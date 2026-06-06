-- 组织成员仅维护在项目组上，部门不再维护成员。

DELETE FROM organization_members
USING departments
WHERE organization_members.department_id = departments.id
  AND departments.org_type <> 'project_group';
