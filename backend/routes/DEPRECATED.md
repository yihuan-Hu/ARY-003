# DEPRECATED

This directory (`backend/routes/`) is part of the **legacy system** and has been superseded by `backend/app/routes/`.

## Migration Status

| Old Route | New Route | Status |
|---|---|---|
| Legacy `/api/export/*` | `/api/v1/organizer/races/<id>/export/*` (C-3) | ✅ Migrated |
| Legacy `/api/jumbotron/snapshot` | `/api/v1/public/races/<id>/live` (D-4) | ✅ Migrated — old route returns 301 + deprecation header |
| Legacy Submission | New Work module (HMAC commitment + immutable triggers) | ✅ Migrated |
| Legacy `/api/auth/*` | `/api/v1/auth/*` (A-3) | ✅ Migrated |
| All other legacy routes | `backend/app/routes/` (A/B/C/D/E) | ✅ Migrated |

## Notes

- Do **NOT** add new code to this directory.
- The old routes are kept for backward compatibility. They should return appropriate deprecation headers or redirects.
- All new endpoints use `/api/v1/` prefix under the new blueprint system.

---

Created by Person D during legacy system cleanup (team-division.md §人员 D §7).
