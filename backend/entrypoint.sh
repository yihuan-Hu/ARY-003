#!/bin/bash
# =============================================
# ARY Entrypoint — 启动前安全校验
# =============================================
set -e

echo "[ARY] === Starting ARY Application ==="
echo "[ARY] Checking required environment variables..."

# 必填变量校验
check_var() {
    local key="$1"
    local val="${!key}"
    if [ -z "$val" ] || [ "$val" = "<generate-randomly>" ]; then
        echo "[ARY] FATAL: $key is not set or uses default placeholder value." >&2
        echo "[ARY] Please generate a random value:" >&2
        echo "[ARY]   python -c 'import secrets; print(secrets.token_hex(32))'" >&2
        exit 1
    fi
    echo "[ARY]   $key: OK"
}

check_var "ARY_SECRET_KEY"
check_var "ARY_SUBMISSION_SECRET"

# CORS 校验
if [ -z "$ARY_CORS_ORIGINS" ]; then
    echo "[ARY] WARNING: ARY_CORS_ORIGINS is not set. Defaulting to http://localhost" >&2
    export ARY_CORS_ORIGINS="http://localhost"
fi
echo "[ARY]   ARY_CORS_ORIGINS: $ARY_CORS_ORIGINS"

# 数据库路径
echo "[ARY]   ARY_DATABASE_PATH: ${ARY_DATABASE_PATH:-/data/ary.db}"

# JWT 过期时间
echo "[ARY]   ARY_JWT_EXPIRATION_HOURS: ${ARY_JWT_EXPIRATION_HOURS:-1}"

echo "[ARY] All checks passed. Starting gunicorn..."

exec gunicorn \
    --bind 0.0.0.0:8000 \
    --workers "${ARY_WORKERS:-4}" \
    --worker-class sync \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level "${ARY_LOG_LEVEL:-info}" \
    --chdir /app/backend \
    "run:app"
