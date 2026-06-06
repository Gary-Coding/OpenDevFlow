-- 用户级大模型配置：平台不提供 AI 服务，用户自带兼容接口和 API Key。
CREATE TABLE IF NOT EXISTS model_providers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(120) NOT NULL,
  provider_type VARCHAR(40) NOT NULL,
  base_url TEXT NOT NULL,
  api_key_encrypted TEXT,
  default_model VARCHAR(160),
  is_default BOOLEAN NOT NULL DEFAULT false,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_model_providers_user_name UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_model_providers_user_id ON model_providers(user_id);
CREATE INDEX IF NOT EXISTS idx_model_providers_provider_type ON model_providers(provider_type);
CREATE INDEX IF NOT EXISTS idx_model_providers_is_default ON model_providers(is_default);
CREATE INDEX IF NOT EXISTS idx_model_providers_status ON model_providers(status);

WITH workbench_menu AS (
  SELECT id
  FROM menus
  WHERE menu_name IN ('工作台', '需求工作台')
    AND parent_id IS NULL
  ORDER BY CASE WHEN menu_name = '工作台' THEN 0 ELSE 1 END
  LIMIT 1
),
desired AS (
  SELECT *
  FROM (
    VALUES
      ('模型配置', 'C', '/model-providers', 'model/ModelProviderView', 'model_provider:list', 'Cpu', 20, true),
      ('新增模型配置', 'F', NULL, NULL, 'model_provider:create', NULL, 21, false),
      ('修改模型配置', 'F', NULL, NULL, 'model_provider:update', NULL, 22, false),
      ('删除模型配置', 'F', NULL, NULL, 'model_provider:delete', NULL, 23, false)
  ) AS item(menu_name, menu_type, path, component, permission, icon, order_num, visible)
),
model_menu AS (
  INSERT INTO menus (parent_id, menu_name, menu_type, path, component, permission, icon, order_num, visible, status)
  SELECT workbench_menu.id, d.menu_name, d.menu_type, d.path, d.component, d.permission, d.icon, d.order_num, d.visible, 'active'
  FROM desired d
  CROSS JOIN workbench_menu
  WHERE d.permission = 'model_provider:list'
    AND NOT EXISTS (SELECT 1 FROM menus WHERE permission = d.permission)
  RETURNING id
),
updated_model_menu AS (
  UPDATE menus m
  SET parent_id = workbench_menu.id,
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
  CROSS JOIN workbench_menu
  WHERE m.permission = d.permission
    AND d.permission = 'model_provider:list'
  RETURNING m.id
),
model_parent AS (
  SELECT id FROM menus WHERE permission = 'model_provider:list' LIMIT 1
)
INSERT INTO menus (parent_id, menu_name, menu_type, path, component, permission, icon, order_num, visible, status)
SELECT model_parent.id, d.menu_name, d.menu_type, d.path, d.component, d.permission, d.icon, d.order_num, d.visible, 'active'
FROM desired d
CROSS JOIN model_parent
WHERE d.permission <> 'model_provider:list'
  AND NOT EXISTS (SELECT 1 FROM menus WHERE permission = d.permission);

WITH desired AS (
  SELECT *
  FROM (
    VALUES
      ('model_provider:create', '新增模型配置', 21),
      ('model_provider:update', '修改模型配置', 22),
      ('model_provider:delete', '删除模型配置', 23)
  ) AS item(permission, menu_name, order_num)
),
model_parent AS (
  SELECT id FROM menus WHERE permission = 'model_provider:list' LIMIT 1
)
UPDATE menus m
SET parent_id = model_parent.id,
    menu_name = d.menu_name,
    menu_type = 'F',
    path = NULL,
    component = NULL,
    icon = NULL,
    order_num = d.order_num,
    visible = false,
    status = 'active',
    updated_at = now()
FROM desired d
CROSS JOIN model_parent
WHERE m.permission = d.permission;

WITH desired AS (
  SELECT *
  FROM (
    VALUES
      ('新增模型配置', 'model_provider:create', 21),
      ('修改模型配置', 'model_provider:update', 22),
      ('删除模型配置', 'model_provider:delete', 23)
  ) AS item(menu_name, permission, order_num)
),
model_parent AS (
  SELECT id FROM menus WHERE permission = 'model_provider:list' LIMIT 1
)
INSERT INTO menus (parent_id, menu_name, menu_type, path, component, permission, icon, order_num, visible, status)
SELECT model_parent.id, d.menu_name, 'F', NULL, NULL, d.permission, NULL, d.order_num, false, 'active'
FROM desired d
CROSS JOIN model_parent
WHERE NOT EXISTS (SELECT 1 FROM menus WHERE permission = d.permission);

INSERT INTO role_menus (role_id, menu_id)
SELECT roles.id, menus.id
FROM roles
CROSS JOIN menus
WHERE roles.name = 'admin'
  AND menus.permission IN ('model_provider:list', 'model_provider:create', 'model_provider:update', 'model_provider:delete')
ON CONFLICT DO NOTHING;

INSERT INTO role_menus (role_id, menu_id)
SELECT roles.id, menus.id
FROM roles
CROSS JOIN menus
WHERE roles.name = 'user'
  AND menus.permission IN ('model_provider:list', 'model_provider:create', 'model_provider:update', 'model_provider:delete')
ON CONFLICT DO NOTHING;
