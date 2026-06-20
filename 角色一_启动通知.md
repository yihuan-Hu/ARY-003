# ARY MVP 第一 Checkpoint 启动通知

**发送人**：角色一（集成负责人）  
**发送时间**：2026-06-20  
**收件人**：角色二、角色三、角色四、角色五  
**主题**：两天冲刺——建立最小参赛事实链

---

## 各位，以下是本次 Checkpoint 的完整安排，请仔细阅读并在第一天上午对齐会上确认各自部分。

---

## 一、Checkpoint 目标

> 在保留现有后端可运行能力的前提下，建立符合新文档的最小参赛事实链，并用自动化测试证明核心不变量成立。

必须跑通的主链：

```
User → 创建 Race → User 提交 Registration
→ Organizer 审核 Registration → Registration approved
→ 系统自动且幂等生成唯一 RaceProject
→ Rider 可读取自己的 Registration 和 RaceProject
```

---

## 二、本次 Checkpoint 明确不做

为了保证两天内交付，本轮**不做**以下内容：

- GitHub OAuth 完整联调（保留本地测试登录，预留字段即可）
- CAConnection 登记和握手实现
- RidingSignalMessage push / Session Snapshot fetch
- Evidence、Projection 和 Review Flag
- Work 完整生命周期
- JudgeAssignment、JudgingRecord、Award 和 Report
- Public Site、完整 Console UI 和 Jumbotron 改版
- 正式生产部署
- 旧 `racing_entries`、`submissions` 和 Jumbotron 子系统的数据迁移

**不得为了赶进度把这些对象塞进 `racing_entries`。**

---

## 三、Checkpoint 交付标准（两天结束时必须具备）

1. 新数据模型已落库：
   - `users` 支持多角色集合
   - `races` 有 `created_by_user_id` / organizer 关系
   - 新增 `registrations` 表
   - 新增 `race_projects` 表
2. 核心约束由数据库或 Service 保证：
   - 一个 User 对同一 Race 最多一个 Registration
   - 一个 Registration 最多一个 RaceProject
   - 只有 approved Registration 自动生成 RaceProject
   - 重复审批不会生成第二个 RaceProject
3. 最小 API 可调用：
   - Rider 提交报名 / 查看自己的报名
   - Organizer 查看 managed race 的报名
   - Organizer approve / reject 报名
   - Rider 查看自动生成的 RaceProject
4. 最小权限成立：
   - Rider 不能查看或修改他人报名和 RaceProject
   - Organizer 不能审核不属于自己 managed race 的报名
   - Public 不能读取后台报名和 RaceProject
5. 自动化测试通过
6. 现有 21 个旧测试不得无说明地失效
7. 有一个可重复执行的 Checkpoint Demo

---

## 四、五人分工

| 角色 | 负责人 | 核心职责 | 交付物 |
|------|--------|----------|--------|
| 角色一 | 组长 | 领域模型、数据库 Schema/Migration、事务入口、集成合并 | Migration + DAO + 事务方法 + 数据模型说明 |
| 角色二 | 待定 | 身份、角色与资源范围权限 | 权限 helper/decorator + 越权测试 |
| 角色三 | 待定 | Registration API 与业务状态机 | Registration 模块 + 状态转换测试 |
| 角色四 | 待定 | RaceProject API、兼容适配与 Demo | RaceProject 查询 + Demo 脚本 |
| 角色五 | 待定 | 测试负责人 / 契约与回归 | 集成测试 + fixture + 回归报告 |

---

## 五、API 路径契约（第一天上午冻结）

```
Rider 侧：
POST   /api/v1/rider/races/{raceId}/registrations
GET    /api/v1/rider/registrations
GET    /api/v1/rider/registrations/{registrationId}
GET    /api/v1/rider/race-projects/{raceProjectId}

Organizer 侧：
GET    /api/v1/organizer/races/{raceId}/registrations
POST   /api/v1/organizer/registrations/{registrationId}/approve
POST   /api/v1/organizer/registrations/{registrationId}/reject
GET    /api/v1/organizer/races/{raceId}/race-projects
```

路径和请求/响应格式在第一天上午对齐会上统一确认，之后不得随意变更。

---

## 六、文件所有权

| 区域 | 主负责人 | 说明 |
|------|----------|------|
| `database/`、核心 migration | 角色一 | 其他人修改前必须同步 |
| `utils/auth.py`、User / role policy | 角色二 | 角色一、三、四调用 |
| Registration DAO / Service / Route | 角色三 | 调用角色一的事务入口 |
| RaceProject DAO / Service / Route、Demo | 角色四 | 调用角色一的 DAO |
| `tests/` 和验收记录 | 角色五 | 覆盖所有角色的接口 |

**跨负责人文件修改前必须先同步。**

---

## 七、两天时间安排

### 第一天上午（90 分钟）：全员锁契约

| 时间 | 事项 | 主持 |
|------|------|------|
| 15 分钟 | 确认 Checkpoint 范围和不做事项 | 角色一 |
| 15 分钟 | 确认表结构、状态枚举、API 路径 | 角色一 |
| 15 分钟 | 确认 User / roles 两天过渡方案 | 角色一 + 角色二 |
| 10 分钟 | 确认 Registration approve 事务由谁实现、谁调用 | 角色一 + 角色三 |
| 10 分钟 | 确认各自文件所有权 | 角色一 |
| 剩余 | 答疑 + 冻结契约 | 全体 |

**当天上午必须冻结 API 契约和表结构。**

### 第一天下午（约 4 小时）：并行开发

| 角色 | 任务 |
|------|------|
| 角色一 | Schema、Migration、DAO、事务入口 |
| 角色二 | Roles、own、managed race 权限 |
| 角色三 | Registration Service 和 Route |
| 角色四 | RaceProject 查询和 Demo 骨架 |
| 角色五 | 测试 fixture 和失败状态下的集成测试 |

**第一天结束前必须完成一次集成**：
```
数据库可初始化 → 新表可创建 → Registration 可提交 → 测试可运行（即使部分失败）
```

> ⚠️ 不接受五个人各自在独立分支完成、第二天晚上才第一次合并。

### 第二天上午（约 4 小时）：打通主链

目标：`报名 → 审核 → 自动生成 RaceProject → own/managed race 查询` 全部跑通。

优先处理：
1. Registration approve 和 RaceProject 创建的事务集成
2. 重复 approve 幂等
3. own / managed race 越权
4. 新旧用户角色兼容
5. API 响应字段统一

**第二天中午前必须有一条完整集成测试通过。**

### 第二天下午（3 小时）：冻结

**停止新增功能**，只做：

| 时间 | 事项 | 负责人 |
|------|------|--------|
| 14:00-14:30 | 全量测试 `pytest tests -q` | 角色五 |
| 14:30-15:00 | 数据库约束复核 | 角色一 |
| 15:00-15:30 | 越权检查 + 旧测试兼容性 | 角色二 + 角色五 |
| 15:30-16:00 | API Demo 录制 | 角色四 |
| 16:00-16:30 | 已知问题记录 | 全体 |
| 16:30-17:00 | Checkpoint 评审演示 | 全体 |

---

## 八、最终 Checkpoint 评审顺序

```
1. 演示新数据库初始化
2. 演示 Rider 报名
3. 演示 Organizer 审核
4. 演示 RaceProject 自动生成
5. 演示重复审核不重复生成
6. 演示越权被拒绝
7. 展示全量测试结果
```

---

## 九、Checkpoint 失败条件（出现任一即判定未完成）

- RaceProject 由 Rider 手动创建
- RaceProject approve 重试后出现重复记录
- Registration 和 RaceProject 没有数据库唯一约束，只依赖接口判断
- Organizer 可以审核任意 Race 的报名
- Rider 可以读取其他 Rider 的 Registration 或 RaceProject
- CA 接入状态被加入 Registration 资格状态
- 新逻辑直接写入 `racing_entries`，继续扩大万能表
- 只有手工演示，没有自动化测试
- 新测试通过但旧测试大量失效且没有兼容说明

---

## 十、协作规则

1. 每个提交只解决一个明确问题
2. Migration 合并后不随意改写已被其他分支使用的列名
3. 第一天下午和第二天中午各做一次集成窗口
4. 第二天下午进入冻结，只接受 Checkpoint 阻塞修复
5. 不在冲刺中顺手重构与 Checkpoint 无关的旧 Jumbotron 代码
6. 不往 `racing_entries` 堆新字段——这是红线
7. 有任何阻塞问题立即在群内同步，不要独自卡住超过 30 分钟

---

## 十一、Checkpoint 后展望

第一 Checkpoint 通过后，第二 Checkpoint 进入：

```
RaceProject
→ CAConnection 登记与握手
→ RidingSignalMessage 幂等接收
→ Session
→ RaceProject 聚合接入状态
→ Review Flag
```

---

**请各位在第一天上午对齐会前通读本通知，带着疑问和建议参会。**

**角色一**
