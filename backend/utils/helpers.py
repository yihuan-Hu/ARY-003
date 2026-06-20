from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def next_id(conn, table, prefix):
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
