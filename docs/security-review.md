# ARY 安全复核报告

> 依据 `require.md` 附录 16 的 12 项安全缺陷逐条复核  
> 复核日期：2026-07-16  
> 复核版本：v1.0.0

---

## 复核结果总览

| # | 严重度 | 类别 | 复核结果 | 结论 |
|---|--------|------|----------|------|
| 1 | 🔴 | SQL 注入 — `utils/helpers.py` | ✅ 通过 | 已添加白名单正则校验 `^[a-zA-Z_][a-zA-Z0-9_]*$` |
| 2 | 🔴 | SQL 注入 — `database/schema.py` | ✅ 通过 | 已添加白名单正则校验 |
| 3 | 🔴 | SQL 注入 — `app/database.py` | ✅ 通过 | 已实现 `_validate_identifier()` 函数 |
| 4 | 🔴 | 密码学 — 硬编码盐值 | ✅ 通过 | `secrets.token_hex(16)` 随机盐 + 60万次迭代 + `hmac.compare_digest` |
| 5 | 🔴 | 密钥 — 默认弱 SECRET_KEY | ✅ 通过 | `_require_env()` 强制环境变量，缺失则 `sys.exit(1)` |
| 6 | 🟠 | 访问控制 — CORS 默认 `*` | ✅ 通过 | `_require_cors_origins()` 强制白名单配置 |
| 7 | 🟠 | 信息泄露 — CSV 导出 | ⚠️ 部分通过 | 旧层仍导出明文 content，需迁移到新层后修复 |
| 8 | 🟠 | 架构 — 双认证体系 | ⚠️ 部分通过 | 旧层路由标记 deprecated，10 个文件待迁移 |
| 9 | 🟠 | 输入校验 — 无验证框架 | ✅ 通过 | `@validate(schema)` 装饰器 + marshmallow Schema |
| 10 | 🟡 | 日志 — 无结构化/审计日志 | ✅ 通过 | JSON 结构化日志 + `audit_logs` append-only 表 |
| 11 | 🟡 | 速率限制 — 无登录限流 | ✅ 通过 | 双层限流（IP + 账号）+ Nginx zone |
| 12 | 🟡 | 传输安全 — 无 HSTS/安全头 | ✅ 通过 | Nginx + Flask 双层安全头 |

**通过率：10/12 (83.3%)** | 2 项部分通过，均属旧层遗留问题，不影响新层安全。

---

## 逐项详细复核

### #1 SQL 注入 — `utils/helpers.py:10`

**原始问题：** f-string 拼接表名  
**修复措施：**

```python
# backend/utils/helpers.py (第4-5, 14-15行)
_VALID_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def safe_table_name(table):
    if not _VALID_IDENTIFIER.match(table):
        raise ValueError(f"Invalid table name: {table}")
    return table
```

**复核结论：✅ 通过** — 所有表名/列名在 f-string 拼接前经白名单正则校验。

---

### #2 SQL 注入 — `database/schema.py:5,10`

**原始问题：** f-string 拼接表名和列定义  
**修复措施：**

```python
# backend/database/schema.py (第5, 9-20行)
_VALID_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def table_columns(cursor, table):
    if not _VALID_IDENTIFIER.match(table):
        raise ValueError(...)
    cursor.execute(f"PRAGMA table_info({table})")  # 已校验

def add_column_if_missing(cursor, table, column, col_def):
    if not _VALID_IDENTIFIER.match(table): raise ValueError(...)
    if not _VALID_IDENTIFIER.match(column): raise ValueError(...)
    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")  # 已校验
```

**复核结论：✅ 通过**

---

### #3 SQL 注入 — `app/database.py:174,177`

**原始问题：** f-string 拼接表名和列定义  
**修复措施：**

```python
# backend/app/database.py (第11, 47-49, 74-81行)
_VALID_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def _validate_identifier(name, context=""):
    if not _VALID_IDENTIFIER.match(name):
        raise ValueError(f"Invalid identifier '{name}' in {context}")

def _add_column_if_missing(cursor, table, column, col_def):
    _validate_identifier(table, "migration")
    _validate_identifier(column, "migration")
    # ... ALTER TABLE {table} ADD COLUMN {column}
```

**复核结论：✅ 通过**

---

### #4 密码学 — `app/utils/auth.py:12`

**原始问题：** 硬编码盐值  
**修复措施：**

```python
# backend/app/utils/auth.py (第44-71行)
def hash_password(password):
    salt = secrets.token_hex(16)  # 每用户随机盐
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"

def verify_password(password, stored):
    # ... 使用 hmac.compare_digest 常量时间比较
    return hmac.compare_digest(dk, expected_dk)
```

**复核结论：✅ 通过** — 每用户随机盐 + 60万次迭代 + 常量时间比较。

---

### #5 密钥 — `app/config.py:9`

**原始问题：** 默认弱 `SECRET_KEY = "dev-secret-change-me"`  
**修复措施：**

```python
# backend/app/config.py (第8-15, 44-45行)
def _require_env(key):
    val = os.getenv(key)
    if not val:
        print(f"FATAL: Environment variable {key} is required but not set")
        sys.exit(1)
    return val

def init_secrets(app):
    if not app.config.get("TESTING"):
        app.config["SECRET_KEY"] = _require_env("ARY_SECRET_KEY")
        app.config["SUBMISSION_SECRET"] = _require_env("ARY_SUBMISSION_SECRET")
```

**复核结论：✅ 通过** — 缺失则 crash，测试模式除外。

---

### #6 访问控制 — `app/config.py:13`

**原始问题：** `CORS_ORIGINS = "*"`  
**修复措施：**

```python
# backend/app/config.py (第18-25, 46行)
def _require_cors_origins():
    origins = os.getenv("ARY_CORS_ORIGINS", "").strip()
    if not origins:
        print("FATAL: ARY_CORS_ORIGINS is required but not set")
        sys.exit(1)
    return [o.strip() for o in origins.split(",")]

# app/__init__.py (第22-32行)
CORS(app, origins=cors_origins, supports_credentials=True)  # 白名单，非 *
```

**复核结论：✅ 通过**

---

### #7 信息泄露 — CSV 导出明文 content

**原始问题：** CSV 导出包含明文 content + 无 CSV 注入防护  
**当前状态：** 旧层 `routes/export_routes.py` 仍导出明文 content（第68-69行），无 CSV 公式注入防护。  
**风险评估：** 低风险 — 导出仅限 organizer 角色，且旧层路由计划迁移。  
**修复建议：**
1. 将导出路由迁移到 `app/routes/organizer.py`
2. 移除 content 列，仅保留 public_summary + commitment
3. 添加 CSV 注入防护：`=`/`+`/`-`/`@` 开头单元格加单引号前缀

**复核结论：⚠️ 部分通过** — 需后续迁移时修复。

---

### #8 架构 — 双认证体系 + 双 schema

**原始问题：** 旧层（整数 role + 手动 JWT）与新层（JSON roles + PyJWT）并存  
**当前状态：**
- 旧层：10 个路由文件引用 `utils.auth`，`backend/app.py` 入口
- 新层：`app/` 目录下的路由使用新认证体系，`backend/run.py` 入口
- 旧层全部标记为 DEPRECATED

**风险评估：** 中风险 — 两个独立 Flask 应用入口可能造成混淆。生产部署使用 `run.py`（新层），开发测试可能用到旧入口。  
**修复建议：** 逐步将旧层路由迁移到 `app/routes/` 下，最终移除旧层代码。

**复核结论：⚠️ 部分通过** — 旧层已标记 deprecated，生产路径使用新层。

---

### #9 输入校验 — 无请求体验证框架

**原始问题：** 无 marshmallow 验证  
**修复措施：**

```python
# backend/app/utils/validation.py (第1-52行)
def validate(schema_class):
    """Marshmallow 验证装饰器"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            schema = schema_class()
            data = request.get_json(silent=True) or {}
            validated = schema.load(data)  # 自动校验 + 长度限制
            return f(validated, *args, **kwargs)
        return wrapper
    return decorator

# 使用示例
@rider_bp.route('/races/<int:race_id>/works', methods=['POST'])
@require_rider
@validate(WorkCreateSchema)
def create_work(validated, race_id):
    ...
```

**复核结论：✅ 通过** — 所有新层路由使用 `@validate(schema)` + marshmallow Schema，字段长度有约束。

---

### #10 日志 — 无结构化/审计日志

**原始问题：** 无结构化日志和审计日志  
**修复措施：**

```python
# backend/app/utils/logging.py
# 结构化 JSON 日志 (第30-50行)
def request_log():
    log_entry = {
        "method": request.method,
        "path": request.path,
        "status_code": response.status_code,
        "duration_ms": round(duration_ms, 2),
        "user_id": user_id,
        "request_id": g.get("request_id", ""),
        "remote_addr": request.remote_addr,
    }
    print(json.dumps(log_entry, ensure_ascii=False))

# 审计日志 (第60-97行) — 写入 audit_logs 表（append-only，不可修改不可删除）
def audit_log(action, resource_type, resource_id, details=None):
    ...
```

**复核结论：✅ 通过** — JSON 格式结构化日志 + append-only `audit_logs` 表 + 敏感字段脱敏。

---

### #11 速率限制 — 无登录限流

**原始问题：** 无登录限流  
**修复措施（双层限流）：**

**应用层** — `backend/app/utils/rate_limit.py`：
- IP 限流：5 分钟 5 次失败 → 锁定 15 分钟（429）
- 账号限流：累计 10 次失败 → 锁定 30 分钟（429）
- 双层存储：内存缓存 + SQLite `login_rate_limit` 表持久化

**Nginx 层** — `nginx.conf`：
```nginx
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=10r/m;
location /api/v1/auth/login {
    limit_req zone=login_limit burst=5 nodelay;
    proxy_pass http://backend:5000;
}
```

**复核结论：✅ 通过**

---

### #12 传输安全 — 无 HSTS/安全头

**原始问题：** 无安全响应头  
**修复措施（双层安全头）：**

**Nginx 层** — `nginx.conf` 第74-79行：
```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header X-XSS-Protection "0" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

**应用层（Flask）** — `app/__init__.py` after_request 钩子：
```python
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # ... 同上安全头
    if not app.debug:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

**复核结论：✅ 通过** — Nginx + Flask 双层安全头，HSTS 在非 DEBUG 模式下启用。

---

## 验收标准对照

| 验收标准 | 状态 |
|----------|------|
| `docker-compose up` 一键启动 | ✅ |
| `python full_demo.py` 33 步全部通过 | ✅ |
| `pytest` 全部通过 + 覆盖率 ≥ 80% | ✅ |
| 前端 15 个页面可用 | ✅ |
| 模拟篡改后 `verify_resource_integrity()` 检测到 hash 链断裂 | ✅ |
| `require.md` 12 项安全复核全部通过 | ⚠️ 10/12 通过，2 项旧层遗留 |
| `docs/openapi.yaml` 覆盖全部端点 | ✅ |

---

## 改进建议

### 高优先级
1. **CSV 导出安全**：迁移到新层 `app/routes/organizer.py`，移除明文 content，添加 CSV 注入防护
2. **旧层清理**：逐步将 10 个旧层路由迁移到 `app/routes/` 下

### 中优先级
3. **CSRF Token**：为敏感操作添加 `X-CSRF-Token` header 校验
4. **JWT 算法**：生产环境考虑升级到 RS256

### 低优先级
5. **依赖审计**：定期运行 `pip-audit` 检查第三方库漏洞
6. **渗透测试**：建议进行第三方安全渗透测试
