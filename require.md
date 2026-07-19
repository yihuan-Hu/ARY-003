# ARY 上线需求规格说明书

> **定位：** 一次性交付、不做后续迭代、对标行业竞品（Devpost / Kaggle / HackMIT 等赛事平台）的完整上线版本。
>
> **基线版本：** 2026-07-15，与 `team-division.md` 对齐。

---

## 1. 安全加固

### 1.1 SQL 注入

- [ ] 消除所有 f-string SQL 拼接（`utils/helpers.py:10`、`database/schema.py:5,10`、`app/database.py:174,177`），改为白名单正则校验 `^[a-zA-Z_][a-zA-Z0-9_]*$`
- [ ] `bandit` 扫描集成到 CI，SQL 注入规则阻断构建

### 1.2 密码安全

- [ ] 密码哈希：每用户随机盐 + PBKDF2-SHA256 60 万次迭代，格式 `pbkdf2_sha256$<salt>$<digest>`
- [ ] 密码比较：`hmac.compare_digest` 常量时间比较
- [ ] 密码复杂度：≥8 位，含大小写字母 + 数字
- [ ] `SECRET_KEY` 从环境变量强制读取，无默认值，缺则 crash
- [ ] `SUBMISSION_SECRET` 从环境变量强制读取，无默认值
- [ ] 移除所有硬编码种子密码（`database/schema.py`），改为启动时随机生成并打印

### 1.3 JWT 安全

- [ ] Refresh Token 机制：access token 1h + refresh token 7d httpOnly cookie
- [ ] Token 黑名单：logout 时加入内存黑名单 + TTL 自动清理
- [ ] JWT algorithm 可配置（生产环境建议 RS256）

### 1.4 登录限流

- [ ] 同一 IP：5 分钟内 5 次失败 → 锁定 15 分钟，返回 429
- [ ] 同一账号：累计 10 次失败 → 锁定 30 分钟
- [ ] 内存 dict + TTL 实现，不需 Redis

### 1.5 Web 安全

- [ ] CORS 白名单：`ARY_CORS_ORIGINS` 必填，默认不 `*`，未配置 crash
- [ ] CSRF 保护：`SameSite=Strict` cookie + `X-CSRF-Token` header 校验
- [ ] 安全响应头：`X-Content-Type-Options` / `X-Frame-Options` / `Referrer-Policy` / `Permissions-Policy` / HSTS
- [ ] 请求体大小限制 1MB + Content-Type 强制 `application/json`
- [ ] CSV 导出注入防护：`=` / `+` / `-` / `@` 开头单元格加单引号前缀
- [ ] CSV 导出不包含明文 content，只导出 public_summary + commitment

### 1.6 输入校验

- [ ] 统一请求校验框架：所有路由使用 `@validate(schema)` 装饰器，引入 marshmallow
- [ ] 所有字符串字段有长度约束：`name` ≤ 200、`description` ≤ 5000、`username` ≤ 50
- [ ] 所有用户自由文本在前端渲染时 HTML escape（防 XSS）

---

## 2. 认证与用户

### 2.1 认证

- [ ] `POST /api/v1/auth/login` — 本地用户名+密码登录
- [ ] `POST /api/v1/auth/refresh` — refresh token 换 access token
- [ ] `POST /api/v1/auth/logout` — 登出，token 加黑名单
- [ ] `GET /api/v1/auth/me` — 当前用户信息（含 roles 数组）
- [ ] `GET /api/v1/auth/github` + `/callback` — GitHub OAuth 登录，首次自动创建 User

### 2.2 用户模型

- [ ] `users` 表：`roles TEXT NOT NULL DEFAULT '["rider"]'`（JSON 数组，支持 `["rider", "organizer", "judge", "admin"]`）
- [ ] 角色值使用 `rider` 而非 `contestant`——与 docs 权限矩阵和领域分析保持一致
- [ ] 一人可同时拥有多个角色——在赛事 A 是选手、赛事 B 是评委、赛事 C 是组织者
- [ ] 旧 `role INTEGER` 字段废弃

### 2.3 个人信息

- [ ] `GET /api/v1/auth/profile` — 查看个人信息
- [ ] `PUT /api/v1/auth/profile` — 完善个人信息

---

## 3. 赛事（Race）

### 3.1 生命周期

- [ ] Race 状态机（与 docs 领域分析完全对齐）：`draft → published → registration → running → submitting → judging → completed → archived`
  - 非法转换返回 422

| 状态 | 含义 | 组织者可执行操作 |
|---|---|---|
| `draft` | 草稿，仅创建者可见 | publish → `published` |
| `published` | 已发布，报名未开放 | open_registration → `registration` |
| `registration` | 报名开放中 | start → `running` |
| `running` | 比赛进行中 | open_submissions → `submitting` |
| `submitting` | 作品提交通道开放 | start_judging → `judging` |
| `judging` | 评审中 | complete → `completed` |
| `completed` | 比赛结束 | archive → `archived` |
| `archived` | 归档沉淀 | 终态 |

- [ ] 创建赛事时初始状态为 `draft`
- [ ] 组织者创建赛事时填写：name（必填）、description、start_time、end_time、rules、schedule、theme、organizer_name
- [ ] `POST /organizer/races/<id>/publish` — draft → published
- [ ] `POST /organizer/races/<id>/open-registration` — published → registration
- [ ] `POST /organizer/races/<id>/start` — registration → running
- [ ] `POST /organizer/races/<id>/open-submissions` — running → submitting
- [ ] `POST /organizer/races/<id>/start-judging` — submitting → judging
- [ ] `POST /organizer/races/<id>/complete` — judging → completed
- [ ] `POST /organizer/races/<id>/archive` — completed → archived
- [ ] 列表接口：分页 `?page=1&per_page=20`

### 3.2 评审配置

赛事创建时设定：

- [ ] `submission_deadline` — 作品提交截止时间，截止后不可再 submit
- [ ] `judging_deadline` — 评分截止时间，截止后不可再提交/修改评分
- [ ] `judging_mode` — `blind`（盲审，评委看不到作者名）或 `open`（公开评审）
- [ ] `judging_tiebreaker` — 同分排名规则：`avg`（默认）/ `median` / `trimmed_mean`

### 3.3 CA 策略

- [ ] `ca_policy` — `rider_choice`（参赛者自由选择 CA）或 `organizer_specified`（赛事方限定 CA 类型和必填配置）
- [ ] `ca_policy_config` — 当 `organizer_specified` 时存储允许的 CA 类型列表和配置模板

### 3.4 公开浏览

- [ ] `GET /public/races` — 公开赛事列表，支持状态筛选 + 关键词搜索 + 分页
- [ ] `GET /public/races/<id>` — 公开赛事详情
- [ ] `GET /public/stats` — 平台全局统计

---

## 4. 报名（Registration）

- [ ] `POST /rider/races/<id>/registrations` — 报名，校验 race.status 必须为 `registration`
- [ ] `GET /rider/registrations` — 查看自己的报名列表，支持 `?status=&page=&per_page=`
- [ ] `GET /rider/registrations/<id>` — 查看自己的报名详情，非 owner 返回 404
- [ ] `POST /rider/registrations/<id>/withdraw` — 退赛
- [ ] `GET /organizer/races/<id>/registrations` — 组织者查看报名列表
- [ ] `POST /organizer/registrations/<id>/approve` — 审批通过，原子生成 RaceProject（双重幂等）
- [ ] `POST /organizer/registrations/<id>/reject` — 拒绝报名
- [ ] 状态机：`submitted → approved / rejected / withdrawn`，approved 可 withdrawn，rejected/withdrawn 不可再转换
- [ ] 重复报名返回 409
- [ ] 跨赛事隔离：组织者只能管理自己赛事的报名

---

## 5. 参赛项目（RaceProject）

- [ ] RaceProject 由 Registration approved 后自动生成，Rider 不可手动创建
- [ ] `GET /rider/race-projects/<id>` — 查看自己的工作区，含 CA 列表 + 作品 + Timeline + Riding Coach
- [ ] `GET /organizer/races/<id>/race-projects` — 组织者查看赛事参赛项目列表
- [ ] 归属链校验：RaceProject → Registration → User，非 owner 返回 404

---

## 6. 作品（Work）

### 6.1 作品信息

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | ✅ | 作品名称 |
| `description` | 否 | 作品简介 |
| `repo_url` | 否 | 代码仓库 |
| `demo_url` | 否 | 在线 Demo |
| `video_url` | 否 | 演示视频链接，前端 iframe 嵌入 |
| `cover_image_url` | 否 | 封面图 |
| `screenshot_urls` | 否 | 截图列表 JSON `["url1","url2"]` |
| `readme_body` | 否 | README 正文 |

### 6.2 草稿/提交流转

- [ ] `work_status`：`draft`（草稿，可反复修改，不公开，不计入评审池）→ `submitted`（已提交，进入评审池）
- [ ] 草稿阶段不生成 hash 链
- [ ] 提交时生成 v1 hash 链：`content_hash = SHA-256(all_fields)`，`content_commitment = HMAC(content_hash, SUBMISSION_SECRET)`
- [ ] 后续修改更新 hash 链：新 hash 包含 `prev_hash`，形成不可篡改链
- [ ] `submission_deadline` 过后 draft 不可再 submit → 422

### 6.3 作品锁定

- [ ] Race 进入 judging 后 Works 不可修改/删除（SQLite trigger）
- [ ] 组织者对作品只读，不可增删改

### 6.4 作品 API

- [ ] `POST /rider/race-projects/<id>/works` — 创建草稿
- [ ] `PUT /rider/works/<id>` — 编辑作品
- [ ] `POST /rider/works/<id>/submit` — 提交作品（draft → submitted，生成 hash 链）
- [ ] `DELETE /rider/works/<id>` — 删除作品（judging 前）
- [ ] `GET /organizer/races/<id>/works` — 组织者查看 submitted 作品列表（只读）
- [ ] `GET /organizer/works/<id>` — 组织者查看作品详情（截图/视频/README/hash 链）
- [ ] `GET /public/races/<id>/works` — 公开作品列表
- [ ] `GET /public/works/<id>/integrity` — 公开验证 hash 链

### 6.5 取消资格

- [ ] `POST /organizer/works/<id>/disqualify` — 标记违规，榜单排除，公开端隐藏
- [ ] `POST /organizer/works/<id>/restore` — 恢复资格（误判纠正）
- [ ] `works` 表：`disqualified INTEGER DEFAULT 0` + `disqualify_reason TEXT`

---

## 7. CA 接入（CAConnection）

### 7.1 双模式

| 模式 | 说明 |
|---|---|
| `rider_choice` | 参赛者自由选择 CA 类型并自行配置 |
| `organizer_specified` | 赛事方预设 CA 类型白名单和必填配置模板，参赛者只能从中选择 |

- [ ] `GET /rider/race-projects/<id>/ca-policy` — 查询赛事当前 CA 策略

### 7.2 CAConnection API

- [ ] `POST /rider/race-projects/<id>/ca-connections` — 登记 CA 接入
  - 若 `organizer_specified`：校验 ca_type 在白名单内，config 包含必填字段
  - API Key 存储 HMAC hash，不存明文
- [ ] `GET /rider/race-projects/<id>/ca-connections` — 查看已登记 CA 列表
- [ ] `PUT /rider/ca-connections/<id>` — 更新配置
- [ ] `DELETE /rider/ca-connections/<id>` — 移除
- [ ] `POST /ca-connections/<id>/handshake` — 握手验证，连接失败给出可执行错误原因
- [ ] CA 接入状态不触发 Registration 状态变更

### 7.3 CA 接入向导

- [ ] `GET /rider/race-projects/<id>/ca-wizard` — 根据 ca_policy 走不同流程
- [ ] 握手失败分类：not_configured / auth_failed / permission_denied / timeout / invalid_format

### 7.4 Session Ingestion

- [ ] `POST /ca-connections/<id>/ingest` — 接收 CA Session 数据，API Key 鉴权
- [ ] 记录：progress / tokens / cost / risk_level / obstacles / violations / current_phase

### 7.5 Live Hall

- [ ] `GET /public/races/<id>/live` — 实时聚合（活跃 CA 数、CA 分布、平均进度、风险分布）
- [ ] `GET /public/races/<id>/live/entries` — 参赛者实时进度列表
- [ ] 旧 `/api/jumbotron/snapshot` 标记 deprecated → 301 至新 Live API

---

## 8. 评审（Judging）

### 8.1 评委邀请（两步制）

- [ ] `POST /organizer/races/<id>/judge-invitations` — 组织者发送评审邀请
- [ ] `GET /judge-invitations` — 受邀者查看邀请列表
- [ ] `POST /judge-invitations/<id>/accept` — 接受邀请 → 自动获得 judge 角色 → 可被分配
- [ ] `POST /judge-invitations/<id>/reject` — 拒绝邀请
- [ ] `GET /organizer/races/<id>/judge-invitations` — 组织者查看发出的邀请状态
- [ ] 被接受邀请后才可分配作品；未接受邀请就尝试分配 → 422

### 8.2 评委分配

- [ ] `GET /organizer/accounts` — 搜索平台已有账号
- [ ] `POST /organizer/races/<id>/judge-assignments` — 分配已接受邀请的评委到作品
- [ ] 自评防护：评委不能评审自己的作品 → 422
- [ ] `GET /organizer/races/<id>/judges` — 评委阵容列表（每人已评/应评数量）
- [ ] `DELETE /organizer/judge-assignments/<id>` — 取消分配（评分尚未提交时）

### 8.3 评分

- [ ] `GET /judge/assignments` — 评委查看评审清单，盲审时不返回 rider_name
- [ ] `POST /judge/works/<id>/judgments` — 提交四维评分（Technical/Innovation/Presentation/Completeness 1-10）+ 评语
- [ ] `PUT /judge/judgments/<id>` — 修改评分（judging_deadline 前 / ended 前）
- [ ] judging_deadline 过后 → 422 / ended 后 → SQLite trigger 拒绝更新
- [ ] 评委不能修改作品的任何字段

### 8.4 评审结果

- [ ] `GET /organizer/races/<id>/judgments` — 汇总：各维度均分、总分、评语列表、已评/应评人数
- [ ] `GET /organizer/judgments/<id>` — 单条评审明细

### 8.5 评审边界

- ✅ 评审可以：查看被分配的作品、提交评分、修改评分（截止前）
- ❌ 评审不可以：修改作品字段、删除作品、修改作品可见性、查看未分配的作品详情

---

## 9. 奖项与榜单

- [ ] `POST /organizer/races/<id>/awards` — 创建奖项（title + position + 关联 Work）
- [ ] `PUT /organizer/awards/<id>` — 编辑奖项
- [ ] `GET /organizer/races/<id>/awards` — 管理奖项列表
- [ ] `GET /public/races/<id>/leaderboard` — **公开榜单，每次请求重新聚合评分实时计算排名**
  - 排除 disqualified 作品
  - 按 `judging_tiebreaker` 规则计算总分并降序排名
  - 奖项创建前展示原始排名，创建后关联 award_title

---

## 10. 辅助功能

### 10.1 Review Readiness 评审准备度

- [ ] 检测规则：无 Work / 信息不完整 / 缺 repo+ demo / 缺 CA 数据 / CA 异常 / 评分偏低
- [ ] `GET /rider/race-projects/<id>/review-readiness` — Rider 查看准备度
- [ ] `GET /organizer/races/<id>/review-readiness` — Organizer 查看全场风险摘要
- [ ] 准备度只提示，不自动取消资格

### 10.2 Evidence Timeline 证据时间线

- [ ] 聚合关键事件：报名批准、CA 握手、Session ingest、作品提交、评审提交、获奖
- [ ] `GET /rider/race-projects/<id>/timeline` — Rider 查看
- [ ] `GET /organizer/races/<id>/race-projects/<rp_id>/timeline` — Organizer 查看
- [ ] 公开端只展示可公开摘要，不暴露原始 CA Session

### 10.3 Riding Coach 新手提示

- [ ] `GET /rider/race-projects/<id>/next-actions` — 根据当前状态返回下一步建议
- [ ] 规则化提示（不做 AI）：报名待审 → 接入 CA → 开始骑行 → 补充作品 → 检查准备度 → 查看结果

### 10.4 数据导出

- [ ] `GET /organizer/races/<id>/export/registrations` — 报名 CSV
- [ ] `GET /organizer/races/<id>/export/judgments` — 评审 CSV
- [ ] `GET /organizer/races/<id>/export/works` — 作品 CSV

### 10.5 RiderProfile 骑手档案

- [ ] `GET /public/riders/<id>` — 公开骑手档案（参赛次数、完成率、获奖数、作品数）
- [ ] `GET /rider/profile` — 查看自己的完整档案

---

## 11. 通知系统

- [ ] `notifications` 表 + append-only
- [ ] 触发节点：报名确认、审批/拒绝结果、评审邀请、评审任务分配、CA 握手异常
- [ ] `GET /notifications` — 通知列表 + 未读筛选
- [ ] `GET /notifications/unread-count` — 未读数
- [ ] `PUT /notifications/<id>/read` — 标记已读
- [ ] `PUT /notifications/read-all` — 全部已读

---

## 12. 作品完整性保护

| 层 | 机制 |
|---|---|
| 权限 | `@require_own_work` + `@require_readonly` 读写分离 |
| Hash 链 | 每次提交/修改生成 SHA-256 hash + HMAC commitment，`prev_hash` 指向上版 |
| 触发器 | judging 开始锁定 Work，ended 锁定评分 |
| 审计 | `integrity_log`（append-only，不可修改不可删除）+ `audit_logs`（同上） |
| 验证 | `verify_resource_integrity(resource_type, id)` 公开可重算 |

---

## 13. 基础设施

- [ ] 结构化日志：每请求 method/path/status/duration/user_id/request_id
- [ ] 审计日志：所有关键操作记录到 `audit_logs`，append-only + 不可删除 + 不可修改
- [ ] 500 错误记录完整 traceback，响应只返回 request_id
- [ ] `X-Request-ID` 请求头注入
- [ ] 通用 BaseDAO（find_by_id / find_all / create / update / delete / count / paginate）
- [ ] 统一数据库 schema 入口
- [ ] 健康检查：`GET /health` + `GET /health/ready`

---

## 14. 前端

- [ ] 15 个页面：首页、赛事详情、登录注册、个人中心、我组织的比赛、赛事管理、我参与的比赛、报名、RaceProject 工作区、CA 向导、作品提交/编辑、作品详情、评审页、榜单页、骑手档案、Live Hall
- [ ] 所有页面覆盖状态：loading / empty / success / error / unauthorized / forbidden / not found
- [ ] 所有用户输入 HTML escape
- [ ] 1080P 桌面响应式，移动端基础可用
- [ ] 顶部导航固定两个 Tab：「我组织的比赛」「我参与的比赛」——不按角色隐藏，内容由数据决定

---

## 15. 部署

- [ ] Dockerfile + docker-compose.yml（Flask + Nginx）
- [ ] 生产 WSGI：gunicorn
- [ ] .env.example 完整环境变量清单
- [ ] CI/CD：lint → test → bandit → pip-audit → build
- [ ] pytest-cov 覆盖率门禁 ≥ 80%
- [ ] `docker-compose up` 一键启动
- [ ] full_demo.py 全流程 e2e（32+ 步）

---

## 16. 附录：代码审计关键发现

| # | 严重度 | 类别 | 位置 | 说明 |
|---|---|---|---|---|
| 1 | 🔴 | SQL 注入 | `utils/helpers.py:10` | f-string 拼接表名 |
| 2 | 🔴 | SQL 注入 | `database/schema.py:5,10` | f-string 拼接表名和列定义 |
| 3 | 🔴 | SQL 注入 | `app/database.py:174,177` | f-string 拼接表名和列定义 |
| 4 | 🔴 | 密码学 | `app/utils/auth.py:12` | 硬编码盐值 |
| 5 | 🔴 | 密钥 | `app/config.py:9` | 默认弱 SECRET_KEY |
| 6 | 🟠 | 访问控制 | `app/config.py:13` | CORS 默认 `*` |
| 7 | 🟠 | 信息泄露 | `routes/export_routes.py:68-69` | CSV 导出明文 content |
| 8 | 🟠 | 架构 | 全局 | 双认证体系 + 双 schema 并存 |
| 9 | 🟠 | 输入校验 | 全局 | 无请求体验证框架 |
| 10 | 🟡 | 日志 | 全局 | 无结构化日志/审计日志 |
| 11 | 🟡 | 速率限制 | 全局 | 无登录限流 |
| 12 | 🟡 | 传输安全 | 全局 | 无 HSTS / 安全头 |
# ARY MVP QA Plan

版本：v0.3
文档类型：QA Plan
上游入口：`ary-mvp.prd.md`
领域基线：`ary-domain-analysis.v0.3.md`
权限矩阵：`ary-permission-matrix.md`

---

# 1. 文档目的

本文定义 ARY MVP 的测试覆盖范围、关键测试类型和 P0 回归要求。PRD 保留产品验收目标；本文负责把验收目标转成可执行测试范围。

测试原则：

* 优先保证首场赛事完整闭环。
* 优先覆盖权限、CA 实时接入、Projection、Report、大屏和公开展示。
* 所有测试必须遵守实时 CA 接入规则：CA 接入状态不作为参赛资格硬门禁；未登记、未握手、归属错误或被禁用的 CA 数据不得污染 Projection、Evidence 或 Report；不接受事后上传 Session Summary 伪造实时 CA 证据。

---

# 2. 测试覆盖

## 2.1 赛事生命周期测试

覆盖流程：

```text
创建赛事
-> 发布赛事
-> 用户报名
-> 审核报名
-> ARY 自动生成 RaceProject
-> 实时 CA 接入
-> 开赛
-> 作品提交
-> 评审分配
-> 评审提交
-> 发布赛果
-> 发布评审总结
-> 归档赛事
```

验收点：

* Race status 可以按预期流转。
* Registration approved 后 RaceProject 自动幂等生成，Registration、RaceProject、Work、JudgeAssignment、JudgingRecord、Award、Report 可以形成闭环。
* RaceProject 聚合 CA 接入 failed / not_configured 不阻断 Work Submission、评审和 Award 流程，但必须形成评审前风险提示。

## 2.2 角色路径测试

覆盖角色：

* Public：浏览首页、Race Page、Live Hall、Works、Results、Review、Rider Profile。
* Rider：GitHub 登录、资料补全、报名、进入自动生成的 RaceProject、查看 CA 接入状态、提交 Work、查看报告。
* Judge：查看分配作品、查看 Evidence 摘要、评分、提交评语。
* Organizer：创建赛事、管理报名、分配评委、发布榜单、生成和发布报告。
* Admin：查看用户、查看资料补全状态、维护 `User.roles`。
* Screen Operator：进入 Screen Console、选择赛事、切换视图、进入全屏、执行 fallback。

验收点：

* 各角色只能看到与自己职责匹配的入口。
* 多 role 用户可以在授权范围内切换对应视图。
* Screen Operator 不是独立 role，通常由 Organizer 或 Admin 承担。

## 2.3 权限测试

覆盖规则：

* Public 不能访问后台、原始 CA Session、未发布 Work、未发布 JudgingRecord、未发布 Report。
* Public 不能访问 `rider_report`，除非后续单独增加公开发布规则。
* Rider 不能查看其他选手的非公开 Session、私有 Evidence、未发布评分和报告。
* Rider / Judge 不能查看未发布 Award / Leaderboard draft。
* Judge 不能查看未分配给自己的作品，不能越权评分。
* Organizer 只能管理自己负责的 Race。
* Admin 可以维护 `User.roles`，但 Admin Console 不承担赛事执行、CA 接入维护或数据运营职责。
* 非 Admin 不能修改 `User.roles`。

验收点：

* 每个资源动作必须符合 `ary-permission-matrix.md`。
* 越权请求必须被拒绝，不能只在 UI 层隐藏入口。

## 2.4 CA 接入测试

覆盖场景：

* 实时 CA 接入成功。
* 单个选手 RaceProject 聚合 CA 接入失败。
* 多个选手中部分接入失败。
* 单个选手绑定多个 CAConnection，部分 CAConnection 接入失败但仍有可用连接。
* 单个选手绑定多个 CAConnection，全部 CAConnection 接入失败。
* 参赛过程中新增多个 CAConnection，并在登记和握手成功后接入骑行数据。
* 未登记、未握手、归属错误或被禁用的 CAConnection 尝试 push 骑行信号或提供 Session Snapshot。
* RaceProject Aggregate Ingestion Status 覆盖 not_configured、connected、active、failed。
* CAConnection Ingestion Status 覆盖 not_configured、connected、active、failed。
* GitHub Repo / 代码材料绑定成功。
* 重复同步同一 Session 或重复引用同一代码材料。
* 接入状态可追踪。
* 空骑行、无 CA 数据、空作品、缺必填材料、疑似违规和接入异常可以生成评审前风险提示。

验收点：

* 接入成功的 Registration 可以进入比赛后续流程。
* RaceProject 聚合接入 failed / not_configured 的 Registration 仍可进入提交、评审和 Award 流程，但 Organizer / Judge 必须看到风险提示。
* 部分或全部 CAConnection failed 时，该 Registration 不应被自动视为退赛。
* 未登记、未握手、归属错误或被禁用的 CAConnection 数据不得进入 Projection、Evidence、Report 或评审摘要。
* not_configured / failed 时可以完成 Work Submission，但必须生成证据缺口或接入异常风险提示；connected / active 时展示正常证据状态。
* 部分选手接入失败不影响 Public Site、Live Hall、Screen Console 和其他选手。
* 重复同步不应生成重复事实或污染 Projection。
* GitHub 代码材料不能替代实时 CA 接入。

## 2.5 Projection 测试

覆盖场景：

* Projection 可生成。
* Projection 可手动重算。
* Projection 失败不污染核心事实数据。
* Projection 失败后可回退到最近一次稳定 Projection。
* Live Hall 和 Screen Console 读取 Projection 或稳定 fallback。

验收点：

* Projection 不是最终事实源。
* Award、Report、Leaderboard 不依赖过程 Projection 作为最终结果事实。

## 2.6 Report 测试

覆盖场景：

* rider_report 生成、查看。
* race_report 生成、编辑。
* review_summary 生成、编辑、发布。
* Report 生成失败后手动重跑。
* 未发布 Report 不出现在 Public Site。

验收点：

* `rider_report` 必须关联 `subjectRegistrationId`。
* `race_report` / `review_summary` 的 `subjectRegistrationId` 必须为空。
* `rider_report` 默认只允许对应 Rider、managed race Organizer 和 Admin 查看。
* 已发布 Review 必须来自已发布 `review_summary` Report。

## 2.7 大屏测试

覆盖场景：

* Screen Console 选择赛事。
* Jumbotron / Billboard 切换。
* Live / 榜单 / 作品 / 公告切换。
* 全屏展示。
* 弱网或断流时 fallback 到最近一次稳定 Projection。
* Projection 不可用时 fallback 到静态榜单或公告。

验收点：

* 大屏展示失败不影响公开网页核心数据。
* 大屏 fallback 不改变核心事实数据。

## 2.8 非功能 / 性能测试

覆盖场景：

* 公开页首屏响应时间。
* Live Hall 数据刷新。
* Screen Console 等页面切换加载首屏。
* 公开端、Live Hall、Results、Works、Rider Profile 的并发访问。

验收点：

* 公开页首屏目标响应时间：1s 内。
* Live Hall 数据刷新目标：3s 内。
* Screen Console 等页面切换加载首屏目标响应时间：1s 内。
* MVP 应支持同时在线 200 用户访问公开端、Live Hall、Results、Works 和 Rider Profile 等公开页面。
* 性能测试不应绕过权限、可见性和 Projection / Report 读取边界。

## 2.9 回归测试

P0 回归必须一键跑通：

```text
GitHub 登录
-> 资料补全
-> Admin 分配 roles
-> Organizer 创建并发布 Race
-> Rider 报名
-> Organizer 审核
-> ARY 自动生成 RaceProject
-> 实时 CA 接入成功
-> Live Hall 展示 Projection
-> Rider 提交 Work
-> Organizer 分配 Judge
-> Judge 提交 JudgingRecord
-> Organizer 发布 Award / Leaderboard
-> Report 生成和发布
-> Public 查看 Results / Review / Work / Rider Profile
-> Screen Console 展示赛事状态
```

---

# 3. 测试完成标准

进入首场赛事彩排前，应满足：

* P0 回归测试通过。
* 权限测试无高危漏洞。
* CA 接入成功、部分失败、重复同步场景通过。
* Projection 生成、重算、失败不污染事实数据场景通过。
* Report 生成、发布、未发布不可见场景通过。
* 大屏基础展示和 fallback 场景通过。
* 非功能 / 性能测试达到 PRD 中的 P0 工程就绪目标。
---
