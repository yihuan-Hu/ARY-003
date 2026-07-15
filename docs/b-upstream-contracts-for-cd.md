# B 给 C/D 的上游契约冻结说明

冻结时间：2026-07-15

来源：`team-division.md` 中人员 B「赛事核心域」第一批上游交付要求。

---

## 快速索引

| 你需要什么 | 去哪取 |
|---|---|
| 评审池（submitted works） | `WorkDAO.find_submitted_by_race(race_id)` |
| 公开作品列表 | `WorkDAO.find_public_by_race(race_id)` |
| 单个作品详情 | `WorkDAO.find_by_id(work_id)`（BaseDAO） |
| 作品归属人 user_id | `works.race_project_id` → `race_projects.registration_id` → `registrations.user_id` |
| 评审准备度检测 | `work.description` / `repo_url` / `demo_url` / `readme_body` 判空 |
| 取消资格/恢复 | `WorkDAO.set_disqualified()` / `restore()` |
| RaceProject 信息 | `RaceProjectDAO`（已有，6 个查询方法） |
| CA 策略 | `RaceDAO.find_by_id(race_id)` → `ca_policy` / `ca_policy_config` |

---

## 1. 给 C：Work 表结构 + DAO + 关联链

### 1.1 `works` 表（完整字段）

C 可以依赖以下所有字段。表由 B 的 `database.py` 创建，无需 C 手动建表。

```sql
CREATE TABLE IF NOT EXISTS works (
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
    work_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (work_status IN ('draft', 'submitted')),
    visibility TEXT NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private', 'public')),
    content_hash TEXT DEFAULT '',
    content_commitment TEXT DEFAULT '',
    prev_hash TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    submitted_at TEXT,
    disqualified INTEGER NOT NULL DEFAULT 0
        CHECK (disqualified IN (0, 1)),
    disqualify_reason TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**C 直接依赖的字段：**

| 字段 | C 的用途 |
|---|---|
| `id` | 评审/榜单/导出的 Work 标识 |
| `race_project_id` | → JOIN race_projects → JOIN registrations 取 `user_id`（盲审隐藏、自评防护） |
| `title` | 评审清单、榜单、导出 |
| `description` | 评审详情、Review Readiness 判空 |
| `repo_url` | 评审详情、Review Readiness 判空（为空 → "缺代码仓库"） |
| `demo_url` | 评审详情、Review Readiness 判空（为空 → "缺演示链接"） |
| `video_url` | 评审详情页嵌入 |
| `cover_image_url` | 评审清单/榜单卡片 |
| `screenshot_urls` | 评审详情页轮播 |
| `readme_body` | 评审详情、Review Readiness 判空（为空 → "README 缺失"） |
| `work_status` | `'submitted'` → 进入评审池；`'draft'` → 不进入 |
| `visibility` | `'public'` → 可入公开列表 |
| `content_hash` / `content_commitment` / `prev_hash` | 完整性验证链接（B 负责生成，C 只需透传） |
| `submitted_at` | 榜单排序、导出 |
| `disqualified` | 榜单排除（=1 时不在榜单中出现） |
| `disqualify_reason` | 导出、前端展示取消原因 |

### 1.2 WorkDAO 签名

文件：`backend/app/dao/work_dao.py`

```python
from app.dao.base import BaseDAO

class WorkDAO(BaseDAO):
    table = "works"

    # ---- C 直接使用的方法 ----

    def find_submitted_by_race(self, race_id: int) -> list[dict]
        """返回 race_id 下所有 work_status='submitted' 的作品（评审池）"""

    def find_public_by_race(self, race_id: int) -> list[dict]
        """返回 race_id 下 submitted + visibility='public' + disqualified=0 的作品"""

    def set_disqualified(self, work_id: int, reason: str) -> dict | None
        """标记取消资格，返回更新后的 work dict"""

    def restore(self, work_id: int) -> dict | None
        """恢复资格，清除 disqualify_reason"""

    # ---- 继承自 BaseDAO 的方法 ----

    def find_by_id(self, id: int) -> dict | None
        """按 id 查单条，C 用于查看作品详情"""

    def paginate(self, page, per_page, order_by, **filters) -> dict
        """分页查询，返回 {"items": [...], "total": N, "page": P, "per_page": PP}"""

    # ---- B 内部使用（C 不需要调用） ----

    def create_draft(self, race_project_id, title, **fields) -> dict
    def find_by_race_project(self, race_project_id: int) -> list[dict]
    def mark_submitted(self, work_id, content_hash, content_commitment, prev_hash=None) -> dict | None
```

### 1.3 关联链：如何从 Work 找到 owner

C 的评审模块需要知道每件作品的参赛者是谁（盲审隐藏、自评防护、取消资格通知）。

**从 Work → User 的 JOIN 路径：**

```
works.race_project_id → race_projects.id → race_projects.registration_id → registrations.id → registrations.user_id → users.id
```

**C 可以直接用的 DAO（均已存在）：**

```python
from app.dao.race_project_dao import RaceProjectDAO   # find_by_id()
from app.dao.registration_dao import RegistrationDAO   # find_by_id()
```

**C 获取作品 owner 的代码模板：**

```python
def _get_work_owner_user_id(work: dict) -> int:
    """从 Work 追溯到 User"""
    rp = RaceProjectDAO().find_by_id(work["race_project_id"])
    reg = RegistrationDAO().find_by_id(rp["registration_id"])
    return reg["user_id"]
```

**C 在评审清单中隐藏 rider_name 的代码模板（盲审）：**

```python
race = RaceDAO().find_by_id(race_id)
if race["judging_mode"] == "blind":
    # 不返回 rider_name / rider_user_id
    work_data.pop("rider_name", None)
```

### 1.4 Review Readiness 检测字段

C 的 Review Readiness 规则需要检查以下字段。这些字段在 `works` 表中，C 可以直接读取：

| 检测规则 | 检查字段 |
|---|---|
| 作品未提交 | `work_status != 'submitted'` |
| 作品信息不完整 | `title` / `description` / `readme_body` 为空 |
| 缺少代码仓库 | `repo_url` 为空 |
| 缺少演示链接 | `demo_url` 为空 |
| CA 数据缺失 | 调用 D 的接口查询（不在本契约范围，待 D 提供） |
| CA 接入异常 | 调用 D 的接口查询（同上） |

---

## 2. 给 D：RaceProject + Race 依赖

### 2.1 RaceProjectDAO（已存在，无需 B 改动）

文件：`backend/app/dao/race_project_dao.py`

```python
class RaceProjectDAO:
    def create(self, registration_id: int, *, commit: bool = True) -> dict
    def find_by_id(self, race_project_id: int) -> dict | None
    def find_by_registration(self, registration_id: int) -> dict | None
    def find_by_race(self, race_id: int) -> list[dict]
    def find_by_user(self, user_id: int) -> list[dict]
    def count_by_registration(self, registration_id: int) -> int
```

**D 可依赖的 RaceProject 字段：**

| 字段 | D 的用途 |
|---|---|
| `id` | CAConnection/CASession/Live Hall 的归属标识 |
| `registration_id` | → JOIN registrations 取 `race_id` 和 `user_id` |
| `aggregate_ingestion_status` | CA 聚合状态落点（`not_configured` / `connected` / `active` / `failed`），D 的 CAConnection/CASession 写入后更新此字段 |
| `connection_health` | CA 连接健康度（`no_signal` / `ok` / `partial_failed` / `all_failed`），D 负责维护 |
| `primary_work_id` | Work 主链接占位，D 不应把 CA Session 当 Work |
| `created_at` / `updated_at` | Evidence Timeline 事件时间 |

### 2.2 RaceDAO（已存在 —— CA 策略字段待 B 补充）

文件：`backend/app/dao/race_dao.py`

```python
class RaceDAO:
    def find_by_id(self, race_id: int) -> dict | None
    # 其他方法略
```

**D 需要读的 Race 字段（CA 双模式 + 向导）：**

| 字段 | D 的用途 |
|---|---|
| `ca_policy` | `'rider_choice'` = 参赛者自由选择，`'organizer_specified'` = 赛事方限定 |
| `ca_policy_config` | JSON，当 `organizer_specified` 时存储 `{"allowed_ca_types": [...], "required_fields": [...]}` |

**D 读取 CA 策略的代码模板：**

```python
race = RaceDAO().find_by_id(race_id)

if race["ca_policy"] == "organizer_specified":
    config = json.loads(race["ca_policy_config"] or "{}")
    allowed_types = config.get("allowed_ca_types", [])
    required_fields = config.get("required_fields", [])
    # 校验参赛者创建的 CAConnection 在允许范围内
else:
    # rider_choice：参赛者完全自由
```

**约束：**

- `ca_policy` / `ca_policy_config` 字段由 B 在 Race 创建/编辑 API 中写入。D 只读，不写。
- 这两个字段当前已在 `database.py` 建表 SQL 中定义（`ca_policy TEXT NOT NULL DEFAULT 'rider_choice'`），D 可以直接依赖。

### 2.3 关联链：如何从 RaceProject 找到 Race

D 的 Live Hall 和 Evidence Timeline 需要按 Race 聚合数据。

**从 RaceProject → Race 的 JOIN 路径：**

```
race_projects.registration_id → registrations.id → registrations.race_id → races.id
```

**D 可以直接用的 DAO：**

```python
from app.dao.registration_dao import RegistrationDAO   # find_by_id()
from app.dao.race_dao import RaceDAO                   # find_by_id()
```

**D 获取 Race 的代码模板：**

```python
def _get_race_from_race_project(race_project_id: int) -> dict:
    rp = RaceProjectDAO().find_by_id(race_project_id)
    reg = RegistrationDAO().find_by_id(rp["registration_id"])
    return RaceDAO().find_by_id(reg["race_id"])
```

---

## 3. 本轮不做事项（明确边界）

以下由 B 自己在后续实现，C/D **不应**自行实现或依赖：

- 完整 Work CRUD 路由（`POST/PUT/DELETE /rider/works/...`）
- Work hash 链生成（`content_hash` / `content_commitment` / `prev_hash` 字段已在表中，但 B 负责写入逻辑）
- Race 8 状态生命周期（`publish/open-registration/start/...`）
- Work seal 触发器（`trg_works_sealed`）
- JudgeAssignment / JudgingRecord / Award（C 自己的领域）
- CAConnection / CASession / Live Hall / Evidence Timeline（D 自己的领域）

---

## 4. 验证证据

```bash
pytest backend/tests/test_b_upstream_contracts.py -q
```

4 项测试覆盖：

1. `works` 表 16 个约定字段存在
2. `WorkDAO` 创建 draft → 提交 submitted → 按 RaceProject / Race 查询
3. `find_public_by_race()` 正确过滤 disqualified 作品，`set_disqualified()` / `restore()` 可逆
4. `RaceProjectDAO` 6 个方法供 D 继续使用
