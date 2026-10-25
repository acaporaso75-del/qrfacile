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
