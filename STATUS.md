# STATUS

本文是 ARY 任务瞬时看板，记录当前任务状态、证据和风险。不记录历史流水。

## 当前结论

* 项目处于**五人并行冲刺**阶段。分工见 `team-division.md`。
* 角色 1/2/3/4 已交付并合并。人员 A（认证与安全基座）已交付。
* 人员 B 已冻结给 C/D 的上游契约（`docs/b-upstream-contracts-for-cd.md`），正在实现剩余 6 个模块。
* 人员 C、D、E 已开工。
* 旧任务体系（角色 1-5、`docs/ary.plan.md`）已归档至 `docs/archive/`。
* 当前正式任务定义入口是根目录 `team-division.md`。

## 任务看板

| 任务 | 负责人 | 状态 | 证据 / 下一入口 |
| --- | --- | --- | --- |
| 认证与安全基座 | 人员 A | ✅ 已交付 | `docs/contracts.md`、bandit 零告警、66 项回归通过 |
| B 上游契约（Work 表 + DAO） | 人员 B | ✅ 已冻结 | `docs/b-upstream-contracts-for-cd.md`、4 项测试通过 |
| Race 8 状态生命周期 | 人员 B | 🔄 进行中 | `docs/prompt-b-implementation.md` 模块 1 |
| Registration 扩展 | 人员 B | 🔄 进行中 | `docs/prompt-b-implementation.md` 模块 2 |
| Work CRUD + hash 链 + 触发器 | 人员 B | 🔄 进行中 | `docs/prompt-b-implementation.md` 模块 3 |
| 公开 API + Riding Coach + 公告 | 人员 B | 🔄 进行中 | `docs/prompt-b-implementation.md` 模块 4-6 |
| 评审系统（邀请/分配/评分/盲审） | 人员 C | 🔄 进行中 | `team-division.md` §人员 C |
| 奖项榜单 + CSV 导出 + Review Readiness | 人员 C | 🔄 进行中 | `team-division.md` §人员 C |
| RiderProfile + Report | 人员 C | 🔄 进行中 | `team-division.md` §人员 C |
| CA 全链路（双模式/向导/Ingestion） | 人员 D | 🔄 进行中 | `team-division.md` §人员 D |
| Live Hall + Evidence Timeline | 人员 D | 🔄 进行中 | `team-division.md` §人员 D |
| GitHub OAuth + 旧系统收尾 | 人员 D | 🔄 进行中 | `team-division.md` §人员 D |
| OpenAPI 契约 + 前端 | 人员 E | 🔄 进行中 | `team-division.md` §人员 E |
| CI/CD + Docker + e2e + 上线 | 人员 E | 🔄 进行中 | `team-division.md` §人员 E |

## 证据索引

| 结论 | 证据 |
| --- | --- |
| 五人分工方案 | `team-division.md` |
| 上线需求规格 | `require.md` |
| 人员 A 接口契约 | `docs/contracts.md` |
| 人员 A 安全加固完整 | `backend/app/utils/auth.py`、`rate_limit.py`、`logging.py`、`validation.py`、`permissions.py`；`backend/app/dao/base.py`；`backend/app/database.py` |
| B 给 C/D 的上游契约 | `docs/b-upstream-contracts-for-cd.md` |
| B 的实现提示词 | `docs/prompt-b-implementation.md` |
| 业务文档集中管理 | `docs/`（7 份有效文档 + `docs/archive/` 6 份归档） |
| 归档的文件（不可再引用） | `docs/archive/ary.plan.md`、`ux-hifi.taskbook.md`、`registration-ca-rules-alignment.taskbook.md` |
| A 完成后 66 项回归通过 | `pytest tests/test_checkpoint.py tests/test_registration_state_machine.py tests/legacy -q` |

## 风险与阻塞

| 项目 | 状态 |
| --- | --- |
| 过期的 PLAN/STATUS 引用已清理 | ✅ 本文件 + PLAN.md + AGENTS.md 已更新 |
| 旧文档归档 | ✅ 6 个文件移至 `docs/archive/` 和 `backend/docs/archive/` |
| 网络连 GitHub 不稳定 | ⚠️ SSL_ERROR_SYSCALL，间歇性不可用 |
