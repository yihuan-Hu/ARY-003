# ARY 文档索引

本文用于帮助 Agent 和开发者快速找到当前权威文档。任务定义入口是根目录 `team-division.md`，任务状态见根目录 `STATUS.md`。

## 文档路由

| 文档 | 作用 |
| --- | --- |
| `contracts.md` | 人员 A 接口契约：装饰器签名、BaseDAO、错误码、g 对象。 |
| `ary-mvp.prd.md` | 产品目标、MVP 范围、角色路径、产品验收口径。 |
| `ary-domain-analysis.v0.3.md` | 领域概念、核心对象、关系和不变量。 |
| `ary-mvp.ia.md` | 信息架构、页面层级、导航、页面状态和 URL 建议。 |
| `ary-permission-matrix.md` | 资源动作级权限、角色范围和接口鉴权输入。 |
| `ary-ca-integration-spec.md` | CA 接入契约：CAConnection 登记与握手、push/fetch 边界、骑行状态消息。 |
| `b-upstream-contracts-for-cd.md` | 人员 B 冻结给 C/D 的上游契约：`works` 表、`WorkDAO` 签名。 |
| `deployment.md` | 部署步骤、环境变量、监控、备份、值守和回滚。 |
| `mock-server.md` | 本地 Mock Server 使用说明。 |
| `security-review.md` | 安全复核报告。 |

## 阅读建议

- 产品/范围：`ary-mvp.prd.md`
- 架构/模型/权限：`ary-domain-analysis.v0.3.md` + `ary-permission-matrix.md`
- 页面/体验：`ary-mvp.ia.md` + `../design-prototype/`
- 开发接口：`contracts.md` + `b-upstream-contracts-for-cd.md`
- 验收/上线：`../require.md`（含 QA 计划）+ `deployment.md`
- 项目推进：`../team-division.md` + `../STATUS.md`
