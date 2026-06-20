# PLAN

本文是 ARY 近期任务窗口，记录近期要推进的任务和里程碑。长期任务定义见 `docs/ary.plan.md`；任务瞬时状态见 `STATUS.md`。

## 近期窗口

| 窗口 | 目标 |
| --- | --- |
| UX 高保真原型评审 | 完成 UX-1 第一轮高保真原型评审，确认能否作为架构设计输入继续推进。 |
| 报名 / CA 参赛语义整改 | 确认 Registration approved 自动生成 RaceProject、CAConnection 参赛中动态接入、CA 接入状态不再作为参赛资格硬门禁，并完成文档一致性整改。 |

## 近期任务

| 任务 | 目标 | 下一入口 |
| --- | --- | --- |
| `PRD-1` 文档基线与范围确认 | 完成首轮文档一致性检查，确认能否作为架构入口。 | `docs/ary.plan.md` |
| `PRD-TEMP-1` 报名 / RaceProject / CA 参赛语义整改 | 已完成首轮整改并进入待复审：PRD、领域、CA 契约、IA、UX / 高保真原型、权限、QA、OPS 和计划文档已同步新口径。 | `docs/registration-ca-rules-alignment.taskbook.md` |
| `UX-1` UX/UI 高保真原型与设计基线 | 已产出 IA 对齐版 1080P 高密度高保真原型，后续页面按高保真页面工作流继续深化。 | `docs/ux-hifi.taskbook.md`、`.agents/skills/hifi-ui-page-workflow/SKILL.md`、`design-prototype/index.html` |
| `DEV-1` 领域模型 + 权限 + 数据模型 | 输出聚合边界、数据模型草案和接口鉴权规则。 | `docs/ary-domain-analysis.v0.3.md` |
| `DEV-4` Registration API（角色 3） | 已完成报名提交、查询、审核、退赛和状态机；approved 原子幂等生成 RaceProject，重复报名返回 409，CA 接入状态不驱动 withdrawn；两轮评测问题已收口：写事务内重读，Registration / RaceProject own 资源枚举统一 404，详情查询去重并移除 DAO 死代码。 | `riding-record.md`、`角色三_评测报告.md`、`backend/tests/test_registration_state_machine.py` |
| `DEV-5` CA 接入 / Projection / Live Hall | 已按新口径整改 CA 原始骑行状态消息草案：CAConnection 可在参赛过程中登记和握手，合法连接数据进入证据链，接入异常进入评审前风险提示；继续收敛投影规则、字段必填性、push / fetch 边界和幂等规则。 | `docs/ary-ca-integration-spec.md` |

## 近期里程碑

| 里程碑 | 完成口径 |
| --- | --- |
| `M1` 文档基线可作为架构入口 | PRD、领域、IA、权限、QA、计划、OPS、CA 草案无高优先级冲突。 |
| `M2` 架构设计输入就绪 | 领域边界、权限规则、数据模型、CA 接入待定项、UX/UI 高保真原型和关键页面状态有明确输入。 |

## 下一步

1. 评审 `UX-1` IA 对齐版 1080P 高密度高保真原型，重点确认首页 Public Header、Race Gallery 层级、具体内容卡、蓝白竞赛视觉、Console 气质和 Screen Display 表达。
2. 后续高保真页面新增或整改时，使用 `.agents/skills/hifi-ui-page-workflow/SKILL.md`，先确认 IA 合约、数据面和已通过页面惯例，再进入页面实现和浏览器复审。
3. 暂缓 `DEV-1` 架构设计进入，直到 `UX-1` 的高保真原型和关键页面状态被确认可作为输入。
4. 复审 `PRD-TEMP-1` 整改后的 PRD、领域、IA、UX / 高保真原型、权限、QA、OPS 和 CA 契约一致性，确认是否可将临时任务并入正式 `PRD-1` 基线。

## 执行纪律

* 开工前读取对应任务在 `docs/ary.plan.md` 中的定义。
* 近期窗口变化时更新本文；任务状态变化时更新 `STATUS.md`。
