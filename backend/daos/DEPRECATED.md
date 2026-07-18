# DEPRECATED

This directory (`backend/daos/`) is part of the **legacy system** and has been superseded by `backend/app/dao/`.

## Migration Status

| Old Module | New Module | Status |
|---|---|---|
| All legacy DAOs | `backend/app/dao/` (BaseDAO + domain-specific DAOs) | ✅ Migrated |

## Notes

- Do **NOT** add new code to this directory.
- All persistence logic now uses `backend/app/dao/` via `BaseDAO` or domain-specific DAOs.
- This directory is kept for backward compatibility only and will be removed in a future release.
- For current DAO patterns, see `docs/contracts.md` (BaseDAO signature) and `docs/b-upstream-contracts-for-cd.md` (DAO signatures for B/C/D).

---

Created by Person D during legacy system cleanup (team-division.md §人员 D §7).
