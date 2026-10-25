# Wine B2B annual packages — local implementation, not released

## Approved catalogue

| Product code | Package | Units / 12 months | Net EUR | Italian ordinary VAT 22% | Gross EUR |
|---|---|---:|---:|---:|---:|
| annual_start | Start | 15 | 99.00 | 21.78 | 120.78 |
| annual_winery | Cantina | 50 | 179.00 | 39.38 | 218.38 |
| annual_business | Business | 100 | 299.00 | 65.78 | 364.78 |

One unit creates one 10-year wine QR; two create one 25-year QR. Duration is measured in calendar years from QR creation, including leap-day handling.
The 15-unit plan supports seven 25-year QRs and one remaining unit.
The old upgrade proposal remains a **support-request operation**, not an automated self-service endpoint.
Studio / multi-winery / large volumes require a quotation. Annual self-service checkout is restricted to winery accounts so payment and credit ownership cannot diverge.

Each paid order grants its own allowance for 12 calendar months. Manual renewal only; no PayPal subscription or automatic charge.
Unused units expire, without rollover or extension through another purchase.
Existing QR records are not changed when annual units expire. Existing correction permissions are unchanged.
Historical start/pro/plus orders retain their original 20/60/200 credits and amounts. Those product codes are no longer available for new purchases.

## Payment and tax boundaries

The server computes net, VAT and total and freezes the purchased terms and saved customer details in orders.commercial_snapshot.
The checkout requires confirmation of professional use, Italian fiscal location and ordinary VAT treatment.
Saved foreign-country details or missing/malformed VAT numbers block checkout. The current VAT check is **format only**, not an official verification of tax registration.
Foreign and special tax cases require a reviewed quotation, not an automatic zero-rate decision.
The new tax treatment applies to the new annual Wine products; existing generic/assisted products were not repriced.
Invoice issuance/reconciliation and fiscal master-data completeness still require staging acceptance and accounting validation before release.

PayPal responses must match the saved order ID, amount, currency and completed capture.
Grant and paid status are saved together, with row locking and a unique annual order-grant index.
The same paid order cannot grant twice. Provider calls in local tests are mocks, not proof of an actual sandbox/live settlement.

## Database and release order

1. Review the actual staging schema and take a verified backup.
2. Apply the previously prepared payment-environment and legal-document migrations as applicable.
3. Apply sql/2026_annual_wine_packages.sql **before** starting this application version.
4. Verify view/trigger definitions and compare historical balances and QR records before/after.
5. Run native PostgreSQL integration, two-session concurrent spending, sandbox checkout/capture/retry,
   and browser acceptance for winery and Studio roles.
6. Obtain separate release authorization. No production migration/deploy/PayPal Live configuration is authorized.

credit_ledger retains the original events; available_credit_ledger computes effective balances.
Expired grants contribute only annual_used, offsetting the already recorded debits without removing perpetual credits.
A trigger allocates negative wine movements against earliest-expiring grants before perpetual credits and serializes customer movements with an advisory transaction lock.
All application balance readers use the effective view. Historical ledger screens continue to show the actual events; the billing screen lists annual remaining units and their expiry separately.

Do not roll back to old application balance queries after selling annual units: they would count expired grants.
Before the first annual sale a reviewed rollback may restore old application/views; after sales, use a forward fix or a reconciled database restoration.
The migration does not delete existing rows and is transaction-wrapped and repeatable.
The 2026-10-25 legal version is still unreleased; its public terms hash has been updated. Never overwrite an accepted/released legal version in a future release.

## Local verification

Final local result after Studio-access hardening: **279 passed, 0 skipped** using an isolated native
PostgreSQL 16.15 database bound to 127.0.0.1. This includes the two-connection overspend test and
the staging reconciliation migration/rollback test. The separate in-memory PostgreSQL/PGlite run
also passed all **18** assertions.
Dependency audit found no known vulnerabilities; pip check, compile/import, secret scan,
SQL parse/transaction guards and git diff formatting passed.

- Python regression suite, application import with warnings as errors, SQL transaction guard and security checks.
- scripts/test_annual_packages_pglite.mjs: 18 real PostgreSQL-engine checks using local PGlite 0.5.11 in memory:
  migration replay, FIFO use, unused expiry, perpetual preservation, spent-grant expiry, rejected overdraft,
  duplicate order grant, rollback and unchanged existing-label fixture.
- tests/test_annual_packages_database.py: native PostgreSQL expiry and two-connection concurrency tests
  passed through QRFACILE_TEST_DATABASE_URL pointing to the local qrfacile_test_native database.
  This is still not a substitute for actual staging-schema verification.
- No remote CI run, push, merge, deploy, production write, real payment, or credentials change performed.
- Security audit: **0 findings** after requiring both the winery connection and an active per-label assignment
  on Studio dashboard, preview, wine hub, label ACL and bulk-export paths. Legacy duplicate invitation acceptance
  is no longer registered; the active creation/acceptance routes use hashed invitations. Reviewed owner-only
  Studio-selection queries carry narrow audit annotations and regression coverage.
  This remains a source-level result, not a blanket security/GDPR/AI Act clearance or a production acceptance.
