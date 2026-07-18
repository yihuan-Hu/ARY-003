# DEPRECATED

This directory (`backend/utils/`) is part of the **legacy system** and has been superseded by `backend/app/utils/`.

## Migration Status

| Old Module | New Module | Status |
|---|---|---|
| `utils/auth.py` | `app/utils/auth.py` (A-3) | ✅ Migrated + deleted |
| All legacy utilities | `backend/app/utils/` | ✅ Migrated |

## Notes

- Do **NOT** add new code to this directory.
- The old `utils/auth.py` has been **deleted**. All references now use `app.utils.auth`.
- For current utility patterns, see `backend/app/utils/`.

---

Created by Person D during legacy system cleanup (team-division.md §人员 D §7).
