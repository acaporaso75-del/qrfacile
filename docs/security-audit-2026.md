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
