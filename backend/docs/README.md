# Backend 文档

Partner 建议阅读顺序：

1. `../README.md`：启动、测试、接口入口和当前边界。
2. `MODULE_FLOW.md`：代码目录、调用链和修改定位（**注意：描述的是旧 `routes/`/`daos/`/`services/` 层；新 ARY MVP 模块见 `../app/` 目录**）。
3. `SECURITY_MODEL.md`：Submission 内容保护与权限安全说明。
4. `RACEPROJECT_COMPATIBILITY.md`：**角色 4 交付** — RaceProject API 与旧 `/api/entries`、Jumbotron Snapshot 的兼容性边界分析。

仓库上层的最新 ARY MVP 文档优先于本目录中的实现说明。

## 当前实现状态（Checkpoint 1）

| 能力 | 状态 | 位置 |
|------|------|------|
| Registration（报名/审核） | ✅ 已实现 | `../app/services/registration_service.py`、`../app/routes/rider.py`、`../app/routes/organizer.py` |
| RaceProject（自动生成/查询） | ✅ 已实现 | `../app/services/race_project_service.py`、`../app/routes/rider.py`、`../app/routes/organizer.py` |
| 权限策略（own/managed_race） | ✅ 已实现 | `../app/utils/permissions.py` |
| Demo 脚本 | ✅ 已实现 | `../demo.py`（17/17 步骤通过） |
| CAConnection | ❌ 未实现 | Checkpoint 2 |
| Work 完整生命周期 | ❌ 未实现 | Checkpoint 2 |
| 评审/奖项/报告 | ❌ 未实现 | 后续 Checkpoint |
