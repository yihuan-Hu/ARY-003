#!/usr/bin/env python
"""
ARY MVP 启动入口（人员 A 更新）

使用前必须设置环境变量：
    export ARY_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
    export ARY_SUBMISSION_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))')
    export ARY_CORS_ORIGINS=http://localhost:3000,http://localhost:5000

缺少环境变量将拒绝启动。

开发模式（跳过 secret 强制检查）：
    export ARY_DEV_MODE=1
    # 此时使用默认 dev secret，仅用于本地开发
"""
import os
import sys

from app import create_app

# 检查运行模式
dev_mode = os.environ.get("ARY_DEV_MODE", "0") == "1"

if dev_mode:
    os.environ.setdefault("ARY_SECRET_KEY", "dev-secret-do-not-use-in-production")
    os.environ.setdefault("ARY_SUBMISSION_SECRET", "dev-submission-secret-do-not-use")
    os.environ.setdefault("ARY_CORS_ORIGINS", "http://localhost:3000,http://localhost:5000")
    print("[ARY] WARNING: Running in DEV mode with default secrets. Do NOT use in production.")

app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("ARY_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=5000)
