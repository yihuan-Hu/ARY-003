# RaceProject API 兼容性分析（角色 4 交付）

日期：2026-06-20
分析范围：旧 `/api/entries`、旧 Jumbotron Snapshot 与新 RaceProject API 的边界

---

## 1. 结论

**旧 `/api/entries` 和 Jumbotron Snapshot 不会被误认为 RaceProject API。** 三者运行在不同的数据库表、不同的 Flask 应用实例和不同的 URL 空间上，不存在数据污染或路由混淆。

---

## 2. 架构隔离

当前仓库有两个 Flask 应用入口，各自独立运行：

| 入口 | 模块 | 数据库表 | 用途 |
|------|------|----------|------|
| `app.py` / `routes/` | 旧 PoC 后端 | `races`, `riders`, `racing_entries`, `submissions`, `track_profiles`, `agent_api_usage` | 旧 Jumbotron / PoC 能力（保留兼容） |
| `app/__init__.py` / `app/routes/` | 新 ARY MVP 后端 | 旧表 + `registrations`, `race_projects`（新增列：`users.roles`, `races.created_by_user_id`） | Checkpoint 1 新参赛事实链 |

测试隔离：
- 旧测试：`tests/legacy/` → 使用 `conftest_legacy.py` → 导入 `app.py` 的 `create_app`
- 新测试：`tests/test_checkpoint.py` → 使用 `conftest.py` → 导入 `app/__init__.py` 的 `create_app`

## 3. 路由空间对比

### 3.1 旧 Entry API（操作 `racing_entries` 表）

| 方法 | 路径 | 蓝图 | 数据表 |
|------|------|------|--------|
| GET | `/api/entries` | `entry_bp` | `racing_entries` |
| POST | `/api/entries` | `entry_bp` | `racing_entries` |
| GET | `/api/v1/organizer/entries` | `organizer_v1_bp` | `racing_entries` |
| POST | `/api/v1/organizer/entries` | `organizer_v1_bp` | `racing_entries` |

### 3.2 旧 Jumbotron Snapshot（聚合 `racing_entries` + `submissions` + `agent_api_usage`）

| 方法 | 路径 | 蓝图 | 数据表 |
|------|------|------|--------|
| GET | `/api/jumbotron/snapshot` | `jumbotron_bp` | 聚合 `racing_entries`, `submissions`, `agent_api_usage`, `track_profiles` |

### 3.3 新 RaceProject API（操作 `race_projects` 表）

| 方法 | 路径 | 蓝图 | 数据表 |
|------|------|------|--------|
| GET | `/api/v1/rider/race-projects/{id}` | `rider_bp` | `race_projects` (JOIN `registrations`) |
| GET | `/api/v1/organizer/races/{raceId}/race-projects` | `organizer_bp` | `race_projects` (JOIN `registrations`) |

### 3.4 路由冲突分析

```
旧 Entry API:
  /api/entries
  /api/v1/organizer/entries
  /api/v1/contestant/entries

新 RaceProject API:
  /api/v1/rider/race-projects/{id}
  /api/v1/organizer/races/{raceId}/race-projects
```

**无冲突：**
- 旧 API 使用 `/entries` 路径段，新 API 使用 `/race-projects` 路径段
- 旧 `/api/v1/organizer/entries` 和新 `/api/v1/organizer/races/{id}/race-projects` 路径完全不同
- 旧 Jumbotron 使用 `/api/jumbotron/snapshot`，与新 API 无交集

## 4. 数据表隔离

| 旧表 | 用途 | 是否被新 RaceProject API 使用 |
|------|------|-------------------------------|
| `racing_entries` | 旧参赛展示/进度/排名 | ❌ 不使用 |
| `submissions` | 不可变消息/封存内容 | ❌ 不使用 |
| `agent_api_usage` | Agent API 调用记录 | ❌ 不使用 |
| `track_profiles` | Jumbotron 赛道配置 | ❌ 不使用 |

| 新表 | 用途 | 是否被旧 API 使用 |
|------|------|-------------------|
| `registrations` | 报名申请/审核 | ❌ 不使用 |
| `race_projects` | 自动生成的参赛工作区 | ❌ 不使用 |

**数据隔离结论：新 RaceProject API 完全不触碰旧表（`racing_entries`, `submissions` 等），旧 API 也不访问新表（`registrations`, `race_projects`）。**

## 5. 语义不混淆

| 概念 | 旧模型 | 新模型 | 区别 |
|------|--------|--------|------|
| 参赛资格 | `racing_entries` (Organizer 手动 upsert) | `registrations` (Rider 自主报名 → Organizer 审核 → approved) | 旧模型无报名审核流程 |
| 参赛工作区 | `racing_entries` 混合报名+项目+指标+排名 | `race_projects` (Registration approved 后系统自动生成，1:1) | 旧模型一个表承载多种语义 |
| 作品/提交 | `submissions` (不可变消息) | `work` (未来，占位字段 `work: null`) | 语义不兼容 |
| 聚合展示 | Jumbotron Snapshot (过程排名) | RaceProject `aggregate_ingestion_status` + `connection_health` | 新模型字段含义明确 |

## 6. Checkpoint 红线验证

按 `小组安排.md` 第九节和 `backend-current-docs-gap-analysis.md` 13.7 节的失败条件逐一验证：

| # | 失败条件 | 当前状态 | 判定 |
|---|----------|----------|------|
| 1 | RaceProject 由 Rider 手动创建 | 无 POST/PUT 路由，Rider 只能 GET | ✅ 通过 |
| 2 | RaceProject approve 重试后出现重复记录 | DB UNIQUE(registration_id) + Service 双重幂等 | ✅ 通过 |
| 3 | Registration 和 RaceProject 没有数据库唯一约束 | UNIQUE(race_id, user_id) + UNIQUE(registration_id) 均存在 | ✅ 通过 |
| 4 | Organizer 可以审核任意 Race 的报名 | `require_managed_race` + Service 层双重校验 | ✅ 通过 |
| 5 | Rider 可以读取他人 Registration/RaceProject | `require_own_registration` + `require_own_race_project` | ✅ 通过 |
| 6 | CA 接入状态进入 Registration 资格状态 | `aggregate_ingestion_status` 只在 RaceProject 上，不影响 Registration | ✅ 通过 |
| 7 | 新逻辑写入 `racing_entries` | `race_projects` 独立表，旧表零触碰 | ✅ 通过 |
| 8 | 只有手工演示，没有自动化测试 | 31 新测试 + 21 旧测试 + demo.py | ✅ 通过 |
| 9 | 新测试通过但旧测试大量失效 | 52 项全部通过 (31 新 + 21 旧) | ✅ 通过 |

## 7. 占位字段说明

RaceProject API 响应中包含两个占位字段，为后续 Checkpoint 2 扩展预留：

```json
{
  "id": 1,
  "registration_id": 1,
  "aggregate_ingestion_status": "not_configured",
  "connection_health": "no_signal",
  "created_at": "2026-06-20T...",
  "ca_connections": [],     // 未来: CAConnection 数组
  "work": null              // 未来: 主 Work 链接
}
```

- `ca_connections: []` — Checkpoint 2 将填充 `CAConnection` 登记和握手后的连接对象数组
- `work: null` — Checkpoint 2 将填充 `Work` 对象引用（draft → submitted → locked → hidden）

这些字段不包含虚假业务数据，仅作为结构预留给前端适配。

---

**分析人**：角色 4
**状态**：已完成，可进入 Checkpoint 评审
