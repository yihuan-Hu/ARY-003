# Submission Security Model

本文说明当前系统如何保护参赛者提交的代码/成果内容，避免攻击者通过公开 API、CSV 导出或 SQLite 数据库直接获得别人的提交原文，并确保提交入库后不可修改。

## 1. 威胁模型

重点防护：

- 攻击者调用公开接口读取别人的 submission。
- 攻击者下载 CSV 导出。
- 攻击者拿到 SQLite 数据库文件后直接查 `submissions.content`。
- 攻击者或误操作尝试覆盖已入库的 submission。
- 选手抓包调用组织端接口，例如创建赛事或导出 CSV。

当前不覆盖：

- 服务器运行时被完全控制。
- `ARY_SUBMISSION_SECRET` 泄露。
- 管理员主动把用户原文复制到 `publicSummary`。

## 2. 设计思路

系统采用“链上承诺/密钥证明”式设计：

```text
原始提交内容
  -> normalize
  -> SHA-256 内容哈希
  -> HMAC-SHA256 内容承诺（使用 ARY_SUBMISSION_SECRET）
  -> 数据库只保存公开摘要 + hash + commitment
```

公开接口只返回：

- `content`: 公开摘要，不是原文
- `contentProtected: true`
- `contentCommitment`: HMAC 承诺
- `protectionMode: sealed_commitment_v1`

原始代码/成果文本不会出现在普通 API 响应、Jumbotron message、CSV 导出或 `submissions.content` 明文字段里。

提交入库后不可变：

- Service 层发现同一个 `raceId + studentName` 已存在时返回 409。
- SQLite 层创建 `trg_submissions_immutable` trigger，任何 `UPDATE submissions` 都会被拒绝。

## 3. 数据库字段

`submissions` 新增字段：

| 字段 | 说明 |
| --- | --- |
| `content` | 向后兼容字段，现在只保存公开摘要 |
| `content_hash` | SHA-256 哈希，用于内部审计 |
| `content_commitment` | HMAC-SHA256 承诺，用于证明某份原文就是当时提交内容 |
| `content_public_summary` | 可公开展示的摘要 |
| `content_protection` | 当前为 `sealed_commitment_v1` |

## 4. 提交流程

接口：

```text
POST /api/submissions
```

请求仍然可以传：

```json
{
  "raceId": "race_001",
  "riderId": "rider_001",
  "content": "private code payload",
  "publicSummary": "提交已封存"
}
```

后端处理：

```text
content 原文
  -> 计算 content_hash
  -> 计算 content_commitment
  -> content 字段改写为 publicSummary 或 [protected submission]
  -> 保存
```

如果没有传 `publicSummary`，公开摘要默认为：

```text
[protected submission]
```

## 5. 验证流程

接口：

```text
POST /api/submissions/verify
```

用途：证明某份本地原文与当时提交记录匹配，但不要求后端公开原文。

请求：

```json
{
  "submissionId": "sub_001",
  "content": "private code payload"
}
```

响应：

```json
{
  "submissionId": "sub_001",
  "matched": true,
  "contentCommitment": "...",
  "protectionMode": "sealed_commitment_v1"
}
```

## 6. 密钥配置

生产环境必须配置：

```bash
set ARY_SUBMISSION_SECRET=<long-random-secret>
```

如果不配置，开发环境会使用默认值：

```text
dev-only-change-me
```

默认值只适合本地开发，不适合生产或评审环境。

## 7. 旧数据处理

启动时，`database/schema.py` 会对旧的明文 `submissions.content` 做一次封存：

```text
旧 content 明文
  -> 计算 hash/commitment
  -> content 改写为 [protected submission]
```

这样可以防止旧库继续暴露已提交代码。

## 8. 注意事项

- 不要把代码原文放进 `publicSummary`。
- 不要在日志中打印请求体的 `content`。
- 不要把 `ARY_SUBMISSION_SECRET` 提交到仓库。
- 如果更换 `ARY_SUBMISSION_SECRET`，旧提交的 commitment 将无法用新密钥验证。
- 不要手动删除 `trg_submissions_immutable` trigger，否则会破坏不可变提交模型。

## 9. 组织端与选手端隔离

系统现在使用轻量 RBAC + HMAC-JWT：

- `role = 0`：普通选手
- `role = 1`：赛事组织者
- `role = 2`：超级管理员

登录接口：

```text
POST /api/v1/auth/login
```

组织端命名空间：

```text
/api/v1/organizer/*
```

选手端命名空间：

```text
/api/v1/contestant/*
```

后端强制校验：

- 组织端写操作、组织端命名空间统计、导出必须是 organizer 或 admin。
- 选手提交和 verify 必须携带合法 JWT。
- 公开赛事读取和公开聚合统计 `/api/stats` 可以匿名访问。

生产环境必须设置：

```bash
set ARY_JWT_SECRET=<long-random-secret>
```

默认开发账号和默认 JWT secret 只适合本地开发，不适合评审/生产。
