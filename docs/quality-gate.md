# ARY 质量门禁

本文定义期末提交前必须通过的检查。目标是让项目不只“能跑”，还具备可回归、可演示、可解释的工程质量。

## 必过命令

```bash
node frontend/ux-audit.test.js
node --check frontend/app.js
node --check frontend/js/api.js
node --check frontend/js/constants.js
node --check frontend/js/ux.js
node --check frontend/js/components.js
python -m py_compile scripts/seed_demo.py scripts/smoke_check.py
git diff --check
```

后端全量测试：

```bash
pytest
```

如果时间有限，至少运行 C/D/B/A 专项测试和前端 UX 检查：

```bash
pytest backend/tests/test_race_lifecycle.py backend/tests/test_registration_extensions.py backend/tests/test_work_integrity.py
pytest backend/tests/test_judging.py backend/tests/test_awards.py backend/tests/test_c_remediation.py
pytest backend/tests/test_ca_connection.py backend/tests/test_ca_ingestion.py backend/tests/test_public_apis.py
node frontend/ux-audit.test.js
```

## 演示门禁

| 检查项 | 命令 | 通过标准 |
| --- | --- | --- |
| 演示数据 | `python scripts/seed_demo.py` | 输出 demo 用户、密码和赛事 ID |
| 冒烟接口 | `python scripts/smoke_check.py` | 所有步骤输出 `OK`，最后输出 `Smoke checks passed.` |
| 前端 UX | `node frontend/ux-audit.test.js` | 输出 `UX audit passed` |
| JS 语法 | `node --check ...` | 无输出且退出码为 0 |
| Python 语法 | `python -m py_compile ...` | 无输出且退出码为 0 |

## 安全门禁

1. 不允许新增 f-string SQL 拼接，表名和列名必须白名单校验。
2. 写接口必须走认证、权限和审计日志。
3. 密码必须使用 PBKDF2 哈希，不允许写入明文密码。
4. CSV 导出必须保留注入防护。
5. 前端 URL 输出必须使用 `safeUrl()`。
6. 生产前端不得硬编码 `http://localhost:5000`。

## 前端门禁

1. 用户可见文案必须中文化，允许保留 `CA`、`CSV`、`URL`、`ID`、`API` 等技术缩写。
2. 参与、组织、评审三个工作区必须保留任务面板。
3. `frontend/app.js` 不再直接维护底层 API 请求、状态中文文案和通用数据解析。
4. 新增首页入口时必须兼顾移动端，不允许按钮溢出。
5. 修改前端后必须运行 `frontend/ux-audit.test.js`。

## 后端门禁

1. Route 只负责 HTTP 输入输出、认证和校验。
2. Service 负责业务规则和跨表校验。
3. DAO 负责数据库访问和参数化查询。
4. 事务性批量写入必须显式回滚。
5. 跨赛事访问必须校验组织者归属。

## 已知测试口径

`STATUS.md` 记录过全量测试 `183 passed, 0 failed`。如果本地存在旧归档用例或历史兼容用例失败，应在提交说明中区分“当前验收集”和“旧接口断言”，避免把已归档需求作为当前阻塞。
