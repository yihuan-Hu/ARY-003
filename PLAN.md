# PLAN

本文是 ARY 近期任务窗口。长期需求见 `require.md`，分工见 `team-division.md`，任务瞬时状态见 `STATUS.md`。

## 当前阶段

五人并行冲刺。人员 A 已交付，人员 B 已冻结上游契约，C/D/E 正在开发。

## 近期窗口

| 窗口 | 目标 |
| --- | --- |
| B 完成剩余 6 个模块 | Race 状态机 → Registration 扩展 → Work CRUD → 公开 API → Riding Coach → 公告 |
| C 基于 B 契约开 | 评审系统 + 奖项榜单 + 导出 + Review Readiness + RiderProfile + Report |
| D 基于 B 契约开 | CA 全链路 + Live Hall + GitHub OAuth + 旧系统收尾 |
| E 基于 A/B/C/D 开 | OpenAPI + 前端 + CI/CD + Docker + e2e + 上线 |

## 近期任务

| 任务 | 负责人 | 状态 | 下一入口 |
| --- | --- | --- | --- |
| 安全基座 | 人员 A | ✅ 已交付 | `docs/contracts.md` |
| B 上游契约 | 人员 B | ✅ 已冻结 | `docs/b-upstream-contracts-for-cd.md` |
| Race 生命周期 + Work + 公开 API + Coach + 公告 | 人员 B | 🔄 进行中 | `docs/prompt-b-implementation.md` |
| 评审系统 + 奖项榜单 + 导出 + Readiness + Profile + Report | 人员 C | 🔄 进行中 | `team-division.md` §人员 C |
| CA 全链路 + Live Hall + OAuth + 旧系统收尾 | 人员 D | 🔄 进行中 | `team-division.md` §人员 D |
| 集成 + 前端 + CI/CD + Docker + e2e | 人员 E | 🔄 进行中 | `team-division.md` §人员 E |

## 近期里程碑

| 里程碑 | 完成口径 |
| --- | --- |
| B 完成 | 6 个模块全部可测，≥ 18 项测试通过，全量回归 84+ 项通过 |
| C/D 完成 | 各自 ≥ 10 项测试通过，全量回归通过 |
| E 完成 | `docker-compose up` 一键启动，`full_demo.py` 41 步全通过 |

## 执行纪律

* 开工前读 `team-division.md` 中自己的章节 + `docs/contracts.md`。
* 跨模块改动先在群里说明影响范围。
* 新增或修改接口前，先更新 `docs/openapi.yaml` 草稿。
* 近期窗口变化时更新本文；任务状态变化时更新 `STATUS.md`。
* 所有过期引用已清理——不再使用 `docs/ary.plan.md`、`docs/ux-hifi.taskbook.md`、`docs/registration-ca-rules-alignment.taskbook.md`（均已归档至 `docs/archive/`）。
