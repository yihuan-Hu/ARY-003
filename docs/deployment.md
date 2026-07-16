# ARY 部署手册

## 1. 环境要求

- Docker 20.10+
- Docker Compose 1.29+ (或 `docker compose` 插件)
- 启用 BuildKit: `export DOCKER_BUILDKIT=1` (Linux/Mac) 或 `$env:DOCKER_BUILDKIT=1` (Windows PowerShell)
- Python 3.12+ (仅开发/测试)

## 2. 环境变量清单

部署前必须设置以下环境变量。复制 `.env.example` 为 `.env` 并填入真实值。

| 变量 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `ARY_SECRET_KEY` | ✅ | JWT 签名密钥，至少 32 字符随机值 | `$(python -c 'import secrets; print(secrets.token_hex(32))')` |
| `ARY_SUBMISSION_SECRET` | ✅ | 作品提交签名密钥 | 同上 |
| `ARY_CORS_ORIGINS` | ✅ | CORS 白名单，逗号分隔 | `https://your-domain.com` |
| `ARY_DATABASE_PATH` | ❌ | SQLite 数据库路径 | `/data/ary.db` (默认) |
| `ARY_JWT_EXPIRATION_HOURS` | ❌ | JWT 过期时间（小时） | `1` (默认) |
| `ARY_WORKERS` | ❌ | Gunicorn worker 数量 | `4` (默认，建议设为 CPU 核数×2+1) |
| `ARY_LOG_LEVEL` | ❌ | 日志级别 | `info` (可选: debug, warning, error) |
| `ARY_HTTP_PORT` | ❌ | Nginx HTTP 端口 | `80` (默认) |
| `GITHUB_OAUTH_CLIENT_ID` | ❌ | GitHub OAuth Client ID | 从 GitHub 获取 |
| `GITHUB_OAUTH_CLIENT_SECRET` | ❌ | GitHub OAuth Client Secret | 从 GitHub 获取 |

### 生成安全随机值

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 3. 启动方式

### 3.1 Docker Compose 一键启动（推荐）

```bash
# 1. 准备 .env 文件
cp .env.example .env
# 编辑 .env，替换 <generate-randomly> 和 <from-github> 为真实值
# 至少需要设置: ARY_SECRET_KEY, ARY_SUBMISSION_SECRET, ARY_CORS_ORIGINS

# 2. 启用 BuildKit 并启动
export DOCKER_BUILDKIT=1   # Linux/Mac
# $env:DOCKER_BUILDKIT=1   # Windows PowerShell
docker-compose up -d --build

# 3. 验证
curl http://localhost/health
# 返回 {"status":"ok"}

curl http://localhost/health/ready
# 返回 {"status":"ready","database":"ok"}

# 4. 查看日志
docker-compose logs -f
```

### 3.2 仅构建镜像（不启动）

```bash
DOCKER_BUILDKIT=1 docker build -t ary-app:latest .
```

### 3.3 本地开发模式

```bash
cd backend
set ARY_DEV_MODE=1      # Windows
# export ARY_DEV_MODE=1  # Linux/Mac
python run.py
```

## 4. 架构说明

```
Browser ───> Nginx (80) ───> Gunicorn (8000) ───> Flask App
                │
                ├─ /            → 前端静态文件 (SPA)
                ├─ /api/*       → 代理到 Flask
                ├─ /health      → 健康检查
                └─ /health/ready → 就绪检查
```

| 服务 | 容器 | 端口 | 说明 |
|------|------|------|------|
| Nginx | ary-nginx | 80 (外部) | 反向代理 + 静态文件 + 限流 |
| Flask | ary-backend | 8000 (内部) | 后端 API (gunicorn 4 workers) |

## 5. 健康检查

| 端点 | 说明 |
|------|------|
| `GET /health` | 服务存活检查 |
| `GET /health/ready` | 就绪检查（含数据库连通性） |

Docker Compose 已内置 healthcheck：
- Backend: 每 30s 检查 `/health`，3 次失败标记 unhealthy
- Nginx: 依赖 backend healthy 后才启动

## 6. 全流程验收

```bash
cd backend
set ARY_DEV_MODE=1
python full_demo.py
```

预期输出：33 步全部 PASS，0 FAIL。

## 7. 运行测试

```bash
cd backend
pip install -r requirements.txt
set ARY_DEV_MODE=1
python -m pytest tests/ -v --cov=app --cov-report=term --cov-fail-under=80
```

覆盖率门禁：≥ 80%。

## 8. 安全扫描

```bash
# Bandit 安全扫描
pip install bandit
bandit -r backend/

# 依赖漏洞扫描
pip install pip-audit
pip-audit -r backend/requirements.txt
```

## 9. 回滚步骤

1. 停止当前服务：`docker-compose down`
2. 恢复数据库备份：`docker cp backup.db ary-backend:/data/ary.db`
3. 切换到目标版本：`git checkout <version-tag>`
4. 重新构建并启动：`docker-compose up -d --build`
5. 验证健康检查：`curl http://localhost/health`

## 10. 数据备份与恢复

### 备份

```bash
# SQLite 数据库位于 docker volume
docker cp ary-backend:/data/ary.db ./backup_$(date +%Y%m%d_%H%M%S).db
```

### 恢复

```bash
docker cp ./backup.db ary-backend:/data/ary.db
docker-compose restart backend
```

## 11. 日志

```bash
# 查看后端日志（实时）
docker-compose logs -f backend

# 查看 Nginx 日志（实时）
docker-compose logs -f nginx

# 查看最近 100 行
docker-compose logs --tail=100 backend

# 查看错误日志
docker-compose logs backend | grep -i error
```

## 12. 常用运维命令

```bash
# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 停止并删除数据卷（危险！会清除数据库）
docker-compose down -v

# 查看资源使用
docker stats ary-backend ary-nginx

# 进入容器调试
docker exec -it ary-backend sh
```

## 13. 安全注意事项

1. **生产环境务必更换默认密钥**: `ARY_SECRET_KEY` 和 `ARY_SUBMISSION_SECRET` 必须使用强随机值
2. **CORS 白名单**: 生产环境 `ARY_CORS_ORIGINS` 必须精确配置，不要使用 `*`
3. **HTTPS**: 生产环境建议在前端加 TLS 终止（Cloudflare/CDN/负载均衡器）
4. **定期备份**: 建议设置 cron job 定期备份数据库
5. **监控**: 建议接入日志收集（ELK/Loki）和监控告警（Prometheus）

## 14. 打标签

```bash
git tag v1.0.0
git push origin v1.0.0
```
