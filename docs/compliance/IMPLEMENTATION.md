# Compliance implementation checklist

## Database

Apply migrations before enabling compliance APIs:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/2026_legal_ai_compliance.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/2026_legal_acceptances.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/2026_privacy_requests.sql
```

Verify while authenticated as administrator:

```text
GET /api/admin/compliance/status
```

The response must return `ok: true` and all required tables must be present.

## Application

The branch enables:

- security headers on all responses;
- HSTS when HTTPS is detected or `FORCE_HTTPS=1`;
- no-store caching for admin, application and API paths;
- public AI transparency policy at `/ai-policy`;
- protected compliance status endpoint;
- protected AI usage registration with hashed input/output evidence;
- mandatory pending human review for every registered AI output;
- versioned legal acceptance records;
- GDPR privacy-request workflow with 30-day due date;
- compliance-incident register with authority/data-subject notification fields;
- audit events for legal, privacy, AI and incident operations.

## E-label privacy gate

Public e-label pages must not include analytics, advertising pixels, profiling or fingerprinting. The regression test scans the public modules for common tracking providers. Any future telemetry on these pages requires a separate legal and technical review and must not identify or track visitors.

## Release gate

Do not merge to production until:

1. all SQL migrations succeed on staging;
2. `pytest -q` passes;
3. `/ai-policy` renders correctly;
4. `/api/admin/compliance/status` returns `ok: true`;
5. response headers are verified over HTTPS;
6. `/admin/compliance/ai-review` is admin-only;
7. privacy requests can be opened, listed and closed with audit evidence;
8. compliance incidents can be created and updated;
9. retention runs first in dry-run and only then with `--apply`.
