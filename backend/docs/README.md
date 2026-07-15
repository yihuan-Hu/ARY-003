# Backend 文档

## 当前文档

| 文档 | 作用 |
|------|------|
| `../README.md` | 启动、测试、接口入口和当前边界。 |
| `../../docs/contracts.md` | 人员 A 冻结的接口契约（装饰器、BaseDAO、g对象、错误类）。 |
| `../../docs/b-upstream-contracts-for-cd.md` | 人员 B 冻结给 C/D 的上游契约（Work 表 + DAO 签名）。 |
| `../../team-division.md` | 五人分工方案（当前权威任务定义）。 |
| `../../require.md` | 上线需求规格说明书。 |

旧实现说明（`MODULE_FLOW.md`、`SECURITY_MODEL.md`、`RACEPROJECT_COMPATIBILITY.md`）已归档至 `archive/`。

## 当前实现状态

| 能力 | 状态 | 负责人 |
|------|------|--------|
| 认证与安全基座（SQL注入修复/随机盐密码/JWT/限流/CSRF/日志/BaseDAO/@validate/integrity_log/audit_logs） | ✅ 已实现 | 人员 A |
| 接口契约（contracts.md） | ✅ 已冻结 | 人员 A |
| Race 8 状态生命周期 | ❌ 待实现 | 人员 B |
| Registration 扩展（分页/状态校验） | ❌ 待实现 | 人员 B |
| Work 作品管理（草稿/提交/hash链/富媒体） | ❌ 待实现 | 人员 B |
| 公开赛事浏览 + Riding Coach | ❌ 待实现 | 人员 B |
| 赛事公告（Announcement） | ❌ 待实现 | 人员 B |
| 评审系统（邀请/分配/评分/盲审/截止/取消资格） | ❌ 待实现 | 人员 C |
| 奖项榜单 + CSV导出 + Review Readiness + RiderProfile + Report | ❌ 待实现 | 人员 C |
| CA 全链路（双模式/向导/Ingestion/Live Hall/Evidence Timeline） | ❌ 待实现 | 人员 D |
| GitHub OAuth + 旧系统收尾 | ❌ 待实现 | 人员 D |
| 前端（15+ 页）+ CI/CD + Docker + e2e + 上线 | ❌ 待实现 | 人员 E |
