# B 给 C/D 的上游契约冻结说明

冻结时间：2026-07-15

来源：`team-division.md` 中人员 B「赛事核心域」第一批上游交付要求。

## 1. 给 C：Work 表结构

C 的评审、榜单、导出、Review Readiness 和骑手档案可先依赖 `works` 表，不需要等待完整 Work API。

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

说明：

* `race_project_id` 是作品所属参赛工作区。
* `work_status='draft'` 表示 Rider 草稿；`submitted` 表示进入 C 的评审池。
* `visibility='public'` 且未取消资格的 submitted work 可进入公开 Works / Work Page。
* `content_hash`、`content_commitment`、`prev_hash`、`version` 是完整性链占位；生成策略由后续 WorkService 完成。
* `disqualified`、`disqualify_reason` 供 C 的榜单排除、恢复资格和导出逻辑使用。

## 2. 给 C：WorkDAO 签名

文件：`backend/app/dao/work_dao.py`

```python
class WorkDAO(BaseDAO):
    table = "works"

    def create_draft(self, race_project_id: int, title: str, **fields) -> dict
    def find_by_race_project(self, race_project_id: int) -> list[dict]
    def find_submitted_by_race(self, race_id: int) -> list[dict]
    def find_public_by_race(self, race_id: int) -> list[dict]
    def mark_submitted(
        self,
        work_id: int,
        content_hash: str,
        content_commitment: str,
        prev_hash: str | None = None,
    ) -> dict | None
    def set_disqualified(self, work_id: int, reason: str) -> dict | None
    def restore(self, work_id: int) -> dict | None
```

C 可先基于 `find_submitted_by_race()` 构建评审分配池，基于 `find_public_by_race()` 构建公开作品列表，基于 `set_disqualified()` / `restore()` 支撑榜单排除和误判恢复。

## 3. 给 D：RaceProjectDAO 依赖边界

D 的 CAConnection、Session Ingestion、Live Hall 和 Evidence Timeline 可继续依赖现有 `RaceProjectDAO`：

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

D 当前可依赖字段：

* `id`
* `registration_id`
* `aggregate_ingestion_status`
* `connection_health`
* `primary_work_id`
* `created_at`
* `updated_at`

约束：

* RaceProject 仍只由 Registration approve 原子生成，D 不应手动创建参赛工作区。
* `aggregate_ingestion_status` 与 `connection_health` 可作为 CA 聚合状态落点，但 CAConnection / CASession 表不在本次 B 冻结范围。
* `primary_work_id` 是 Work 主链接占位；D 不应把 CA Session 当作 Work 或替代 Work。

## 4. 本轮不做事项

* 不实现完整 Work CRUD 路由。
* 不实现 WorkService 的 HMAC commitment 生成和完整 hash 链。
* 不实现 Race 完整生命周期状态机。
* 不实现 JudgeAssignment、JudgingRecord、Award。
* 不实现 CAConnection、CASession、Live Hall 或 Evidence Timeline。

## 5. 验证证据

本轮冻结测试：

```bash
pytest backend/tests/test_b_upstream_contracts.py -q
```

覆盖内容：

* `works` 表字段存在。
* `WorkDAO` 可创建 draft、提交为 submitted、按 RaceProject / Race 查询。
* `find_public_by_race()` 会过滤取消资格作品。
* `RaceProjectDAO` 给 D 的既有依赖方法仍可用。
