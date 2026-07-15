# UX-1 高保真原型与设计基线任务书

版本：v0.2
状态：讨论稿
任务编号：UX-1
上游入口：`ary-mvp.prd.md`、`ary-mvp.ia.md`、`ary-permission-matrix.md`、`ary-domain-analysis.v0.3.md`
当前目的：明确 UX-1 的高保真原型工作方式，先供讨论，不直接进入正式实施。

---

# 1. 核心原则

UX-1 的最终产物一定是 **高保真原型**。

本任务采取 **视觉为主，体验为先** 的工作流程：

* 视觉为主：优先建立 ARY 的第一印象、视觉气质、赛事现场感、公开传播力和关键页面表达。
* 体验为先：高保真不是静态装饰图，而是能串起核心场景、用户意图和页面重点的可走查原型。
* 业务护栏：业务约束、权限控制、异常状态不作为本任务的主线展开，只作为避免高保真原型明显跑偏的设计护栏。
* 后期完善：全面的权限控制、接口约束、状态机细节、异常恢复和数据一致性应在后续架构、开发和 QA 阶段逐步实现。

换句话说，UX-1 不应被做成业务流程审计、权限矩阵审计或架构前置规范。它首先要回答：

```text
ARY 看起来是什么？
用户第一眼如何理解它？
赛事、骑手、Agent Riding、Live Hall 和大屏如何形成记忆点？
Public、Console、Screen 三类体验面如何在视觉上成立？
```

---

# 2. 任务目标

本任务目标是输出一套可展示、可走查、可指导实现的 ARY MVP 高保真原型与设计基线。

高保真原型应优先表达：

* Gallery-first 的公开赛事展示体验。
* Agent Racing / Agent Riding 的产品气质。
* Live Hall 的实时赛事观看感。
* 作品、赛果、骑手档案的传播和资产沉淀感。
* Race Console 的专业工作台气质。
* Rider / Organizer / Judge 的关键操作场景。
* Screen Display 的现场大屏冲击力和可读性。

高保真原型需要达到：

* 能被产品、设计、研发、潜在合作方共同走查。
* 能支撑后续前端视觉系统和组件方向。
* 能作为架构设计输入之一，但不替代架构设计。
* 能暴露关键体验判断，而不是穷尽全部业务规则。

---

# 3. 工作方式

## 3.1 视觉方向先行

第一步不是完整业务流，也不是全量权限态，而是确定高保真视觉方向。

需要探索：

* ARY 的品牌第一感受。
* 公开端是赛事媒体、作品画廊、能力展示场，而不是后台入口。
* Live Hall 如何表达实时性、速度、风险、成本、进度和骑手状态。
* Console 如何专业、稳定、可操作，但不变成传统后台模板。
* Screen Display 如何适合现场、课堂、直播和远距离观看。

建议形成：

* 视觉关键词。
* 色彩和密度方向。
* 关键页面气质参考。
* 桌面、移动、大屏的表达差异。
* 一组核心高保真样张的优先级。

## 3.2 关键场景高保真样张

先做能代表 ARY 的高保真页面样张，而不是先铺完整页面清单。

第一轮建议优先做 5 个关键样张：

1. Home / Race Gallery
2. Race Page / Live Hall
3. Rider View 或 Organizer View
4. Judge View
5. Screen Display

这些样张要解决的是视觉基调和核心体验，不要求一开始覆盖所有状态。

## 3.3 核心原型串联

在关键样张方向稳定后，串起 1 到 2 条最能展示产品价值的高保真路径。

优先路径：

```text
Public 进入首页
→ 查看当前主推赛事
→ 进入 Race Page
→ 进入 Live Hall
→ 查看作品 / 榜单 / 骑手
```

可选路径：

```text
Rider 进入 Race Page
→ 报名或进入 Rider View
→ 查看 CA 接入和骑行状态
→ 提交作品
```

可选路径：

```text
Screen Operator 进入 Screen Console
→ 选择 Race 和 Display Mode
→ 打开 Screen Display
→ 切换 Live / Leaderboard / Works / Announcement
```

## 3.4 轻量体验补充

高保真主路径稳定后，再补充必要体验说明。

补充内容以“帮助高保真可走查”为准，不做全量业务穷举：

* 页面主任务。
* 主要用户意图。
* 主要 CTA。
* 关键状态。
* 必要的权限提示。
* 关键异常态。
* 需要后续研发细化的点。

## 3.5 设计护栏

业务规则只作为高保真护栏进入本任务。

高保真原型不能明显违反以下规则：

* 首页保持 Gallery-first，不做后台功能索引。
* Race 是公开端和工作台的核心上下文。
* Console Entry 不抢占公开端主视觉。
* 实时 CA 接入是骑行过程证据和评审参考，不是参赛资格硬门禁。
* GitHub Repo 不能被表达为实时 CA 接入替代物。
* CA 未接入、空骑行或接入异常应表达为证据缺口 / 评审风险提示，而不是自动退赛或提交阻断。
* Projection 只表达过程展示，不表达最终事实源。
* 最终赛果不能被设计成由过程榜单直接决定。
* 原始 CA Session 默认不公开。
* Screen Console 是控制面，Screen Display 是展示输出面。

除此之外，更细的权限、异常恢复、状态机和接口约束留给后续阶段完善。

## 3.6 后续页面执行套路

UX-1 后续高保真页面新增或整改时，默认使用共享 Skill：

```text
$hifi-ui-page-workflow
```

该 Skill 的位置：

```text
.agents/skills/hifi-ui-page-workflow/SKILL.md
```

执行时必须把首页本轮整改经验作为通用套路复用：

* 动手前先明确页面审查标准：页面主角、IA 位置、首屏信息、主 CTA、不能出现的内容。
* 如果数据不足，先补足符合 Domain Model 的样例数据，再用数据驱动页面，而不是用宣传文案或 PRD 文案填页面。
* 动手前先查看已完成整改页面的视觉语言和交互惯例，包括 Header、标题层级、下划线切换器、Drawer、状态标签、卡片密度和 CTA 形式。
* 动手后必须审查一致性：新页面不能静默发明另一套视觉语言或交互模式。
* 页面可见文案只表达用户正在看的对象、状态、作品、赛果、Rider、任务和动作，不表达需求说明、实现解释或内部术语。
* 高保真优先解决视觉主次、信息层级和交互可理解性；细权限、全异常和完整业务状态机仍作为后续阶段细化项。

---

# 4. 第一轮交付

第一轮交付应直接服务高保真，而不是先沉淀大量 UX 文档。

建议第一轮产出：

1. **视觉方向定义**
   * ARY 的产品气质和视觉关键词。
   * Public / Console / Screen 三类体验面的视觉差异。
   * 桌面、移动、大屏的密度和构图方向。

2. **关键高保真样张**
   * Home / Race Gallery。
   * Race Page 或 Live Hall。
   * 一个 Console 工作台视图。
   * Judge View 或 Rider View。
   * Screen Display。

3. **一条核心高保真路径**
   * Public 观看赛事路径优先。
   * 需要能从首页走到赛事、Live Hall、作品或赛果。

4. **轻量设计说明**
   * 每个样张服务什么用户意图。
   * 页面重点是什么。
   * 哪些业务规则只是护栏。
   * 哪些细节后续再补。

第一轮不要求：

* 不要求覆盖所有 P0 页面。
* 不要求完整权限矩阵。
* 不要求完整异常态。
* 不要求完整低保真线框。
* 不要求完整接口或数据字段。
* 不要求写应用代码。

---

# 5. 页面优先级

## 5.1 第一优先级：建立产品第一印象

这些页面决定 ARY 是否像一个有传播力的赛事产品，而不是普通后台。

| 页面 | 目标 | 高保真重点 |
| --- | --- | --- |
| Home / Race Gallery | 让公众第一眼理解 ARY 和当前赛事 | Gallery-first、赛事卡、当前主推赛事、Live / Results / Works 入口 |
| Race Page | 建立单场 Race 的内容承载 | 状态、赛题、赛程、阶段 CTA、Live / Works / Results / Review 入口 |
| Live Hall | 展示 Agent Racing 正在发生 | 实时感、骑手动态、进度、成本、风险、过程榜单 |
| Screen Display | 建立现场展示记忆点 | 大字号、强状态、远距离可读、Live / Leaderboard / Works / Announcement 模式 |

## 5.2 第二优先级：建立核心工作台气质

这些页面决定 ARY 是否能被主办方、选手和评委理解为可操作产品。

| 页面 | 目标 | 高保真重点 |
| --- | --- | --- |
| Organizer View | 展示办赛控制感 | Race 状态、报名、CA、提交、评审、榜单、报告概览 |
| Rider View | 展示参赛进度和个人任务 | 报名状态、CA 接入、骑行状态、提交入口、结果反馈 |
| Judge View | 展示评审效率和可信依据 | Assigned Works、Work Detail、Evidence Summary、评分和评语 |
| Screen Console | 展示大屏控制面 | Race 选择、Display Mode、预览、全屏输出、fallback |

## 5.3 第三优先级：资产沉淀与补充页面

这些页面可在主风格稳定后补齐。

| 页面 | 目标 | 高保真重点 |
| --- | --- | --- |
| Works | 公开作品浏览 | 筛选、作品卡、精选 / 获奖标识 |
| Work Page | 作品资产沉淀 | Demo、作者、技术说明、骑行摘要、评委点评 |
| Results | 最终赛果传播 | Award Leaderboards、Winning Works、Riding Skill Highlights |
| Review | 赛事复盘传播 | Review Summary、Featured Cases、Judge Comments |
| Rider Profile | 骑手能力资产 | 作品、获奖、技能标签、公开 Evidence 摘要 |
| Cooperation | 合作转化 | 参赛、办赛、赞助、联系合作 |
| Admin Console | 最小账号角色管理 | 用户列表、资料状态、User.roles |

---

# 6. 高保真路径草案

以下流程用于帮助原型串联，不作为全量业务规则。

## 6.1 Public 观看赛事路径

```text
进入首页 / Race Gallery
→ 在 Hero 中看到当前主推赛事并切换不同 live Race
→ 进入 Race Page
→ 进入 Live Hall
→ 查看骑手动态、作品入口或过程榜单
→ 进入 Work Page / Results / Rider Profile
```

高保真重点：

* 首页需要有强烈的赛事入口和作品画廊感。
* Race Page 不只是说明页，还要能承载不同阶段的赛事气氛。
* Live Hall 要让用户感到“赛事正在发生”。
* 作品、赛果、骑手档案要有可传播资产感。

## 6.2 Rider 参赛路径

```text
进入 Race Page
→ 报名或进入 Rider View
→ 查看报名 / CA 接入 / 骑行状态
→ 提交作品
→ 查看评审结果或报告入口
```

高保真重点：

* Rider View 要像个人参赛 cockpit，而不是表单堆叠。
* CA 接入状态和证据完整度需要清楚，但不需要在第一版穷尽所有失败恢复细节。
* 提交入口要表达阶段感和截止感。

## 6.3 Organizer 办赛路径

```text
进入 Organizer View
→ 查看 Race 总览
→ 管理报名、CA、作品、评审和榜单
→ 发布赛果或报告
```

高保真重点：

* Organizer View 要表达“赛事控制台”的掌控感。
* 第一屏应能快速看出赛事状态、风险和待处理事项。
* 不需要第一版就完整覆盖所有内部维护操作。

## 6.4 Judge 评审路径

```text
进入 Judge View
→ 查看分配作品
→ 打开评审详情
→ 查看作品和骑行摘要
→ 填写评分和评语
→ 提交评审
```

高保真重点：

* 评审页要兼顾作品理解和评分效率。
* Evidence / Riding Summary / Review Flag 是评审参考，不应压过作品本身。
* 第一版可先表达固定评分项，不展开复杂评分配置。

## 6.5 Screen 展示路径

```text
进入 Screen Console
→ 选择 Race 和 Display Mode
→ 打开 Screen Display
→ 切换 Live / Leaderboard / Works / Announcement
```

高保真重点：

* Screen Display 是现场观看产物，不是后台页面放大版。
* 大屏需要远距离可读、状态清楚、视觉记忆点强。
* Fallback 在第一版中可以作为轻量控制或备用状态，不需要完整事故流程。

---

# 7. 设计护栏

以下内容需要在高保真中避免明显违背，但不要求第一版完整实现。

## 7.1 Gallery-first

首页必须以赛事展示、Live、作品、赛果和优秀骑手为主体，不设置独立 Leaderboards 模块。

避免：

* 首页变成后台模块入口。
* 首屏只讲平台介绍，不露出赛事。
* Console 入口抢占主视觉。

## 7.2 Race 上下文

Race 是核心内容对象。

避免：

* 页面像功能模块集合，而不是围绕赛事展开。
* Console 操作看不出当前 Race。
* Work Page、Rider Profile 完全失去 Race 回链。

## 7.3 CA 接入表达

实时 CA 接入是 ARY 差异点，也是骑行过程证据和评审参考。

避免：

* 把 GitHub Repo 表达成 CA 接入替代。
* 把未接入 CA、空骑行或接入异常表达成自动退赛或不可提交。
* 把证据缺口表达成已通过评审风险检查。
* 公开端暴露原始 CA Session。

## 7.4 Projection 与最终结果

Projection 是过程展示，不是最终结果。

避免：

* Live Hall 的过程榜单被视觉表达成最终赛果。
* Screen Display 的实时榜单和 Results 的最终榜单没有区分。
* Projection 异常看起来污染了最终 Award。

## 7.5 Screen 控制面和展示面

Screen Console 和 Screen Display 要分开设计。

避免：

* 现场大屏直接投后台表格。
* 控制按钮出现在观众大屏上。
* 大屏模式切换不清楚。

---

# 8. 不做事项

本任务不做：

* 不先做完整业务流程审计。
* 不先做完整权限矩阵落地。
* 不先做完整状态机和异常恢复方案。
* 不替代领域模型、接口契约、数据库设计或 QA 方案。
* 不写正式应用代码。
* 不展开 P1 / P2 平台化体验。
* 不新增 Organization、Team、RoleAssignment 等 MVP 已排除结构。
* 不把高保真原型降级成低保真流程图或文档清单。

---

# 9. 验收口径

UX-1 完成时，必须以高保真原型验收。

验收重点：

* 高保真原型能一眼看出 ARY 是 Agent Racing Yard，而不是普通 Hackathon 平台或后台系统。
* 公开端具备 Gallery-first 的赛事传播和资产展示能力。
* Live Hall 有实时观看感和 Agent Riding 过程感。
* Screen Display 有现场大屏冲击力和远距离可读性。
* Console 具备专业工作台气质，能看出 Organizer / Rider / Judge 的差异。
* 至少一条 Public 观看路径可以用高保真原型完整走查。
* 至少一个 Console 工作台关键场景可以用高保真原型走查。
* 关键业务规则没有被明显反向表达。
* 设计输出能指导后续前端视觉系统、组件拆分和页面实现。

第一轮评审不以业务完备度作为主要标准。

第一轮评审主要看：

* 视觉方向是否成立。
* 产品第一印象是否准确。
* 关键页面样张是否有说服力。
* 主路径是否能讲清楚 ARY 的价值。
* 哪些页面需要继续深化。

---

# 10. 待讨论问题

1. 第一轮高保真样张是否按 Home、Live Hall、Console、Judge / Rider、Screen Display 五张推进？
2. Public Site 的视觉调性更偏赛事传播、教学实训、能力证明，还是三者混合但以赛事传播为第一眼？
3. 高保真最终形态优先采用 Figma，还是仓库内 `design-prototype/` 静态 HTML 原型？
4. 首场赛事示例数据是否沿用现有 prototype 中的 `Campus Agent Racing 01`，还是改成真实首赛命名与数据？
5. 大屏第一版优先支持 16:9，还是同时考虑 21:9 和竖屏？
6. Console 第一版优先做 Organizer View，还是 Rider View 更能体现 ARY 差异？
7. CA failed、Projection failed、permission denied 等异常态第一版画到什么深度？
8. 是否需要先做一页视觉方向板，再开始页面样张？

---

# 11. 建议讨论顺序

建议先按以下顺序讨论：

1. 确认“最终产物一定是高保真原型”。
2. 确认“视觉为主，体验为先，业务护栏后置细化”的工作原则。
3. 确认第一轮高保真样张页面。
4. 确认 Public / Console / Screen 的视觉调性差异。
5. 确认高保真最终交付形态。
