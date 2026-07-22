# Compliance implementation checklist

## Database

Apply migrations in this order:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/2026_legal_ai_compliance.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/2026_legal_acceptance_constraints.sql
```

Verify while authenticated as administrator:

```text
GET /api/admin/compliance/status
GET /api/admin/compliance/legal-acceptances
```

## Legal document lifecycle

1. Insert each active legal document in `legal_documents` with a stable `document_key`, version, hash and effective date.
2. The authenticated client calls `GET /api/me/legal-status`.
3. The user performs an explicit acceptance action.
4. The client calls `POST /api/me/legal-acceptances` with `document_key` and `document_version`.
5. QRFacile records timestamp, IP, user-agent, evidence and an audit event.
6. A new document version requires a new acceptance; prior evidence remains immutable.

## Application controls

The branch enables:

- security headers on all responses;
- HSTS when HTTPS is detected or `FORCE_HTTPS=1`;
- no-store caching for admin, application and API paths;
- public AI transparency policy at `/ai-policy`;
- protected compliance status endpoint;
- protected AI usage registration with hashed input/output evidence;
- mandatory pending human review for every registered AI output;
- administrative AI review queue;
- version-specific legal acceptance evidence;
- retention job with dry-run and explicit apply mode.

## E-label privacy gate

Public e-label pages must not include analytics, advertising pixels, profiling or fingerprinting. The regression test scans the public modules for common tracking providers. Any future telemetry on these pages requires a separate legal and technical review and must not identify or track visitors.

## Automated CI

`.github/workflows/compliance-ci.yml` runs on the compliance branch and on pull requests to `staging`. It compiles compliance modules, runs regression tests and checks that SQL migrations are transactional.

## Release gate

Do not merge to production until:

1. both SQL migrations succeed on staging;
2. GitHub Compliance CI passes;
3. `/ai-policy` renders correctly;
4. `/api/admin/compliance/status` returns `ok: true`;
5. legal status and acceptance APIs work with an authenticated test user;
6. response headers are verified over HTTPS;
7. retention is tested first in dry-run;
8. a human-review workflow approves AI records before publication.
