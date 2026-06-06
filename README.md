# OpenDevFlow

OpenDevFlow 是一个面向公司内部交付协作的开源、自托管 AI 工作流平台。平台以“需求”为绝对主体，把需求澄清、PRD、产品设计、OpenSpec、开发实施、QA 验收和交付归档串成可追踪的闭环。

当前版本优先验证“平台编排 + Git Skill + 用户自有模型 + 本地 Bridge 代码上下文”的可行性：AI 在平台内推进阶段，代码扫描、命令执行、编译验证等资源消耗留在用户本机。

## 技术栈

- 前端：Vue 3、Vite、Vue Router、Pinia、Element Plus
- 后端：Python、FastAPI、SQLAlchemy
- 数据库：PostgreSQL
- 鉴权：JWT + RBAC + 菜单权限
- Skill 来源：GitHub、Gitee、GitLab
- 本地工作区：Node Bridge

## 当前 MVP 已完成能力

- 系统管理：公司、组织架构、用户、角色、菜单权限、审计日志。
- 需求管理：需求列表、需求详情、需求成员、期望上线时间、状态流转。
- 工作流管理：支持完整流程、缺陷修复、小需求三类工作流模板。
- 阶段编排：阶段绑定 Skill，阶段完成后自动进入下一阶段。
- Skill 管理：配置统一 Skill 仓库来源，从 Git 仓库读取 `SKILL.md` 注入 AI Prompt。
- 模型配置：用户自行配置模型服务和可用模型，平台不内置大模型服务。
- AI 流式会话：工作流详情页支持阶段 AI 对话、快捷指令、流式回复。
- 工作空间文件：每个需求生成独立工作空间，支持阶段文件预览、编辑和自动保存。
- Markdown 渲染：AI 消息和文档预览支持 Markdown、代码高亮和基础净化。
- 代码上下文快照：通过本地 Bridge 扫描代码根目录，生成当前需求的代码上下文。
- 本地 Bridge：支持扫描多项目代码根目录、同步本地项目、执行本地命令、回传日志。
- Gate 校验：支持手动阶段检查和阶段完成前检查，结合平台规则和 Skill Gate 语义要求。
- 产物版本：阶段完成时生成当前阶段产物版本，便于后续追踪。

## 当前完整流程

```text
新建需求
  -> 新建工作流
  -> 启动本地 Bridge
  -> 扫描代码上下文
  -> 平台 AI 阶段对话
  -> 预览/编辑阶段产物
  -> 自动保存
  -> 阶段检查
  -> 阶段完成，进入下一步
  -> 重复推进后续阶段
  -> 交付归档
```

## 本地开发

### 数据库

```bash
docker compose up -d postgres
```

也可以使用本机 PostgreSQL，按后端 `.env` 配置 `DATABASE_URL`。

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload
```

默认地址：

```text
http://localhost:8765
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

默认地址：

```text
http://localhost:5173
```

### Bridge

Bridge 用于把用户本机代码上下文和命令执行能力接入平台。前期推荐使用一个代码根目录，Bridge 会在有限深度内自动识别多项目结构。

```bash
npx --registry https://registry.npmjs.org/ @opendevflow/bridge --server http://localhost:8765 --client-key muke-mac --root /your/code/root
```

参数说明：

- `--server`：OpenDevFlow 后端地址。
- `--client-key`：平台中登记的 Bridge 客户端标识。
- `--root`：本机代码根目录，可以包含多个微服务或子项目。

## 默认账号

```text
账号：admin
密码：admin
```

## 验收建议

- 使用管理员登录，确认公司、组织架构、用户、角色、菜单权限可维护。
- 配置模型服务和默认模型，确认模型列表可用。
- 配置 Skill 仓库来源，确认阶段 Skill 能从 Git 仓库读取。
- 新建需求并创建工作流，进入工作流详情。
- 启动 Bridge，触发代码上下文扫描，确认代码上下文快照生成。
- 在阶段 AI 会话中发送消息，确认流式回复和 Markdown 渲染正常。
- 修改阶段产物，确认自动保存和预览切换正常。
- 执行阶段检查，确认弹窗展示检查结果。
- 点击“阶段完成，进入下一步”，确认二次确认、Gate 校验、产物版本和阶段推进正常。

## 后续可继续优化

- Bridge 安全：增加客户端密钥、吊销、过期、IP/设备指纹和操作审计。
- 命令执行：增加命令白名单、本地二次确认、实时日志推送和更细粒度权限。
- 代码上下文：增强业务入口识别、接口/路由/数据库结构提取、变更影响分析。
- Git 扩展：在公司允许后支持绑定 Git 仓库、云端拉取代码和自动生成差异。
- 云端 Workspace：作为后续扩展支持容器化开发环境，当前不是 MVP 主路径。
- Gate 能力：把 Gate 结果拆成提示、警告、阻塞，并支持按阶段配置规则。
- AI 工具调用：逐步把文件读写、命令执行、产物生成做成标准工具调用链路。
- 产物治理：支持产物版本对比、回滚、审批、评论和归档报告。
- Skill 治理：支持 Skill 版本锁定、发布审批、变更记录和灰度启用。
- 测试体系：补充后端单元测试、接口测试、前端组件测试和端到端验收用例。
- 数据迁移：完善数据库迁移工具链，减少手工执行 SQL 的维护成本。
