# ARY 五人分工方案

> 工期两天。每人拿到自己的清单，照着做就行。不单独拆分"创新功能"或"安全专项"——所有任务已直接写进各自清单。

---

## 分工总览

```
                         人员 E：集成负责人
              OpenAPI · 前端 · e2e · CI/CD · Docker · 上线
                 ▲        ▲        ▲        ▲
                 │        │        │        │
   ┌─────────────┴──┐ ┌──┴───────┐ ┌┴────────┐ ┌┴─────────────┐
   │ 人员 A          │ │ 人员 B    │ │ 人员 C   │ │ 人员 D         │
   │ 认证 + 安全基座  │ │ 赛事核心域 │ │ 评审展示 │ │ CA接入 + 旧系统  │
   └────────────────┘ └──────────┘ └─────────┘ └───────────────┘
```

**所有人必须在开工前读完自己的清单和「依赖关系及并行条件」章节。**

---

- 任何人不能长期私有化公共文件：`backend/app/database.py`、`backend/app/__init__.py`、`docs/openapi.yaml`、`.env.example`、CI 文件由 A/E 协调修改。
- 接口一旦被其他人使用，不允许静默改字段；必须同步调用方和测试。
- 一个任务完成 = 有真实接口/页面 + 有数据库持久化 + 有权限校验 + 有错误处理 + 有一条成功测试 + 有一条失败测试 + 本人本地跑过测试并截图发群里。

---

## 人员 A：认证与安全基座

**定位：** A 的装饰器、错误类、中间件被 B/C/D 直接 import。任何 A 的接口签名变更会影响所有人，所以先冻结接口约定（写入 `docs/contracts.md`）。

### 1. 安全修复

- [ ] 消除所有 f-string SQL 拼接，改为白名单正则校验 `^[a-zA-Z_][a-zA-Z0-9_]*$`：
  - `backend/utils/helpers.py:10` — `f'SELECT id FROM {table} ...'`
  - `backend/database/schema.py:5,10` — `f'PRAGMA table_info({table})'` 和 `f'ALTER TABLE {table} ADD COLUMN {ddl}'`
  - `backend/app/database.py:174,177` — 同上模式
- [ ] 密码哈希改为每用户随机盐 + 60 万次 PBKDF2 迭代：废弃 `backend/app/utils/auth.py` 的硬编码 `"ary-salt-v1"`，统一用 `pbkdf2_sha256$<random_salt>$<digest>` 格式
- [ ] 密码比较使用 `hmac.compare_digest` 常量时间比较
- [ ] `SECRET_KEY` 从环境变量强制读取，无默认值，缺则启动 crash
- [ ] 移除 `backend/database/schema.py` 中硬编码的种子密码（`contestant123`/`organizer123`/`admin123`），改为启动时随机生成并打印到控制台
- [ ] 密码复杂度校验：注册/改密时 ≥8 位，含大小写字母 + 数字
- [ ] `SUBMISSION_SECRET` 从环境变量强制读取，无默认值（此 key 用于后续 B/C/D 的 HMAC commitment 生成）

### 2. 登录限流

- [ ] 同一 IP：5 分钟内 5 次登录失败 → 锁定 15 分钟
- [ ] 同一账号：累计 10 次登录失败 → 锁定 30 分钟
- [ ] 锁定期间返回 429 Too Many Requests
- [ ] 使用内存 dict + TTL 实现，不需 Redis

### 3. 认证统一

- [ ] 废弃旧层 `backend/utils/auth.py`（整个文件删除，所有引用迁移）
- [ ] 所有路由统一使用 `backend/app/utils/auth.py` 的装饰器：
  - `@require_auth` — JWT 必填
  - `@require_role("organizer")` — 单角色门禁
  - `@require_any_role("admin", "organizer")` — 多角色任一满足
- [ ] 统一用户模型：`users` 表只使用 `roles TEXT NOT NULL DEFAULT '["rider"]'`（JSON 数组），旧 `role INTEGER` 字段标记 deprecated 并在 seed 脚本里不再写入
- [ ] 角色值统一使用 `rider`（非 `contestant`）——与 docs 权限矩阵和领域分析的 `rider` role 一致
- [ ] `UserDAO.get_roles(user) -> list[str]` — 从 JSON 字段解析，已有则保持
- [ ] `POST /api/v1/auth/login` — 本地登录，已有，保持
- [ ] `POST /api/v1/auth/refresh` — 用 refresh token 换新 access token（refresh token 存在 httpOnly cookie，7 天有效）
- [ ] `POST /api/v1/auth/logout` — access token 加入内存黑名单 + 清除 refresh cookie
- [ ] `GET /api/v1/auth/me` — 已有，保持
- [ ] `GET /api/v1/auth/profile` — 查看个人信息（username、github_login、roles、profile_completed）
- [ ] `PUT /api/v1/auth/profile` — 完善个人信息（姓名、学校/组织、简介）

### 4. 安全中间件

- [ ] CORS 白名单：`ARY_CORS_ORIGINS` 环境变量必填，默认不再 `*`，未配置时启动 crash
- [ ] Flask-CORS 在 `create_app()` 中显式传入 `origins` 配置
- [ ] CSRF 保护：`SameSite=Strict` cookie + 请求头 `X-CSRF-Token` 校验
- [ ] 安全响应头中间件：`X-Content-Type-Options: nosniff` / `X-Frame-Options: DENY` / `Referrer-Policy: strict-origin-when-cross-origin` / `Permissions-Policy: camera=(), microphone=(), geolocation=()` / `X-XSS-Protection: 0`
- [ ] HSTS（生产环境）：`Strict-Transport-Security: max-age=31536000; includeSubDomains`
- [ ] 请求体大小限制 1MB：`app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024`
- [ ] 所有路由强制 `Content-Type: application/json`（GET 和 OPTIONS 除外），拒绝其他类型

### 5. 基础设施

- [ ] 结构化日志：每个 HTTP 请求记录 method / path / status_code / duration_ms / user_id / request_id
- [ ] 审计日志函数 `audit_log(action, actor_id, target_type, target_id, detail)` → 记录：login 成功/失败、registration 创建/approve/reject/withdraw、work 创建/更新/删除、judgment 提交/修改、award 创建/修改、权限变更
- [ ] 审计日志写入 `audit_logs` 表（append-only + 不可变触发器）
- [ ] 全局日志脱敏：自动过滤 token、password、password_hash 字段
- [ ] 统一请求校验框架：引入 `marshmallow`，提供 `@validate(MySchema)` 装饰器供 B/C/D 使用
- [ ] 统一数据库 schema 入口：合并 `backend/database/schema.py` + `backend/app/database.py` → 只保留 `backend/app/database.py`
- [ ] 通用 `BaseDAO` 基类，提供 `find_by_id` / `find_all` / `create` / `update` / `delete` / `count` / `paginate` 模板方法，B/C/D 直接继承
- [ ] 500 错误处理：记录完整 traceback 到日志，响应只返回 `{"error": {"code": "INTERNAL_ERROR", "message": "...", "request_id": "..."}}`
- [ ] 每个请求生成 `request_id`（UUID），注入 `g.request_id` + 响应头 `X-Request-ID`
- [ ] 系统内通知系统（轻量——本项目不做邮件通知，但必须做系统内通知）：

```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    body TEXT DEFAULT '',
    link TEXT DEFAULT '',
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] `notification_service.send(user_id, title, body, link)` — 供 B/C/D 在关键事件时调用
- [ ] 触发节点（B/C/D 在各自 Service 中调用 `send()`）：
  - **B** — 报名提交后通知选手确认；报名被批/拒后通知选手；race 开放报名时通知关注者
  - **C** — 评委被分配后通知；评审截止前 24h 提醒
  - **D** — CA 握手失败后通知选手
- [ ] `GET /api/v1/notifications` — 当前用户的通知列表（`?unread_only=1&page=&per_page=`），需 `@require_auth`
- [ ] `GET /api/v1/notifications/unread-count` — 未读数量（前端轮询或 WebSocket），需 `@require_auth`
- [ ] `PUT /api/v1/notifications/<id>/read` — 标记已读，需 `@require_auth`
- [ ] `PUT /api/v1/notifications/read-all` — 全部已读，需 `@require_auth`

### 6. 作品完整性保护基础设施（第1层 + 第4层 + 第5层）

- [ ] `@require_own_work(work_id_param)` 装饰器：校验 Work → RaceProject → Registration → User 归属链，非 owner 返回 404
- [ ] `@require_readonly(domain)` 装饰器：标记某角色的某域只有读权限（例如 Organizer 对 Work 只能 GET 不能 POST/PUT/DELETE），写操作返回 403
  - `@require_readonly("work")` 用于 Organizer 查看作品列表/详情的路由
  - 评审对作品无任何写权限——评审的路由只注册 `judgments` 端点，作品的写路由由 `@require_own_work` 独占，评审调用作品修改 API 会因不满足所有权而返回 404
- [ ] 跨赛事主办方隔离：所有 Organizer 路由中涉及 Registration/RaceProject/Work/JudgingRecord/Award 的操作，必须在 Service 层校验 `race.created_by_user_id == current_user_id`
- [ ] `integrity_log` 建表（append-only + 不可删除 + 不可修改）：

```sql
CREATE TABLE integrity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id INTEGER NOT NULL,
    actor_user_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    prev_hash TEXT,
    commitment TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TRIGGER trg_integrity_log_immutable
BEFORE UPDATE ON integrity_log
BEGIN
    SELECT RAISE(ABORT, 'integrity_log is append-only');
END;

CREATE TRIGGER trg_integrity_log_no_delete
BEFORE DELETE ON integrity_log
BEGIN
    SELECT RAISE(ABORT, 'integrity_log records cannot be deleted');
END;
```

- [ ] `audit_logs` 建表（同上：append-only + 不可变）：

```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    actor_user_id INTEGER NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER,
    detail TEXT DEFAULT '',
    request_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TRIGGER trg_audit_logs_immutable
BEFORE UPDATE ON audit_logs
BEGIN
    SELECT RAISE(ABORT, 'audit_logs is append-only');
END;

CREATE TRIGGER trg_audit_logs_no_delete
BEFORE DELETE ON audit_logs
BEGIN
    SELECT RAISE(ABORT, 'audit_logs records cannot be deleted');
END;
```

- [ ] 提供公开验证函数 `verify_resource_integrity(resource_type, resource_id) -> dict`：从 `integrity_log` 重算 hash 链，返回 `{"valid": true/false, "chain_length": N, "first_seen": "...", "last_modified": "..."}`

### A 的交付物

```
backend/app/utils/auth.py          # 统一认证（废弃旧层）
backend/app/utils/permissions.py    # 扩展：require_own_work + require_readonly
backend/app/utils/validation.py     # @validate 装饰器
backend/app/utils/logging.py        # 结构化日志 + audit_log + 脱敏
backend/app/utils/errors.py         # 已有，保持
backend/app/utils/response.py       # 已有，保持
backend/app/database.py             # 统一 schema + integrity_log + audit_logs
backend/app/dao/base.py             # BaseDAO
backend/app/dao/integrity_dao.py    # IntegrityLogDAO
backend/app/dao/audit_log_dao.py    # AuditLogDAO
backend/app/services/integrity_service.py  # verify_resource_integrity
backend/app/dao/notification_dao.py    # NotificationDAO
backend/app/services/notification_service.py  # send() + 列表 + 未读数 + 标记已读
backend/app/routes/notification.py   # 通知路由
docs/contracts.md                   # A 的接口契约（装饰器/错误类/g对象/BaseDAO 签名）
```

---

## 人员 B：赛事核心域

**定位：** Race 生命周期 + Registration 扩展 + Work 作品管理 + 公开赛事浏览 + Riding Coach 状态提示。B 的 Work 模型是 C（评审）的上游，需要最先把 Work 表结构确定下来通知 C。

**依赖：** A 的 `@require_auth`、`@require_role`、`@validate`、`BaseDAO`、错误类、`audit_log()`、`integrity_log`。

### 1. Race 完整生命周期

- [ ] `PUT /api/v1/organizer/races/<id>` — 编辑赛事信息（名称、描述、规则、赛程、theme、organizer_name），仅 draft/published/registration 状态可编辑

**Race 状态机（与 docs 领域分析完全对齐）：**

| 状态 | 含义 | 转换 API |
|---|---|---|
| `draft` | 草稿，仅创建者可见 | `POST .../publish` → published |
| `published` | 已发布，报名未开放 | `POST .../open-registration` → registration |
| `registration` | 报名开放中 | `POST .../start` → running |
| `running` | 比赛进行中 | `POST .../open-submissions` → submitting |
| `submitting` | 作品提交通道开放 | `POST .../start-judging` → judging |
| `judging` | 评审中 | `POST .../complete` → completed |
| `completed` | 比赛结束 | `POST .../archive` → archived |
| `archived` | 归档沉淀 | 终态 |

- [ ] Race `ALLOWED_TRANSITIONS`：`draft → published → registration → running → submitting → judging → completed → archived`，非法转换返回 422
- [ ] 创建赛事时初始状态为 `draft`
- [ ] `POST /api/v1/organizer/races/<id>/publish` — 发布赛事，需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/races/<id>/open-registration` — 开放报名，需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/races/<id>/start` — 开始比赛（截止报名），需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/races/<id>/open-submissions` — 开放作品提交窗口，需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/races/<id>/start-judging` — 进入评审阶段，需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/races/<id>/complete` — 结束比赛，需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/races/<id>/archive` — 归档，需 `@require_managed_race`
- [ ] `GET /api/v1/organizer/races/<id>` — 赛事详情（owner 视角）
- [ ] `GET /api/v1/organizer/races` — 已有，增加分页 `?page=1&per_page=20`
- [ ] Race schema 补全字段：`start_time`、`end_time`、`rules`、`schedule`、`theme`、`organizer_name`
  - `submission_deadline TEXT` — 作品提交截止时间（ISO 8601），截止后 draft 不可再 submit
  - `judging_deadline TEXT` — 评分截止时间（ISO 8601），截止后评委不可再提交/修改评分
  - `judging_mode TEXT NOT NULL DEFAULT 'blind' CHECK(judging_mode IN ('blind', 'open'))` — 盲审/公开评审
  - `judging_tiebreaker TEXT NOT NULL DEFAULT 'avg' CHECK(judging_tiebreaker IN ('avg', 'median', 'trimmed_mean'))` — 同分时排名规则
  - 新增 CA 策略字段：`ca_policy TEXT NOT NULL DEFAULT 'rider_choice' CHECK(ca_policy IN ('organizer_specified', 'rider_choice'))`
  - `ca_policy = 'organizer_specified'` → 赛事方在创建赛事时预设允许的 CA 类型和配置模板，参赛者只能从中选择
  - `ca_policy = 'rider_choice'` → 参赛者可以自由选择任何 CA 类型并自己配置
  - `ca_policy_config TEXT DEFAULT '{}'` — 当 `organizer_specified` 时，存储赛事方预设的 CA 类型列表和配置模板（JSON）

### 2. Registration 扩展

- [ ] 已有 `POST /api/v1/rider/races/<id>/registrations` → 增加校验：race.status 必须为 `registration`，否则返回 422
- [ ] 已有 `GET /api/v1/rider/registrations` → 增加分页筛选 `?status=submitted&page=1&per_page=20`
- [ ] 已有 `GET /api/v1/rider/registrations/<id>` → 保持
- [ ] 已有 `POST /api/v1/rider/registrations/<id>/withdraw` → 保持
- [ ] 已有 `GET /api/v1/organizer/races/<id>/registrations` → 增加分页筛选 `?status=submitted&page=1&per_page=20`
- [ ] 已有 `POST /api/v1/organizer/registrations/<id>/approve` → 保持（内含 RaceProject 原子生成 + 双重幂等）
- [ ] 已有 `POST /api/v1/organizer/registrations/<id>/reject` → 保持
- [ ] 以上所有写操作调用 `audit_log()`

### 3. Work 作品管理（新模块，C 的上游依赖）

**先建表，把表结构 + DAO 签名发到群里，C 才能开工。**

- [ ] `works` 建表：

```sql
CREATE TABLE works (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_project_id INTEGER NOT NULL REFERENCES race_projects(id),
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    repo_url TEXT DEFAULT '',
    demo_url TEXT DEFAULT '',
    video_url TEXT DEFAULT '',
    cover_image_url TEXT DEFAULT '',
    screenshot_urls TEXT DEFAULT '[]',
    readme_body TEXT DEFAULT '',
    work_status TEXT NOT NULL DEFAULT 'draft' CHECK(work_status IN ('draft', 'submitted')),
    visibility TEXT NOT NULL DEFAULT 'private',
    content_hash TEXT DEFAULT '',
    content_commitment TEXT DEFAULT '',
    prev_hash TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    submitted_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**字段说明：**

| 字段 | 分类 | 说明 |
|---|---|---|
| `title` | 基础 | ✅ 必填，作品名 |
| `description` | 基础 | 作品简介 |
| `repo_url` | 基础 | 代码仓库 |
| `demo_url` | 基础 | 在线 Demo |
| `video_url` | **富媒体** | 演示视频链接（YouTube / Bilibili），前端嵌入 iframe 播放 |
| `cover_image_url` | **富媒体** | 封面图，作品列表卡片展示 |
| `screenshot_urls` | **富媒体** | 截图列表 JSON `["url1","url2"]`，作品详情页轮播 |
| `readme_body` | 基础 | README 正文 |
| `work_status` | **状态** | `draft`（草稿，可反复改，不公开）/ `submitted`（已提交，进入评审池） |
| `visibility` | 权限 | `private` / `public` |
| `content_hash` / `content_commitment` / `prev_hash` / `version` | 完整性 | hash 承诺链 |

- [ ] `race_projects` 表增字段 `primary_work_id INTEGER REFERENCES works(id)`

- [ ] Work hash 链实现：
  - v1 首次提交 → `content_hash = SHA-256(title + description + repo_url + demo_url + readme_body)`
  - v2+ 修改 → `content_hash = SHA-256(title + ... + prev_hash + readme_body)`
  - `content_commitment = HMAC-SHA-256(content_hash, SUBMISSION_SECRET)`
  - `prev_hash` 指向上一版本的 `content_hash`

- [ ] `POST /api/v1/rider/race-projects/<id>/works` — 创建作品（初始 `work_status='draft'`），需 `@require_own_race_project` + `@validate(WorkCreateSchema)`
  - 创建时不触发 hash 链（草稿阶段不记录完整性）
  - `submitted_at` 为 NULL 直到首次提交
- [ ] `GET /api/v1/rider/race-projects/<id>/works` — 查看自己的作品列表（返回所有 `work_status`，含 draft）
- [ ] `PUT /api/v1/rider/works/<id>` — 编辑作品，需 `@require_own_work`
  - race.status 为 `draft/published/registration/running/submitting` 时可编辑
  - race.status 为 `judging/completed/archived` → 拒绝 UPDATE（触发器 `trg_works_sealed`）
- [ ] `POST /api/v1/rider/works/<id>/submit` — **草稿提交为正式作品**，需 `@require_own_work`
  - race.status 必须为 `submitting`，否则返回 422；进入 `judging` 后禁止提交、重提、编辑和删除
  - 生成 v1 hash 链：`content_hash = SHA-256(all_fields)`
  - `content_commitment = HMAC-SHA-256(content_hash, SUBMISSION_SECRET)`
  - 写入 `integrity_log`（event_type: `work.submit`）
  - 调用 `audit_log("work.submit", ...)`
- [ ] 已提交作品修改（v2+ hash 链）→ race.status 为 `submitting` 时可改，`judging/completed/archived` 时锁定
- [ ] `DELETE /api/v1/rider/works/<id>` — 删除作品，需 `@require_own_work` + race.status 不能是 `judging/completed/archived`
- [ ] `GET /api/v1/organizer/races/<id>/works` — Organizer 查看作品列表 **只读**，需 `@require_managed_race` + `@require_readonly("work")`
  - 只返回 `work_status='submitted'` 的作品（草稿不进入评审池）
- [ ] `GET /api/v1/organizer/works/<id>` — Organizer 查看单个作品详情（含完整描述、截图、视频、hash 链验证），需 `@require_managed_race`
- [ ] `trg_works_sealed` 触发器：race 进入 judging 后，Rider 内容字段的 UPDATE 和作品 DELETE 被拒绝；C 的 `disqualified` / `disqualify_reason` 审核处置字段仍可更新

```sql
CREATE TRIGGER trg_works_sealed
BEFORE UPDATE ON works
WHEN (
    SELECT r.status FROM race_projects rp
    JOIN registrations reg ON rp.registration_id = reg.id
    JOIN races r ON reg.race_id = r.id
    WHERE rp.id = NEW.race_project_id
) IN ('judging', 'completed', 'archived')
AND (
    OLD.title IS NOT NEW.title OR OLD.description IS NOT NEW.description OR
    OLD.repo_url IS NOT NEW.repo_url OR OLD.demo_url IS NOT NEW.demo_url OR
    OLD.video_url IS NOT NEW.video_url OR
    OLD.cover_image_url IS NOT NEW.cover_image_url OR
    OLD.screenshot_urls IS NOT NEW.screenshot_urls OR
    OLD.readme_body IS NOT NEW.readme_body OR
    OLD.work_status IS NOT NEW.work_status OR
    OLD.visibility IS NOT NEW.visibility OR
    OLD.content_hash IS NOT NEW.content_hash OR
    OLD.content_commitment IS NOT NEW.content_commitment OR
    OLD.prev_hash IS NOT NEW.prev_hash OR OLD.version IS NOT NEW.version OR
    OLD.submitted_at IS NOT NEW.submitted_at
)
BEGIN
    SELECT RAISE(ABORT, 'works are sealed once judging begins');
END;
```

另建 `BEFORE DELETE` 的 `trg_works_sealed_delete`，在相同 Race 状态下拒绝删除。审核处置不属于 Rider 内容修改，因此不受 UPDATE 触发器影响。

- [ ] `GET /api/v1/public/works/<id>/integrity` — 公开验证端点，返回 hash 链验证结果 **无需认证**

### 4. 公开赛事浏览

- [ ] `GET /api/v1/public/races` — 公开赛事列表 **无需认证**，支持 `?status=open&page=1&per_page=20&q=keyword`
- [ ] `GET /api/v1/public/races/<id>` — 公开赛事详情 **无需认证**（含赛事信息、参赛人数、公开作品数）
- [ ] `GET /api/v1/public/races/<id>/works` — 赛事公开作品（只返回 `visibility='public'` 的作品）**无需认证**
- [ ] `GET /api/v1/public/stats` — 平台全局统计 **无需认证**：赛事总数、进行中赛事数、参赛总人数、作品总数

### 5. 组织者与参赛者视图分离（关键）

**每个账号登录后，前端始终展示两个 Tab：「我组织的比赛」和「我参与的比赛」。不根据角色隐藏 Tab——所有用户都能看到两个入口。**

同一个用户可以在赛事 A 是组织者、在赛事 B 是参赛者、在赛事 C 是评审——每个比赛内的身份互相独立。

| 视图 | 数据来源 | 展示内容 |
|---|---|---|
| **我组织的比赛** | `GET /api/v1/organizer/races` | 当前用户作为 `created_by_user_id` 的赛事列表。如果没创建过赛事，列表为空，引导"创建第一场赛事"。 |
| **我参与的比赛** | `GET /api/v1/rider/registrations` + `GET /api/v1/rider/races` | 两个子视图：<br>• **作为参赛者**：报名记录和对应赛事。空则引导"浏览公开赛事并报名"<br>• **作为评审**：已接受评审邀请的赛事列表（`judge_invitations WHERE status='accepted'`） |

| 操作 | 权限 |
|---|---|
| **我组织的比赛 Tab 内** | |
| 创建赛事 | `@require_role("organizer")` |
| 编辑赛事 / 开赛 / 截止 / 结束 | `@require_managed_race`（`created_by_user_id == current_user_id`） |
| 查看报名列表 | `@require_managed_race` |
| 审批/拒绝报名 | `@require_managed_race`（Service 层校验 reviewer_scope） |
| 查看参赛者作品 | `@require_managed_race`，**只读**（`@require_readonly("work")`） |
| 查看 CA 数据 | `@require_managed_race` |
| 发送评审邀请 | `@require_managed_race` |
| 分配评委（仅已接受邀请的） | `@require_managed_race` |
| 查看评审汇总 | `@require_managed_race` |
| 取消资格 / 发奖 / 导出 | `@require_managed_race` |
| **我参与的比赛 Tab 内** | |
| — 作为参赛者 | 同上（报名/退赛/工作区/作品） |
| — 作为评审 | |
| 查看评审邀请 | `GET /judge-invitations`，接受/拒绝 |
| 已接受后查看分配 | `GET /judge/assignments` |
| 评分 | `POST /judge/works/<id>/judgments` |
| 接入 CA | `@require_own_race_project` |
| 提交/编辑/删除作品 | `@require_own_work`，judging 后锁定 |
| 查看 Review Readiness / Timeline / Coach | `@require_own_race_project` |

**跨赛事隔离（必须）：** 组织者 O 创建了赛事 A，只能管理赛事 A 的报名/作品/CA/评审/奖项，**完全不能触碰** 赛事 B（O 不是赛事 B 的 `created_by_user_id`）的任何数据。Service 层每次操作前校验 `race.created_by_user_id == current_user_id`。

**B 在本节新增的 API：**

- [ ] `GET /api/v1/rider/races` — Rider 查看自己已报名的赛事列表（通过 Registration 关联），需 `@require_role("rider")`
- [ ] `GET /api/v1/organizer/races` — 已有，查询 `created_by_user_id`，增加分页 `?page=&per_page=`
- [ ] `GET /api/v1/auth/me` 返回的 `roles` 数组由前端用于决定哪些操作按钮可见，但**不用于隐藏 Tab**

### 6. Riding Coach 状态提示

- [ ] `GET /api/v1/rider/race-projects/<id>/next-actions` — 返回 Rider 当前下一步行动建议，需 `@require_own_race_project`
- [ ] 建议来源（规则化，不做 AI）：
  - Registration submitted → "报名已提交，等待主办方审批"
  - Registration approved + 无 CAConnection → "接入你的编码助手，开始骑行"
  - 有 CAConnection 但状态都为 pending → "完成 CA 握手，激活连接"
  - 有活跃 CA + 无 Work → "提交你的作品"
  - 有 Work 但 Review Readiness 有风险 → "检查作品准备度，修复以下问题……"
  - Race ended + 有 Award → "恭喜获奖！查看榜单"
  - Race ended + 无 Award → "赛事已结束，查看你的骑手档案"
- [ ] 每条建议包含：`action_label`（短标题）、`description`（一句话说明）、`target_url`（前端跳转路径）

### 7. 赛事公告（Announcement）

- [ ] `announcements` 建表：

```sql
CREATE TABLE announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id INTEGER NOT NULL REFERENCES races(id),
    title TEXT NOT NULL,
    body TEXT DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'draft' CHECK(visibility IN ('draft', 'private', 'public')),
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] `POST /api/v1/organizer/races/<id>/announcements` — 创建公告，需 `@require_managed_race` + `@validate(AnnouncementSchema)`
  - 调用 `audit_log("announcement.create", ...)`
- [ ] `GET /api/v1/organizer/races/<id>/announcements` — 组织者查看所有公告（含 draft），需 `@require_managed_race`
- [ ] `PUT /api/v1/organizer/announcements/<id>` — 编辑公告，需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/announcements/<id>/publish` — 发布（visibility → public），需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/announcements/<id>/hide` — 隐藏（visibility → private），需 `@require_managed_race`
- [ ] `DELETE /api/v1/organizer/announcements/<id>` — 删除，需 `@require_managed_race`
- [ ] `GET /api/v1/public/races/<id>/announcements` — 公开公告列表（只返回 `visibility='public'`），**无需认证**

### B 的交付物

```
backend/app/dao/work_dao.py              # WorkDAO（继承 BaseDAO）
backend/app/dao/race_dao.py              # RaceDAO（已有，扩展分页 + 状态机方法）
backend/app/services/race_service.py      # RaceService（状态机 + 生命周期）
backend/app/services/work_service.py      # WorkService（CRUD + hash 链 + 触发器）
backend/app/dao/announcement_dao.py     # AnnouncementDAO
backend/app/services/announcement_service.py  # 公告 CRUD + 发布/隐藏
backend/app/services/coach_service.py     # RidingCoachService（下一步建议）
backend/app/routes/organizer.py           # 扩展 Race 生命周期端点
backend/app/routes/rider.py              # 扩展 Work CRUD 端点
backend/app/routes/public.py             # 新增（公开赛事浏览 + 作品验证）
backend/tests/test_race_lifecycle.py      # Race 状态机测试
backend/tests/test_work_integrity.py      # Work hash 链测试
backend/tests/test_coach.py              # Coach 建议测试
```

---

## 人员 C：评审与展示域

**定位：** 评委分配、四维评分、奖项榜单、CSV 导出、Review Readiness、骑手档案。

**依赖：** A 的认证/装饰器 + B 的 Work 表结构和 DAO（B 先发群里的建表 SQL 和 DAO 签名即可开工）。

### 1. 评审系统

**完整链路：组织者如何拿到并评审作品**

```
参赛者                    组织者                       评委
──────                    ──────                       ────

1. 创建草稿(draft)
   ├ 反复编辑
   └ 提交(submit) ───→ 2. 看到作品列表
                         GET /organizer/races/<id>/works
                         （只看 submitted 的）

                      3. 点开作品详情
                         GET /organizer/works/<id>
                         （看截图/视频/README/hash链）

                      4. 分配评委 ────────────────→ 5. 收到通知
                         POST /organizer/races/<id>      GET /judge/assignments
                         /judge-assignments               看到待评清单
                         （组织者自己赛事的评委分配，
                           不需要 Admin 介入）        6. 打分 1-10 × 4 维度
                                                         POST /judge/works/<id>/judgments

                      7. 查看评审结果 ←───────────── 
                         GET /organizer/races/<id>
                         /judgments
                         （汇总：各维度均分、总分、
                          评语列表、已评/应评人数）

                      8. 根据评分发奖
                         POST /organizer/races/<id>/awards

                      9. 发布榜单
                         公开可见
```

**关键：组织者是评审流程的主控者。组织者创建赛事 → 从平台已有账号中选择评委并发送邀请 → 受邀者接受邀请成为评委 → 分配评委到作品 → 评委打分 → 组织者查看汇总 → 发奖 → 榜单实时公开。一人可同时在多个赛事中担任不同角色（赛事A是选手，赛事B是评委，赛事C是组织者）。**

```
组织者                                 受邀者                        公开端
──────                                ────                         ────

1. 创建赛事时设定：
   - judging_mode = blind | open
   - judging_deadline
   - judging_tiebreaker

2. 选手提交作品后，
   在「我组织的比赛」→「作品」
   看到 submitted 作品列表

3. 点开作品详情
   （截图/视频/README/hash链）

4. 搜索平台账号 ──────────────→ 5. 收到邀请通知
   GET /organizer/accounts            "你被邀请成为《赛事名》评审"
   发送评审邀请                       点击「接受」→ 成为评委
   POST /organizer/races/             点击「拒绝」→ 不参与
   <id>/judge-invitations

6. 分配评委到作品 ──────────────→ 7. 收到新评审任务通知
   POST /organizer/races/            GET /judge/assignments
   <id>/judge-assignments            （盲审：不显示 rider_name）

                                  8. 打分 ────────────────→ 9. 排行榜实时更新
                                     POST /judge/works/         GET /public/races/
                                     <id>/judgments             <id>/leaderboard
                                     （截止时间后锁定）          （实时计算排名）

                           10. 查看评审汇总
                               GET /organizer/races/
                               <id>/judgments

                           11. 发现违规 → 取消资格
                               POST /organizer/works/
                               <id>/disqualify

                           12. 发奖
                               POST /organizer/races/
                               <id>/awards

                           13. 结束赛事 → 所有评分锁定
```

- [ ] `judging_records` 建表：

- [ ] `judging_records` 建表：

```sql
CREATE TABLE judging_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_id INTEGER NOT NULL REFERENCES works(id),
    judge_user_id INTEGER NOT NULL REFERENCES users(id),
    technical_score INTEGER CHECK(technical_score BETWEEN 1 AND 10),
    innovation_score INTEGER CHECK(innovation_score BETWEEN 1 AND 10),
    presentation_score INTEGER CHECK(presentation_score BETWEEN 1 AND 10),
    completeness_score INTEGER CHECK(completeness_score BETWEEN 1 AND 10),
    comment TEXT DEFAULT '',
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (work_id, judge_user_id)
);
```

- [ ] `judge_assignments` 建表：

```sql
CREATE TABLE judge_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id INTEGER NOT NULL REFERENCES races(id),
    work_id INTEGER NOT NULL REFERENCES works(id),
    judge_user_id INTEGER NOT NULL REFERENCES users(id),
    assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (work_id, judge_user_id)
);
```

- [ ] `GET /api/v1/organizer/accounts` — 搜索平台已有账号列表（用于评委邀请），需 `@require_role("organizer")`
  - 支持 `?q=username&page=&per_page=` 搜索
  - 返回 `{"accounts": [{"id": 1, "username": "...", "github_login": "..."}]}`

**评委邀请（两步——组织者发邀请，受邀者接受后才成为评委）：**

- [ ] `judge_invitations` 建表：

```sql
CREATE TABLE judge_invitations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id INTEGER NOT NULL REFERENCES races(id),
    invitee_user_id INTEGER NOT NULL REFERENCES users(id),
    inviter_user_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'rejected')),
    message TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    responded_at TEXT,
    UNIQUE (race_id, invitee_user_id)
);
```

- [ ] `POST /api/v1/organizer/races/<id>/judge-invitations` — 组织者发送评审邀请，需 `@require_managed_race`
  - body: `{"invitee_user_id": 5, "message": "请帮忙评审这场比赛的作品"}`
  - 校验 race.created_by_user_id == current_user_id
  - 同一赛事同一受邀者不可重复邀请 → 409
  - **发送通知**：`notification_service.send(invitee_user_id, "评审邀请", f"你被邀请成为《{race.name}》的评审", link=f"/judge-invitations")`
  - 调用 `audit_log("judge.invite", ...)`
- [ ] `GET /api/v1/judge-invitations` — 当前用户收到的评审邀请列表，需 `@require_auth`
  - 返回 pending / accepted / rejected 分类
- [ ] `POST /api/v1/judge-invitations/<id>/accept` — **接受邀请**，需 `@require_auth`
  - 校验 `invitee_user_id == current_user_id`
  - 当前用户没有 `judge` 角色 → 自动追加到 `roles` JSON 数组
  - `status → accepted`，`responded_at = now`
  - **发送通知给组织者**："{username} 已接受评审邀请"
  - 调用 `audit_log("judge.invitation.accept", ...)`
- [ ] `POST /api/v1/judge-invitations/<id>/reject` — **拒绝邀请**，需 `@require_auth`
  - 校验 `invitee_user_id == current_user_id`
  - `status → rejected`
  - 调用 `audit_log("judge.invitation.reject", ...)`
- [ ] `GET /api/v1/organizer/races/<id>/judge-invitations` — 组织者查看发出的邀请+状态，需 `@require_managed_race`

**分配已接受邀请的评委到作品（需先接受邀请）：**

- [ ] `POST /api/v1/organizer/races/<id>/judge-assignments` — 批量分配评委到作品，需 `@require_managed_race`
  - body: `{"assignments": [{"work_id": 1, "judge_user_id": 5}, ...]}`
  - 校验：`judge_user_id` 必须先已接受该赛事的评审邀请（存在 `accepted` 状态的 `judge_invitations` 记录），否则返回 422 "该用户尚未接受评审邀请"
  - **自评防护**：校验 `judge_user_id` 不等于该 Work 的 owner → 422
  - **发送通知**：`notification_service.send(judge_user_id, "新的评审任务", f"你被分配评审作品「{work.title}」", link=f"/judge/assignments")`
  - 调用 `audit_log("judge.assign", ...)`
- [ ] `GET /api/v1/organizer/races/<id>/judgments` — **查看全部评审结果汇总**，需 `@require_managed_race`
  - 返回每个作品的评分汇总：各维度平均分、总分、已评/应评人数、评语列表
  - 响应格式：
  ```json
  {
    "works": [
      {
        "work_id": 1, "title": "作品A", "rider_name": "rider_a",
        "judge_count": 3, "assigned_count": 3,
        "scores": {
          "technical_avg": 8.3, "innovation_avg": 7.0,
          "presentation_avg": 9.0, "completeness_avg": 7.7,
          "total_avg": 8.0
        },
        "comments": [
          {"judge_name": "judge_1", "comment": "...", "total": 8.5},
          {"judge_name": "judge_2", "comment": "...", "total": 7.5}
        ]
      }
    ]
  }
  ```
- [ ] `GET /api/v1/organizer/judgments/<id>` — 查看单条评审明细，需 `@require_managed_race`
- [ ] `GET /api/v1/judge/assignments` — 评委查看自己的评审清单，需 `@require_role("judge")`
  - 返回 Work 摘要 + Review Readiness 风险摘要
  - **盲审**：`judging_mode='blind'` 时不返回 `rider_name` / `rider_user_id`，只返回作品内容
  - **公开评审**：`judging_mode='open'` 时返回完整信息含作者名
- [ ] `POST /api/v1/judge/works/<id>/judgments` — 提交四维评分 + 评语，需 `@require_role("judge")`
  - 校验评委已分配到该 Work
  - **截止时间**：`judging_deadline` 已过 → 拒绝 422 "评分已截止"
  - 写入 `integrity_log`（event_type: `judgment.submit`）
  - 调用 `audit_log("judgment.submit", ...)`

**评审的权限边界（硬约束）：**
- ✅ 评审可以：查看被分配的作品（含截图/视频/README）、提交评分、修改评分（截止前）
- ❌ 评审不可以：修改作品的任何字段（title/description/repo/demo/截图等）、删除作品、修改作品可见性、查看非分配给自己的作品详情
- 实现方式：评审的路由只注册 `@require_role("judge")`，作品的写路由只认 `@require_own_work`。评审没有 Work 的 owner 身份，`@require_own_work` 自动返回 404。
- [ ] `PUT /api/v1/judge/judgments/<id>` — 修改评分，需 `@require_role("judge")`
  - race.status 非 `judging` 或 judging_deadline 已过 → 拒绝 422
  - 写入 `integrity_log`（event_type: `judgment.update`）

```sql
CREATE TRIGGER trg_judgments_sealed
BEFORE UPDATE ON judging_records
WHEN EXISTS (
    SELECT 1 FROM works w
    JOIN race_projects rp ON w.race_project_id = rp.id
    JOIN registrations reg ON rp.registration_id = reg.id
    JOIN races r ON reg.race_id = r.id
    WHERE w.id = NEW.work_id AND r.status IN ('completed', 'archived')
)
BEGIN
    SELECT RAISE(ABORT, 'judgments are sealed after race ends');
END;
```

### 2. 取消资格 + 奖项与榜单

**作品违规处理：**

- [ ] `works` 表增设：`disqualified INTEGER NOT NULL DEFAULT 0` + `disqualify_reason TEXT DEFAULT ''`
- [ ] `POST /api/v1/organizer/works/<id>/disqualify` — 取消资格，需 `@require_managed_race`
  - body: `{"reason": "违反比赛规则：使用了禁用工具"}`
  - 调用 `audit_log("work.disqualify", ...)`
- [ ] `POST /api/v1/organizer/works/<id>/restore` — 恢复资格（误判纠正），需 `@require_managed_race`
- [ ] 被取消资格的作品：
  - 评委仍可见评分记录但标注"已取消资格"
  - 榜单中不出现
  - 公开端不展示

**奖项与榜单：**

- [ ] `awards` 建表：

```sql
CREATE TABLE awards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id INTEGER NOT NULL REFERENCES races(id),
    title TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 1),
    work_id INTEGER REFERENCES works(id),
    registration_id INTEGER REFERENCES registrations(id),
    description TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] `POST /api/v1/organizer/races/<id>/awards` — 创建奖项，需 `@require_managed_race` + `@validate(AwardCreateSchema)`
  - 校验 race.created_by_user_id == current_user_id（跨赛事隔离）
  - 写入 `integrity_log`（event_type: `award.create`）
  - 调用 `audit_log("award.create", ...)`
- [ ] `PUT /api/v1/organizer/awards/<id>` — 编辑奖项，需校验 race ownership
- [ ] `DELETE /api/v1/organizer/awards/<id>` — 删除奖项，需校验 race ownership + race.status 不能是 `archived`
- [ ] `GET /api/v1/organizer/races/<id>/awards` — 管理奖项列表
- [ ] `GET /api/v1/public/races/<id>/leaderboard` — 公开榜单 **无需认证**，**实时计算、每次请求重新聚合评分数据**
  - 排除 `disqualified=1` 的作品
  - 按总分降序排列（总分 = 四维度得分按 `judging_tiebreaker` 规则计算后的值）
  - 平局规则（由 Race.`judging_tiebreaker` 决定）：
    - `avg` — 所有评委各维度均值再取平均（默认）
    - `median` — 所有评委总分取中位数
    - `trimmed_mean` — 去掉最高最低分后取平均
  - 返回：
  ```json
  {
    "race_id": 1,
    "judging_mode": "blind",
    "judging_tiebreaker": "avg",
    "rankings": [
      {
        "rank": 1, "work_id": 3, "work_title": "作品A",
        "rider_name": "rider_a",
        "scores": {"technical": 8.5, "innovation": 7.0, "presentation": 9.0, "completeness": 8.0},
        "total_score": 8.125,
        "judge_count": 3,
        "award_title": "第一名"
      },
      {
        "rank": 2, "work_id": 7, "work_title": "作品B",
        "rider_name": "rider_b",
        "scores": {"technical": 7.0, "innovation": 8.5, "presentation": 7.0, "completeness": 7.5},
        "total_score": 7.5,
        "judge_count": 3,
        "award_title": null
      }
    ],
    "disqualified": [
      {"work_id": 5, "work_title": "违规作品", "reason": "使用了禁用工具"}
    ]
  }
  ```
- [ ] 榜单在奖项创建前展示原始排名（award_title 为 null）；奖项创建后 association 到排名行
- [ ] 奖项创建不改变排名计算，只关联展示

### 3. CSV 数据导出

- [ ] `GET /api/v1/organizer/races/<id>/export/registrations` — 报名数据 CSV，需 `@require_managed_race`
- [ ] `GET /api/v1/organizer/races/<id>/export/judgments` — 评审结果 CSV，需 `@require_managed_race`
- [ ] `GET /api/v1/organizer/races/<id>/export/works` — 作品列表 CSV，需 `@require_managed_race`
- [ ] CSV 注入防护：单元格值以 `=` / `+` / `-` / `@` 开头时，自动加单引号前缀
- [ ] CSV 不导出明文 content，只导出 `content_public_summary` + `content_commitment`
- [ ] 调用 `audit_log("export.xxx", ...)` 记录导出操作

### 4. Review Readiness 评审准备度

- [ ] `GET /api/v1/rider/race-projects/<id>/review-readiness` — Rider 查看准备度，需 `@require_own_race_project`
- [ ] `GET /api/v1/organizer/races/<id>/review-readiness` — Organizer 查看全场准备度摘要，需 `@require_managed_race`
- [ ] 检测规则，不依赖 AI：
  - 无 Work → 标记 "作品未提交"
  - Work title/description/readme_body 为空 → 标记 "作品信息不完整"
  - repo_url 和 demo_url 都为空 → 标记 "缺少代码仓库或演示链接"
  - CA 数据全部缺失（无 ca_session）→ 标记 "缺少骑行过程数据"
  - CA 有 failed 连接 → 标记 "CA 接入异常"
  - 当前评分不足（已评作品均分 < 5）→ 标记 "评审得分偏低"
- [ ] Judge assignments 接口的 Work 摘要中附带该 Work 的准备度风险列表
- [ ] 准备度只提示风险，不自动取消资格、不自动 withdraw、不自动隐藏作品

### 5. RiderProfile 骑手档案

- [ ] `GET /api/v1/public/riders/<id>` — 公开骑手档案 **无需认证**，聚合数据：
  ```json
  {
    "user": { "id": 1, "username": "...", "github_login": "..." },
    "stats": {
      "total_races": 3,
      "completed_races": 2,
      "awards_count": 1,
      "works_count": 5
    },
    "recent_works": [...],
    "awards": [...]
  }
  ```
- [ ] `GET /api/v1/rider/profile` — Rider 查看自己的完整档案（含未公开的 work），需 `@require_auth`

### 6. 报告生成（Report）

- [ ] `reports` 建表：

```sql
CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id INTEGER NOT NULL REFERENCES races(id),
    subject_registration_id INTEGER REFERENCES registrations(id),
    report_type TEXT NOT NULL CHECK(report_type IN ('rider_report', 'race_report', 'review_summary')),
    title TEXT NOT NULL,
    body TEXT DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'draft' CHECK(visibility IN ('draft', 'private', 'public')),
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    published_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**报告类型说明：**

| report_type | subject_registration_id | 说明 |
|---|---|---|
| `rider_report` | ✅ 必填 | 单个选手的参赛报告，默认仅 Rider + Organizer + Admin 可见 |
| `race_report` | ❌ 必须为空 | 赛事整体总结报告 |
| `review_summary` | ❌ 必须为空 | 评审综述，含统计分析 |

- [ ] `POST /api/v1/organizer/races/<id>/reports/generate` — 生成报告，需 `@require_managed_race`
  - body: `{"report_type": "race_report", "title": "...", "auto_fill": true}`
  - `auto_fill=true` 时系统自动填充赛事数据（报名数、作品数、评审完成率、奖项列表、各维度均分、参赛者排名等）
  - 报告以 `draft` 状态生成，组织者可在发布前编辑
  - rider_report 的 `subject_registration_id` 必填
- [ ] `PUT /api/v1/organizer/reports/<id>` — 编辑报告（标题、正文），需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/reports/<id>/publish` — 发布报告（visibility → public），需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/reports/<id>/hide` — 隐藏报告，需 `@require_managed_race`
- [ ] `GET /api/v1/organizer/races/<id>/reports` — 组织者查看该赛事所有报告（含 draft），需 `@require_managed_race`
- [ ] `GET /api/v1/public/races/<id>/reports` — 公开报告列表（只返回 `visibility='public'` 的 race_report / review_summary），**无需认证**
- [ ] `GET /api/v1/rider/registrations/<id>/report` — Rider 查看自己的 rider_report，需 `@require_own_registration`
  - 如果报告尚未发布 → 返回 404
- [ ] `GET /api/v1/organizer/reports/<id>` — 查看单个报告详情，需 `@require_managed_race`

### C 的交付物

```
backend/app/dao/judging_dao.py           # JudgingRecordDAO + JudgeAssignmentDAO
backend/app/dao/award_dao.py             # AwardDAO
backend/app/services/judging_service.py   # JudgingService（分配+评分+触发器）
backend/app/services/award_service.py     # AwardService
backend/app/services/readiness_service.py # ReviewReadinessService
backend/app/services/report_service.py         # ReportService（生成+编辑+发布）
backend/app/services/rider_profile_service.py  # RiderProfileService
backend/app/routes/admin.py              # 新增（Admin 蓝图）
backend/app/routes/judge.py              # 新增（Judge 蓝图）
backend/app/routes/public.py             # 扩展（public leaderboard + rider profile）
backend/app/routes/organizer.py           # 扩展（awards + export + readiness）
backend/tests/test_judging.py            # 评审系统测试
backend/tests/test_awards.py             # 奖项榜单测试
backend/tests/test_readiness.py          # 准备度测试
```

---

## 人员 D：CA 接入域 + 旧系统收尾 + Evidence Timeline

**定位：** CAConnection 全链路、Session Ingestion、Live Hall、CA 接入向导、GitHub OAuth、Evidence Timeline、旧系统收尾。

**依赖：** A（认证）+ B（RaceProjectDAO，已有角色4代码，可直接开工）。

### 1. CAConnection 接入（双模式）

**CA 接入支持两种模式，由赛事方在创建 Race 时选择 `ca_policy`：**

| 模式 | `ca_policy` | CA 配置来源 | 参赛者自由度 |
|---|---|---|---|
| 赛事方指定 | `organizer_specified` | Race 创建者预设 CA 类型列表 + 配置模板（`ca_policy_config`） | 只能从预设列表中选择，填充赛事方要求的字段 |
| 参赛者自由 | `rider_choice` | 参赛者自行选择和配置 | 完全自由 |

- [ ] `ca_connections` 建表（在已有基础上补充 `ca_policy_source` 字段）：

```sql
CREATE TABLE ca_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_project_id INTEGER NOT NULL REFERENCES race_projects(id),
    ca_type TEXT NOT NULL CHECK(ca_type IN ('codex', 'claude', 'other')),
    provider_name TEXT NOT NULL,
    connection_status TEXT NOT NULL DEFAULT 'pending' CHECK(connection_status IN ('pending', 'connected', 'active', 'failed')),
    ca_policy_source TEXT NOT NULL DEFAULT 'rider_choice' CHECK(ca_policy_source IN ('organizer_specified', 'rider_choice')),
    api_key_hash TEXT DEFAULT '',
    handshake_at TEXT,
    last_signal_at TEXT,
    error_message TEXT DEFAULT '',
    config_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(race_project_id, provider_name)
);
```

- [ ] `GET /api/v1/rider/race-projects/<id>/ca-policy` — 查询该赛事当前的 CA 策略：
  ```json
  // organizer_specified 模式返回：
  { "ca_policy": "organizer_specified", "allowed_ca_types": ["codex", "claude"], "config_template": { "repo_url": true, "api_key": true } }
  
  // rider_choice 模式返回：
  { "ca_policy": "rider_choice", "allowed_ca_types": ["codex", "claude", "other"], "config_template": null }
  ```
  Rider 端和前端 CA 向导根据此接口决定展示什么样的配置流程。

- [ ] `POST /api/v1/rider/race-projects/<id>/ca-connections` — 登记 CA 接入，需 `@require_own_race_project`
  - 如果 `ca_policy == 'organizer_specified'`：校验 `ca_type` 在 `allowed_ca_types` 白名单内，校验 `config_json` 包含模板要求的必填字段
  - 如果 `ca_policy == 'rider_choice'`：不做限制，参赛者自由填写
  - `ca_policy_source` 记录当前使用的模式
  - API Key 使用 HMAC-SHA-256 存储 hash，不存明文
  - 调用 `audit_log("ca_connection.create", ...)`
- [ ] `GET /api/v1/rider/race-projects/<id>/ca-connections` — 查看已登记 CA 列表（不返回 api_key_hash）
- [ ] `PUT /api/v1/rider/ca-connections/<id>` — 更新 CA 配置
- [ ] `DELETE /api/v1/rider/ca-connections/<id>` — 移除 CA 连接
- [ ] `POST /api/v1/ca-connections/<id>/handshake` — CA 握手验证
  - 握手成功 → `connection_status = 'connected'`
  - 握手失败 → `connection_status = 'failed'` + 写入 `error_message`
  - 后续首次 Ingestion 成功后 → `connection_status = 'active'`（CAConnectionService 自动转换）
  - 调用 `audit_log("ca_connection.handshake", ...)`
- [ ] 更新 `RaceProjectService._format()` — 把 `ca_connections: []` 占位改为真实查询数据
- [ ] CA 接入异常不触发 Registration 状态变更（维持现有隔离原则）

### 2. CA 接入向导（根据 ca_policy 走不同流程）

- [ ] `GET /api/v1/rider/race-projects/<id>/ca-wizard` — 返回向导步骤和当前状态
- [ ] 向导流程根据 `ca_policy` 分叉：

**模式 A：赛事方指定（`organizer_specified`）**
  1. 展示赛事方预设的 CA 类型列表（只读，不能选其他）
  2. 选择 CA 类型 → 展示赛事方要求的配置字段模板（如 repo_url、api_key）
  3. 填写必填字段 → 提交
  4. 握手测试 → 显示 connected / failed + 错误原因
  5. 完成 → 同一 CA 类型下只能有一个连接（UNIQUE 约束）

**模式 B：参赛者自由（`rider_choice`）**
  1. 选择 CA 类型（codex / claude / other）
  2. 填写 provider 名称 + repo_url + API Key（全部自由填写）
  3. 握手测试 → 显示 connected / failed + 错误原因
  4. 完成 → 可以添加多个同类型的 CA 连接

- [ ] `POST /api/v1/rider/race-projects/<id>/ca-wizard/step/<step>` — 提交向导每步数据，校验后写入 CAConnection
- [ ] 握手失败的错误原因分类：
  - `not_configured` — 缺少 API Key
  - `auth_failed` — API Key 无效
  - `permission_denied` — 权限不足
  - `timeout` — 连接超时
  - `invalid_format` — 返回数据格式不匹配

### 3. CA Session Ingestion

- [ ] `ca_sessions` 建表：

```sql
CREATE TABLE ca_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ca_connection_id INTEGER NOT NULL REFERENCES ca_connections(id),
    overall_progress REAL DEFAULT 0.0 CHECK(overall_progress >= 0 AND overall_progress <= 1),
    round_progress REAL DEFAULT 0.0 CHECK(round_progress >= 0 AND round_progress <= 1),
    cost_tokens INTEGER DEFAULT 0 CHECK(cost_tokens >= 0),
    cost_usd REAL DEFAULT 0.0 CHECK(cost_usd >= 0),
    risk_level TEXT DEFAULT 'none' CHECK(risk_level IN ('none', 'low', 'medium', 'high')),
    obstacle_count INTEGER DEFAULT 0,
    violation_count INTEGER DEFAULT 0,
    current_phase TEXT DEFAULT 'DEV',
    started_at TEXT,
    ended_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] `POST /api/v1/ca-connections/<id>/ingest` — 接收 CA Session 数据
  - 鉴权方式：请求头 `X-API-Key: <api_key>`，与 `api_key_hash` 比对（HMAC 常量时间比较）
  - 调用 `audit_log("ca_session.ingest", ...)`
  - 写入 `integrity_log`（event_type: `ca_session.ingest`）
- [ ] `GET /api/v1/rider/ca-connections/<id>/sessions` — 查看 Session 历史列表
- [ ] `GET /api/v1/organizer/races/<id>/ca-sessions` — Organizer 查看全场 CA Session 摘要

### 4. Live Hall 实时大屏

- [ ] `GET /api/v1/public/races/<id>/live` — 赛事实时聚合 **无需认证**：
  ```json
  {
    "race": { "id": 1, "name": "...", "status": "open" },
    "active_riders": 12,
    "ca_distribution": { "claude": 8, "codex": 3, "other": 1 },
    "avg_progress": 0.65,
    "risk_summary": { "none": 5, "low": 4, "medium": 2, "high": 1 }
  }
  ```
- [ ] `GET /api/v1/public/races/<id>/live/entries` — 参赛者实时进度列表 **无需认证**
  - 每个 Entry 返回：rider_name、ca_type、round_progress、cost_tokens、risk_level、current_phase
- [ ] 旧层 `/api/jumbotron/snapshot` 标记 deprecated，重定向到新 Live API（返回 301 + 新 URL）
- [ ] 旧 Jumbotron 路由保持不变但加入 deprecation 响应头，确保前端有时间迁移

### 5. Evidence Timeline 证据时间线

- [ ] `GET /api/v1/rider/race-projects/<id>/timeline` — Rider 查看自分の时间线，需 `@require_own_race_project`
- [ ] `GET /api/v1/organizer/races/<id>/race-projects/<rp_id>/timeline` — Organizer 查看选手时间线，需 `@require_managed_race`
- [ ] 时间线聚合来源（从真实数据读，不做前端假数据）：
  - `registration.submitted` — 报名时间
  - `registration.approved` — 审批通过时间
  - `ca_connection.handshake` — CA 握手时间
  - `ca_session.ingest` — 每次 CA 数据接入（摘要：tokens、进度、阶段）
  - `work.created` / `work.updated` — 作品提交和修改
  - `judgment.submitted` — 评审提交
  - `award.created` — 获奖
- [ ] 公开端 Timeline（`GET /api/v1/public/race-projects/<id>/timeline`）只展示可公开摘要事件，不暴露详细 Session 数据

### 6. GitHub OAuth

- [ ] `GET /api/v1/auth/github` — 发起 GitHub OAuth 授权（redirect 到 GitHub）
- [ ] `GET /api/v1/auth/github/callback` — GitHub 回调处理
  - 首次登录：自动创建 User（`github_user_id` + `github_login` 字段已在 schema 中预留），`roles = ["rider"]`，`profile_completed = 0`
  - 已注册：更新 `github_login`，签发 JWT
  - 调用 `audit_log("auth.login.github", ...)`
- [ ] 如 GitHub OAuth 配置因外部原因阻塞，保留本地登录作为应急入口，但 OAuth 代码路径和文档必须完成

### 7. 旧系统收尾

- [ ] 旧层 `backend/utils/auth.py` 确认已删除（A 负责，D 负责验证旧路由全部迁移）
- [ ] 旧层 `/api/export/*` 确认功能已由 C-3 接管，旧路由标记 deprecated
- [ ] 旧层 `/api/jumbotron/snapshot` 标记 deprecated → 新 `/api/v1/public/races/<id>/live`
- [ ] 旧层 Submission 安全逻辑确认已平移到新 Work 模块（不可变触发器 + HMAC commitment）
- [ ] 旧层 `backend/daos/`、`backend/services/`、`backend/routes/` 中的文件：新增一个 `DEPRECATED.md` 文件到各旧目录，说明迁移状态
- [ ] `backend/app/__init__.py` 注册所有新蓝图：`auth_bp`、`rider_bp`、`organizer_bp`、`public_bp`、`judge_bp`、`admin_bp`、`ca_bp`

### D 的交付物

```
backend/app/dao/ca_connection_dao.py      # CAConnectionDAO
backend/app/dao/ca_session_dao.py         # CASessionDAO
backend/app/services/ca_service.py         # CAService（登记+握手+向导）
backend/app/services/ca_ingestion_service.py  # CAIngestionService（Session 数据）
backend/app/services/live_hall_service.py  # LiveHallService（实时聚合）
backend/app/services/timeline_service.py   # EvidenceTimelineService
backend/app/services/oauth_service.py      # GitHubOAuthService
backend/app/routes/ca.py                  # 新增（CA 蓝图）
backend/app/routes/auth.py                # 扩展（GitHub OAuth 回调）
backend/app/routes/public.py              # 扩展（Live Hall + 公开 Timeline）
tests/test_ca_connection.py               # CAConnection + 握手测试
tests/test_ca_ingestion.py                # Ingestion 测试
tests/test_live_hall.py                   # Live Hall 测试
tests/test_timeline.py                    # Evidence Timeline 测试
tests/test_github_oauth.py                # OAuth 测试
```

---

## 人员 E：集成负责人

**定位：** 出契约 → 写前端 → 搭 CI/CD → Docker → e2e 全流程 → 上线。

**依赖：** 所有人的 API 实现。但前端用 Mock Server 独立开发，不阻塞。

### 1. OpenAPI 接口契约

- [ ] 编写 `docs/openapi.yaml`（OpenAPI 3.0），覆盖全部端点，标注每个接口的鉴权要求
- [ ] 与 A/B/C/D 逐人确认接口的 request body / response body / error code
- [ ] 基于 OpenAPI 启动本地 Mock Server（`npx @stoplight/prism-cli mock docs/openapi.yaml`），前端对 Mock 开发

### 2. 前端（共 14 页）

- [ ] 基于 `design-prototype/` 原型实现。技术选型由 E 自己决定
- [ ] 页面清单与对应后端 API：

**关键设计：所有用户登录后顶部导航固定显示「我组织的比赛」和「我参与的比赛」两个 Tab——不按角色隐藏。每个 Tab 内的数据由各自接口返回，没数据时展示引导文案。具体可操作按钮由 `roles` 决定。**

| # | 页面 | 对应 API | 谁能访问 |
|---|---|---|---|
| 1 | 首页（公开赛事列表 + 平台统计） | `GET /public/races` + `GET /public/stats` | 所有人 |
| 2 | 赛事详情（公开） | `GET /public/races/<id>` | 所有人 |
| 3 | 登录/注册 | GitHub OAuth + `POST /auth/login` | 未登录 |
| 4 | 个人中心 | `GET/PUT /auth/profile` | 已登录 |
| 4a | ├ 通知中心 | `GET /notifications` + 铃铛 badge 显示未读数 | 已登录 |
| 4b | ├ 评审邀请 | `GET /judge-invitations` + 接受/拒绝 | 已登录 |
| 5 | **「我组织的比赛」Tab** | `GET /organizer/races` — 显示 `created_by_user_id` 的赛事列表。空列表时展示"创建第一场赛事"引导 | **所有人可见**，内容由是否有已创建赛事决定 |
| 5a | ├ 赛事管理（单赛事） | `PUT /organizer/races/<id>` + publish/open-registration/start/open-submissions/start-judging/complete/archive | 该赛事创建者 |
| 5b | ├ 报名管理 | `GET /organizer/races/<id>/registrations` + approve/reject | 该赛事创建者 |
| 5c | ├ 作品查看 | `GET /organizer/races/<id>/works`（只读） | 该赛事创建者 |
| 5d | ├ CA 数据查看 | `GET /organizer/races/<id>/ca-sessions` | 该赛事创建者 |
| 5e | ├ 作品详情 | `GET /organizer/works/<id>`（截图/视频/README/hash链） | 该赛事创建者 |
| 5f | ├ 选择评委 | `GET /organizer/accounts` 搜索 + `POST /organizer/races/<id>/judge-assignments` | 该赛事创建者 |
| 5g | ├ 评审结果 | `GET /organizer/races/<id>/judgments`（汇总均分/总分/评语/已评人数） | 该赛事创建者 |
| 5h | ├ 取消资格 | `POST /organizer/works/<id>/disqualify` | 该赛事创建者 |
| 5i | ├ 奖项管理 | `POST /organizer/races/<id>/awards` | 该赛事创建者 |
| 5j | ├ 导出 | `GET /organizer/races/<id>/export/*` | 该赛事创建者 |
| 5k | ├ 公告管理 | `POST /organizer/races/<id>/announcements` + publish/hide | 该赛事创建者 |
| 5l | ├ 报告管理 | `POST /organizer/races/<id>/reports/generate` + publish | 该赛事创建者 |
| 6 | **「我参与的比赛」Tab** | 两个子视图：<br>• 参赛身份：`GET /rider/registrations`<br>• 评审身份：`GET /judge-invitations`（已接受的） | **所有人可见**，内容由是否有报名/评审记录决定 |
| 7 | 赛事报名 | `POST /rider/races/<id>/registrations` | 有 contestant 角色 |
| 8 | RaceProject 工作区 | `GET /rider/race-projects/<id>` + CA 列表 + Timeline + Riding Coach | 该报名所属用户 |
| 9 | CA 接入向导 | `GET /rider/race-projects/<id>/ca-wizard`（多步骤） | 该 RaceProject 所属用户 |
| 10 | 作品提交/编辑 | Work CRUD + Review Readiness 检查 | 该 Work 所属用户 |
| 11 | 作品详情（公开） | `GET /public/works/<id>` + `GET /public/works/<id>/integrity` | 所有人 |
| 12 | 评审页（评委） | `GET /judge/assignments` + `POST /judge/works/<id>/judgments` | judge |
| 13 | 榜单页（实时公开） | `GET /public/races/<id>/leaderboard`（每次请求重新聚合，含平局规则） | 所有人 |
| 14 | 骑手档案 | `GET /public/riders/<id>` | 所有人 |
| 15 | 公告列表（公开） | `GET /public/races/<id>/announcements` | 所有人 |
| 16 | 报告详情（公开） | `GET /public/races/<id>/reports` | 所有人 |
| 17 | Rider 个人报告 | `GET /rider/registrations/<id>/report` | 该报名所属用户 |
| 18 | Live Hall 大屏 | `GET /public/races/<id>/live` + `/live/entries` | 所有人 |

**要点：每个用户都看到两个 Tab，不根据角色隐藏。如果用户是纯 rider，「我组织的比赛」Tab 内容为空+显示引导；如果用户是纯 organizer，「我参与的比赛」Tab 内容为空+显示引导；如果两者都是，两个 Tab 都有实际内容。**

- [ ] 所有用户输入的文本在渲染时做 HTML escape（防 XSS）
- [ ] 每个页面覆盖状态：loading / empty / success / error / unauthorized / forbidden / not found
- [ ] 响应式：1080P 桌面为主，移动端基础可用

### 3. CI/CD

- [ ] `.github/workflows/ci.yml`：lint（flake8）→ test（pytest）→ security scan（bandit）→ dependency scan（pip-audit）
- [ ] `pytest-cov` 覆盖率报告，门禁 ≥ 80%，低于则阻断合并
- [ ] `bandit` 检测到 SQL 注入规则（B608 hardcoded_sql_expressions）→ 阻断构建
- [ ] `pip-audit` 检测到已知高危漏洞 → 阻断构建

### 4. 容器化与部署

- [ ] `Dockerfile`：基于 `python:3.12-slim`，生产 WSGI 用 `gunicorn`
- [ ] `docker-compose.yml`：Flask + Nginx 反向代理
- [ ] `nginx.conf`：HTTPS 终结、gzip、静态资源缓存、安全头、请求体大小限制、`/api/` 代理到 Flask
- [ ] `.env.example` 完整环境变量清单：
  ```
  ARY_SECRET_KEY=<generate-randomly>
  ARY_CORS_ORIGINS=https://your-domain.com
  ARY_DATABASE_PATH=/data/ary.db
  ARY_SUBMISSION_SECRET=<generate-randomly>
  ARY_JWT_EXPIRATION_HOURS=1
  GITHUB_OAUTH_CLIENT_ID=<from-github>
  GITHUB_OAUTH_CLIENT_SECRET=<from-github>
  ```
- [ ] 启动时 secret 校验脚本：`SECRET_KEY` 和 `SUBMISSION_SECRET` 未设置或为默认值 → 拒绝启动

### 5. Seed Race 全流程验收

- [ ] 编写 `backend/full_demo.py`，调用真实 API + 真实数据库，覆盖完整流程（> 20 步）：

```
01. 数据库初始化验证
02. 创建 admin 用户、Organizer、Rider A、Rider B、Judge X、Judge Y
03. Organizer 登录
04. Organizer 创建赛事（draft，ca_policy=rider_choice, judging_mode=blind, judging_tiebreaker=avg, submission_deadline, judging_deadline）
05. Organizer 发布赛事（draft → published）
05b. Organizer 开放报名（published → registration）
06. Rider A 报名 → 通知
07. Rider A 重复报名 → 409
08. Rider B 报名
09. Organizer 开始比赛（registration → running）
10. Organizer 批准 Rider A → RaceProject 生成 → 通知
11. Organizer 拒绝 Rider B → 通知
12. Organizer 开放作品提交（running → submitting）
13. Rider A 查看 RaceProject
14. Rider A 创建作品（draft）+ 上传截图/视频 → 编辑 2 次
15. Rider A 提交作品（submit）→ v1 hash 链生成
16. Rider A 修改已提交作品 → v2 hash 链更新
17. Rider A 接入 CA + 握手 → connected
18. Organizer 查看作品列表 + 点开详情
19. Organizer 进入评审（submitting → judging）→ 作品锁定
20. Rider A 尝试编辑 locked 作品 → 422
21. Organizer 搜索平台账号 → 选择 Judge X、Judge Y
22. Organizer 发送评审邀请 → Judge X 收到通知
23. Organizer 尝试分配未接受邀请的评委 → 422
24. Judge X 接受邀请 → 自动获得 judge 角色
25. Judge Y 接受邀请
26. Organizer 分配评委（Judge X → Work A，Judge Y → Work A）
27. Organizer 尝试把 Rider A 分配为评委 → 422
28. Judge X 查看评审清单（盲审）
29. Judge X 提交评分
30. Judge Y 提交评分
31. Judge Y 修改评分（judging 截止前）
32. 榜单实时查询 → 排名自动计算
33. Organizer 查看评审汇总
34. Organizer 取消资格（如适用）
35. judging_deadline 过后 → Judge X 尝试修改 → 422
36. Organizer 结束比赛（judging → completed）→ 评分锁定
37. Organizer 创建奖项（关联 Work A）
38. 公开榜单 → 含奖项 title
39. Organizer 归档（completed → archived）
40. 验证 Work hash 链完整性 → valid=true
41. 模拟数据库篡改 → verify_resource_integrity 检测到断裂
```

- [ ] 安全验收：按 `require.md` 附录 10.1 的 12 项安全缺陷逐条复核，每项有通过/不通过结论

### 6. 上线交付

- [ ] `docs/deployment.md` — 部署步骤、环境变量清单、启动命令、健康检查方式、回滚步骤
- [ ] 最终 `git tag v1.0.0` + 确保 `docker-compose up` 一键启动全栈

### E 的交付物

```
docs/openapi.yaml              # API 契约
docs/deployment.md             # 部署手册
frontend/                      # 前端应用（14 页）
Dockerfile
docker-compose.yml
nginx.conf
.env.example
.github/workflows/ci.yml
backend/full_demo.py            # 全流程 e2e demo（32 步）
```

---

## 依赖关系及并行条件

```
人员A（认证安全）────────────────────────────────────────┐
    │  提供：@require_auth, @require_role, @require_any_role,
    │        @require_own_work, @require_readonly, @validate,
    │        audit_log(), BaseDAO, AppError 家族, g 对象  │
    │  冻结：docs/contracts.md                           │
    │                                                    │
    ├──→ 人员B（赛事核心）────────────────────────────┐    │
    │        │  先冻结：works 表结构 + WorkDAO 签名    │    │
    │        │  提供：WorkDAO, RaceDAO                 │    │
    │        │                                         │    │
    │        ├──→ 人员C（评审展示）                     │    │
    │        │       依赖：WorkDAO 签名（B 建表后发群里）│    │
    │        │                                         │    │
    │        └──→ 人员D（CA接入）                       │    │
    │                依赖：RaceProjectDAO（已有角色4代码）│    │
    │                                                  │    │
    └──→ 人员E（集成）←────────────────────────────────┘    │
            依赖：所有人 API 实现                            │
            但前端可用 Mock Server 独立开发                  │
```

| 人员 | 开工前提 | 提供者 |
|---|---|---|
| A | 无阻塞，直接开工 | — |
| B | A 的接口约定（装饰器/错误类/BaseDAO 签名），不等 A 实现完 | A 先写 `docs/contracts.md` |
| C | B 的 `works` 建表 SQL + WorkDAO 函数签名（不等 B 实现完） | B 开工后第一批产出 |
| D | A 接口约定 + RaceProjectDAO（已有角色4代码） | A + B |
| E | 自己的 OpenAPI 草稿（自己先写） + Mock Server | E 自己 |

**并行启动顺序：**
1. A 直接开工；E 直接开工写 OpenAPI + 搭 Mock
2. 半天后 A 把接口约定写入 `docs/contracts.md` → B/D 开工
3. B 建完 `works` 表 + 写完 DAO 签名发群里 → C 开工
4. E 前端始终对 Mock 开发，最后一天切真实 API 联调

---

## 验收标准

| 人员 | 必须通过 |
|---|---|
| **A** | ① `bandit` 零告警 ② 登录限流脚本验证（5 次失败 → 429）③ 旧 `utils/auth.py` 已删除 ④ CORS 未配置白名单时启动 crash ⑤ 密码哈希为随机盐 ⑥ `@require_readonly` Organizer 无法 PUT/POST Work ⑦ `integrity_log` append-only 触发器生效 |
| **B** | ① Race 状态机 4 种转换 + 非法返回 422 ② 报名时 race 非 registration → 422 ③ Work 每次修改 hash 链可验证 ④ judging 后 Work 不可修改（触发器）⑤ 公开 API 无需 token ⑥ 分页生效 ⑦ Riding Coach 返回正确下一步 ⑧ 公告 CRUD + publish/hide 生效 ⑨ 18+ 测试全部通过 |
| **C** | ① 评委不能评未分配作品 → 403 ② 同一作品不可重复评分 → 409 ③ ended 后评分不可改（触发器）④ 榜单按 position 排列正确 ⑤ CSV 无明文 content ⑥ CSV 注入防护生效 ⑦ Review Readiness 检测规则全部触发 ⑧ RiderProfile 聚合数据正确 ⑨ Report 生成含 auto_fill 赛事数据 ⑩ rider_report 仅 Rider 可见 ⑪ 12+ 测试全部通过 |
| **D** | ① CA 全链路（登记 → 握手 → Ingestion → Live 聚合）数据一致 ② API Key 存储为 HMAC hash 不存明文 ③ 握手失败错误原因分类正确 ④ Live Hall 聚合数据与实际 Session 数据一致 ⑤ GitHub OAuth 首次登录自动建用户 ⑥ 旧 Jumbotron 返回 301 + deprecation 头 ⑦ Evidence Timeline 事件顺序正确 ⑧ 10+ 测试全部通过 |
| **E** | ① `docker-compose up` 一键启动 ② `python full_demo.py` 32 步全部通过 ③ `pytest` 全部通过 + 覆盖率 ≥ 80% ④ 前端 15 个页面可用（含 loading/empty/error 状态）⑤ 模拟篡改后 `verify_resource_integrity()` 检测到 hash 链断裂 ⑥ `require.md` 12 项安全复核全部通过 ⑦ `docs/openapi.yaml` 覆盖全部端点 |
