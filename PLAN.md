# PLAN

本文是 ARY 近期任务窗口。长期需求见 `require.md`，分工见 `team-division.md`，任务瞬时状态见 `STATUS.md`。

## 当前阶段

五人并行冲刺。人员 A、B、C、D、E 已全部交付。

## 近期窗口

| 窗口 | 目标 |
| --- | --- |
| B 交付回归与集成 | 保持 C/D 冻结契约，等待 E 集成 OpenAPI 与端到端流程 |
| C 基于 B 契约开发 | ✅ 评审系统 + 奖项榜单 + 导出 + Review Readiness + RiderProfile + Report |
| D 基于 B 契约开发 | ✅ CA 全链路 + Live Hall + GitHub OAuth + 旧系统收尾 |
| E 基于 A/B/C/D 集成 | ✅ OpenAPI + 前端 + CI/CD + Docker + e2e + 上线 |

## 近期任务

| 任务 | 负责人 | 状态 | 下一入口 |
| --- | --- | --- | --- |
| 安全基座 | 人员 A | ✅ 已交付 | `docs/contracts.md` |
| B 上游契约 | 人员 B | ✅ 已冻结 | `docs/b-upstream-contracts-for-cd.md` |
| Race 生命周期 + Registration + Work + 公开 API + Coach + 公告 | 人员 B | ✅ 已交付 | `backend/tests/test_race_lifecycle.py` 等 7 份 B 专项测试 |
| 评审系统 + 奖项榜单 + 导出 + Readiness + Profile + Report | 人员 C | ✅ 已交付 | 30 项测试通过 |
| CA 全链路 + Live Hall + OAuth + 旧系统收尾 | 人员 D | ✅ 已交付 | 28 项测试通过 |
| 集成 + 前端 + CI/CD + Docker + e2e | 人员 E | ✅ 已交付 | CI/CD 就绪，docker-compose 一键启动 |

## 近期里程碑

| 里程碑 | 完成口径 |
| --- | --- |
| B 完成 | ✅ 6 个模块完成，31 项 B 专项测试覆盖；B 验收集通过 97 项 |
| C/D 完成 | ✅ C 30 项测试通过，D 28 项测试通过，全量回归 183 项通过 |
| E 完成 | ✅ `docker-compose up` 一键启动，`full_demo.py` 33 步全通过，CI/CD 已配置 |

## 执行纪律

* 开工前读 `team-division.md` 中自己的章节 + `docs/contracts.md`。
* 跨模块改动先在群里说明影响范围。
* 新增或修改接口前，先更新 `docs/openapi.yaml` 草稿。
* 近期窗口变化时更新本文；任务状态变化时更新 `STATUS.md`。
* 所有过期引用已清理——不再使用 `docs/ary.plan.md`、`docs/ux-hifi.taskbook.md`、`docs/registration-ca-rules-alignment.taskbook.md`（均已归档至 `docs/archive/`）。
