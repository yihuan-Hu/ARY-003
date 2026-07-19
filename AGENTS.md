# AGENTS.md

本文定义 ARY 项目中 Agent 协作的长期规则。业务细节以 `docs/` 下的权威文档为准。

## 工作规范

* 项目文档、计划、状态更新和协作说明优先使用中文。
* 开始任务前先读本文件，然后读 `team-division.md` 中自己的章节。
* 不把临时进度写进长期规则；任务状态写入 `STATUS.md`。
* 修改长期范围、验收口径或发布要求时，同步更新对应的 `docs/` 文档。

## 文档入口

* 当前任务分配：`team-division.md`（五人分工）
* 上线需求规格：`require.md`
* 产品入口：`docs/ary-mvp.prd.md`
* 领域模型：`docs/ary-domain-analysis.v0.3.md`
* 权限矩阵：`docs/ary-permission-matrix.md`
* 信息架构：`docs/ary-mvp.ia.md`
* CA 接入：`docs/ary-ca-integration-spec.md`
* A 接口契约：`docs/contracts.md`
* B 上游契约：`docs/b-upstream-contracts-for-cd.md`
* 文档路由：`docs/README.md`
* 任务看板：`STATUS.md`

## 执行纪律

* 实施前确认目标、产出、验收口径和不做事项（从 `team-division.md` 获取）。
* 完成任务或改变产物后，更新 `STATUS.md`。
* 重要结论必须能追溯到用户指令、仓库文件或验证结果。
* 跨模块修改在群里沟通后再改公共文件（`database.py`、`__init__.py`、`openapi.yaml`、`.env.example`、CI 文件）。
* 质量标准：对标 `backend/app/utils/rate_limit.py`（生产级实现模式）。
