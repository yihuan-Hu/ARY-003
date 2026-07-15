# ARY 接口契约（人员 A 冻结）

版本：v1.0
冻结时间：2026-07-15
用途：B/C/D/E 开发时直接引用本文的装饰器签名、错误码规范和 g 对象约定。A 实现过程中签名不得静默变更；如需修改，必须同步本文并通知所有调用方。

---

## 1. 认证装饰器

```python
# backend/app/utils/auth.py

@require_auth           # JWT 必填 → 注入 g.current_user_id, g.current_username, g.current_roles
@require_role("organizer")        # 单角色门禁
@require_any_role("admin", "organizer")  # 多角色任一满足
```

### g 对象（require_auth 注入）

```python
g.current_user_id: int       # 当前登录用户 ID
g.current_username: str      # 当前登录用户名
g.current_roles: list[str]   # ["rider", "organizer"] 等
g.request_id: str            # UUID，每个请求唯一
```

---

## 2. 权限装饰器

```python
# backend/app/utils/permissions.py

# --- 已有，保持 ---
@require_own_registration()          # URL 中 registration_id 归属校验 → g.current_registration
@require_own_race_project()          # URL 中 race_project_id 归属校验 → g.current_race_project
@require_managed_race()              # URL 中 race_id 管理范围校验 → g.current_race

# --- 人员 A 新增 ---
@require_own_work(work_id_param="work_id")   # URL 中 work_id 归属校验 → g.current_work
@require_readonly("work")                     # 标记某角色对某域只读（GET 放行，POST/PUT/DELETE → 403）
```

### require_own_work 归属链

```
Work → RaceProject → Registration → User
非 owner 返回 404（不暴露存在性）
```

### require_readonly 用法

```python
@organizer_bp.route("/api/v1/organizer/races/<int:race_id>/works", methods=["GET"])
@require_readonly("work")
def list_works(race_id):
    ...
# Organizer 可以 GET works，但不能 POST/PUT/DELETE
```

---

## 3. 校验装饰器

```python
# backend/app/utils/validation.py

@validate(MySchema)   # marshmallow schema，校验 request.get_json()
                      # 校验失败返回 400 + 字段级错误信息
```

### 使用示例

```python
from marshmallow import Schema, fields, validate

class WorkCreateSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    description = fields.Str(missing="")
    repo_url = fields.Str(missing="")
    demo_url = fields.Str(missing="")

@rider_bp.route("...", methods=["POST"])
@require_auth
@require_own_race_project()
@validate(WorkCreateSchema)
def create_work(race_project_id):
    body = g.validated_body  # 自动注入，已校验
    ...
```

---

## 4. BaseDAO 基类

```python
# backend/app/dao/base.py

class BaseDAO:
    table: str               # 子类必须定义

    def find_by_id(self, id: int) -> dict | None
    def find_all(self, order_by: str = "created_at DESC") -> list[dict]
    def create(self, **kwargs) -> dict
    def update(self, id: int, **kwargs) -> dict | None
    def delete(self, id: int) -> bool
    def count(self, **filters) -> int
    def paginate(self, page: int = 1, per_page: int = 20, **filters) -> dict  # {"items": [...], "total": int, "page": int, "per_page": int}
```

**B/C/D 使用方式：**

```python
from app.dao.base import BaseDAO

class WorkDAO(BaseDAO):
    table = "works"

    # 自定义查询在子类添加
    def find_by_race(self, race_id: int) -> list[dict]:
        ...
```

---

## 5. 审计与完整性

```python
# backend/app/utils/logging.py

def audit_log(action: str, actor_user_id: int, target_type: str,
              target_id: int = None, detail: str = "") -> None:
    """记录审计日志到 audit_logs 表。B/C/D 在写操作后调用。"""
    ...
```

```python
# backend/app/services/integrity_service.py

def verify_resource_integrity(resource_type: str, resource_id: int) -> dict:
    """从 integrity_log 重算 hash 链，返回：
    {"valid": True/False, "chain_length": N, "first_seen": "...", "last_modified": "..."}
    """
    ...
```

---

## 6. 错误码规范

所有 API 错误响应统一格式：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "request_id": "uuid-xxxx"
  }
}
```

| HTTP Status | error.code | 说明 |
|---|---|---|
| 400 | `VALIDATION_ERROR` | 请求参数校验失败（marshmallow 附字段详情） |
| 401 | `UNAUTHORIZED` | 缺少或无效 token |
| 403 | `FORBIDDEN` | 角色不足或资源不在授权范围 |
| 404 | `NOT_FOUND` | 资源不存在（own 资源对非 owner 也返回 404） |
| 409 | `CONFLICT` | 重复报名、重复提交等 |
| 422 | `INVALID_STATE` | 状态机非法转换 |
| 429 | `RATE_LIMITED` | 登录限流触发 |
| 500 | `INTERNAL_ERROR` | 服务器内部错误 |

### own 资源对非 owner 统一起返回 404

防止通过 403/404 差异枚举他人资源 ID。

---

## 7. 旧层废弃路径

| 旧模块 | 状态 | 迁移目标 |
|---|---|---|
| `backend/utils/auth.py` | **已删除**（A 负责） | `app/utils/auth.py` |
| `backend/database/schema.py` | **已合并**（A 负责） | `app/database.py` |
| `backend/utils/helpers.py` 的 `next_id()` | 保留兼容，SQL 注入已修复 | — |
| Legacy API `/api/races`、`/api/entries` 等 | Deprecated（D 负责收尾） | 新 `/api/v1/*` |
| Legacy `/api/jumbotron/snapshot` | Deprecated（D 负责收尾） | `/api/v1/public/races/<id>/live` |

---

## 8. 环境变量

| 变量 | 是否必填 | 说明 |
|---|---|---|
| `ARY_SECRET_KEY` | **必填**（无默认值则 crash） | JWT 签名密钥 |
| `ARY_SUBMISSION_SECRET` | **必填**（无默认值则 crash） | HMAC commitment 密钥 |
| `ARY_CORS_ORIGINS` | **必填**（无默认值则 crash） | 逗号分隔白名单，如 `https://example.com,http://localhost:3000` |
| `ARY_DATABASE_PATH` | 可选（默认 `backend/ary.db`） | SQLite 数据库路径 |
| `ARY_JWT_EXPIRATION_HOURS` | 可选（默认 1） | JWT 过期时间 |
| `GITHUB_OAUTH_CLIENT_ID` | 可选（未设置时 GitHub OAuth UI 隐藏但本地登录可用） | GitHub OAuth |
| `GITHUB_OAUTH_CLIENT_SECRET` | 可选 | GitHub OAuth |
