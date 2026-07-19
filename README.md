# ARY — Agent Racing Yard

面向 Agentic Development 时代的智能体骑行赛事平台。通过赛事组织、过程展示、作品提交、评审总结和骑手档案，将开发者与 Coding Agent 协同完成任务的过程变成可观看、可评审、可复盘的能力资产。

## 快速启动

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Linux/Mac
# .venv\Scripts\Activate.ps1    # Windows

pip install -r requirements.txt

# 必须设置的环境变量
export ARY_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
export ARY_SUBMISSION_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))')
export ARY_CORS_ORIGINS=http://localhost:3000

python run.py
# 服务启动在 http://127.0.0.1:5000
```

首次启动自动创建数据库并生成三个种子账号，密码打印在控制台。

### Docker 一键启动

```bash
docker-compose up
```

## 运行测试

```bash
cd backend
pytest tests/ -q
```

## 文档

| 文档 | 说明 |
| --- | --- |
| `team-division.md` | 五人分工方案（A/B/C/D/E） |
| `require.md` | 上线需求规格说明书（含 QA 计划） |
| `STATUS.md` | 任务看板 |
| `AGENTS.md` | Agent 协作规则 |
| `docs/ary-mvp.prd.md` | 产品目标、MVP 范围、验收口径 |
| `docs/ary-domain-analysis.v0.3.md` | 领域模型、核心对象、不变量 |
| `docs/ary-mvp.ia.md` | 信息架构、页面层级、导航 |
| `docs/ary-permission-matrix.md` | 权限矩阵 |
| `docs/ary-ca-integration-spec.md` | CA 接入契约 |
| `docs/contracts.md` | 人员 A 接口契约（装饰器/BaseDAO/错误码）|
| `docs/deployment.md` | 部署、监控、备份、回滚 |
| `docs/security-review.md` | 安全复核报告 |

## 项目结构

```
backend/
├── app/                # 新 ARY 应用（Flask 工厂 + Blueprint）
│   ├── __init__.py     # create_app + 中间件 + 蓝图注册
│   ├── config.py       # 环境配置
│   ├── database.py     # 统一 schema + migration
│   ├── dao/            # 数据访问层（BaseDAO + 各模块 DAO）
│   ├── services/       # 业务逻辑层
│   ├── routes/         # 蓝图路由（auth/rider/organizer/public/judge/admin/ca/notification）
│   ├── utils/          # 工具（auth/permissions/rate_limit/logging/validation/errors/response）
│   └── schemas/        # marshmallow schema
├── tests/              # 全量测试（183 passed）
│   ├── legacy/         # 旧层回归测试（21 passed）
│   └── ...
├── run.py              # 开发启动入口
├── Dockerfile
├── nginx.conf
└── entrypoint.sh

frontend/               # SPA 前端（17 页）
design-prototype/       # 高保真 UX 原型
docs/                   # 产品/领域/架构文档
```

## 测试覆盖率

183 tests passed, 0 failed. bandit 安全扫描零告警.
