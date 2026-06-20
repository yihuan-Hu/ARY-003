# ARY Organizer Backend

这是当前可运行的 ARY Organizer / Jumbotron 后端包，技术栈为 Flask + SQLite。

本包适合用于：

* 演示赛事、Rider、Racing Entry 和 Jumbotron Snapshot。
* 记录 Agent API Usage、token、成本与延迟。
* 提交受保护且不可修改的 Submission。
* 作为新 ARY MVP 后端重构的工程底座。

注意：当前业务模型仍属于旧 PoC / Jumbotron 模型，并不等于最新 ARY MVP 的完整实现。最新模型中的 Registration、RaceProject、CAConnection、Work、评审、Award、Evidence 和 Report 尚未在本包中实现。

## Partner 快速开始

要求：

* Python 3.10+
* PowerShell、CMD 或其他终端

在 `backend/` 目录执行：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
pytest tests -q
python app.py
```

服务地址：

```text
http://127.0.0.1:5000
```

常用页面：

```text
/admin
/public
/jumbotron
/calibrator
```

首次启动会自动创建本地 `organizer.db`。该文件是运行产物，不包含在分享包中。

## 环境变量

参考 `.env.example`。当前程序不会自动读取 `.env`，请通过终端或运行环境设置变量。

PowerShell 示例：

```powershell
$env:ARY_JWT_SECRET = "replace-with-a-random-secret"
$env:ARY_SUBMISSION_SECRET = "replace-with-a-random-secret"
$env:ORGANIZER_DB = "C:\temp\ary-organizer.db"
python app.py
```

本地开发未设置 secret 时会使用开发默认值。不要把默认值用于评审环境或生产环境。

## Demo 数据

从 `backend/` 目录执行：

```powershell
python -m scripts.seed_demo
```

脚本会通过 Flask test client 创建一组 Race、Rider、Entry、Submission、Agent Usage 和 Track Profile，并打印对应的 Jumbotron Snapshot URL。

## 当前 API

推荐优先使用带命名空间的接口。

### Auth

| Method | Path | 说明 |
| --- | --- | --- |
| POST | `/api/v1/auth/login` | 本地开发登录并获取 JWT |

开发种子账号：

| Username | Password | Role |
| --- | --- | --- |
| `contestant` | `contestant123` | contestant |
| `organizer` | `organizer123` | organizer |
| `admin` | `admin123` | admin |

### Organizer

以下接口要求 organizer 或 admin token：

```text
POST /api/v1/organizer/races
PUT  /api/v1/organizer/races/{raceId}
GET  /api/v1/organizer/riders
POST /api/v1/organizer/riders
GET  /api/v1/organizer/entries
POST /api/v1/organizer/entries
POST /api/v1/organizer/track-profiles
GET  /api/v1/organizer/agent-usage
POST /api/v1/organizer/agent-usage
GET  /api/v1/organizer/stats
```

### Contestant

```text
GET  /api/v1/contestant/races
GET  /api/v1/contestant/races/{raceId}
POST /api/v1/contestant/submissions
POST /api/v1/contestant/submissions/verify
```

Race 读取目前公开；Submission 写入和验证要求合法 token。

### Public / Display

```text
GET /api/jumbotron/snapshot?raceId={raceId}
GET /api/stats
```

### Legacy 兼容接口

`/api/races`、`/api/riders`、`/api/entries`、`/api/submissions`、`/api/track-profiles`、`/api/agent-usage` 和 `/api/export/*` 为旧客户端兼容路径。

敏感写入、导出和内部查询仍有角色校验。新开发优先使用 `/api/v1/*`，不要再为 Legacy 路径增加新业务能力。

## 目录结构

```text
backend/
├── app.py
├── config.py
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── database/
│   ├── connection.py
│   ├── schema.py
│   └── migrations/
├── daos/
├── services/
├── routes/
├── schemas/
├── utils/
├── tests/
├── scripts/
│   └── seed_demo.py
└── docs/
    ├── MODULE_FLOW.md
    └── SECURITY_MODEL.md
```

调用方向：

```text
Route -> Service -> DAO -> SQLite
```

## 数据库

当前自动初始化的主要表：

* `races`
* `riders`
* `users`
* `racing_entries`
* `track_profiles`
* `agent_api_usage`
* `submissions`

应用启动时由 `database/schema.py` 自动创建或补齐当前结构。`database/migrations/` 保留历史迁移记录；新环境直接启动应用即可，不需要手工执行旧迁移。

## Submission 安全

Submission 原文默认不会以明文暴露给普通 API、CSV 或 Jumbotron。

后端保存：

* 公开摘要。
* SHA-256 hash。
* 使用 `ARY_SUBMISSION_SECRET` 生成的 HMAC commitment。

Submission 创建后由 Service 和 SQLite trigger 双重禁止修改。详细说明见 `docs/SECURITY_MODEL.md`。

## 测试

运行全部测试：

```powershell
pytest tests -q
```

整理分享包时的基线结果：

```text
21 passed
```

测试会使用临时 SQLite 数据库，不依赖分享包中的本地数据库文件。

## 当前边界

当前实现有意保持 PoC 级技术复杂度：

* 使用原生 `sqlite3`，没有 ORM。
* JSON Schema 目前作为契约参考，不做运行时强制校验。
* Migration 使用 SQL 文件，没有 Alembic。
* 本地登录不是 GitHub OAuth。
* 当前单值角色模型尚未升级为最新文档要求的多角色集合。
* Jumbotron Snapshot 是聚合读取接口，不是正式可重建 Projection。

进一步开发前，请先阅读 `docs/MODULE_FLOW.md` 和仓库上层的当前 MVP 文档，避免把新领域职责继续堆入 `racing_entries`。
