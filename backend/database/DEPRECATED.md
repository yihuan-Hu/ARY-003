# DEPRECATED

This directory (`backend/database/`) is part of the **legacy system** and has been superseded by `backend/app/database.py`.

## Migration Status

| Old Module | New Module | Status |
|---|---|---|
| `database/schema.py` | `app/database.py` (unified schema + init_db) | ✅ Migrated |
| All legacy SQL/scripts | `app/database.py` (inline schema definitions) | ✅ Migrated |

## Notes

- Do **NOT** add new code to this directory.
- All schema initialization is now centralized in `backend/app/database.py::init_db()`.
- Table creation uses `CREATE TABLE IF NOT EXISTS` for idempotent migration.

---

Created by Person D during legacy system cleanup (team-division.md §人员 D §7).
