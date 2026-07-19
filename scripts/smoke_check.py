"""Run HTTP smoke checks against a running ARY backend.

Run from repository root after starting the backend:
    python scripts/smoke_check.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("ARY_BASE_URL", "http://localhost:5000").rstrip("/")
DEMO_PASSWORD = os.environ.get("ARY_DEMO_PASSWORD", "Demo1234")

SMOKE_STEPS = [
    ("GET", "/health", None, None),
    ("GET", "/api/v1/public/stats", None, None),
    ("GET", "/api/v1/public/races", None, None),
    ("POST", "/api/v1/auth/login", {"username": "rider_demo", "password": DEMO_PASSWORD}, "rider"),
    ("GET", "/api/v1/auth/me", None, "rider"),
    ("GET", "/api/v1/rider/registrations", None, "rider"),
    ("POST", "/api/v1/auth/login", {"username": "organizer_demo", "password": DEMO_PASSWORD}, "organizer"),
    ("GET", "/api/v1/organizer/races", None, "organizer"),
    ("POST", "/api/v1/auth/login", {"username": "judge_demo", "password": DEMO_PASSWORD}, "judge"),
    ("GET", "/api/v1/judge/assignments", None, "judge"),
]


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=8) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def main() -> int:
    tokens: dict[str, str] = {}
    for method, path, body, role in SMOKE_STEPS:
        try:
            token = tokens.get(role or "")
            payload = request(method, path, body, token)
            if path == "/api/v1/auth/login" and role:
                tokens[role] = payload.get("token") or payload.get("data", {}).get("token", "")
                if not tokens[role]:
                    raise RuntimeError(f"login for {role} did not return token")
            print(f"OK {method} {path}")
        except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
            print(f"FAIL {method} {path}: {exc}", file=sys.stderr)
            return 1
    print("Smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
