# =============================================
# ARY Multi-stage Docker Build
# =============================================
# Build:  docker build -t ary-app:latest .
# 需要 BuildKit: DOCKER_BUILDKIT=1 docker build -t ary-app:latest .
# =============================================

# ---- Stage 1: Python dependencies ----
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt gunicorn>=21.2

# ---- Stage 2: Production runtime ----
FROM python:3.12-slim

WORKDIR /app

# 安装运行时依赖（curl 用于健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -r ary && useradd -r -g ary -d /app -s /sbin/nologin ary

# 从 builder 复制 Python 包
COPY --from=builder /root/.local /home/ary/.local
ENV PATH=/home/ary/.local/bin:$PATH

# 复制应用代码
COPY backend/ /app/backend/
COPY docs/deployment.md /app/docs/deployment.md
COPY docs/openapi.yaml /app/docs/openapi.yaml
COPY entrypoint.sh /app/entrypoint.sh

# 创建数据目录并设置权限（以 root 执行）
RUN mkdir -p /data && chown -R ary:ary /app /data && chmod +x /app/entrypoint.sh

# 切换到非 root 用户
USER ary

# 暴露端口（gunicorn 默认 8000）
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "--chdir", "/app/backend", \
     "run:app"]
