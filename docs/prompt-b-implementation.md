# Person B 生产级实现提示词

> 把本文档 + `docs/b-upstream-contracts-for-cd.md` + `docs/contracts.md` + `team-division.md` 一起给 AI。
>
> **质量基准：对标人员 A 已交付代码。** 查看 `app/utils/rate_limit.py`（双层缓存+DB持久化+fail-safe）、`app/utils/auth.py`（BEGIN IMMEDIATE事务+hmac.compare_digest+黑名单双层）、`app/services/integrity_service.py`（hash链验证+HMAC）理解生产级标准。

---

## 前置依赖（全部已就绪，不要重新实现）

| 模块 | 来源 | 用法 |
|---|---|---|
| `@require_auth` | `app/utils/auth.py` | 注入 `g.current_user_id` / `g.current_roles` |
| `@require_role("organizer")` | 同上 | 单角色门禁 |
| `@require_any_role("admin", "organizer")` | 同上 | 多角色任一满足 |
| `@require_managed_race()` | `app/utils/permissions.py` | 校验 `race.created_by_user_id == g.current_user_id`，注入 `g.current_race` |
| `@require_own_registration()` | 同上 | 归属链: Registration → User，非owner→404 |
| `@require_own_race_project()` | 同上 | 归属链: RaceProject → Registration → User |
| `@require_own_work()` | 同上 | 归属链: Work → RaceProject → Registration → User |
| `@require_readonly("work")` | 同上 | Organizer 对 Work 只读，POST/PUT/DELETE→403 |
| `@validate(Schema)` | `app/utils/validation.py` | marshmallow 校验，校验通过后 `g.validated_body` |
| `audit_log(action, actor_id, target_type, target_id, detail)` | `app/utils/logging.py` | fail-safe：DB写入失败不阻断业务，stderr兜底 |
| `BaseDAO` | `app/dao/base.py` | `find_by_id` / `create` / `update` / `delete` / `count` / `paginate` |
| `WorkDAO` | `app/dao/work_dao.py` | `create_draft` / `find_by_race_project` / `find_submitted_by_race` / `find_public_by_race` / `mark_submitted` / `set_disqualified` / `restore` |
| `RaceDAO` | `app/dao/race_dao.py` | `find_by_id` / `find_by_organizer` / `create` / `update_status` |
| `RaceProjectDAO` | `app/dao/race_project_dao.py` | `find_by_id` / `find_by_registration` / `find_by_race` / `find_by_user` |
| `RegistrationDAO` | `app/dao/registration_dao.py` | `find_by_id` / `find_by_user` / `find_by_race_and_user` |
| `NotFoundError/ForbiddenError/ConflictError/InvalidStateError/ValidationError` | `app/utils/errors.py` | 精确抛异常 |
| `success(data)` / `created(data)` | `app/utils/response.py` | JSON 响应 |
| `get_db()` | `app/database.py` | 获取 SQLite 连接 |
| `current_app.config["SUBMISSION_SECRET"]` | `app/config.py` | HMAC 密钥 |

---

## 生产级编码规范（对标 A，每一条都必须遵守）

### 1. 事务安全
所有涉及多表写操作必须：

```python
db = get_db()
try:
    db.execute("BEGIN IMMEDIATE")   # 串行化写操作
    # 事务内重读，防御 TOCTOU
    race = self.race_dao.find_by_id(race_id)
    if race["status"] not in allowed_states:
        raise InvalidStateError("...")
    # 执行写操作
    db.commit()
except Exception:
    db.rollback()
    raise
```

### 2. SQL 注入防护
- 所有 DAO 方法使用 `?` 占位符参数化查询
- 动态列名/排序：使用 BaseDAO 内置的 `_validate_columns()` / `_validate_order_by()` 正则白名单
- 绝不允许 f-string 拼接用户输入到 SQL

### 3. 错误码精确映射

| 场景 | 异常 | HTTP |
|---|---|---|
| 资源不存在（含非owner访问） | `NotFoundError("Race not found")` | 404 |
| 无权限 | `ForbiddenError("...")` | 403 |
| 状态非法 | `InvalidStateError("Cannot transition from X to Y")` | 422 |
| 重复/冲突 | `ConflictError("You have already registered")` | 409 |
| 参数校验失败 | `ValidationError("Race name is required")` | 400 |
| 资源已被锁定 | `InvalidStateError("Works are sealed once judging begins")` | 422 |

### 4. 跨赛事隔离
Service 层所有 Organizer 方法校验：
```python
if race is None or race["created_by_user_id"] != current_user_id:
    raise ForbiddenError("You can only manage your own races")
```

### 5. 审计日志
所有写操作后调用 `audit_log()`。Service 层调，路由层不调。遵循 A 的 fail-safe 模式——审计失败不阻断业务。

### 6. 分页规范
- 默认 `page=1, per_page=20`
- `per_page` 上限 100（超出截断）
- 使用 `BaseDAO.paginate()` 或自行实现同样格式 `{"items": [...], "total": N, "page": P, "per_page": PP}`

### 7. Marshmallow Schema 规范
每个写接口必须有独立 Schema，字段级错误信息：
```json
{"error": {"code": "VALIDATION_ERROR", "message": "...", "fields": {"title": ["Missing data for required field."]}, "request_id": "..."}}
```

---

## 模块 1：Race 完整 8 状态生命周期（预计 150 行 Service + 80 行路由）

### 1.1 数据库补字段（`app/database.py`）

在 `init_db()` 中用 `_add_column_if_missing()` 补全：

```python
_add_column_if_missing(cursor, "races", "start_time", "TEXT")
_add_column_if_missing(cursor, "races", "end_time", "TEXT")
_add_column_if_missing(cursor, "races", "rules", "TEXT DEFAULT ''")
_add_column_if_missing(cursor, "races", "schedule", "TEXT DEFAULT ''")
_add_column_if_missing(cursor, "races", "theme", "TEXT DEFAULT ''")
_add_column_if_missing(cursor, "races", "organizer_name", "TEXT DEFAULT ''")
_add_column_if_missing(cursor, "races", "submission_deadline", "TEXT")
_add_column_if_missing(cursor, "races", "judging_deadline", "TEXT")
_add_column_if_missing(cursor, "races", "judging_mode", "TEXT NOT NULL DEFAULT 'blind' CHECK(judging_mode IN ('blind', 'open'))")
_add_column_if_missing(cursor, "races", "judging_tiebreaker", "TEXT NOT NULL DEFAULT 'avg' CHECK(judging_tiebreaker IN ('avg', 'median', 'trimmed_mean'))")
_add_column_if_missing(cursor, "races", "ca_policy", "TEXT NOT NULL DEFAULT 'rider_choice' CHECK(ca_policy IN ('organizer_specified', 'rider_choice'))")
_add_column_if_missing(cursor, "races", "ca_policy_config", "TEXT DEFAULT '{}'")
```

注意：这些字段已在你之前创建的 `docs/b-upstream-contracts-for-cd.md` 中声明为 C/D 的依赖，D 已开始依赖 `ca_policy`/`ca_policy_config`。**所有字段必须在 `database.py` 中存在。**

### 1.2 创建赛事改初始 status

在 `app/routes/organizer.py` 的 `POST /api/v1/organizer/races` 中，把 `status=body.get("status", "upcoming")` 改为 `status="draft"`。

创建赛事时不接受 `status` 参数（状态只能通过转换 API 变更，不能在建赛事时指定）。

### 1.3 RaceService 生产级实现（`app/services/race_service.py`）

```python
import sqlite3
from app.database import get_db
from app.dao.race_dao import RaceDAO
from app.utils.errors import NotFoundError, ForbiddenError, InvalidStateError, ValidationError
from app.utils.logging import audit_log

class RaceService:
    ALLOWED_TRANSITIONS = {
        "draft":       {"published"},
        "published":   {"registration"},
        "registration": {"running"},
        "running":     {"submitting"},
        "submitting":  {"judging"},
        "judging":     {"completed"},
        "completed":   {"archived"},
        "archived":    set(),
    }

    def __init__(self):
        self.dao = RaceDAO()

    def transition(self, race_id: int, target_status: str, user_id: int) -> dict:
        """执行状态转换。事务保护 + 事务内重读。

        Raises:
            NotFoundError: race 不存在
            ForbiddenError: 非该赛事的组织者
            InvalidStateError: 非法状态转换
        """
        race = self.dao.find_by_id(race_id)
        if race is None:
            raise NotFoundError("Race not found")
        if race["created_by_user_id"] != user_id:
            raise ForbiddenError("You can only manage your own races")

        allowed = self.ALLOWED_TRANSITIONS.get(race["status"], set())
        if target_status not in allowed:
            raise InvalidStateError(
                f"Cannot transition race from '{race['status']}' to '{target_status}'"
            )

        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            # 事务内重读
            race = self.dao.find_by_id(race_id)
            if race is None:
                raise NotFoundError("Race not found")
            if race["created_by_user_id"] != user_id:
                raise ForbiddenError("You can only manage your own races")
            allowed = self.ALLOWED_TRANSITIONS.get(race["status"], set())
            if target_status not in allowed:
                raise InvalidStateError(
                    f"Cannot transition race from '{race['status']}' to '{target_status}'"
                )

            updated = self.dao.update_status(race_id, target_status)
            db.commit()
        except Exception:
            db.rollback()
            raise

        audit_log(
            f"race.{target_status}",
            user_id,
            "race",
            race_id,
            f"Transitioned from {race['status']} to {target_status}",
        )
        return updated
```

### 1.4 7 个转换路由（`app/routes/organizer.py`）

每个转换一个 POST 端点。**不要写 7 个重复函数——用一个通用 handler + route 注册模式：**

```python
# 注册 7 个状态转换路由
_TRANSITIONS = [
    ("publish",          "published"),
    ("open-registration","registration"),
    ("start",            "running"),
    ("open-submissions", "submitting"),
    ("start-judging",    "judging"),
    ("complete",         "completed"),
    ("archive",          "archived"),
]

for action, target in _TRANSITIONS:
    def _make_handler(target_status):
        @require_auth
        @require_role("organizer")
        @require_managed_race()
        def handler(race_id):
            result = race_service.transition(race_id, target_status, g.current_user_id)
            return success(result)
        handler.__name__ = f"transition_to_{target_status}"
        return handler

    organizer_bp.add_url_rule(
        f"/api/v1/organizer/races/<int:race_id>/{action}",
        endpoint=f"race_{target_status}",
        view_func=_make_handler(target),
        methods=["POST"],
    )
```

### 1.5 编辑赛事（`PUT /api/v1/organizer/races/<id>`）

仅 `draft`/`published`/`registration` 状态可编辑。可编辑字段：

```python
EDITABLE_FIELDS = {"name", "description", "start_time", "end_time", "rules",
                   "schedule", "theme", "organizer_name",
                   "ca_policy", "ca_policy_config",
                   "submission_deadline", "judging_deadline",
                   "judging_mode", "judging_tiebreaker"}
```

非可编辑状态返回 `InvalidStateError("Race can only be edited in draft/published/registration status")`。

创建 marshmallow schema：
```python
class RaceEditSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=200))
    description = fields.Str(missing="", validate=validate.Length(max=5000))
    start_time = fields.Str(missing=None)
    end_time = fields.Str(missing=None)
    rules = fields.Str(missing="")
    schedule = fields.Str(missing="")
    theme = fields.Str(missing="")
    organizer_name = fields.Str(missing="")
    ca_policy = fields.Str(missing="rider_choice", validate=validate.OneOf(["organizer_specified", "rider_choice"]))
    ca_policy_config = fields.Str(missing="{}")
    submission_deadline = fields.Str(missing=None)
    judging_deadline = fields.Str(missing=None)
    judging_mode = fields.Str(missing="blind", validate=validate.OneOf(["blind", "open"]))
    judging_tiebreaker = fields.Str(missing="avg", validate=validate.OneOf(["avg", "median", "trimmed_mean"]))
```

### 1.6 `GET /api/v1/organizer/races`

已有端点，用 `BaseDAO.paginate()` 或直接代码加 `?page=1&per_page=20`，`per_page` 上限 100。

---

## 模块 2：Registration 扩展（预计 20 行改动）

### 2.1 报名状态校验

在 `app/routes/rider.py` 的 `POST /api/v1/rider/races/<id>/registrations` 或对应 Service 中：

把 `race["status"] not in ("upcoming", "open")` 改为 `race["status"] != "registration"`。

错误文案：`"Registration is not open for this race"` → 422。

### 2.2 列表分页

`GET /api/v1/rider/registrations` 和 `GET /api/v1/organizer/races/<id>/registrations`：
- 加 `?status=submitted&page=1&per_page=20` 参数
- `status` 过滤 Registration 状态（可选，不传返回全部）
- `per_page` 上限 100

### 2.3 `GET /api/v1/rider/races`

新增。返回 `@require_auth` 用户的已报名赛事列表：

```python
def list_my_races():
    registrations = RegistrationDAO().find_by_user(g.current_user_id)
    race_ids = [r["race_id"] for r in registrations]
    races = []
    for rid in set(race_ids):
        race = RaceDAO().find_by_id(rid)
        if race:
            races.append({
                "race_id": race["id"],
                "name": race["name"],
                "status": race["status"],
            })
    return success(races)
```

### 2.4 所有写操作调用 audit_log

approve/reject/submit/withdraw——在现有 Service 方法末尾加 `audit_log()`。

---

## 模块 3：Work 作品管理（核心，预计 200 行 Service + 60 行路由）

### 3.1 触发器（`app/database.py`）

在 `init_db()` 末尾加：

```sql
CREATE TRIGGER IF NOT EXISTS trg_works_sealed
BEFORE UPDATE ON works
WHEN (
    SELECT r.status FROM race_projects rp
    JOIN registrations reg ON rp.registration_id = reg.id
    JOIN races r ON reg.race_id = r.id
    WHERE rp.id = NEW.race_project_id
) IN ('judging', 'completed', 'archived')
BEGIN
    SELECT RAISE(ABORT, 'works are sealed once judging begins');
END;
```

### 3.2 `race_projects` 表加字段

```python
_add_column_if_missing(cursor, "race_projects", "primary_work_id", "INTEGER REFERENCES works(id)")
```

### 3.3 Marshmallow Schema

```python
class WorkCreateSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    description = fields.Str(missing="", validate=validate.Length(max=5000))
    repo_url = fields.Str(missing="", validate=validate.Length(max=500))
    demo_url = fields.Str(missing="", validate=validate.Length(max=500))
    video_url = fields.Str(missing="", validate=validate.Length(max=500))
    cover_image_url = fields.Str(missing="", validate=validate.Length(max=500))
    screenshot_urls = fields.Str(missing="[]")
    readme_body = fields.Str(missing="")
    visibility = fields.Str(missing="private", validate=validate.OneOf(["private", "public"]))
```

### 3.4 WorkService 生产级实现（`app/services/work_service.py`）

**hash 计算方法：**
```python
import hashlib
import hmac
from flask import current_app

def _compute_content_hash(self, work: dict) -> str:
    """v1: SHA-256(all text fields)
       v2+: SHA-256(concat + prev_hash)"""
    data = "|".join([
        work.get("title", ""),
        work.get("description", ""),
        work.get("repo_url", ""),
        work.get("demo_url", ""),
        work.get("video_url", ""),
        work.get("cover_image_url", ""),
        work.get("screenshot_urls", "[]"),
        work.get("readme_body", ""),
    ])
    if work.get("prev_hash"):
        data += "|" + work["prev_hash"]
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def _compute_commitment(self, content_hash: str) -> str:
    secret = current_app.config["SUBMISSION_SECRET"]
    return hmac.new(secret.encode("utf-8"), content_hash.encode("utf-8"), hashlib.sha256).hexdigest()
```

**create_draft:**
```python
def create_draft(self, race_project_id: int, user_id: int, data: dict) -> dict:
    # 事务保护
    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        # 重读 RaceProject + 校验归属
        rp = RaceProjectDAO().find_by_id(race_project_id)
        if rp is None:
            raise NotFoundError("RaceProject not found")
        reg = RegistrationDAO().find_by_id(rp["registration_id"])
        if reg is None or reg["user_id"] != user_id:
            raise NotFoundError("RaceProject not found")
        # 校验状态
        race = RaceDAO().find_by_id(reg["race_id"])
        if race["status"] in ("judging", "completed", "archived"):
            raise InvalidStateError("Cannot create work in current race status")
        
        work = self.dao.create_draft(race_project_id, data["title"], **fields)
        db.commit()
    except Exception:
        db.rollback()
        raise
    
    audit_log("work.create", user_id, "work", work["id"], f"Draft created: {data['title']}")
    return work
```

**submit:**
```python
def submit(self, work_id: int, user_id: int) -> dict:
    # 查 Work + 校验归属链
    work = self.dao.find_by_id(work_id)
    if work is None:
        raise NotFoundError("Work not found")
    # require_own_work 已在路由层校验，Service 做二次确认
    rp = RaceProjectDAO().find_by_id(work["race_project_id"])
    reg = RegistrationDAO().find_by_id(rp["registration_id"])
    if reg["user_id"] != user_id:
        raise NotFoundError("Work not found")
    race = RaceDAO().find_by_id(reg["race_id"])
    
    if work["work_status"] != "draft":
        raise InvalidStateError(f"Work is already {work['work_status']}")
    if race["status"] != "submitting":
        raise InvalidStateError(
            f"Cannot submit work in race status '{race['status']}'. "
            "Submissions are only accepted during 'submitting'. "
            "Works are sealed once judging begins."
        )
    
    # 计算 hash 链
    content_hash = self._compute_content_hash(work)
    commitment = self._compute_commitment(content_hash)
    prev_hash = work.get("content_hash") if work.get("version", 0) >= 1 else None
    
    db = get_db()
    try:
        db.execute("BEGIN IMMEDIATE")
        # 事务内重读
        work = self.dao.find_by_id(work_id)
        if work["work_status"] != "draft":
            raise InvalidStateError(f"Work is already {work['work_status']}")
        
        updated = self.dao.mark_submitted(work_id, content_hash, commitment, prev_hash)
        db.commit()
    except Exception:
        db.rollback()
        raise
    
    # 写入 integrity_log
    self._write_integrity_log("work.submit", "work", work_id, user_id, content_hash, prev_hash, commitment)
    audit_log("work.submit", user_id, "work", work_id, f"Submitted v{updated['version']}")
    return updated
```

**update_draft / delete:**
同样事务保护 + 事务内重读 + audit_log。

### 3.5 路由

```python
# === rider.py ===
POST   /api/v1/rider/race-projects/<int:race_project_id>/works
       @require_auth + @require_role("rider") + @require_own_race_project() + @validate(WorkCreateSchema)
       → work_service.create_draft(race_project_id, g.current_user_id, g.validated_body)

GET    /api/v1/rider/race-projects/<int:race_project_id>/works
       @require_auth + @require_role("rider") + @require_own_race_project()
       → WorkDAO.find_by_race_project(race_project_id)

PUT    /api/v1/rider/works/<int:work_id>
       @require_auth + @require_own_work() + @validate(WorkCreateSchema)
       → work_service.update_draft(work_id, g.current_user_id, g.validated_body)

POST   /api/v1/rider/works/<int:work_id>/submit
       @require_auth + @require_own_work()
       → work_service.submit(work_id, g.current_user_id)

DELETE /api/v1/rider/works/<int:work_id>
       @require_auth + @require_own_work()
       → work_service.delete(work_id, g.current_user_id)

# === organizer.py ===
GET    /api/v1/organizer/races/<int:race_id>/works
       @require_auth + @require_role("organizer") + @require_managed_race() + @require_readonly("work")
       → WorkDAO.find_submitted_by_race(race_id)

GET    /api/v1/organizer/works/<int:work_id>
       @require_auth + @require_role("organizer") + @require_managed_race()
       → WorkDAO.find_by_id(work_id) + 关联查询 RaceProject/Registration/Race

# === public.py ===
GET    /api/v1/public/works/<int:work_id>/integrity
       → verify_resource_integrity("work", work_id)  # 无需认证
```

### 3.6 integrity_log 写入辅助方法

```python
def _write_integrity_log(self, event_type, resource_type, resource_id, actor_id, content_hash, prev_hash, commitment):
    from app.database import get_db
    db = get_db()
    db.execute(
        """INSERT INTO integrity_log
           (event_type, resource_type, resource_id, actor_user_id, content_hash, prev_hash, commitment)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (event_type, resource_type, resource_id, actor_id, content_hash, prev_hash, commitment),
    )
    db.commit()
```

---

## 模块 4：公开赛事浏览（`app/routes/public.py`，预计 60 行）

新建 `public_bp = Blueprint("public", __name__)`，在 `app/__init__.py` 注册。

```python
# 1. 公开赛事列表
GET /api/v1/public/races
    参数: ?status=registration&page=1&per_page=20&q=keyword
    搜索: q 对 name 做 LIKE '%keyword%'
    过滤: status != 'draft'（草稿不公开）
    分页: BaseDAO.paginate()

# 2. 公开赛事详情
GET /api/v1/public/races/<int:race_id>
    返回: 所有 Race 字段
         + "participant_count": registrations WHERE status='approved' 的 COUNT
         + "public_work_count": works WHERE work_status='submitted' AND visibility='public' 的 COUNT

# 3. 公开作品
GET /api/v1/public/races/<int:race_id>/works
    → WorkDAO.find_public_by_race(race_id)

# 4. 平台统计
GET /api/v1/public/stats
    SELECT COUNT(*) FROM races WHERE status != 'draft'   → total_races
    SELECT COUNT(*) FROM races WHERE status NOT IN ('draft','completed','archived') → active_races
    SELECT COUNT(DISTINCT user_id) FROM registrations WHERE status='approved' → total_riders
    SELECT COUNT(*) FROM works WHERE work_status='submitted' AND disqualified=0 → total_works
```

**所有公开端点无需任何认证装饰器。**

---

## 模块 5：Riding Coach（`app/services/coach_service.py`，预计 40 行）

```python
class RidingCoachService:
    def __init__(self):
        self.registration_dao = RegistrationDAO()
        self.race_project_dao = RaceProjectDAO()
        self.work_dao = WorkDAO()
        self.race_dao = RaceDAO()

    def get_next_actions(self, race_project_id: int, user_id: int) -> list[dict]:
        """纯规则化，不做 AI。返回 0-N 条建议。"""
        rp = self.race_project_dao.find_by_id(race_project_id)
        reg = self.registration_dao.find_by_id(rp["registration_id"])
        race = self.race_dao.find_by_id(reg["race_id"])
        works = self.work_dao.find_by_race_project(race_project_id)
        submitted_works = [w for w in works if w["work_status"] == "submitted"]

        actions = []

        if reg["status"] == "submitted":
            actions.append({
                "action_label": "等待审批",
                "description": "报名已提交，等待主办方审批",
                "target_url": f"/rider/registrations/{reg['id']}",
            })
            return actions  # 最早阶段，只返回这一条

        if reg["status"] == "approved":
            # 检查 CA——这里 D 还没实现，先检查是否有 ca_connections 表
            has_ca = self._has_active_ca(race_project_id)
            if not has_ca:
                actions.append({
                    "action_label": "接入编码助手",
                    "description": "接入你的 Coding Agent，开始骑行",
                    "target_url": f"/rider/race-projects/{race_project_id}/ca-wizard",
                })
            elif self._ca_all_pending(race_project_id):
                actions.append({
                    "action_label": "完成 CA 握手",
                    "description": "所有 CA 连接仍在等待握手，请完成握手以激活连接",
                    "target_url": f"/rider/race-projects/{race_project_id}",
                })

            if not submitted_works:
                actions.append({
                    "action_label": "提交作品",
                    "description": "你还没有提交作品，请完成并提交",
                    "target_url": f"/rider/race-projects/{race_project_id}/works",
                })

            if submitted_works:
                # check readiness
                readiness_issues = self._check_readiness(submitted_works[0])
                if readiness_issues:
                    actions.append({
                        "action_label": "检查作品准备度",
                        "description": f"修复以下问题：{'; '.join(readiness_issues)}",
                        "target_url": f"/rider/race-projects/{race_project_id}/review-readiness",
                    })

        if race["status"] == "completed":
            if self._has_award(reg["id"]):
                actions.append({
                    "action_label": "查看获奖",
                    "description": "恭喜获奖！查看榜单",
                    "target_url": f"/public/races/{race['id']}/leaderboard",
                })
            else:
                actions.append({
                    "action_label": "赛事已结束",
                    "description": "查看你的骑手档案，积累的能力已沉淀",
                    "target_url": f"/public/riders/{user_id}",
                })

        return actions

    def _check_readiness(self, work: dict) -> list[str]:
        issues = []
        if not work.get("title"):
            issues.append("作品名称为空")
        if not work.get("description"):
            issues.append("作品简介缺失")
        if not work.get("readme_body"):
            issues.append("README 缺失")
        if not work.get("repo_url") and not work.get("demo_url"):
            issues.append("缺少代码仓库和演示链接")
        return issues
```

路由：`GET /api/v1/rider/race-projects/<id>/next-actions` + `@require_own_race_project()`。

---

## 模块 6：赛事公告（预计 30 行 DAO + 50 行 Service + 30 行路由）

### AnnouncementDAO（`app/dao/announcement_dao.py`）
```python
from app.dao.base import BaseDAO
from app.database import get_db

class AnnouncementDAO(BaseDAO):
    table = "announcements"

    def find_by_race(self, race_id: int, visibility: str | None = None) -> list[dict]:
        db = get_db()
        if visibility:
            rows = db.execute(
                "SELECT * FROM announcements WHERE race_id = ? AND visibility = ? ORDER BY created_at DESC",
                (race_id, visibility),
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM announcements WHERE race_id = ? ORDER BY created_at DESC",
                (race_id,),
            ).fetchall()
        return [dict(r) for r in rows]
```

### AnnouncementService（`app/services/announcement_service.py`）
- `create(race_id, user_id, data)` → 校验 `@require_managed_race`（Service 层），`audit_log`
- `update(id, user_id, data)` → 同上
- `publish(id, user_id)` / `hide(id, user_id)` → visibility 变更，`audit_log`
- `delete(id, user_id)` → 校验 managed_race，`audit_log`

所有写操作：`BEGIN IMMEDIATE` + 事务内重读。

### 路由
```python
# organizer.py
POST   /api/v1/organizer/races/<id>/announcements    @require_managed_race + @validate(AnnouncementSchema)
GET    /api/v1/organizer/races/<id>/announcements     @require_managed_race
PUT    /api/v1/organizer/announcements/<id>           @require_managed_race
POST   /api/v1/organizer/announcements/<id>/publish   @require_managed_race
POST   /api/v1/organizer/announcements/<id>/hide      @require_managed_race
DELETE /api/v1/organizer/announcements/<id>           @require_managed_race

# public.py
GET    /api/v1/public/races/<id>/announcements        无需认证
```

---

## 实现顺序

```
1. 模块 1（Race 状态机）     → 改 database.py + 写 RaceService + 7 个转换路由
2. 模块 2（Registration）   → 改已有校验 + 加分页
3. 模块 3（Work）            → 改 database.py（触发器+字段）→ WorkService → 路由
4. 模块 4（公开 API）        → 新建 public.py
5. 模块 5（Coach）           → CoachService + 路由
6. 模块 6（公告）            → DAO + Service + 路由
```

---

## 测试要求（每个模块 ≥2 项测试）

| 测试文件 | 测试项 |
|---|---|
| `tests/test_race_lifecycle.py` | ① draft→published 正常 ② published→registration 正常 ③ 非法转换返回 422 ④ 非owner转换返回 403 |
| `tests/test_work_integrity.py` | ① draft→submit 生成 hash 链 ② 修改后重提交 v2 hash 链 ③ judging 后编辑返回 422 |
| `tests/test_public_apis.py` | ① GET /public/races 返回非 draft 赛事 ② 搜索关键字生效 ③ 分页生效 ④ GET /public/stats 返回计数 |
| `tests/test_announcement.py` | ① 创建+publish ② 公开端点只返回 public ③ 非 owner 不可编辑 |
| `tests/test_coach.py` | ① 报名后返回"等待审批" ② 审批后无 Work 返回"提交作品" |

---

## 最终验收

```bash
# 所有测试通过
pytest tests/test_race_lifecycle.py tests/test_work_integrity.py tests/test_public_apis.py tests/test_announcement.py tests/test_coach.py tests/test_checkpoint.py tests/test_registration_state_machine.py tests/legacy/ -q

# 手动 demo 关键路径
curl POST /organizer/races → draft (status=draft)
curl POST /organizer/races/<id>/publish → published
curl POST /organizer/races/<id>/open-registration → registration
curl POST /rider/races/<id>/registrations → submitted
curl POST /organizer/races/<id>/start → running
curl POST /organizer/registrations/<id>/approve → approved + RaceProject 生成
curl POST /organizer/races/<id>/open-submissions → submitting
curl POST /rider/race-projects/<id>/works → draft
curl POST /rider/works/<id>/submit → v1 hash 链
curl PUT /rider/works/<id> → 成功
curl POST /rider/works/<id>/submit → v2 hash 链
curl POST /organizer/races/<id>/start-judging → judging（作品锁定）
curl PUT /rider/works/<id> → 422 "sealed"
curl POST /organizer/races/<id>/announcements → 公告
curl POST /organizer/announcements/<id>/publish → 公开
curl GET /public/races/<id>/announcements → 可见
curl POST /organizer/races/<id>/complete → completed
curl POST /organizer/races/<id>/archive → archived
curl GET /rider/race-projects/<id>/next-actions → Coach 建议
curl GET /public/works/<id>/integrity → hash 链 valid=true
```
