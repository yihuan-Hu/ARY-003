# 角色一 操作手册：集成负责人 / 领域与数据库主线

## 一、角色定位

你是本 Checkpoint 的**集成负责人**，负责"骨架"和"事实底座"。你定义的表结构和事务入口会被角色二、三、四直接依赖。你的决策直接影响整个两天的交付成败。

---

## 二、目标一句话

> **在保留现有后端可运行能力的前提下，建立符合新文档的最小参赛事实链（User → Race → Registration → RaceProject），并用数据库约束保证核心不变量成立。**

---

## 三、交付物清单（Checkpoint 结束必须全部完成）

| 序号 | 交付物 | 验收标准 |
|------|--------|----------|
| 1 | 数据库 Schema 和 Migration | 新表可创建，旧表不被删除，可重复执行 |
| 2 | `users` 多角色过渡方案 | 支持 `roles` 集合或等价设计，非单值数字 |
| 3 | `races` 增加 `created_by_user_id` / organizer 关系 | 能表达"谁管理哪个 Race" |
| 4 | `registrations` 表 | 含状态枚举 `submitted/approved/rejected/withdrawn` |
| 5 | `race_projects` 表 | 含最小字段 + `UNIQUE(registration_id)` |
| 6 | 数据库级约束 | `UNIQUE(race_id, user_id)` 等，不能只依赖接口 |
| 7 | Registration approved → RaceProject 单事务入口 | Service 层方法，确保一次 approve 只生成一个 RaceProject |
| 8 | DAO 基础接口 | 供角色二、三、四调用的 CRUD 方法 |
| 9 | 数据模型说明文档/注释 | 表结构含义、约束原因、与其他角色的契约说明 |
| 10 | 旧表保留策略说明 | 明确哪些旧表不动、为什么不删 |

---

## 四、Checkpoint 失败条件（必须避免）

- ❌ RaceProject 由 Rider 手动创建
- ❌ RaceProject approve 重试后出现重复记录
- ❌ Registration 和 RaceProject 没有数据库唯一约束，只依赖接口判断
- ❌ 新逻辑直接写入 `racing_entries`，继续扩大万能表
- ❌ 旧测试大量失效且没有兼容说明

---

## 五、两天分步操作

### 📅 第一天上午（90 分钟）：锁契约

这是全员共同完成的部分，你作为集成负责人需要**主导**以下事项：

**1. 确认领域模型（15 分钟）**

与所有人确认最终表结构，建议如下：

```
users
├── id (PK)
├── username
├── password_hash
├── roles (JSON 数组或关联表)  ← 替代原来的单值 role
├── github_user_id (nullable)  ← 为未来 GitHub OAuth 预留
├── github_login (nullable)
├── profile_completed (boolean, default false)
├── created_at
└── updated_at

races
├── id (PK)
├── name / slug
├── status (upcoming/open/judging/ended)
├── created_by_user_id (FK → users.id)  ← 新增 Organizer 关系
├── visibility / rules / schedule 等
├── created_at
└── updated_at

registrations  ← 全新表
├── id (PK)
├── race_id (FK → races.id)
├── user_id (FK → users.id)
├── status (ENUM: submitted / approved / rejected / withdrawn)
├── submitted_at
├── reviewed_at
├── reviewed_by_user_id (FK → users.id, nullable)
├── UNIQUE (race_id, user_id)  ← 核心约束
├── created_at
└── updated_at

race_projects  ← 全新表
├── id (PK)
├── registration_id (FK → registrations.id, UNIQUE)  ← 一对一约束
├── aggregate_ingestion_status (default: 'not_configured')
├── connection_health (default: 'no_signal')
├── created_at
└── updated_at
```

**2. 确认 API 路径契约（10 分钟）**

与角色三、四确认文档中定义的路径：

```
POST   /api/v1/rider/races/{raceId}/registrations         ← 角色三
GET    /api/v1/rider/registrations                         ← 角色三
GET    /api/v1/rider/registrations/{registrationId}        ← 角色三
GET    /api/v1/rider/race-projects/{raceProjectId}         ← 角色四

GET    /api/v1/organizer/races/{raceId}/registrations      ← 角色三
POST   /api/v1/organizer/registrations/{registrationId}/approve  ← 角色三
POST   /api/v1/organizer/registrations/{registrationId}/reject   ← 角色三
GET    /api/v1/organizer/races/{raceId}/race-projects      ← 角色四
```

**3. 确认文件所有权（10 分钟）**

你是 `database/` 和核心 migration 的唯一负责人。跨负责人文件修改前先同步。

**4. 确认事务入口归属（10 分钟）**

你提供事务方法，角色三调用：

- 方法名建议：`registration_service.approve_and_create_race_project(registration_id, reviewer_user_id)`
- 此方法必须在**同一事务**内完成 status 更新和 RaceProject 插入

---

### 📅 第一天下午（3-4 小时）：并行实现

**你的任务清单：**

#### 步骤 1：建立 Migration（第 1 小时）

```sql
-- 1. 修改 users 表：添加 roles 字段和多角色支持
ALTER TABLE users ADD COLUMN roles TEXT NOT NULL DEFAULT '["contestant"]';
-- 或新建 user_roles 关联表

-- 2. 修改 users 表：添加 GitHub 预留字段
ALTER TABLE users ADD COLUMN github_user_id TEXT;
ALTER TABLE users ADD COLUMN github_login TEXT;
ALTER TABLE users ADD COLUMN profile_completed INTEGER DEFAULT 0;

-- 3. 修改 races 表：添加 created_by_user_id
ALTER TABLE races ADD COLUMN created_by_user_id INTEGER REFERENCES users(id);

-- 4. 创建 registrations 表
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id INTEGER NOT NULL REFERENCES races(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'submitted'
        CHECK (status IN ('submitted', 'approved', 'rejected', 'withdrawn')),
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at TEXT,
    reviewed_by_user_id INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (race_id, user_id)
);

-- 5. 创建 race_projects 表
CREATE TABLE IF NOT EXISTS race_projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_id INTEGER NOT NULL UNIQUE REFERENCES registrations(id),
    aggregate_ingestion_status TEXT NOT NULL DEFAULT 'not_configured',
    connection_health TEXT NOT NULL DEFAULT 'no_signal',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

> ⚠️ **关键原则**：不在本轮删除旧表（`riders`, `racing_entries`, `submissions`, `track_profiles`, `agent_api_usage`），保持旧测试能通过。

#### 步骤 2：编写 DAO 层（第 2 小时）

为每张新表编写 DAO，至少包含：

**RegistrationDAO：**

```python
class RegistrationDAO:
    def create(self, race_id, user_id) -> Registration
    def find_by_id(self, registration_id) -> Registration | None
    def find_by_race_and_user(self, race_id, user_id) -> Registration | None
    def find_by_race(self, race_id) -> list[Registration]
    def find_by_user(self, user_id) -> list[Registration]
    def update_status(self, registration_id, new_status, reviewer_user_id) -> bool
```

**RaceProjectDAO：**

```python
class RaceProjectDAO:
    def create(self, registration_id) -> RaceProject
    def find_by_id(self, race_project_id) -> RaceProject | None
    def find_by_registration(self, registration_id) -> RaceProject | None
    def find_by_race(self, race_id) -> list[RaceProject]
    def count_by_registration(self, registration_id) -> int  # 幂等检查
```

#### 步骤 3：实现核心事务入口（第 3 小时）

这是你**最重要的代码**，是 Checkpoint 的命脉：

```python
# registration_service.py

class RegistrationService:
    def __init__(self, dao: RegistrationDAO, race_project_dao: RaceProjectDAO, db):
        self.dao = dao
        self.race_project_dao = race_project_dao
        self.db = db

    def approve_registration(self, registration_id: int, reviewer_user_id: int):
        """
        事务入口：审批报名并幂等生成 RaceProject

        - 必须在同一事务中完成
        - 重复调用不产生第二个 RaceProject
        - 只有 approved 状态才生成 RaceProject
        """
        with self.db.transaction():  # 确保事务
            # 1. 验证 registration 存在且状态为 submitted
            reg = self.dao.find_by_id(registration_id)
            if reg is None:
                raise NotFoundError("Registration not found")
            if reg.status == 'approved':
                # 已经 approved，幂等返回已有 RaceProject
                existing = self.race_project_dao.find_by_registration(registration_id)
                return existing  # 不创建第二个
            if reg.status != 'submitted':
                raise InvalidStateError(
                    f"Cannot approve registration in '{reg.status}' status"
                )

            # 2. 更新状态
            self.dao.update_status(registration_id, 'approved', reviewer_user_id)

            # 3. 幂等检查后创建 RaceProject
            existing = self.race_project_dao.find_by_registration(registration_id)
            if existing:
                return existing  # 双重保险

            race_project = self.race_project_dao.create(registration_id)
            return race_project
```

#### 步骤 4：Integration 窗口（第 4 小时，第一天结束前）

与其他人合并代码，验证：

```bash
# 1. 数据库可初始化
flask db upgrade  # 或你的 migration 命令

# 2. 新表可创建
sqlite3 ary.db ".tables"  # 应看到 registrations, race_projects

# 3. 基础 DAO 可调用
# 跑角色五的第一个测试
```

---

### 📅 第二天上午（3-4 小时）：打通主链

#### 重点任务：

**1. 集成 Registration approve 事务（第 1-2 小时）**

与角色三配对：

- 确保角色三的 approve API 调用了你的 `approve_registration` 方法
- 确保异常情况（registration 不存在、状态非法）返回正确错误码

**2. 幂等验证（第 2 小时）**

与角色五一起执行以下场景：

```
创建 Organizer 和 Rider
→ Organizer 创建 Race
→ Rider 提交 Registration (角色三)
→ Organizer approve (调用你的事务入口)
→ 查询 RaceProject 出现 1 个
→ 再次 approve (调用同一入口)
→ 验证仍然只有 1 个 RaceProject  ← 关键
```

**3. 数据库约束复核（第 2-3 小时）**

直接操作数据库验证：

```sql
-- 验证唯一约束
INSERT INTO registrations (race_id, user_id, status) VALUES (1, 1, 'submitted');
-- 再次插入相同 race_id + user_id
INSERT INTO registrations (race_id, user_id, status) VALUES (1, 1, 'submitted');
-- ↑ 预期报错：UNIQUE constraint failed

-- 验证一个 registration 只有一个 race_project
INSERT INTO race_projects (registration_id) VALUES (1);
-- 再次插入相同 registration_id
INSERT INTO race_projects (registration_id) VALUES (1);
-- ↑ 预期报错：UNIQUE constraint failed
```

**4. 完善 DAO 接口（第 3-4 小时）**

确保角色二、四需要的查询接口都已提供并且正确。

---

### 📅 第二天下午（3 小时）：冻结与收口

**只做以下事情，不做任何新功能：**

| 时间 | 操作 |
|------|------|
| 14:00-14:30 | 运行全量测试 → `pytest tests -q` |
| 14:30-15:00 | 逐条检查数据库约束是否全部落库 |
| 15:00-15:30 | 旧测试兼容性检查，记录失效原因 |
| 15:30-16:00 | 与角色四配对完成 Demo 脚本 |
| 16:00-16:30 | 编写已知问题清单 + 数据模型说明 |
| 16:30-17:00 | 最终 Checkpoint 评审演示 |

---

## 六、Checkpoint 最终评审演示清单

你必须准备好演示以下 7 项：

```
☐ 1. 新数据库初始化成功
      flask db upgrade 执行无报错，新表全部存在

☐ 2. 演示 Rider 报名（通过角色三的 API）

☐ 3. 演示 Organizer 审核（调用你的事务入口）

☐ 4. 演示 RaceProject 自动生成
      查询 race_projects 表确认记录已创建

☐ 5. 演示重复审核不重复生成
      连续 approve 两次，SELECT COUNT(*) FROM race_projects WHERE registration_id=? 返回 1

☐ 6. 演示越权被拒绝（与角色二一起）
      Rider 不能查看他人 Registration / RaceProject

☐ 7. 全量测试通过
      pytest tests -q 输出通过 + 旧测试兼容说明
```

---

## 七、文件所有权与协作规则

| 你负责 | 别人负责但有交集时 |
|--------|-------------------|
| `database/` 全部 | 修改前通知角色二/三/四 |
| `models/` 新表定义 | 角色二可能需 User 模型扩展 |
| `dao/registration_dao.py` | 角色三调用 |
| `dao/race_project_dao.py` | 角色四调用 |
| `services/registration_service.py` | 角色三调用 `approve_registration` |
| Migration 文件 | 合并后不再改列名 |

**规则：**

- 每个提交只解决一个明确问题
- 第一天下午和第二天中午各一次集成窗口
- 第二天下午冻结，只接受阻塞修复
- **绝对不在冲刺中顺手重构旧 Jumbotron 代码**

---

## 八、你与其他角色的接口契约

```
角色一（你）提供：
  ├── RegistrationDAO     → 角色三调用
  ├── RaceProjectDAO      → 角色四调用
  ├── approve_registration() 事务入口 → 角色三调用
  └── DB 约束             → 角色五验证

角色一（你）依赖：
  ├── 角色二：current_user / roles / managed_race 判断
  └── 无其他代码依赖（你是底座）
```

---

## 九、操作速查卡

| 如果遇到... | 这样做 |
|-------------|--------|
| 有人想往 `racing_entries` 加字段 | 拒绝，新建独立表 |
| 有人想把 CA 状态放入 Registration | 拒绝，CA 接入状态属于 RaceProject |
| 有人想在 approve 时跳过事务 | 拒绝，必须单事务 |
| 有人想手动创建 RaceProject | 拒绝，只能由 approve 事务生成 |
| 旧测试因新表迁移失败 | 检查 migration 是否修改了旧表结构 |
| 紧急需要你修别人的 bug | 先记下来，除非阻塞 Checkpoint 主链 |

---

## 十、关键不可妥协项

1. **数据库级 UNIQUE 约束**是最后防线——接口校验可能被绕过，约束不能缺
2. **事务一致性**——approve 和 RaceProject 创建必须是同一个数据库事务
3. **幂等性**——同一 registration 被 approve 两次，数据库中只有一个 RaceProject
4. **不删旧表**——`riders`、`racing_entries`、`submissions` 等全部保留，新旧并行
5. **不加万能表**——绝不在 `racing_entries` 上加 Registration、RaceProject 或 CA 字段
