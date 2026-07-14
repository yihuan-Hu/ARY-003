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
- [ ] 统一用户模型：`users` 表只使用 `roles TEXT NOT NULL DEFAULT '["contestant"]'`（JSON 数组），旧 `role INTEGER` 字段标记 deprecated 并在 seed 脚本里不再写入
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

### 6. 作品完整性保护基础设施（第1层 + 第4层 + 第5层）

- [ ] `@require_own_work(work_id_param)` 装饰器：校验 Work → RaceProject → Registration → User 归属链，非 owner 返回 404
- [ ] `@require_readonly(domain)` 装饰器：标记某角色的某域只有读权限（例如 Organizer 对 Work 只能 GET 不能 POST/PUT/DELETE），写操作返回 403
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
docs/contracts.md                   # A 的接口契约（装饰器/错误类/g对象/BaseDAO 签名）
```

---

## 人员 B：赛事核心域

**定位：** Race 生命周期 + Registration 扩展 + Work 作品管理 + 公开赛事浏览 + Riding Coach 状态提示。B 的 Work 模型是 C（评审）的上游，需要最先把 Work 表结构确定下来通知 C。

**依赖：** A 的 `@require_auth`、`@require_role`、`@validate`、`BaseDAO`、错误类、`audit_log()`、`integrity_log`。

### 1. Race 完整生命周期

- [ ] `PUT /api/v1/organizer/races/<id>` — 编辑赛事信息（名称、描述、规则、赛程、theme、organizer_name）
- [ ] `POST /api/v1/organizer/races/<id>/open` — 开放报名（upcoming → open）Organizer，需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/races/<id>/close` — 截止报名（open → judging）Organizer，需 `@require_managed_race`
- [ ] `POST /api/v1/organizer/races/<id>/end` — 结束赛事（judging → ended）Organizer，需 `@require_managed_race`
- [ ] Race `ALLOWED_TRANSITIONS` 状态机：`upcoming → open → judging → ended`，非法转换返回 422
- [ ] `GET /api/v1/organizer/races/<id>` — 赛事详情（owner 视角）
- [ ] `GET /api/v1/organizer/races` — 已有，增加分页 `?page=1&per_page=20`
- [ ] Race schema 补全字段：`start_time`、`end_time`、`rules`、`schedule`、`theme`、`organizer_name`

### 2. Registration 扩展

- [ ] 已有 `POST /api/v1/rider/races/<id>/registrations` → 增加校验：race.status 必须为 `open`，否则返回 422
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
    readme_body TEXT DEFAULT '',
    visibility TEXT NOT NULL DEFAULT 'private',
    content_hash TEXT DEFAULT '',
    content_commitment TEXT DEFAULT '',
    prev_hash TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] `race_projects` 表增字段 `primary_work_id INTEGER REFERENCES works(id)`

- [ ] Work hash 链实现：
  - v1 首次提交 → `content_hash = SHA-256(title + description + repo_url + demo_url + readme_body)`
  - v2+ 修改 → `content_hash = SHA-256(title + ... + prev_hash + readme_body)`
  - `content_commitment = HMAC-SHA-256(content_hash, SUBMISSION_SECRET)`
  - `prev_hash` 指向上一版本的 `content_hash`

- [ ] `POST /api/v1/rider/race-projects/<id>/works` — 提交作品，需 `@require_own_race_project` + `@validate(WorkCreateSchema)`
  - 写入 `integrity_log`（event_type: `work.create`）
  - 调用 `audit_log("work.create", ...)`
- [ ] `GET /api/v1/rider/race-projects/<id>/works` — 查看自己的作品列表
- [ ] `PUT /api/v1/rider/works/<id>` — 编辑作品，需 `@require_own_work` + race.status 不能是 judging/ended
  - 自增 `version`，更新 `prev_hash` + `content_hash` + `content_commitment`
  - 写入 `integrity_log`（event_type: `work.update`）
  - 调用 `audit_log("work.update", ...)`
- [ ] `DELETE /api/v1/rider/works/<id>` — 删除作品，需 `@require_own_work` + race.status 不能是 judging/ended
  - 调用 `audit_log("work.delete", ...)`
- [ ] `GET /api/v1/organizer/races/<id>/works` — Organizer 查看作品列表 **只读**，需 `@require_managed_race` + `@require_readonly("work")`
- [ ] `trg_works_sealed` 触发器：race 进入 judging 后，works 的 UPDATE/DELETE 被拒绝

```sql
CREATE TRIGGER trg_works_sealed
BEFORE UPDATE ON works
WHEN (
    SELECT r.status FROM race_projects rp
    JOIN registrations reg ON rp.registration_id = reg.id
    JOIN races r ON reg.race_id = r.id
    WHERE rp.id = NEW.race_project_id
) IN ('judging', 'ended')
BEGIN
    SELECT RAISE(ABORT, 'works are sealed once judging begins');
END;
```

- [ ] `GET /api/v1/public/works/<id>/integrity` — 公开验证端点，返回 hash 链验证结果 **无需认证**

### 4. 公开赛事浏览

- [ ] `GET /api/v1/public/races` — 公开赛事列表 **无需认证**，支持 `?status=open&page=1&per_page=20&q=keyword`
- [ ] `GET /api/v1/public/races/<id>` — 公开赛事详情 **无需认证**（含赛事信息、参赛人数、公开作品数）
- [ ] `GET /api/v1/public/races/<id>/works` — 赛事公开作品（只返回 `visibility='public'` 的作品）**无需认证**
- [ ] `GET /api/v1/public/stats` — 平台全局统计 **无需认证**：赛事总数、进行中赛事数、参赛总人数、作品总数

### 5. Riding Coach 状态提示

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

### B 的交付物

```
backend/app/dao/work_dao.py              # WorkDAO（继承 BaseDAO）
backend/app/dao/race_dao.py              # RaceDAO（已有，扩展分页 + 状态机方法）
backend/app/services/race_service.py      # RaceService（状态机 + 生命周期）
backend/app/services/work_service.py      # WorkService（CRUD + hash 链 + 触发器）
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

- [ ] `POST /api/v1/admin/races/<id>/judge-assignments` — 批量分配评委，需 `@require_role("admin")`
  - body: `{"assignments": [{"work_id": 1, "judge_user_id": 5}, ...]}`
  - 校验 race.created_by_user_id == current_user_id（跨赛事隔离）
  - 调用 `audit_log("judge.assign", ...)`
- [ ] `GET /api/v1/admin/races/<id>/judge-assignments` — 查看当前分配情况
- [ ] `DELETE /api/v1/admin/judge-assignments/<id>` — 取消单条分配（评审尚未提交时）
- [ ] `GET /api/v1/judge/assignments` — 评委查看自己的评审清单，需 `@require_role("judge")`，返回包含 Work 摘要 + Review Readiness 风险摘要
- [ ] `POST /api/v1/judge/works/<id>/judgments` — 提交四维评分 + 评语，需 `@require_role("judge")`
  - 校验评委已分配到该 Work
  - 写入 `integrity_log`（event_type: `judgment.submit`）
  - 调用 `audit_log("judgment.submit", ...)`
- [ ] `PUT /api/v1/judge/judgments/<id>` — 修改评分，需 `@require_role("judge")` + race.status 不是 ended
  - 写入 `integrity_log`（event_type: `judgment.update`）
  - 调用 `audit_log("judgment.update", ...)`
- [ ] `trg_judgments_sealed` 触发器：

```sql
CREATE TRIGGER trg_judgments_sealed
BEFORE UPDATE ON judging_records
WHEN EXISTS (
    SELECT 1 FROM works w
    JOIN race_projects rp ON w.race_project_id = rp.id
    JOIN registrations reg ON rp.registration_id = reg.id
    JOIN races r ON reg.race_id = r.id
    WHERE w.id = NEW.work_id AND r.status = 'ended'
)
BEGIN
    SELECT RAISE(ABORT, 'judgments are sealed after race ends');
END;
```

### 2. 奖项与榜单

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
- [ ] `DELETE /api/v1/organizer/awards/<id>` — 删除奖项，需校验 race ownership + race.status 不能是 ended
- [ ] `GET /api/v1/organizer/races/<id>/awards` — 管理奖项列表
- [ ] `GET /api/v1/public/races/<id>/leaderboard` — 公开榜单 **无需认证**，按 `position` ASC 排列，返回奖项名 + 获奖者 username + 作品标题 + 总分

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

### C 的交付物

```
backend/app/dao/judging_dao.py           # JudgingRecordDAO + JudgeAssignmentDAO
backend/app/dao/award_dao.py             # AwardDAO
backend/app/services/judging_service.py   # JudgingService（分配+评分+触发器）
backend/app/services/award_service.py     # AwardService
backend/app/services/readiness_service.py # ReviewReadinessService
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

### 1. CAConnection 接入

- [ ] `ca_connections` 建表：

```sql
CREATE TABLE ca_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_project_id INTEGER NOT NULL REFERENCES race_projects(id),
    ca_type TEXT NOT NULL CHECK(ca_type IN ('codex', 'claude', 'other')),
    provider_name TEXT NOT NULL,
    connection_status TEXT NOT NULL DEFAULT 'pending' CHECK(connection_status IN ('pending', 'connected', 'failed')),
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

- [ ] `POST /api/v1/rider/race-projects/<id>/ca-connections` — 登记 CA 接入，需 `@require_own_race_project`
  - API Key 使用 HMAC-SHA-256 存储 hash，不存明文：`api_key_hash = HMAC-SHA-256(api_key, SUBMISSION_SECRET)`
  - 调用 `audit_log("ca_connection.create", ...)`
- [ ] `GET /api/v1/rider/race-projects/<id>/ca-connections` — 查看已登记 CA 列表（不返回 api_key_hash）
- [ ] `PUT /api/v1/rider/ca-connections/<id>` — 更新 CA 配置
- [ ] `DELETE /api/v1/rider/ca-connections/<id>` — 移除 CA 连接
- [ ] `POST /api/v1/ca-connections/<id>/handshake` — CA 握手验证
  - 更新 `connection_status` 为 `connected` 或 `failed`
  - `failed` 时写入 `error_message`
  - 调用 `audit_log("ca_connection.handshake", ...)`
- [ ] 更新 `RaceProjectService._format()` — 把 `ca_connections: []` 占位改为真实查询数据
- [ ] CA 接入异常不触发 Registration 状态变更（维持现有隔离原则）

### 2. CA 接入向导

- [ ] `GET /api/v1/rider/race-projects/<id>/ca-wizard` — 返回向导步骤和当前状态
- [ ] 向导步骤流程（状态来自真实 CAConnection 数据）：
  1. 选择 CA 类型 → 展示 codex/claude/other 的字段模板
  2. 填写 provider 名称 + 仓库 URL + API Key
  3. 握手测试 → 显示结果：connected（绿色）、failed + 错误原因（红色）
  4. 完成 → 展示连接健康度和下一个可用 CAConnection 入口
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
  - 首次登录：自动创建 User（`github_user_id` + `github_login` 字段已在 schema 中预留），`roles = ["contestant"]`，`profile_completed = 0`
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

| # | 页面 | 对应 API |
|---|---|---|
| 1 | 首页（赛事列表 + 平台统计） | `GET /public/races` + `GET /public/stats` |
| 2 | 赛事详情 | `GET /public/races/<id>` |
| 3 | 登录/注册 | GitHub OAuth + 本地登录 `POST /auth/login` |
| 4 | 个人中心 | `GET/PUT /auth/profile` |
| 5 | 赛事报名 | `POST /rider/races/<id>/registrations` |
| 6 | 我的报名列表 | `GET /rider/registrations` |
| 7 | RaceProject 工作区 | `GET /rider/race-projects/<id>` + CA 列表 + Timeline + Riding Coach |
| 8 | CA 接入向导 | `GET /rider/race-projects/<id>/ca-wizard`（多步骤） |
| 9 | 作品提交/编辑 | Work CRUD + Review Readiness 检查 |
| 10 | 作品详情（公开） | `GET /public/works/<id>` + `GET /public/works/<id>/integrity` |
| 11 | 评审页（评委） | `GET /judge/assignments` + `POST /judge/works/<id>/judgments` |
| 12 | 榜单页 | `GET /public/races/<id>/leaderboard` |
| 13 | 骑手档案 | `GET /public/riders/<id>` |
| 14 | Live Hall 大屏 | `GET /public/races/<id>/live` + `/live/entries` |
| 15 | 管理后台（Organizer） | Race 管理 + 报名审批 + 评委分配 + 导出 |

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
01. 创建数据库初始化验证
02. 创建 admin 用户
03. Organizer 登录 → 获取 token
04. Organizer 创建赛事
05. Organizer 开放报名（open）
06. Rider A 报名
07. Rider A 重复报名 → 409
08. Rider B 报名
09. Rider A 查看自己的报名 → 200
10. Rider B 尝试查看 Rider A 的报名 → 404
11. Organizer 批准 Rider A → RaceProject 自动生成
12. Organizer 重新批准 Rider A → 幂等返回
13. Organizer 拒绝 Rider B
14. Rider A 查看 RaceProject
15. Rider A 登记 CAConnection
16. Rider A CA 握手 → connected
17. Rider A CA 数据 Ingestion（3 条 Session）
18. Rider A 提交作品
19. Rider A 修改作品（v2 hash 链验证）
20. Organizer 截止报名（close → judging）
21. Admin 分配评委
22. Judge 提交评分
23. Judge 尝试修改评分 → 成功
24. Organizer 结束赛事（end）→ 评分锁定
25. Judge 尝试再修改评分 → 403/422
26. Organizer 创建奖项
27. 查看公开榜单
28. 查看 Live Hall
29. 查看 Evidence Timeline
30. 查看 Riding Coach 建议
31. CSV 导出
32. 验证 Work hash 链完整性 → valid=true
33. 模拟数据库篡改 → verify_resource_integrity 检测到断裂
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
| **B** | ① Race 状态机 4 种转换 + 非法返回 422 ② 报名时 race 非 open → 422 ③ Work 每次修改 hash 链可验证 ④ judging 后 Work 不可修改（触发器）⑤ 公开 API 无需 token ⑥ 分页生效 ⑦ Riding Coach 返回正确下一步 ⑧ 18+ 测试全部通过 |
| **C** | ① 评委不能评未分配作品 → 403 ② 同一作品不可重复评分 → 409 ③ ended 后评分不可改（触发器）④ 榜单按 position 排列正确 ⑤ CSV 无明文 content ⑥ CSV 注入防护生效 ⑦ Review Readiness 检测规则全部触发 ⑧ RiderProfile 聚合数据正确 ⑨ 12+ 测试全部通过 |
| **D** | ① CA 全链路（登记 → 握手 → Ingestion → Live 聚合）数据一致 ② API Key 存储为 HMAC hash 不存明文 ③ 握手失败错误原因分类正确 ④ Live Hall 聚合数据与实际 Session 数据一致 ⑤ GitHub OAuth 首次登录自动建用户 ⑥ 旧 Jumbotron 返回 301 + deprecation 头 ⑦ Evidence Timeline 事件顺序正确 ⑧ 10+ 测试全部通过 |
| **E** | ① `docker-compose up` 一键启动 ② `python full_demo.py` 32 步全部通过 ③ `pytest` 全部通过 + 覆盖率 ≥ 80% ④ 前端 15 个页面可用（含 loading/empty/error 状态）⑤ 模拟篡改后 `verify_resource_integrity()` 检测到 hash 链断裂 ⑥ `require.md` 12 项安全复核全部通过 ⑦ `docs/openapi.yaml` 覆盖全部端点 |
