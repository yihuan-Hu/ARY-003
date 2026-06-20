# Backend Module And Flow Guide

本文说明 Organizer Backend 拆分后的模块职责、调用链路和关键接口流向。目标是让后续维护者不用翻完整代码，也能快速知道“东西放在哪里、请求怎么走、要改哪里”。

## 1. 总体结构

```text
backend/
├── app.py                  # Flask app factory，只负责组装
├── config.py               # 环境配置
├── database/               # 数据库连接和建表迁移
├── daos/                   # SQL 数据访问层
├── services/               # 业务逻辑和字段映射
├── routes/                 # Flask Blueprint 路由层
├── schemas/                # JSON Schema 响应契约
├── utils/                  # 通用工具和统一错误
├── tests/                  # pytest 测试
├── scripts/
│   └── seed_demo.py        # 目标模式种子数据
├── docs/                   # 模块和安全说明
└── README.md
```

核心原则：

```text
Route -> Service -> DAO -> SQLite
```

- Route：只取参数、取 JSON、返回 `jsonify()`。
- Service：做业务校验、事务、字段映射、聚合。
- DAO：只写 SQL，不做业务判断。
- SQLite：由 `database/` 统一连接和初始化。

## 2. 启动链路

入口文件：`../app.py`

启动流程：

```text
python app.py
  -> create_app()
  -> 加载 config.py
  -> CORS(app)
  -> init_db()
  -> register_blueprints(app)
  -> register_error_handlers(app)
  -> app.run()
```

`app.py` 不再放业务代码，也不直接写 SQL。它只是 Flask 工厂。

数据库路径来自：

```text
ORGANIZER_DB 环境变量
  或
backend/organizer.db
```

测试时也通过 `ORGANIZER_DB` 指向临时 SQLite 文件。

## 3. 数据库层

目录：`../database/`

### 3.1 connection.py

职责：

- 创建 SQLite 连接
- 设置 `row_factory = sqlite3.Row`
- 开启外键：`PRAGMA foreign_keys = ON`

使用方式：

```python
from database import get_db

conn = get_db()
```

### 3.2 schema.py

职责：

- 创建当前 7 张主要业务表
- 给旧库补 v2 字段
- 创建索引

当前主要表：

- `races`
- `riders`
- `users`
- `racing_entries`
- `track_profiles`
- `agent_api_usage`
- `submissions`

兼容逻辑：

- 老库如果只有 `races` 和 `submissions`，启动时会自动 `ALTER TABLE` 补字段。
- `database/migrations/v001_initial.sql` 是旧 2 表初始结构。
- `database/migrations/v002_target.sql` 是 5 表目标结构迁移脚本。

## 4. DAO 层

目录：`../daos/`

DAO 只做 SQL，不负责：

- 参数校验
- HTTP 状态码
- JSON 字段命名
- 业务异常

各 DAO 职责：

| 文件 | 负责的表/查询 |
| --- | --- |
| `race_dao.py` | `races` CRUD、比赛统计、导出查询 |
| `rider_dao.py` | `riders` 创建和查询 |
| `entry_dao.py` | `racing_entries` 创建、更新、排行、KPI 聚合 |
| `submission_dao.py` | `submissions` 创建、查询、消息查询、导出查询 |
| `track_dao.py` | `track_profiles` 创建、更新、读取 |

典型 DAO 调用：

```python
race = RaceDAO.get_by_id(conn, race_id)
rows = EntryDAO.list_by_race(conn, race_id)
```

DAO 接收 `conn`，事务由 Service 控制。

## 5. Service 层

目录：`../services/`

Service 是业务核心。它负责：

- 校验必填字段
- 校验枚举值
- 打开/关闭 DB 连接
- 控制 `commit()`
- 调用 DAO
- 把数据库 snake_case 字段转成 API camelCase 字段
- 组合复杂响应，例如 Jumbotron snapshot

### 5.1 serializers.py

统一字段映射。

例如：

```text
races.start_time -> startTime
racing_entries.round_progress -> roundProgress
submissions.msg_type -> msgType
```

主要 serializer：

- `race_to_dict()`
- `rider_to_dict()`
- `entry_to_dict()`
- `submission_to_dict()`
- `submission_to_message()`
- `competition_from_race()`

### 5.2 constants.py

统一枚举：

- Race status
- CA provider
- Risk level
- Entry status
- Message type
- Severity

如果以后新增枚举值，优先改这里，再同步 schema。

## 6. Route 层

目录：`../routes/`

每类 API 一个 Blueprint。

| 文件 | URL |
| --- | --- |
| `race_routes.py` | `/api/races/*` |
| `submission_routes.py` | `/api/submissions` |
| `rider_routes.py` | `/api/riders` |
| `entry_routes.py` | `/api/entries` |
| `track_routes.py` | `/api/track-profiles` |
| `jumbotron_routes.py` | `/api/jumbotron/*` |
| `export_routes.py` | `/api/export/*` |
| `stats_routes.py` | `/api/stats` |
| `pages.py` | `/`, `/admin`, `/public`, `/jumbotron`, `/calibrator` |

蓝图注册入口：

```python
routes/__init__.py
```

Route 示例：

```python
@entry_bp.route('', methods=['POST'])
def upsert_entry():
    data = request.get_json(silent=True)
    if not data:
        raise ValidationError('Request body is required')
    payload, status_code = EntryService.upsert_entry(data)
    return jsonify(payload), status_code
```

Route 不写 SQL，不做复杂业务。

## 7. 错误处理链路

文件：`../utils/errors.py`

统一异常：

- `ValidationError` -> HTTP 400
- `NotFoundError` -> HTTP 404
- `ConflictError` -> HTTP 409
- 未捕获 404 -> `{ "error": "Not found" }`
- 未捕获 500 -> `{ "error": "Internal server error" }`

业务层直接抛异常：

```python
raise NotFoundError('Race')
```

最终由 Flask error handler 转成 JSON 响应。

## 7.1 内容安全模块

文件：`../utils/content_security.py`

职责：

- 规范化提交原文
- 计算 `content_hash`
- 使用 `ARY_SUBMISSION_SECRET` 计算 HMAC `content_commitment`
- 生成公开摘要 `content_public_summary`
- 验证用户提供的原文是否匹配已入库 commitment

调用位置：

```text
SubmissionService.upsert_submission()
  -> protect_content()
  -> SubmissionDAO.create()

SubmissionService.verify_submission()
  -> verify_content()
```

注意：

- 该模块不依赖 Flask、DAO 或 Service。
- `database/schema.py` 只在旧数据迁移封存时调用它，目的是把历史明文 submission 转成受保护记录。
- 新提交一律在 Service 层封存后再入库。

## 7.2 组织端与选手端权限隔离

文件：

- `../utils/auth.py`
- `../routes/auth_routes.py`
- `../routes/v1_routes.py`

角色：

```text
role = 0 contestant
role = 1 organizer
role = 2 admin
```

登录链路：

```text
POST /api/v1/auth/login
  -> AuthService.login()
  -> UserDAO.get_by_username()
  -> verify_password()
  -> issue_token()
  -> JSON { token, user }
```

组织端命名空间：

```text
/api/v1/organizer/*
```

统一使用 `@require_organizer`，允许 organizer/admin。

选手端命名空间：

```text
/api/v1/contestant/*
```

其中赛事读取公开，提交和 verify 使用 `@require_contestant`。

旧接口兼容策略：

- 旧 GET race/detail/stats/Jumbotron 保持公开读取。
- 旧 POST/PUT、export、entries、riders、track profile 已加同样的角色校验。
- 这样旧路径不能绕过新的组织端/选手端隔离。

## 8. 关键链路说明

### 8.1 创建比赛

接口：

```text
POST /api/races
```

链路：

```text
race_routes.create_race()
  -> RaceService.create_race()
  -> 校验 title/description/startTime/endTime/status
  -> next_id(conn, 'races', 'race')
  -> RaceDAO.create()
  -> conn.commit()
  -> race_to_dict()
  -> JSON 201
```

返回字段由 `race_to_dict()` 控制。

### 8.2 查询比赛详情

接口：

```text
GET /api/races/<raceId>
```

链路：

```text
race_routes.race_detail()
  -> RaceService.get_race_detail()
  -> RaceDAO.get_by_id()
  -> SubmissionDAO.list_by_race()
  -> race_to_dict() + submission_to_dict()
  -> JSON 200
```

如果比赛不存在：

```text
RaceService -> raise NotFoundError('Race') -> JSON 404
```

### 8.3 创建不可变 Submission

接口：

```text
POST /api/submissions
```

链路：

```text
submission_routes.create_submission()
  -> SubmissionService.upsert_submission()
  -> 校验 raceId/content/studentName 或 riderId
  -> RaceDAO.get_by_id()
  -> 如果有 riderId，RiderDAO.get_by_id()
  -> SubmissionDAO.get_by_race_student()
  -> 如果已存在，返回 409，禁止修改
  -> 如果不存在，next_id() + SubmissionDAO.create()
  -> conn.commit()
  -> submission_to_dict()
  -> JSON 201
```

兼容逻辑：

- 旧模式可以传 `studentName`
- 目标模式可以传 `riderId`
- 如果只传 `riderId`，后端会用 rider 的 name 填 `studentName`
- `content` 原文不会明文返回或落在 `content` 字段，会被转换为公开摘要 + HMAC 承诺
- 创建后不可修改。数据库内置 `trg_submissions_immutable` trigger，任何 `UPDATE submissions` 都会失败

验证提交原文：

```text
POST /api/submissions/verify
  -> SubmissionService.verify_submission()
  -> SubmissionDAO.get_by_id()
  -> verify_content(content, content_commitment)
  -> JSON 200 { matched: true/false }
```

### 8.4 创建 Rider

接口：

```text
POST /api/riders
```

链路：

```text
rider_routes.create_rider()
  -> RiderService.create_rider()
  -> 校验 name
  -> next_id(conn, 'riders', 'rider')
  -> RiderDAO.create()
  -> conn.commit()
  -> rider_to_dict()
  -> JSON 201
```

如果传入已存在的 `id`：

```text
ConflictError -> JSON 409
```

### 8.5 创建或更新 Entry

接口：

```text
POST /api/entries
```

链路：

```text
entry_routes.upsert_entry()
  -> EntryService.upsert_entry()
  -> 校验 raceId/riderId/caProvider/riskLevel/status
  -> RaceDAO.get_by_id()
  -> RiderDAO.get_by_id()
  -> EntryDAO.get_by_race_rider()
  -> 如果存在：保留未传字段，EntryDAO.update()
  -> 如果不存在：next_id()，EntryDAO.create()
  -> conn.commit()
  -> entry_to_dict()
  -> JSON 201 或 200
```

关键点：

- `raceId + riderId` 是业务唯一键。
- Entry 重复提交是更新，不是新增。注意：Submission 不允许重复覆盖。
- 更新时没有传的字段会保留旧值。

### 8.6 查询 Entry 列表

接口：

```text
GET /api/entries?race=<raceId>
```

链路：

```text
entry_routes.list_entries()
  -> EntryService.list_entries()
  -> RaceDAO.get_by_id()
  -> EntryDAO.list_by_race()
  -> 按 round_progress DESC 排序
  -> entry_to_dict(rank=index+1)
  -> JSON 200
```

排行由后端根据 `round_progress` 生成。

### 8.7 写入 Track Profile

接口：

```text
POST /api/track-profiles
```

链路：

```text
track_routes.upsert_track_profile()
  -> TrackService.upsert_track_profile()
  -> 校验 raceId/profile
  -> RaceDAO.get_by_id()
  -> json.dumps(profile)
  -> TrackDAO.get_by_race()
  -> 存在则 TrackDAO.update()
  -> 不存在则 next_id() + TrackDAO.create()
  -> conn.commit()
  -> JSON 201
```

注意：

- 后端不拆解 `profile` 内部结构。
- Calibrator 传什么 JSON，后端就存什么 JSON。
- 读取时原样 `json.loads()` 返回。

### 8.8 Jumbotron Snapshot

接口：

```text
GET /api/jumbotron/snapshot?raceId=<raceId>
```

这是目标模式核心端点。

链路：

```text
jumbotron_routes.jumbotron_snapshot()
  -> JumbotronService.snapshot()
  -> RaceDAO.get_by_id()
  -> EntryDAO.list_by_race()
  -> 对每个 entry 查 SubmissionDAO.latest_for_entry()
  -> entry_to_dict() 附加 rank 和 lastMessage
  -> EntryDAO.kpi_by_race()
  -> RaceDAO.count_open()
  -> SubmissionDAO.recent_messages()
  -> TrackDAO.get_by_race()
  -> competition_from_race()
  -> JSON 200
```

返回结构：

```json
{
  "competition": {},
  "entries": [],
  "kpi": {},
  "messages": [],
  "trackProfile": {}
}
```

其中：

- `competition` 来自 `races`
- `entries` 来自 `racing_entries JOIN riders`
- `lastMessage` 来自每个 entry 最近一条 `submissions`
- `kpi` 来自 `racing_entries` SQL 聚合
- `messages` 来自最近 20 条 `submissions`
- `trackProfile` 来自 `track_profiles.profile_json`

### 8.9 Stats

接口：

```text
GET /api/stats
```

链路：

```text
stats_routes.stats()
  -> StatsService.get_stats()
  -> RaceDAO.count()
  -> SubmissionDAO.count()
  -> SubmissionDAO.distinct_student_count()
  -> RaceDAO.submissions_by_race()
  -> JSON 200
```

这是 Demo 兼容统计接口，字段保持：

权限说明：

- `/api/stats` 是公开聚合读接口，供 public/Jumbotron/Demo adapter 使用。
- `/api/v1/organizer/stats` 是组织端命名空间接口，仍要求 organizer/admin token。

```json
{
  "raceCount": 0,
  "submissionCount": 0,
  "studentCount": 0,
  "submissionsByRace": []
}
```

### 8.10 CSV Export

接口：

```text
GET /api/export/races
GET /api/export/submissions
```

链路：

```text
export_routes
  -> DAO 查询导出行
  -> csv.writer()
  -> Response(text/csv)
```

CSV 使用 UTF-8 BOM：

```python
out.write('\ufeff')
```

这样 Excel 打开中文不容易乱码。

Submission CSV 兼容旧列名：

- 仍保留 `content` 列，避免旧消费者因为缺列失败。
- `content` 现在只包含公开摘要，不包含提交原文。
- 新增 `publicSummary`、`contentCommitment`、`protectionMode`，用于说明保护状态和证明信息。

## 9. Schema 放置规则

目录：`../schemas/`

当前 schema：

- `race.schema.json`
- `submission.schema.json`
- `stats.schema.json`
- `rider.schema.json`
- `entry.schema.json`
- `entries.schema.json`
- `track-profile.schema.json`
- `track-profile-write.schema.json`
- `jumbotron-snapshot.schema.json`

规则：

- API 返回字段变化时，同步更新对应 schema。
- 枚举变化时，同步改 `services/constants.py` 和 schema。
- Schema 目前用于前端契约参考，不在运行时强制校验。

## 10. 新增接口时怎么放

例如要新增：

```text
POST /api/foo
```

推荐步骤：

1. 如果需要新表，先改 `database/schema.py` 和 migration。
2. 新增或扩展 DAO，只写 SQL。
3. 新增或扩展 Service，写校验、事务和字段映射。
4. 新增 Route Blueprint 或加入已有 Blueprint。
5. 在 `routes/__init__.py` 注册 Blueprint。
6. 补 schema。
7. 补测试。

不要把 SQL 写进 Route。

## 11. 测试与验证

安装测试依赖：

```bash
pip install -r requirements-dev.txt
```

运行测试：

```bash
pytest tests/ -v
```

当前测试覆盖：

- Race 创建、详情、更新
- Submission 创建、保护、不可变约束
- Stats
- Entry 创建和查询
- Jumbotron snapshot

其他快速验证：

```bash
python -m compileall backend
```

```bash
python -m scripts.seed_demo
```

`scripts/seed_demo.py` 会通过 Flask test client 创建一组目标模式数据，并输出 snapshot URL。

## 12. 修改定位速查

| 你要改什么 | 优先看哪里 |
| --- | --- |
| URL 或 HTTP 方法 | `routes/` |
| 参数校验 | `services/*_service.py` |
| SQL 查询 | `daos/*_dao.py` |
| 数据库表结构 | `database/schema.py` |
| API 返回字段 | `services/serializers.py` |
| 枚举值 | `services/constants.py` |
| 统一错误格式 | `utils/errors.py` |
| Submission 内容保护 | `utils/content_security.py` |
| RBAC/JWT 权限 | `utils/auth.py` |
| JSON 契约 | `schemas/` |
| 启动配置 | `config.py` |

## 13. 当前设计边界

当前后端仍然保持 PoC 轻量设计：

- 使用原生 `sqlite3`，没有 ORM。
- JSON Schema 不做运行时校验。
- Migration 是 SQL 文件，没有 Alembic。
- Service 自己管理连接和事务。
- Export 路由为了生成 CSV，直接调用 DAO，没有额外 ExportService。

这些都是有意保持简单，方便 Demo 和目标模式快速迭代。
