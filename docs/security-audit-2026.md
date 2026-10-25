# Security audit notes

## Dynamic SQL review

The SQL interpolation findings reviewed in July 2026 do not interpolate request
values. Search text, status, IDs and similar values are passed separately through
psycopg `%s` bindings.

The interpolated fragments are application-owned:

- optional `WHERE` clauses are assembled from fixed SQL literals;
- permission columns are selected from the fixed `can_view`, `can_edit` and
  `can_create` set;
- dashboard work filters select fixed `EXISTS` expressions after validating the
  mode against an internal tuple;
- public ingredient/allergen identifiers are returned only when they occur both
  in a fixed candidate list and in `information_schema.columns`.

`tests/test_security_regressions.py` locks these invariants. Any new file using an
f-string in `cursor.execute` remains a HIGH finding until it receives an
equivalent review and test.

## State-changing routes and account verification

Studio invitation acceptance is POST-only. The GET invitation route renders a
confirmation form and the administrator legal-acceptance GET route only lists
existing evidence.

An account becomes verified only after a transaction locks a token row selected
by its SHA-256 hash, rejects used/revoked/expired tokens, updates the user, and
marks the token used in the same transaction.

After `2026_email_verification_enforcement.sql`, new Cantina and Studio accounts
receive an initial verification attempt and cannot enter role-protected routes
until verified. Existing accounts retain their prior access state and are not
silently reclassified as verified. SMTP delivery remains a staging acceptance
requirement; a failed attempt leaves the account restricted with a protected resend path.

Session tokens are accepted only while their server-side `created_at`/`expires_at`
window remains within the 14-day maximum. Compatibility attempts cover the two
known session tables and epoch/timestamp schemas; a table without a usable expiry
column fails closed instead of accepting an unbounded token.
Logout and successful password reset revoke tokens from both compatible session
tables inside savepoints, so an optional missing table cannot undo the password
change. Session cookies receive the `Secure` attribute whenever the request or
configured application base URL uses HTTPS.

Verification-email creation locks the user row and reserves one of at most five
send attempts in a rolling 60-minute window before releasing the transaction.
Concurrent resend requests therefore cannot bypass the limit; provider delivery
success or failure is recorded on the hashed token without exposing it.

Password-reset requests lock the matched user, allow at most five requests per
60 minutes, keep the same public response for existing, missing and limited
accounts, and invalidate older unused links before creating a replacement.

Failed logins are recorded by SHA-256 identity hash and client address, never by
plain email. Transaction advisory locks make the 10-per-identity and 50-per-IP
limits within 15 minutes safe against concurrent attempts. Unknown identities
still run a real password-hash verification, and every rejected login uses the
same public error. Apply `sql/2026_login_rate_limit.sql` before this application
revision is enabled; records older than 24 hours are removed during subsequent
login attempts, and the migration is transaction-wrapped and idempotent. The
dedicated `2026_login_rate_limit_rollback.sql` removes only these transient
counters and leaves users, credentials and sessions unchanged.

All new passwords created through Cantina registration, Studio registration or
password reset use the same server-side policy: 12 to 128 characters. Matching
HTML bounds give immediate feedback but are not trusted for enforcement.
Both registration forms also require a matching confirmation before any account
is created. Existing password hashes and login compatibility are unchanged.

The central HTTP exception handler HTML-escapes exception details for both the
branded 403/404/405 pages and all other HTML error responses. Request-derived
error text can therefore no longer become executable markup through this path.
The email-verification error page applies the same escaping before embedding a
service error in its branded response.

User-controlled return destinations in winery-context selection, label
collaboration and print sending pass through one same-origin path validator.
Protocol-relative, encoded-slash, backslash and control-character variants fall
back to the dashboard. The active-winery context cookie is Secure under HTTPS.

The compliance retention job includes failed-login counters with a 24-hour
limit, in addition to request-time cleanup. Dry-run remains the default and
rolls back every deletion; applying changes still requires the explicit flag.
Expired password-reset token records have a 24-hour technical tail and expired
email-verification token records a seven-day tail under the same job. These are
proposed operational periods and still require the documented privacy review.

Compliance-incident creation bounds category, summary and serialized evidence;
evidence must be a JSON object rather than an arbitrary scalar or list. Reopened
incidents clear their previous closure timestamp while preserving the audit trail.

The AI-system registry cannot mark a system approved or enable automatic
publication through the current administration form. Personal-data use requires
a numeric retention period; special-category data additionally requires human
oversight and a verified DPA. A separate evidenced legal/security approval
workflow remains intentionally required before these gates can be opened.

The AI-output review queue escapes every database-derived value before rendering,
includes a CSRF token in each approval/rejection form, and returns a generic 503
instead of disclosing database exception details when its schema is unavailable.
