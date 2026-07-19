# STATUS

本文是 ARY 任务瞬时看板，记录当前任务状态、证据和风险。不记录历史流水。

## 当前结论

* 项目处于**五人全部交付**阶段。分工见 `team-division.md`。
* 角色 1/2/3/4 已交付并合并。人员 A（认证与安全基座）已交付。人员 D（CA 全链路 + Live Hall + GitHub OAuth）已交付。
* 人员 B 已完成赛事核心域 6 个模块，并保持给 C/D 的 Work、RaceProject、CA policy 上游契约稳定。
* 人员 C 已完成评审系统 + 奖项榜单 + CSV 导出 + Review Readiness + RiderProfile。30 项 C 专项测试通过。
* 人员 D 已完成 CA 全链路 + Live Hall + GitHub OAuth + 旧系统收尾。28 项 D 专项测试通过。
* 人员 E 已完成集成：OpenAPI + 前端 + CI/CD + Docker + e2e。CI/CD pipeline 已配置，`docker-compose up` 一键启动。
* 前端 UX 审计问题已修复：导航双 Tab 常显、Dashboard RaceProject 参数修正、参与/组织流程入口中文化、评委邀请接受后跳转评审清单。
* 前端上线前轻抛光已完成：用户可见文案统一中文化，参与/组织/评审三个工作区改为任务面板表达。
* 前端 90+ 提分改造已完成：请求层、状态文案、UX helper 拆分到 `frontend/js/`，新增 `docs/final-review.md` 作为期末评审展示材料。
* 期末 95 分冲刺资产已补齐：新增演示数据脚本、冒烟验收脚本、演示路线文档、质量门禁文档、轻量 Vue 组件和首页演示入口。
* 全量测试：183 passed, 0 failed ✅
* 旧任务体系（角色 1-5、`docs/ary.plan.md`）已归档至 `docs/archive/`。
* 当前正式任务定义入口是根目录 `team-division.md`。

## 任务看板

| 任务 | 负责人 | 状态 | 证据 / 下一入口 |
| --- | --- | --- | --- |
| 认证与安全基座 | 人员 A | ✅ 已交付 | `docs/contracts.md`、bandit 零告警、66 项回归通过 |
| B 上游契约（Work 表 + DAO） | 人员 B | ✅ 已冻结 | `docs/b-upstream-contracts-for-cd.md`、4 项测试通过 |
| Race 8 状态生命周期 | 人员 B | ✅ 已交付 | 7 个转换端点、编辑/分页、旧状态约束无损迁移；`test_race_lifecycle.py` |
| Registration 扩展 | 人员 B | ✅ 已交付 | registration 准入、双视角分页、Rider赛事列表、写审计；`test_registration_extensions.py` |
| Work CRUD + hash 链 + 触发器 | 人员 B | ✅ 已交付 | v1/v2 hash/HMAC/integrity、仅 submitting 提交、judging 内容/删除封存；`test_work_integrity.py` |
| 公开 API + Riding Coach + 公告 | 人员 B | ✅ 已交付 | 无认证公开查询、可选 C/D 表 Coach、公告 CRUD/发布/隐藏；3 份专项测试 |
| 评审系统（邀请/分配/评分/盲审） | 人员 C | ✅ 已交付 | 12 测试通过；judge_bp + admin_bp 蓝图 |
| 奖项榜单 + CSV 导出 + Review Readiness | 人员 C | ✅ 已交付 | 10 测试通过；organizer_bp + public_bp 扩展 |
| RiderProfile + Report | 人员 C | ✅ 已交付 | 8 测试通过；rider_bp + public_bp 扩展 |
| CA 全链路（双模式/向导/Ingestion） | 人员 D | ✅ 已交付 | 22 测试通过；`ca_bp` 蓝图 + `ca_connections`/`ca_sessions` 表 + LiveHall/Timeline；`test_ca_connection.py` + `test_ca_ingestion.py` |
| Live Hall + Evidence Timeline | 人员 D | ✅ 已交付 | 4 测试通过；`public_bp` + `rider_bp` + `organizer_bp` 扩展；`test_public_apis.py` |
| GitHub OAuth + 旧系统收尾 | 人员 D | ✅ 已交付 | 2 测试通过；`auth.py` OAuth 端点 + 5 个 `DEPRECATED.md`；`test_github_oauth.py` |
| OpenAPI 契约 + 前端 | 人员 E | ✅ 已交付 | `docs/openapi.yaml` 53.88 KB, 17 页 SPA；`frontend/ux-audit.test.js`；`docs/final-review.md` |
| CI/CD + Docker + e2e + 上线 | 人员 E | ✅ 已交付 | `.github/workflows/ci.yml`, `docker-compose up` 一键启动；`scripts/seed_demo.py`；`scripts/smoke_check.py` |

## 证据索引

| 结论 | 证据 |
| --- | --- |
| 五人分工方案 | `team-division.md` |
| 上线需求规格 | `require.md` |
| 人员 A 接口契约 | `docs/contracts.md` |
| 人员 A 安全加固完整 | `backend/app/utils/auth.py`、`rate_limit.py`、`logging.py`、`validation.py`、`permissions.py`；`backend/app/dao/base.py`；`backend/app/database.py` |
| B 给 C/D 的上游契约 | `docs/b-upstream-contracts-for-cd.md` |
| B 的实现提示词 | `docs/prompt-b-implementation.md` |
| B 6 模块验收 | 31 项 B 专项测试；连同 Checkpoint、Registration、Legacy 共 97 项通过 |
| C 评审 + 奖项 + 导出 + Readiness + Profile | `backend/app/dao/judging_dao.py`、`award_dao.py`；`services/judging_service.py`、`award_service.py`、`readiness_service.py`、`rider_profile_service.py`；`routes/judge.py`、`admin.py`；30 项 C 专项测试通过 |
| D CA 全链路 + Live Hall + OAuth | `backend/app/routes/ca.py`（ca_bp）、`routes/auth.py`（OAuth）；`dao/ca_connection_dao.py`、`ca_session_dao.py`；`services/timeline_service.py`；`database.py`（ca_connections/ca_sessions 表）；28 项 D 专项测试通过；5 个 `DEPRECATED.md` |
| E CI/CD pipeline | `.github/workflows/ci.yml`：lint → test → bandit → pip-audit |
| E 版本标签 | `git tag v1.0.0` |
| 业务文档集中管理 | `docs/`（7 份有效文档 + `docs/archive/` 6 份归档） |
| 归档的文件（不可再引用） | `docs/archive/ary.plan.md`、`ux-hifi.taskbook.md`、`registration-ca-rules-alignment.taskbook.md` |
| A 完成后 66 项回归通过 | `pytest tests/test_checkpoint.py tests/test_registration_state_machine.py tests/legacy -q` |

## 风险与阻塞

| 项目 | 状态 |
| --- | --- |
| 过期的 PLAN/STATUS 引用已清理 | ✅ 本文件 + PLAN.md + AGENTS.md 已更新 |
| 旧文档归档 | ✅ 6 个文件移至 `docs/archive/` 和 `backend/docs/archive/` |
| 网络连 GitHub 不稳定 | ⚠️ SSL_ERROR_SYSCALL，间歇性不可用 |
| 仓库根历史测试套件 | ⚠️ 17 个旧用例依赖已移除的 fixture，另有 4 个旧接口断言失败；不纳入 B 的 97 项验收集，待集成阶段清理或归档 |
