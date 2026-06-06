-- 组织架构产品文案调整，需求成员支持从归属组织架构导入。

UPDATE menus
SET menu_name = '组织架构',
    path = '/admin/organizations',
    updated_at = now()
WHERE permission = 'system:department:list';
