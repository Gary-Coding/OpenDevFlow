# OpenDevFlow AI 软件交付工作流整合方案

## 1. 背景与目标

OpenDevFlow 的定位不是单纯的在线编码工具，而是公司级、可开源的 AI 软件交付生命周期平台。平台的核心入口应该是“需求”，而不是“项目”或“代码仓库”：一个需求可以是新业务需求、新项目需求、优化需求、Bugfix 或重构需求，创建需求后再衍生出规格、设计、开发计划、代码实施、验证、QA 验收和归档。

本方案整合四类已有能力：

- OpenSpec：负责需求变更的规格化表达和事实源沉淀。
- Superpowers：负责 AI 协作过程中的工作方法、计划、TDD、审查和完成准则。
- Comet：负责把 OpenSpec 和 Superpowers 串成可恢复、可守卫、可归档的阶段化流程。
- super-engineer-workflow：负责开发实施阶段的本地交付经验，包括 OpenSpec 桥接、状态机、计划、实施、审查、验证和归档检查。

平台化之后，以上能力不再依赖开发者本地手动安装多个 skill，而是由 OpenDevFlow 内置为可配置的流程、产物、Agent Run、审批和守卫规则。

## 2. 四个参考体系的职责边界

| 体系 | 适合吸收的优点 | 在 OpenDevFlow 中的定位 | 不建议照搬的部分 |
| --- | --- | --- | --- |
| OpenSpec | proposal、design、tasks、spec delta；先达成一致再开发；变更目录和规格事实源；适合 brownfield 项目 | 作为“规格层”，把需求从口语描述固化为可追踪的需求变更、设计说明和任务拆分 | 不直接把本地目录结构作为平台唯一事实源，平台事实源应进入数据库和产物表 |
| Superpowers | brainstorming、writing-plans、TDD、code review、verification-before-completion、finish branch；强调证据而不是口头完成 | 作为“工作方法层”，约束 AI 在产品、开发、测试每个阶段怎么思考、怎么产出、什么时候需要用户确认 | 不要求用户逐条运行本地 skill；平台应把这些方法封装为阶段模板和 Agent 指令 |
| Comet | 五阶段流水线、阶段守卫、handoff context、`.comet.yaml` 状态、hotfix/tweak/full 模式、归档守卫 | 作为“流程编排层”，把需求生命周期做成可恢复、可审计、可阻断、可归档的工作流 | 不照搬本地 YAML 作为状态中心，平台应使用 workflows、workflow_stages、agent_runs 存状态 |
| super-engineer-workflow | `/se:propose`、`/se:bridge`、`/se:plan`、`/se:apply`、`/se:review`、`/se:verify`、`/se:archive`；脚本管理状态；验证命令和报告 | 作为“开发交付执行器”的原型，优先吸收实施阶段的状态推进、报告、验证和归档检查能力 | 不把它扩展成产品经理和测试 skill 的唯一来源，产品和 QA 应平台化单独建模 |

## 3. 总体流程

```mermaid
flowchart LR
  A["需求登记"] --> B["需求头脑风暴"]
  B --> C["规格产出"]
  C --> D["深度设计"]
  D --> E["开发计划"]
  E --> F["代码实现"]
  F --> G["开发审查"]
  G --> H["开发验证"]
  H --> I["QA 验收"]
  I --> J["最终审查"]
  J --> K["归档"]
```

平台第一阶段可以沿用当前已有阶段：

- `demand_created`：需求已创建。
- `product_discovery`：需求澄清。
- `spec_authoring`：规格产出。
- `dev_planning`：开发计划。
- `implementation`：代码实现。
- `dev_review`：开发审查。
- `dev_verify`：开发验证。
- `qa_verification`：QA 验收。
- `final_review`：最终审查。
- `archived`：已归档。

其中“深度设计”可以先作为 `spec_authoring` 和 `dev_planning` 之间的一类产物或子步骤，不一定第一阶段新增数据库阶段。等流程稳定后，再拆成独立阶段。

## 4. 完整阶段与采纳来源

| 阶段 | 阶段目标 | 主要采纳来源 | 采纳的具体优点 | 平台产物 | 出口守卫 |
| --- | --- | --- | --- | --- | --- |
| 需求登记 | 用最少字段创建需求入口，明确类型、描述、期望上线时间、归属组织、相关仓库 | OpenDevFlow 原生模型 | 以需求为根节点，而不是以项目为根节点 | demand 记录、初始 workflow、默认 stages | 需求标题、类型、描述、组织归属存在 |
| 需求头脑风暴 | 把模糊诉求澄清为业务目标、用户、场景、边界和验收方向 | Superpowers brainstorming、OpenSpec explore | AI 先提问和澄清，再输出设计方向；用户确认后进入下一步 | 需求澄清记录、PRD 草稿、用户故事、验收标准草稿 | 用户确认澄清结论；关键待确认项为空或明确延期 |
| 规格产出 | 把需求固化为可实现、可评审的规格变更 | OpenSpec proposal/design/tasks/spec delta | proposal/design/tasks/spec delta 分离；规格变更可追踪；先对齐再实施 | proposal.md、design.md、tasks.md、spec_delta | proposal、design、tasks 产物齐全；任务可执行；影响范围明确 |
| 深度设计 | 把规格转成系统设计和开发上下文 | Comet design handoff、Superpowers brainstorming | 从 OpenSpec 生成 handoff context；设计阶段可恢复；设计文档被用户确认 | 技术设计文档、接口草案、数据模型草案、风险清单 | 关键技术方案已确认；数据库、接口、权限影响已说明 |
| 开发计划 | 把设计拆成小步可验证的实施计划 | Superpowers writing-plans、super-engineer-workflow `/se:plan` | 文件地图、任务拆分、测试策略、执行命令、验收口径 | implementation_plan、任务清单、验证命令 | 每个任务有明确文件范围和验证方式；计划通过确认 |
| 代码实现 | 按计划完成代码和必要测试 | super-engineer-workflow `/se:apply`、Superpowers TDD/executing-plans | 状态机推进；按计划实施；TDD 或至少先定义验证；遇到阻塞显式记录 | 代码 diff、提交记录、实现报告、测试记录 | 计划任务完成；无未处理阻塞；产生可审查 diff |
| 开发审查 | 对实现做代码审查和修复闭环 | Superpowers requesting-code-review/receiving-code-review、super-engineer-workflow `/se:review` | 审查以问题和证据为中心；反馈需验证，不盲从 | review 报告、问题列表、修复记录 | 严重问题关闭；中低风险有处理结论 |
| 开发验证 | 用构建、测试、lint、手工检查证明可交付 | Superpowers verification-before-completion、super-engineer-workflow `/se:verify` | 完成必须有证据；验证命令可配置；失败不能口头通过 | verification_report、测试输出、构建日志 | 必要验证通过；失败项有明确豁免或阻塞 |
| QA 验收 | 基于 PRD、OpenSpec、diff 产出测试计划并执行验收 | 平台新增 QA Skill、OpenSpec 验收标准、Superpowers 证据原则 | QA 不只看代码，还要对照需求、规格和实现差异 | 测试计划、测试用例、缺陷、验收结论 | P0/P1 缺陷关闭；验收结论为通过或有条件通过 |
| 最终审查 | 产品、技术、测试对交付结果做发布前确认 | Comet verify、平台 reviews | 把发布决策显式化，避免“默认完成” | 最终审查记录、发布建议 | 产品、开发、测试必要角色完成确认 |
| 归档 | 把通过的变更同步回事实源，沉淀可追溯记录 | OpenSpec archive、Comet archive、super-engineer-workflow `/se:archive-check` 和 `/se:archive` | spec delta 合并回主规格；归档前检查；归档后可追溯 | archived spec、归档报告、最终产物包 | 已验证、已审查、规格已同步、归档状态写入 |

## 5. 平台化实现原则

### 5.1 需求是根对象

所有流程都围绕 `demands` 展开。仓库、工作流、产物、Agent Run、评审和测试结果都挂在需求下面。

这样可以同时覆盖：

- 新业务需求：可能没有初始代码仓库。
- 新项目需求：可以后续绑定一个或多个仓库。
- 优化需求：通常绑定已有仓库和模块。
- Bugfix 需求：可以走轻量 hotfix 流程。
- 重构需求：可以强调设计、风险和验证。

### 5.2 平台数据库是事实源

OpenSpec、Comet、super-engineer-workflow 都有本地文件或 YAML 状态的特点，但平台不能依赖某个开发者机器上的目录作为唯一事实源。

平台应该采用以下映射：

| 平台表 | 对应能力 | 说明 |
| --- | --- | --- |
| `demands` | OpenDevFlow 需求入口 | 记录需求本身、类型、描述、期望上线时间、归属公司和组织架构 |
| `workflows` | Comet `.comet.yaml` 的全局状态 | 记录当前阶段、运行状态 |
| `workflow_stages` | Comet phase、super-engineer state | 记录每个阶段的状态、开始时间、完成时间和阻塞原因 |
| `workflow_artifacts` | OpenSpec 文档、Superpowers 计划、验证报告 | 统一保存 PRD、proposal、design、tasks、plan、review、verification、QA 报告 |
| `agent_runs` | AI 执行日志 | 记录每次 AI 运行的输入、输出、日志、状态、阻塞原因 |
| `reviews` | 评审、审批、验收 | 记录产品确认、代码审查、QA 验收、最终审查 |
| `repositories` | 代码上下文 | 记录 Git 仓库地址、分支、状态和工作区绑定 |

### 5.3 本地文件可以生成，但不能替代平台记录

后续平台可以在在线 workspace 中生成 OpenSpec 目录、计划文件、测试报告和归档文件，但每个文件都应该同步为 `workflow_artifacts` 记录，并保留版本、创建人、阶段和类型。

### 5.4 每次 AI 执行都必须可追溯

任何一次产品分析、规格生成、计划生成、代码实施、测试生成、审查修复，都应该生成 `agent_runs`：

- `stage`：所属阶段。
- `agent_type`：例如 `product_discovery`、`openspec_writer`、`developer_delivery`、`qa_verification`。
- `input_summary`：输入上下文摘要。
- `output_summary`：输出结论摘要。
- `logs`：关键执行日志。
- `status`：pending、running、success、failed、blocked。
- `blocker_reason`：阻塞原因。

这部分是平台区别于普通 Chat UI 的核心能力。

## 6. 阶段守卫设计

Comet 的关键价值是“阶段不能随便跳”。OpenDevFlow 应实现 Guard Engine，在每次阶段推进前检查必需条件。

### 6.1 基础守卫

| 推进目标 | 必须满足 |
| --- | --- |
| 进入规格产出 | 需求澄清产物存在，用户确认继续 |
| 进入开发计划 | proposal、design、tasks 或等价产物存在 |
| 进入代码实现 | implementation_plan 存在，任务有明确验证方式 |
| 进入开发审查 | 有代码 diff 或提交记录，实现阶段无阻塞 |
| 进入开发验证 | 开发审查无严重未关闭问题 |
| 进入 QA 验收 | 构建、测试或约定验证通过 |
| 进入最终审查 | QA 验收通过或有明确豁免 |
| 进入归档 | 最终审查通过，规格同步检查通过 |

### 6.2 守卫结果

守卫检查应该返回结构化结果：

- `passed`：是否通过。
- `blocking_items`：阻塞项。
- `warnings`：不阻塞但需要关注的风险。
- `required_artifacts`：缺失产物。
- `suggested_next_action`：建议下一步操作。

前端在工作流详情页展示守卫结果，避免用户不知道为什么不能推进。

## 7. Handoff Context 设计

Comet 的 handoff context 值得吸收。每个阶段结束时，平台应生成一个确定性的交接包，作为下一阶段 AI 的输入，而不是让 AI 自行从聊天记录里猜。

交接包建议包含：

- 需求基本信息。
- 当前阶段结论。
- 已确认的 PRD、OpenSpec、设计、任务、计划。
- 仓库、分支、关键文件范围。
- 未决问题和风险。
- 上一阶段 Agent Run 摘要。
- 产物版本号和 hash。

平台可以把 handoff context 作为一种 `workflow_artifacts.artifact_type = handoff_context` 保存。

## 8. 流程模式

OpenDevFlow 不应该所有需求都强制走最重流程。可以吸收 Comet 的 preset 思路，提供三种模式。

| 模式 | 适用场景 | 需要阶段 |
| --- | --- | --- |
| Full | 新业务、新项目、大型优化、架构调整 | 全阶段：需求澄清、规格、设计、计划、实现、审查、验证、QA、最终审查、归档 |
| Hotfix | 线上故障、紧急修复 | 需求登记、影响说明、开发计划或修复说明、实现、验证、QA 快速验收、归档 |
| Tweak | 文案、样式、小配置、低风险调整 | 需求登记、轻量说明、实现、验证、归档 |

模式不应该绕过证据，只是降低产物粒度。

## 9. 菜单与页面建议

基于“需求是绝对主体”的产品方向，工作流和交付资产不再作为独立一级菜单。用户从“需求管理”进入某个需求后，再在需求详情内查看该需求的工作流、仓库、产物、Agent Run 和 Review。

| 入口 | 页面目标 | 第一阶段重点 |
| --- | --- | --- |
| 工作台 / 首页 | 展示当前用户相关需求进展、待处理阶段、阻塞项 | 需求统计、待办、阶段分布 |
| 需求工作台 / 需求管理 | 创建、搜索、分页查看需求 | 使用卡片展示需求关键信息和操作入口 |
| 需求详情 / 工作流 | 查看当前需求下多轮工作流的阶段流转、守卫和操作 | 支持新建一轮工作流、推进、阻塞、恢复 |
| 需求详情 / 仓库 | 管理当前需求关联的 Git 仓库和 workspace 绑定 | 后续接在线 workspace |
| 需求详情 / 产物 | 查看 PRD、OpenSpec、计划、报告、QA 结论 | 对接 `workflow_artifacts` |
| 需求详情 / Agent Run | 查看 AI 执行记录和日志 | 对接 `agent_runs` |
| 需求详情 / Review | 查看产品确认、代码审查、QA 验收、最终审查 | 对接 `reviews` |
| 系统管理 | 公司、组织、用户、角色、菜单、审计日志 | 已完成基础权限后继续稳定 |

## 10. MVP 后续实施优先级

当前权限和基础数据模型已经具备后，下一阶段不建议优先做完整在线 IDE。更合理的顺序是先把“需求工作流平台化闭环”跑通。

### P1：工作流详情页

目标：一个需求进入详情页后，能看到完整生命周期。

需要实现：

- 阶段时间线。
- 当前阶段状态。
- 阶段产物列表。
- 当前阶段可执行动作。
- 守卫检查结果。
- 阻塞和恢复操作。
- 阶段推进记录。

### P2：产物管理能力

目标：平台能保存、版本化和展示阶段产物。

需要实现：

- `workflow_artifacts` 后端接口。
- 按需求、阶段、类型查询产物。
- 新增、编辑、版本递增。
- Markdown 预览。
- 常见产物类型：`prd`、`user_story`、`acceptance_criteria`、`proposal`、`design`、`tasks`、`implementation_plan`、`review_report`、`verification_report`、`qa_test_plan`、`qa_report`、`handoff_context`。

### P3：基础 Guard Engine

目标：阶段推进前有明确规则，不再靠人工记忆流程。

需要实现：

- 后端定义阶段推进规则。
- 检查必需产物和 review 结果。
- 返回阻塞项和建议动作。
- 前端展示守卫结果。
- 推进失败时不改变阶段状态。

### P4：Agent Run 记录

目标：先不集成完整在线执行器，也要把 AI 过程记录下来。

需要实现：

- `agent_runs` 后端接口。
- 创建运行记录。
- 更新运行状态。
- 记录输入摘要、输出摘要、日志和阻塞原因。
- 在工作流详情页按阶段展示。

### P5：Review 和 QA 验收

目标：把产品确认、开发审查、测试验收从聊天结论变成平台记录。

需要实现：

- `reviews` 后端接口。
- review 类型：`product_confirm`、`tech_review`、`code_review`、`qa_acceptance`、`final_review`。
- review 结果：`approved`、`rejected`、`changes_requested`、`waived`。
- 工作流守卫引用 review 结果。

## 11. 在线 Workspace 的演进方式

在线 workspace 是后续增强，不是第一阶段必须项。建议分三步：

1. 只绑定仓库信息：平台记录 Git URL、默认分支、负责人。
2. 支持拉取仓库和生成产物：平台可以在服务端 workspace 生成 OpenSpec 文件、计划和报告。
3. 支持在线编码和 Agent 执行：接入 Claude Code、Codex 或其他执行器，并把执行过程写入 `agent_runs`。

这样可以避免在业务流程未稳定前，把复杂度提前压到在线 IDE、容器隔离、权限沙箱和长任务执行上。

## 12. 对四类能力的最终吸收方式

### OpenSpec 应吸收为规格标准

OpenDevFlow 应采用 OpenSpec 的产物思想：

- `proposal`：为什么做、做什么、不做什么。
- `design`：关键设计、影响范围、风险。
- `tasks`：可执行任务清单。
- `spec_delta`：对现有系统规格的增量修改。

这些产物应进入 `workflow_artifacts`，并可在归档时合并成长期规格。

### Superpowers 应吸收为 AI 行为规范

OpenDevFlow 应把 Superpowers 的能力拆成平台 Agent 指令模板：

- 产品阶段：brainstorming。
- 计划阶段：writing-plans。
- 实施阶段：executing-plans、TDD。
- 审查阶段：requesting-code-review、receiving-code-review。
- 完成阶段：verification-before-completion、finishing-a-development-branch。

这些能力不是单独暴露给用户的命令，而是阶段按钮背后的默认行为。

### Comet 应吸收为流程引擎

OpenDevFlow 应吸收 Comet 的核心编排思想：

- 阶段检测。
- 阶段准入。
- 阶段守卫。
- handoff context。
- full/hotfix/tweak 模式。
- verify 后才能 archive。

对应到平台就是 `workflows`、`workflow_stages`、Guard Engine 和 `handoff_context` 产物。

### super-engineer-workflow 应吸收为开发交付执行器

当前 skill 不建议改造成全生命周期 skill，它最适合作为开发阶段的成熟经验来源：

- OpenSpec 到开发 todo 的桥接。
- 开发计划生成。
- 按状态机推进实施。
- review、verify、archive-check。
- 报告和验证命令管理。

平台后续可以把它沉淀成 `developer_delivery_agent`，作为“代码实现、开发审查、开发验证、归档检查”阶段的默认执行器。

## 13. 验收标准

后续按照本方案实施时，至少应满足以下验收标准：

- 创建一个需求后，系统自动生成完整工作流阶段。
- 需求详情页能展示阶段、产物、Agent Run、Review 和守卫结果。
- 用户不能在缺少必要产物或审查结论时随意推进关键阶段。
- 每个阶段的 AI 输出都保存为平台产物或 Agent Run，而不是只存在聊天上下文。
- 开发阶段能复用当前 super-engineer-workflow 的计划、实施、审查、验证和归档思想。
- QA 阶段能基于 PRD、OpenSpec、代码 diff 和验证结果产出测试计划与验收结论。
- 归档阶段能确认规格、实现、验证、QA 和最终审查均已闭环。

## 14. 结论

OpenDevFlow 的最佳方向是：用需求驱动流程，用 OpenSpec 固化规格，用 Superpowers 规范 AI 工作方法，用 Comet 管阶段编排和守卫，用现有 super-engineer-workflow 强化开发交付阶段。

第一阶段不要急于做完整在线 IDE，也不要急于补三个本地 skill。更应该先把平台的工作流详情、产物管理、Agent Run、Review 和 Guard Engine 做出来。只要这些能力跑通，后续无论接 Claude Code、Codex、Superpowers、Comet，还是你自己的开发 skill，都可以作为平台内置执行器接入，而不会让流程依赖某个开发者本地环境。
