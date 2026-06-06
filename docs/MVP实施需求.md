# OpenDevFlow MVP 实施需求

## 1. 本轮目标

本轮实现 OpenDevFlow 的第一版 MVP：以“需求”为入口的 AI 软件交付工作流平台。

用户创建一个需求后，系统自动生成该需求的工作流阶段。后续所有规格、开发、QA、交付产物都围绕该需求维护。

本轮重点不是接入真实 AI agent 或在线 IDE，而是先完成公司级平台的基础数据、权限、工作流、产物和页面闭环。

## 2. 本轮实施范围

必须实现：

- 公司、部门、角色数据范围权限模型。
- 需求管理。
- 仓库管理。
- 需求工作流自动初始化。
- 工作流阶段看板。
- 阶段产物 artifact 管理。
- Agent Run 手工记录和日志查看。
- Review / QA 结论记录。
- Final Review 下的 PR 描述产物。
- 关键操作审计日志。

本轮不实现：

- 真实 Claude Code / Codex / Cursor CLI 执行。
- OpenSpec CLI 调用。
- Superpowers 运行时集成。
- Docker workspace。
- Git clone。
- GitHub/GitLab OAuth。
- 自动创建 PR。
- 实时日志 WebSocket。
- Supabase。
- 多公司切换。
- 需求参与人权限。

## 3. 现有基础

项目基于 `biz-skill-hub` 骨架复制而来，当前已具备：

- FastAPI 后端。
- Vue 3 + Vite + Element Plus 前端。
- PostgreSQL。
- JWT 登录。
- RBAC 角色权限。
- 管理后台布局。
- 用户、角色、权限、审计日志基础页面。

本轮应复用现有模块风格和页面布局，不做大规模重构。

## 4. 第一阶段：组织与数据权限

公司级使用需要先补齐组织结构和数据可见性。权限模型参考 Ruoyi 的 RBAC + 部门数据范围思想。

### 4.1 新增公司

新增 `companies` 表。

字段：

- `id`
- `name`
- `code`
- `status`
- `created_at`
- `updated_at`

MVP 只初始化一个默认公司，不做多公司切换。

初始化默认公司：

- `name`: 默认公司
- `code`: default
- `status`: active

### 4.2 新增部门

新增 `departments` 表。

字段：

- `id`
- `company_id`
- `parent_id`
- `ancestors`
- `name`
- `order_num`
- `status`
- `created_at`
- `updated_at`

说明：

- `parent_id` 支持树形部门。
- `ancestors` 保存祖先部门 id 路径，用于查询本部门及以下数据。
- MVP 初始化一个默认部门。

初始化默认部门：

- `company_id`: 默认公司 id
- `parent_id`: null
- `ancestors`: 空字符串
- `name`: 默认部门
- `status`: active

### 4.3 用户绑定公司和部门

扩展 `users` 表：

- 新增 `company_id`
- 新增 `department_id`

初始化管理员用户归属默认公司和默认部门。

用户管理页面需要展示和编辑用户所属部门。MVP 可以用下拉选择部门，不要求复杂树选择器。

### 4.4 角色数据范围

扩展 `roles` 表：

- 新增 `data_scope`

枚举：

- `all`: 全部数据
- `custom_dept`: 自定义部门数据
- `dept`: 本部门数据
- `dept_and_child`: 本部门及以下数据
- `self`: 仅本人数据

初始化规则：

- `admin` 角色默认 `all`
- `user` 角色默认 `self`

### 4.5 自定义部门数据范围

新增 `role_departments` 表。

字段：

- `role_id`
- `department_id`

当角色 `data_scope=custom_dept` 时，通过该表决定可见部门。

### 4.6 数据权限作用范围

本轮数据权限必须作用于：

- `demands`
- `workflows`
- `workflow_stages`
- `workflow_artifacts`
- `agent_runs`
- `reviews`

业务表必须通过需求归属做数据过滤。即 workflow、artifact、agent run、review 的可见性都跟随所属 demand。

MVP 不要求对仓库配置做数据范围过滤，仓库只受功能权限控制。

### 4.7 数据权限规则

查询需求相关数据时，根据当前用户角色的数据范围过滤。

规则：

- `all`: 可见当前公司全部需求。
- `custom_dept`: 可见角色绑定部门下的需求。
- `dept`: 可见当前用户部门下的需求。
- `dept_and_child`: 可见当前用户部门及下级部门下的需求。
- `self`: 仅可见当前用户创建的需求。

如果用户有多个角色，取最宽数据范围：

优先级：

```text
all > dept_and_child > dept > custom_dept > self
```

后端应提供统一函数，例如：

```text
apply_demand_data_scope(query, current_user)
```

所有需求相关列表和详情查询必须使用该函数。

## 5. 需求模型

需求是平台第一主实体。项目和仓库都是需求的上下文，不是第一入口。

### 5.1 需求类型

`type` 枚举：

- `new_business`: 新业务需求
- `new_project`: 新项目需求
- `optimization`: 优化需求
- `bugfix`: 缺陷修复
- `refactor`: 重构需求

### 5.2 需求状态

`status` 枚举：

- `active`: 进行中
- `blocked`: 阻塞
- `delivered`: 已交付
- `archived`: 已归档

### 5.3 需求字段

新增 `demands` 表。

字段：

- `id`
- `title`
- `type`
- `description`
- `expected_live_at`
- `repository_id`
- `status`
- `company_id`
- `department_id`
- `created_by`
- `created_at`
- `updated_at`

字段说明：

- `title`: 需求标题，必填。
- `type`: 需求类型，必填。
- `description`: 原始需求描述，必填。
- `expected_live_at`: 期望上线时间，可选，只展示和编辑，不做 SLA 逻辑。
- `repository_id`: 关联仓库，可选。
- `status`: 默认 `active`。
- `company_id`: 创建时自动取当前用户公司。
- `department_id`: 创建时自动取当前用户部门。
- `created_by`: 创建人。

需求创建表单只展示：

- 需求标题。
- 需求类型。
- 原始需求描述。
- 期望上线时间。
- 关联仓库。

不展示公司和部门字段。

## 6. 仓库模型

新增 `repositories` 表。

字段：

- `id`
- `name`
- `git_url`
- `default_branch`
- `local_path`
- `description`
- `status`
- `created_by`
- `created_at`
- `updated_at`

说明：

- `name`: 仓库名称，必填。
- `git_url`: Git 地址，可选。
- `default_branch`: 默认分支，默认 `main`。
- `local_path`: 本地路径，可选。
- `description`: 描述，可选。
- `status`: `active` / `disabled`。

MVP 只手工录入，不执行 clone。

## 7. 工作流模型

一个需求默认创建一条 workflow。

### 7.1 工作流阶段

MVP 使用以下阶段：

```text
demand_created
product_discovery
spec_authoring
dev_planning
implementation
dev_review
dev_verify
qa_verification
final_review
archived
```

阶段显示名：

- `demand_created`: 需求已创建
- `product_discovery`: 需求澄清
- `spec_authoring`: 规格产出
- `dev_planning`: 开发计划
- `implementation`: 代码实现
- `dev_review`: 开发审查
- `dev_verify`: 开发验证
- `qa_verification`: QA 验收
- `final_review`: 最终审查
- `archived`: 已归档

### 7.2 工作流状态

`workflows.status` 枚举：

- `running`
- `blocked`
- `done`
- `archived`

### 7.3 阶段状态

`workflow_stages.status` 枚举：

- `pending`
- `current`
- `passed`
- `blocked`
- `skipped`

### 7.4 工作流表

新增 `workflows` 表。

字段：

- `id`
- `demand_id`
- `current_stage`
- `status`
- `created_at`
- `updated_at`

创建需求后自动创建 workflow：

- `current_stage`: `demand_created`
- `status`: `running`

### 7.5 阶段表

新增 `workflow_stages` 表。

字段：

- `id`
- `workflow_id`
- `stage_key`
- `stage_name`
- `sort_order`
- `status`
- `started_at`
- `finished_at`
- `blocked_reason`
- `created_at`
- `updated_at`

创建 workflow 时自动生成全部阶段：

- 第一个阶段 `demand_created` 状态为 `current`
- 其余阶段状态为 `pending`

### 7.6 阶段流转规则

MVP 只支持手动流转。

允许动作：

- 标记当前阶段通过。
- 标记当前阶段阻塞。
- 从阻塞恢复为当前阶段。
- 推进到下一阶段。
- 归档。

推进逻辑：

- 当前阶段标记通过后，当前阶段变为 `passed`。
- 下一阶段变为 `current`。
- `workflows.current_stage` 更新为下一阶段。
- 当 `final_review` 通过后，需求状态可变为 `delivered`。
- 执行归档后，workflow 状态为 `archived`，需求状态为 `archived`，`archived` 阶段为 `passed`。

禁止：

- 跳过当前阶段直接进入后续阶段。
- 已归档 workflow 再修改阶段。
- 非授权用户推进阶段。

## 8. Artifact 模型

Artifact 是需求不同阶段的文档产物。

新增 `workflow_artifacts` 表。

字段：

- `id`
- `demand_id`
- `workflow_id`
- `stage`
- `artifact_type`
- `title`
- `content`
- `version`
- `created_by`
- `created_at`
- `updated_at`

### 8.1 Artifact 类型

MVP 支持：

- `prd`
- `user_stories`
- `acceptance_criteria`
- `proposal`
- `design`
- `tasks`
- `dev_plan`
- `implementation_report`
- `code_review`
- `verify_report`
- `test_plan`
- `qa_report`
- `bugs`
- `pr_description`
- `delivery_summary`

### 8.2 默认 Artifact

创建需求后，不自动创建全部 artifact。

在需求详情页提供“新增产物”按钮，由用户选择阶段和类型创建。

MVP 可以提供快捷创建：

- 需求澄清：`prd`、`user_stories`、`acceptance_criteria`
- 规格产出：`proposal`、`design`、`tasks`
- 开发计划：`dev_plan`
- 开发审查：`code_review`
- 开发验证：`verify_report`
- QA 验收：`test_plan`、`qa_report`、`bugs`
- 最终审查：`pr_description`、`delivery_summary`

### 8.3 Artifact 编辑

Artifact 详情支持：

- 查看标题。
- 查看阶段。
- 查看类型。
- Markdown 内容编辑。
- 保存。

MVP 不做多人协同编辑，不做版本恢复，只保留 `version` 自增。

## 9. Agent Run 模型

MVP 不执行真实 agent，只记录 agent run。

新增 `agent_runs` 表。

字段：

- `id`
- `demand_id`
- `workflow_id`
- `stage`
- `agent_type`
- `status`
- `input_summary`
- `output_summary`
- `logs`
- `started_at`
- `finished_at`
- `exit_code`
- `blocker_reason`
- `created_by`
- `created_at`
- `updated_at`

`agent_type` 枚举：

- `manual`
- `claude_code`
- `codex_cli`
- `other`

`status` 枚举：

- `pending`
- `running`
- `success`
- `failed`
- `blocked`

页面支持：

- 新增 agent run 记录。
- 编辑状态。
- 填写输入摘要、输出摘要、日志、阻塞原因。
- 查看 run 列表和详情。

## 10. Review / QA 模型

新增 `reviews` 表。

字段：

- `id`
- `demand_id`
- `workflow_id`
- `stage`
- `review_type`
- `result`
- `comment`
- `created_by`
- `created_at`
- `updated_at`

`review_type` 枚举：

- `product_review`
- `spec_review`
- `dev_review`
- `qa_review`
- `final_review`

`result` 枚举：

- `passed`
- `failed`
- `blocked`

页面支持：

- 在需求详情中新增审查记录。
- 查看审查历史。
- QA 验收结果通过 `review_type=qa_review` 记录。

## 11. 权限项

在现有权限表中新增权限。

组织权限：

- `system:company:list`
- `system:company:update`
- `system:department:list`
- `system:department:create`
- `system:department:update`
- `system:department:delete`

仓库权限：

- `repository:list`
- `repository:create`
- `repository:update`
- `repository:delete`

需求权限：

- `demand:list`
- `demand:create`
- `demand:update`
- `demand:delete`
- `demand:archive`

工作流权限：

- `workflow:view`
- `workflow:advance`
- `workflow:block`

Artifact 权限：

- `artifact:list`
- `artifact:create`
- `artifact:update`
- `artifact:delete`

Agent Run 权限：

- `agent_run:list`
- `agent_run:create`
- `agent_run:update`

Review 权限：

- `review:list`
- `review:create`

管理员默认拥有全部权限。普通用户默认至少拥有：

- `repository:list`
- `demand:list`
- `demand:create`
- `demand:update`
- `workflow:view`
- `artifact:list`
- `artifact:create`
- `artifact:update`
- `agent_run:list`
- `agent_run:create`
- `review:list`
- `review:create`

## 12. 审计要求

以下操作必须写入 `audit_logs`：

- 创建公司。
- 修改公司。
- 创建部门。
- 修改部门。
- 删除部门。
- 修改角色数据范围。
- 修改角色自定义部门。
- 创建仓库。
- 修改仓库。
- 删除仓库。
- 创建需求。
- 修改需求。
- 删除需求。
- 推进工作流阶段。
- 标记阶段阻塞。
- 阶段恢复。
- 创建 artifact。
- 修改 artifact。
- 删除 artifact。
- 创建 agent run。
- 修改 agent run。
- 创建 review。
- 归档需求。

审计日志至少记录：

- 操作人。
- 操作类型。
- 资源类型。
- 资源 id。
- 操作时间。
- 操作摘要。

## 13. 后端模块

新增模块路径：

```text
backend/app/modules/companies
backend/app/modules/departments
backend/app/modules/repositories
backend/app/modules/demands
backend/app/modules/workflows
backend/app/modules/artifacts
backend/app/modules/agent_runs
backend/app/modules/reviews
```

新增或扩展模型路径：

```text
backend/app/models/company.py
backend/app/models/department.py
backend/app/models/repository.py
backend/app/models/demand.py
backend/app/models/workflow.py
backend/app/models/artifact.py
backend/app/models/agent_run.py
backend/app/models/review.py
backend/app/models/user.py
backend/app/models/rbac.py 或现有 role 模型文件
```

数据权限建议放在：

```text
backend/app/core/data_scope.py
```

## 14. 后端 API

API 前缀沿用 `/api/v1`。

### 14.1 部门 API

- `GET /departments`
- `POST /departments`
- `PATCH /departments/{id}`
- `DELETE /departments/{id}`

### 14.2 仓库 API

- `GET /repositories`
- `POST /repositories`
- `GET /repositories/{id}`
- `PATCH /repositories/{id}`
- `DELETE /repositories/{id}`

### 14.3 需求 API

- `GET /demands`
- `POST /demands`
- `GET /demands/{id}`
- `PATCH /demands/{id}`
- `DELETE /demands/{id}`
- `POST /demands/{id}/archive`

需求列表必须应用数据权限。

创建需求时必须自动：

- 写入 `company_id`
- 写入 `department_id`
- 写入 `created_by`
- 创建 workflow
- 创建 workflow stages
- 写审计日志

### 14.4 工作流 API

- `GET /demands/{id}/workflow`
- `POST /workflows/{id}/advance`
- `POST /workflows/{id}/block`
- `POST /workflows/{id}/resume`

阶段推进必须校验当前用户对所属需求的数据可见性和 `workflow:advance` 权限。

### 14.5 Artifact API

- `GET /demands/{id}/artifacts`
- `POST /demands/{id}/artifacts`
- `GET /artifacts/{id}`
- `PATCH /artifacts/{id}`
- `DELETE /artifacts/{id}`

Artifact 查询和详情必须通过所属 demand 校验数据权限。

### 14.6 Agent Run API

- `GET /demands/{id}/agent-runs`
- `POST /demands/{id}/agent-runs`
- `GET /agent-runs/{id}`
- `PATCH /agent-runs/{id}`

### 14.7 Review API

- `GET /demands/{id}/reviews`
- `POST /demands/{id}/reviews`

## 15. 前端页面

沿用现有后台布局，新增菜单。

### 15.1 菜单

新增一级菜单：

- 需求工作台
- 需求列表
- 仓库管理
- 组织管理

系统管理保留现有：

- 用户管理
- 角色管理
- 菜单管理
- 审计日志

### 15.2 需求工作台

路由：

```text
/demands/dashboard
```

展示统计卡片：

- 进行中需求数。
- 阻塞需求数。
- 已交付需求数。
- 已归档需求数。

展示需求列表快捷入口：

- 最新需求。
- 当前用户可见需求。

### 15.3 需求列表

路由：

```text
/demands
```

列表字段：

- 标题。
- 类型。
- 状态。
- 当前阶段。
- 关联仓库。
- 期望上线时间。
- 创建人。
- 创建时间。

支持：

- 新建需求。
- 编辑需求。
- 查看详情。
- 删除需求。

查询条件：

- 标题。
- 类型。
- 状态。

需求列表必须只展示当前用户数据权限范围内的需求。

### 15.4 需求详情

路由：

```text
/demands/:id
```

页面区域：

- 需求基本信息。
- 当前阶段。
- 阶段看板。
- Artifact 列表。
- Agent Run 列表。
- Review / QA 记录。

阶段看板展示全部阶段状态。

支持操作：

- 推进当前阶段。
- 标记当前阶段阻塞。
- 从阻塞恢复。
- 新增 artifact。
- 新增 agent run。
- 新增 review。
- 归档需求。

### 15.5 Artifact 页面

可以做成需求详情内的抽屉或弹窗。

字段：

- 标题。
- 阶段。
- 类型。
- Markdown 内容。

支持保存。

### 15.6 Agent Run 页面

可以做成需求详情内的抽屉或弹窗。

字段：

- 阶段。
- Agent 类型。
- 状态。
- 输入摘要。
- 输出摘要。
- 日志。
- 阻塞原因。
- 开始时间。
- 结束时间。
- 退出码。

### 15.7 Review 页面

可以做成需求详情内的弹窗。

字段：

- 阶段。
- Review 类型。
- 结果。
- 备注。

### 15.8 仓库管理

路由：

```text
/repositories
```

支持：

- 仓库列表。
- 新增仓库。
- 编辑仓库。
- 删除仓库。

### 15.9 组织管理

路由：

```text
/organization/departments
```

支持：

- 部门列表。
- 新增部门。
- 编辑部门。
- 删除部门。

公司管理 MVP 可以不单独做页面，只保留默认公司。

### 15.10 角色管理增强

现有角色管理页面需要增加：

- 数据范围选择。
- 当数据范围为 `custom_dept` 时，可以选择自定义部门。

## 16. 初始化 SQL

更新 `backend/sql/init.sql`。

必须初始化：

- 默认公司。
- 默认部门。
- 管理员用户绑定默认公司和部门。
- 普通用户绑定默认公司和部门。
- admin 角色 `data_scope=all`。
- user 角色 `data_scope=self`。
- 新增权限项。
- admin 角色绑定全部权限。
- user 角色绑定普通用户默认权限。

## 17. 验收标准

### 17.1 权限模型

- 系统启动后存在默认公司和默认部门。
- 管理员和普通用户都绑定默认公司和默认部门。
- 角色页面可以查看和修改角色数据范围。
- `admin` 默认可见全部需求。
- `user` 默认只能看自己创建的需求。
- 需求列表和需求详情都应用数据权限。

### 17.2 需求创建

- 用户可以创建需求。
- 创建表单只包含标题、类型、描述、期望上线时间、关联仓库。
- 创建需求后自动生成 workflow。
- 创建 workflow 后自动生成全部阶段。
- 创建后进入需求详情页。

### 17.3 工作流阶段

- 新需求默认当前阶段为 `demand_created`。
- 阶段看板展示所有阶段。
- 用户可以推进当前阶段到下一阶段。
- 用户可以标记当前阶段阻塞。
- 阻塞后 workflow 状态变为 `blocked`。
- 恢复后 workflow 状态变为 `running`。
- 不允许跳过阶段。
- 归档后不允许继续修改阶段。

### 17.4 Artifact

- 用户可以在需求详情新增 artifact。
- 用户可以编辑 Markdown 内容。
- 保存 artifact 后版本号递增。
- 用户只能访问自己数据权限范围内需求的 artifact。

### 17.5 Agent Run

- 用户可以新增 agent run 记录。
- 用户可以编辑 agent run 状态、摘要、日志。
- Agent run 不执行真实命令。
- 用户只能访问自己数据权限范围内需求的 agent run。

### 17.6 Review / QA

- 用户可以新增 review 记录。
- QA 验收通过可通过 `review_type=qa_review` 和 `result=passed` 记录。
- 用户只能访问自己数据权限范围内需求的 review。

### 17.7 仓库

- 用户可以新增、编辑、删除仓库。
- 新建需求时可以选择一个仓库，也可以不选择。
- 仓库不会触发 clone 或 Git 操作。

### 17.8 审计

- 创建需求写入审计日志。
- 阶段推进写入审计日志。
- 阶段阻塞和恢复写入审计日志。
- 新增和修改 artifact 写入审计日志。
- 新增和修改 agent run 写入审计日志。
- 新增 review 写入审计日志。
- 归档需求写入审计日志。

### 17.9 本地运行

- PostgreSQL 可以通过 Docker Compose 启动。
- 后端可以通过 `uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload` 启动。
- 前端可以通过 `npm run dev` 启动。
- 登录后可以完成从“新建需求”到“归档需求”的完整手工流程。
