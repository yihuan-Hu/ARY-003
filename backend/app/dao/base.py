"""
BaseDAO 基类（人员 A 交付 — 生产级）

B/C/D 继承此类获得以下模板方法：
- find_by_id / find_all / create / update / delete / count / paginate

所有动态 SQL 片段（table/columns/order_by）均经白名单正则校验，防止注入。
子类只需定义 table 属性即可使用。
"""
import re

from app.database import get_db
from app.utils.errors import ValidationError

# 白名单：列名 + 可选 ASC/DESC，支持逗号分隔的多列排序
_VALID_ORDER_BY = re.compile(
    r"^[a-zA-Z_][a-zA-Z0-9_]*(?:\s+(?:ASC|DESC))?(?:\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*(?:\s+(?:ASC|DESC))?)*$"
)
_VALID_COLUMN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_order_by(order_by: str) -> None:
    """校验 order_by 只包含合法列名和 ASC/DESC"""
    if not _VALID_ORDER_BY.match(order_by.strip()):
        raise ValidationError(f"Invalid order_by: {order_by}")


def _validate_columns(kwargs_keys: list[str]) -> None:
    """校验 column names 符合标识符规范"""
    for k in kwargs_keys:
        if not _VALID_COLUMN.match(k):
            raise ValidationError(f"Invalid column name: {k}")


class BaseDAO:
    table: str = ""  # 子类必须定义（开发者硬编码，非用户输入）

    # ---- 查询 ----

    def find_by_id(self, id: int) -> dict | None:
        db = get_db()
        row = db.execute(
            f"SELECT * FROM {self.table} WHERE id = ?", (id,)
        ).fetchone()
        return dict(row) if row else None

    def find_all(self, order_by: str = "created_at DESC") -> list[dict]:
        _validate_order_by(order_by)
        db = get_db()
        rows = db.execute(
            f"SELECT * FROM {self.table} ORDER BY {order_by}"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- 写入 ----

    def create(self, **kwargs) -> dict:
        _validate_columns(list(kwargs.keys()))
        db = get_db()
        columns = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        values = tuple(kwargs.values())
        cursor = db.execute(
            f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
            values,
        )
        db.commit()
        return self.find_by_id(cursor.lastrowid)

    def update(self, id: int, **kwargs) -> dict | None:
        _validate_columns(list(kwargs.keys()))
        db = get_db()
        if not kwargs:
            return self.find_by_id(id)
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = tuple(kwargs.values()) + (id,)
        db.execute(
            f"UPDATE {self.table} SET {sets}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
        db.commit()
        return self.find_by_id(id)

    def delete(self, id: int) -> bool:
        db = get_db()
        cursor = db.execute(
            f"DELETE FROM {self.table} WHERE id = ?", (id,)
        )
        db.commit()
        return cursor.rowcount > 0

    # ---- 聚合 ----

    def count(self, **filters) -> int:
        _validate_columns(list(filters.keys()))
        db = get_db()
        if filters:
            where = " AND ".join(f"{k} = ?" for k in filters)
            row = db.execute(
                f"SELECT COUNT(*) as cnt FROM {self.table} WHERE {where}",
                tuple(filters.values()),
            ).fetchone()
        else:
            row = db.execute(
                f"SELECT COUNT(*) as cnt FROM {self.table}"
            ).fetchone()
        return row["cnt"] if row else 0

    def paginate(self, page: int = 1, per_page: int = 20, order_by: str = "created_at DESC", **filters) -> dict:
        """分页查询，返回 {"items": [...], "total": N, "page": P, "per_page": PP}"""
        _validate_order_by(order_by)
        _validate_columns(list(filters.keys()))
        db = get_db()
        where_clause = ""
        values = ()
        if filters:
            where_clause = " WHERE " + " AND ".join(f"{k} = ?" for k in filters)
            values = tuple(filters.values())

        total = self.count(**filters)
        offset = (page - 1) * per_page
        rows = db.execute(
            f"SELECT * FROM {self.table}{where_clause} ORDER BY {order_by} LIMIT ? OFFSET ?",
            values + (per_page, offset),
        ).fetchall()

        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
