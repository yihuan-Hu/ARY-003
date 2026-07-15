"""
BaseDAO 基类（人员 A 交付）

B/C/D 继承此类获得以下模板方法：
- find_by_id / find_all / create / update / delete / count / paginate

子类需要定义 table 属性。
"""
from app.database import get_db


class BaseDAO:
    # Bandit B608: self.table 是子类开发者定义的硬编码类属性，非用户输入，不存在 SQL 注入
    table: str = ""  # nosec B608: table 由开发者硬编码

    # ---- 查询 ----

    def find_by_id(self, id: int) -> dict | None:
        db = get_db()
        row = db.execute(
            f"SELECT * FROM {self.table} WHERE id = ?", (id,)
        ).fetchone()
        return dict(row) if row else None

    def find_all(self, order_by: str = "created_at DESC") -> list[dict]:
        db = get_db()
        rows = db.execute(
            f"SELECT * FROM {self.table} ORDER BY {order_by}"
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- 写入 ----

    def create(self, **kwargs) -> dict:
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
