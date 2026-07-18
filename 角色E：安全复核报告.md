# 角色E：安全复核报告

> 基于 `require.md` 附录 12 项安全缺陷逐项复核
> 复核日期：2026-07-18

## 复核结论

| # | 严重度 | 类别 | 状态 | 说明 |
|---|--------|------|------|------|
| 1 | 🔴 | SQL 注入 `utils/helpers.py:10` | ✅ 已修复 | 改为白名单正则校验 `^[a-zA-Z_][a-zA-Z0-9_]*$` |
| 2 | 🔴 | SQL 注入 `database/schema.py:5,10` | ✅ 已修复 | f-string 已替换为参数化查询 |
| 3 | 🔴 | SQL 注入 `app/database.py:174,177` | ✅ 已修复 | f-string 已替换为参数化查询 |
| 4 | 🔴 | 密码学 硬编码盐值 | ✅ 已修复 | 每用户随机盐 + PBKDF2-SHA256 60万次迭代 |
| 5 | 🔴 | 密钥 默认弱 SECRET_KEY | ✅ 已修复 | 从环境变量强制读取，无默认值 |
| 6 | 🟠 | 访问控制 CORS 默认 `*` | ✅ 已修复 | `ARY_CORS_ORIGINS` 必填，未配置 crash |
| 7 | 🟠 | 信息泄露 CSV 导出明文 | ✅ 已修复 | CSV 导出不包含明文 content，只导出 public_summary |
| 8 | 🟠 | 架构 双认证体系 | ✅ 已修复 | 统一认证体系，旧 role INTEGER 已废弃 |
| 9 | 🟠 | 输入校验 无验证框架 | ✅ 已修复 | marshmallow 统一校验框架已引入 |
| 10 | 🟡 | 日志 无结构化日志 | ✅ 已修复 | 每请求 method/path/status/duration/user_id/request_id |
| 11 | 🟡 | 速率限制 无登录限流 | ✅ 已修复 | 同 IP 5分钟5次→锁定15分钟，同账号10次→锁定30分钟 |
| 12 | 🟡 | 传输安全 无 HSTS/安全头 | ✅ 已修复 | X-Content-Type-Options / X-Frame-Options / HSTS 等已配置 |

## 总结

- 12 项安全缺陷：**全部已修复** ✅
- bandit 扫描：零告警
- CI/CD 已配置 lint → test → bandit → pip-audit 门禁
- 覆盖率门禁：≥ 80%
