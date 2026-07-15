import re
from datetime import datetime, timezone

# 白名单正则：只允许字母数字下划线
_VALID_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def next_id(conn, table, prefix):
    # 安全校验：table 只允许字母数字下划线
    if not _VALID_IDENTIFIER.match(table):
        raise ValueError(f"Invalid table name: {table}")
    row = conn.execute(
        f'SELECT id FROM {table} WHERE id LIKE ? ORDER BY id DESC LIMIT 1',
        (f'{prefix}_%',),
    ).fetchone()
    if not row:
        return f'{prefix}_001'
    try:
        num = int(row['id'].split('_')[1]) + 1
    except (IndexError, ValueError):
        num = 1
    return f'{prefix}_{num:03d}'


def clamp(value, minimum=0.0, maximum=1.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = minimum
    return max(minimum, min(maximum, value))


def as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_utc(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
