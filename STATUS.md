# STATUS

本文是 ARY 任务瞬时看板，记录当前任务状态、证据和风险。不记录历史流水。

## 当前结论

* 项目处于 MVP 第一 Checkpoint 冲刺阶段。
* 业务文档已集中到 `docs/` 下。
* 当前正式项目任务定义入口是 `docs/ary.plan.md`。
* `PRD-TEMP-1` 已完成首轮整改，报名、RaceProject 自动生成、CAConnection 动态接入和评审前风险提示的新口径已同步到主要文档和高保真原型。
* `UX-1` 已产出第一轮高保真原型和设计说明，但尚未评审验收，不能直接进入 `M2` 或启动架构设计。
* **角色 1 已交付**：领域模型、数据库 Schema（users/races/registrations/race_projects）、DAO、Registration 事务入口、API 路由、18 项集成测试全部通过。
* **角色 2 已交付**：可复用权限策略模块（own/managed_race 装饰器）、Rider withdraw 路由、13 项新增越权/权限单元测试、旧 21 测试兼容隔离。52 项测试全部通过（31 新 + 21 旧）。
* **角色 3 已交付并完成两轮评测整改**：Registration DAO / Service / Route 与显式状态机完成；approve / reject / submit / withdraw 均具备受控事务边界和事务内重读；重复报名稳定返回 409，Rider 非自有 Registration / RaceProject 与不存在资源统一返回 404；详情查询已去重、DAO 死代码已移除；14 项专项测试、既定隔离回归 66 项全部通过。
* **角色 4 已交付**：RaceProjectService 层、Route 重构（含 CAConnection[]/Work 占位字段）、Demo 脚本（17/17 步骤通过）、兼容性分析文档（旧 /api/entries 与 Jumbotron 不与 RaceProject API 混淆）。52 项回归测试全部通过。

## 任务看板

| 任务 | 状态 | 当前判断 | 证据 / 下一入口 |
| --- | --- | --- | --- |
| `PRD-1` 文档基线与范围确认 | 进行中 | 业务文档已集中到 `docs/`，正在校准项目管理结构。 | `docs/README.md`、`docs/ary.plan.md` |
| `PRD-TEMP-1` 报名 / RaceProject / CA 参赛语义整改 | 待复审 | 已完成首轮文档和原型整改：Registration approved 自动生成 RaceProject、参赛中可新增 CAConnection、CA 接入异常进入评审前风险提示而非硬门禁。需复审是否并入正式 `PRD-1` 基线。 | `docs/registration-ca-rules-alignment.taskbook.md`、`docs/ary-mvp.prd.md`、`docs/ary-domain-analysis.v0.3.md`、`design-prototype/` |
| `UX-1` UX/UI 高保真原型与设计基线 | 进行中 | 高保真原型已按 IA 重构为 1080P 高密度蓝白竞赛风格页面，并接入样例赛事数据驱动主要页面；页面可见文案已清理 PRD / 实现说明口吻，二级页面口号式大标题已降级为对象名和状态摘要；本轮已按明确审查标准修正首页 IA：Public Header 收敛为 Races / Works / Riders / Cooperation，Race 子页面入口回到具体 Race/赛果模块，底部快捷菜单移除，Hero 与 Featured Race 合体，Latest Results / Past Races 去重，开放报名 / 合作入口命名明确，首页独立 Leaderboards / Live Skill Board 已撤销，未登录态只显示 Login；首页整改经验已沉淀为通用高保真页面工作流 Skill，后续页面需先审 IA 合约、补足领域样例数据并复用已通过页面视觉 / 交互惯例。 | `docs/ux-hifi.taskbook.md`、`.agents/skills/hifi-ui-page-workflow/SKILL.md`、`design-prototype/index.html`、`design-prototype/README.md` |
| `DEV-1` 领域模型 + 权限 + 数据模型 | **角色 1/2/3 已交付** | 角色 1 完成领域模型、Schema、DAO 和事务入口；角色 2 完成资源范围权限；角色 3 完成 Registration API、显式状态机、真实 approve + RaceProject 原子事务、重复报名冲突映射和 CA 状态隔离。角色 5 待推进。 | `backend/app/database.py`、`backend/app/dao/`、`backend/app/services/registration_service.py`、`backend/app/routes/`、`backend/app/utils/permissions.py`、`backend/tests/test_checkpoint.py`、`backend/tests/test_registration_state_machine.py` |
| `DEV-4` Registration API（角色 3） | **已交付 / 两轮评测已整改** | Rider 提交 / 查询 / withdraw、Organizer managed race 查询 / approve / reject 均完成；非法转换返回 422，重复报名返回 409，approved 幂等生成唯一 RaceProject，CA failed / not_configured 不触发 withdrawn。两轮评测指出的写竞态、Registration / RaceProject 资源枚举、详情重复查询和 DAO 死代码均已处理。 | `riding-record.md`、`角色三_评测报告.md`、`backend/app/services/registration_service.py`、`backend/app/services/race_project_service.py`、`backend/tests/test_registration_state_machine.py` |
| `DEV-4` RaceProject API + Demo（角色 4） | **角色 4 已交付** | RaceProjectService 封装、Route 重构含 CAConnection[]/Work 占位字段、Demo 脚本 17/17 通过、兼容性分析确认旧 /api/entries 与 RaceProject 不混淆。 | `backend/app/services/race_project_service.py`、`backend/demo.py`、`backend/docs/RACEPROJECT_COMPATIBILITY.md` |
| `DEV-5` CA 接入 / Projection / Live Hall | 细化中 | 已将 CA 作为 Agent Race 工具、比赛信号源和评审参考的口径落盘；CAConnection 可在参赛过程中登记和握手，合法连接数据进入证据链，接入异常进入评审前风险提示；`task_progress` 仅用于 unblock / 说明，不做定期推送，且不设 `session_progress` push。 | `docs/ary-ca-integration-spec.md` |
| `REL-1` 赛事彩排 / 灰度发布 / 正式发布 | 待开始 | 等待开发任务和验收证据完成。 | `docs/ary-release-ops-plan.md` |
| `OPS-1` 赛事值守 / 回滚 / 赛后归档 | 待开始 | 等待发布方案和赛事执行计划明确。 | `docs/ary-release-ops-plan.md` |

## 证据索引

| 结论 | 证据 |
| --- | --- |
| 文档集合存在且已集中到 `docs/` | `docs/*.md` |
| 长期任务定义入口为 `docs/ary.plan.md` | `docs/ary.plan.md` |
| 近期窗口入口为 `PLAN.md` | `PLAN.md` |
| CA 接入契约已形成原始骑行状态消息草案，仍需继续讨论完善 | `docs/ary-ca-integration-spec.md` |
| 报名 / RaceProject / CA 参赛语义整改已形成临时任务书 | `docs/registration-ca-rules-alignment.taskbook.md` |
| 当前仓库包含设计原型 | `design-prototype/` |
| UX/UI 高保真原型已作为 `M2` 前置验收任务进入看板 | `PLAN.md`、`docs/ary.plan.md` |
| 角色 1 Checkpoint 已交付：新领域模型、Schema、DAO、事务入口、API 路由 | `backend/app/database.py`、`backend/app/dao/`、`backend/app/services/registration_service.py`、`backend/app/routes/` |
| 角色 1 18 项集成测试全部通过（报名/审批/幂等/越权/DB约束/e2e） | `backend/tests/test_checkpoint.py`、`backend/tests/conftest.py` |
| 角色 2 权限策略模块已交付：own_registration/own_race_project/managed_race 装饰器 + helper | `backend/app/utils/permissions.py` |
| 角色 2 Rider withdraw 路由已暴露：POST /api/v1/rider/registrations/{id}/withdraw | `backend/app/routes/rider.py` |
| 角色 2 13 项新增越权/权限单元测试全部通过 | `backend/tests/test_checkpoint.py`（31 tests） |
| 旧 21 项测试兼容隔离完成，位于 tests/legacy/，全部通过 | `backend/tests/legacy/` |
| 角色 3 Registration 状态机、事务回滚、重复冲突、CA 隔离、事务竞态和 Registration / RaceProject 资源枚举 14 项测试全部通过 | `backend/tests/test_registration_state_machine.py` |
| 角色 3 评测 P0 已整改：withdraw 事务内重读，Rider 非自有 Registration 统一 404；submit 同步补强 Race 状态竞态 | `角色三_评测报告.md`、`backend/app/services/registration_service.py`、`backend/app/utils/permissions.py` |
| 角色 3 第二次评测剩余项已整改：RaceProject 枚举统一 404、Registration 详情查询去重、DAO 死代码移除 | `backend/app/utils/permissions.py`、`backend/app/services/race_project_service.py`、`backend/app/routes/rider.py`、`backend/app/dao/registration_dao.py` |
| 角色 3 整改后既定隔离回归 66 项通过（31 Checkpoint + 14 Registration + 21 Legacy） | `pytest tests/test_checkpoint.py tests/test_registration_state_machine.py tests/legacy -q` |
| 角色 4 RaceProjectService 已交付：get_for_rider / list_for_organizer + _format 统一响应 | `backend/app/services/race_project_service.py` |
| 角色 4 Route 重构已完成：Rider/Organizer RaceProject 响应含 ca_connections[]/work 占位字段 | `backend/app/routes/rider.py`、`backend/app/routes/organizer.py` |
| 角色 4 Demo 脚本 17/17 步骤通过，覆盖全参赛事实链 | `backend/demo.py` |
| 角色 4 兼容性分析已交付：旧 /api/entries 与 Jumbotron 不与 RaceProject 混淆 | `backend/docs/RACEPROJECT_COMPATIBILITY.md` |
| UX-1 高保真原型已按 IA 和 1080P 视口修订并通过本地截图验证 | `design-prototype/index.html`、`design-prototype/*.png` |
| UX-1 样例赛事数据已生成并接入原型渲染，用于支撑 IA 页面密度和状态差异 | `design-prototype/data/sample-races.json`、`design-prototype/data/sample-races.js`、`design-prototype/script.js` |
| UX-1 页面可见文案已去除 PRD、需求说明和实现术语口吻 | `design-prototype/index.html`、`design-prototype/script.js`、`design-prototype/data/sample-races.json`、`design-prototype/README.md` |
| UX-1 二级页面口号式大标题已降级为对象名和状态摘要 | `design-prototype/index.html`、`design-prototype/script.js`、`design-prototype/styles.css` |
| UX-1 本轮 IA 整改已完成：公开导航边界、Home Gallery 模块、单场 Results、Works 筛选/详情入口、Race Riders 入口、Review 下一场、Rider 能力证据、Screen 输出/控制边界，且静态兜底与动态渲染一致 | `design-prototype/index.html`、`design-prototype/script.js`、`design-prototype/styles.css` |
| UX-1 首页 IA 复审标准已落地：顶层导航不放 Race 子页面，CTA 依附具体 Race / 作品 / 合作场景，首页不设置独立 Leaderboards 模块 | `docs/ary-mvp.ia.md`、`design-prototype/index.html`、`design-prototype/script.js`、`design-prototype/README.md` |
| UX-1 外审意见已落实：Hero 直接承载 Featured Race 信息，Latest Results / Past Races 去重，Next Entry 改为开放报名 / 合作入口，Header 按未登录态只显示 Login | `design-prototype/index.html`、`design-prototype/script.js`、`design-prototype/styles.css`、`design-prototype/README.md` |
| UX-1 首页 Leaderboards 已撤销：Live Skill Board 从首页移除，过程榜保留在 Live Hall，最终榜保留在 Results | `docs/ary-mvp.ia.md`、`docs/ary-mvp.prd.md`、`docs/ux-hifi.taskbook.md`、`design-prototype/index.html`、`design-prototype/script.js`、`design-prototype/styles.css` |
| UX-1 首页视觉复审已处理：右侧首卡从重复 Race Card 改为 Open Registration，首页 page-label 横线已隐藏，避免与 Public Header 分隔线冲突 | `design-prototype/index.html`、`design-prototype/script.js`、`design-prototype/styles.css` |
| UX-1 首页 Live Now 结构已修正：独立 Live Now 框已撤销，Hero / Featured Races 直接支持 live Race 切换 | `docs/ary-mvp.ia.md`、`docs/ux-hifi.taskbook.md`、`design-prototype/index.html`、`design-prototype/script.js`、`design-prototype/README.md` |
| UX-1 首页 title 层级已修正：不在顶部额外强调 Series / Gallery title，当前 Live Race title 居中成为首屏主标题，下划线式 Live Race 切换器位于标题下方，赛题位于切换器下方 | `design-prototype/index.html`、`design-prototype/script.js`、`design-prototype/styles.css`、`design-prototype/README.md` |
| UX-1 品牌区 logo 已修正：使用 ico 原图展示，移除额外圆形套框、描边和外圈光晕 | `design-prototype/index.html`、`design-prototype/styles.css` |
| UX-1 首页布局节奏已调整：Header 更轻，Hero 信息组上移并压缩，赛道视觉下沉，作品 / Rider 卡缩高并落在赛道下缘，右侧信息栈与主 Hero 保持错落间距 | `design-prototype/styles.css` |
| UX-1 首页 Live Race 切换器已简化：取消重复赛事文字，只保留下划线式选择指示，并加入自动轮播切换 | `design-prototype/index.html`、`design-prototype/script.js`、`design-prototype/styles.css`、`design-prototype/README.md` |
| UX-1 首页 Live Race 未激活切换线已增强为浅蓝可见状态，active 状态仍保持深蓝加长 | `design-prototype/styles.css` |
| UX-1 右侧信息卡头部状态标签已降噪：从高饱和蓝色实心 pill 改为浅蓝描边淡底标签，避免抢主 Hero 注意力 | `design-prototype/styles.css` |
| UX-1 首页赛道 Riding Signal 角标已移到赛道容器左上，避免与轨迹节点产生关系误读 | `design-prototype/script.js` |
| UX-1 首页右侧辅助信息已改为 Drawer：默认只露出窄 Rail，点击后从右侧滑出 Open Registration、Latest Results、Past Races 和 Cooperation 四个模块 | `design-prototype/index.html`、`design-prototype/script.js`、`design-prototype/styles.css`、`design-prototype/README.md` |
| UX-1 首页 Live Title 已按 Drawer 默认收起态重新居中，Hero 信息组与赛道主画布中轴对齐 | `design-prototype/styles.css` |
| UX-1 品牌区 logo 已替换为马头罗盘 PNG，生成透明底裁切版并按竖向比例调整 Header 图标容器 | `design-prototype/assets/logo-horse-compass-transparent.png`、`design-prototype/index.html`、`design-prototype/styles.css` |
| UX-1 首页设计与交互短视频已录制，覆盖默认首页、Live Race 切换、右侧 Drawer 打开 / 收起，并内嵌字幕说明 | `design-prototype/recordings/ary-homepage-demo.mp4` |
| UX-1 首页整改经验已沉淀为通用高保真页面工作流 Skill，并在任务书和原型 README 中引用；后续页面需先审 IA、补领域样例数据、复用已通过页面视觉 / 交互惯例，再浏览器复审 | `.agents/skills/hifi-ui-page-workflow/SKILL.md`、`docs/ux-hifi.taskbook.md`、`design-prototype/README.md` |

## 风险与阻塞

| 项目 | 状态 |
| --- | --- |
| ~~架构、数据模型和接口契约尚未完成~~ | ✅ 角色 1 已交付数据模型与 API 路由 |
| ~~尚未建立可运行应用和测试命令~~ | ✅ `pytest tests/test_checkpoint.py tests/legacy/ -v`（52 passed） |
| UX/UI 高保真原型和关键页面状态尚未评审验收 | `M2` 前置风险 |
| 报名 / RaceProject / CA 参赛语义已完成首轮整改，但仍需人工复审确认是否并入正式基线 | `PRD-TEMP-1` 待复审，重点看评审前风险命名、CAConnection 新增窗口和违规作品处理 |
| `backend/app/` 包与旧 `backend/app.py` 模块名冲突，旧测试已隔离到 `tests/legacy/` | 集成负责人需在后续合并时处理路径统一 |
| ~~角色 3（Registration API）、角色 4（RaceProject API 与 Demo）、角色 5（测试契约与回归）尚未推进~~ | ✅ 角色 3/4 已交付；角色 5 仍待推进 |
