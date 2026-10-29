# QRFacile production release gate — 2026-10-29

This document records technical evidence for the Wine B2B production release candidate. It is not a legal, accounting, accessibility, or security certification.

## Exact release state

- Production baseline branch: `main`
- Installed production baseline: `de0a4f1d848e68b5ea4113b3b80d2fa94cc23ffd`
- Preserved baseline branch: `legacy/production-de0a4f1-20261029`
- Preserved baseline tag: `production-baseline-de0a4f1-20261029`
- Release branch: `codex/production-integration-20261029`
- Release PR: `#12`, Draft, targeting `main`
- Initial integrated release-candidate SHA: `ca6581e949ccbbbc020183adab61441fc3fb0d0f`
- Initial integration Compliance CI: run `40905902204`, successful
- Staging installed SHA: `59cf70a834dbdd300fc93af35898e7c455753f73`
- Production remains unchanged at the baseline SHA.
- The authoritative current candidate is always the live head of Draft PR `#12`; its exact SHA and latest Compliance CI must be read again before any gate decision.

## Verified backup and restore

Successful production backup:

- Path: `/opt/qrfacile-backups/production/20261029_164543-production-de0a4f1d848e`
- Database dump SHA-256: `443eed3afab38596226157f704e45fc87e9ee6e61da458770562413487049b8e`
- Filesystem archive SHA-256: `6461fe2c6cb02b27cf882caeced51b5941dc22c5f7ed813bdc17c77f2f4a0d7d`
- Database dump size: 204722 bytes
- Filesystem archive size: 76844127 bytes
- Dump listing, archive integrity, and SHA-256 verification: successful
- Restore into an isolated temporary database with application ownership: successful
- Ownership mismatches after restore: 0

The earlier directory `20261029_164317-production-de0a4f1d848e` is an incomplete failed attempt and is not a valid backup or rollback source.

## Migration rehearsal

The exact production backup was restored into an isolated temporary database. The following release sequence was applied twice, in order, under the application database role:

1. `2026_legal_ai_compliance.sql`
2. `2026_legal_acceptance_constraints.sql`
3. `2026_privacy_requests.sql`
4. `2026_ai_system_registry.sql`
5. `2026_wine_compliance_replays.sql`
6. `2026_collaboration_access_hardening.sql`
7. `2026_invitation_lifecycle.sql`
8. `2026_invitation_acceptance_hardening.sql`
9. `2026_email_verification.sql`
10. `2026_production_qr_wines_qr_item_unique.sql`
11. `2026_unified_invitations.sql`
12. `2026_orders_payment_environment.sql`
13. `2026_sell_ready_legal_documents.sql`
14. `2026_annual_wine_packages.sql`
15. `2026_winery_fiscal_profile.sql`
16. `2026_email_verification_enforcement.sql`
17. `2026_login_rate_limit.sql`
18. `2026_terms_single_reference_qr.sql`
19. `2026_paypal_webhook_events.sql`

Both passes succeeded. The staging-only duplicate repair must never be used in production.

Post-migration evidence from the restored copy:

- users: 13 (unchanged)
- orders: 36 (unchanged)
- QR items: 48 (unchanged)
- winery/Studio legacy invitations: 16 (preserved)
- unified invitations: 16
- plaintext invitation tokens: 0
- duplicate `qr_wines.qr_item_id` groups: 0
- QR item 22 and populated wine 8 preserved, including 2 assets and 1 label
- only empty duplicate wine row 7 removed after exact fingerprint and relationship checks
- duplicate-repair audit entries: 1 after two migration passes
- current Terms version: `2026-10-29`; prior version preserved and retired
- payment reconciliation after the candidate payment, annual-package and webhook migrations: 3 paid orders; 0 missing/duplicate captures, invalid paid amounts/currencies, missing paid timestamps, orphan/non-paid grants, user mismatches or open refund reviews; the same 3 historical paid orders remain `payment_environment='unknown'` and require an explicit accounting decision rather than automatic reclassification

## Verification matrix

| Requirement | Source and automated tests | Staging | Production | Residual risk / closing evidence |
| --- | --- | --- | --- | --- |
| Annual Wine packages and 25-year option | Implemented and covered by regression tests | Installed and exercised with the verified staging release | Not installed | Accounting and commercial approval of prices and tax treatment |
| VAT-exclusive order calculation and fiscal snapshot | Implemented with frozen snapshots, aggregate reconciliation probe and fail-closed refund/dispute runbook | Tested in staging flows | Not installed | Accountant approval of `PAYMENT_REFUND_DISPUTE_RUNBOOK_2026-10-29.md`, historical `unknown` classification and invoicing rules |
| Winery and Studio onboarding | Implemented and covered by regression tests | Main flows exercised | Legacy version only | Final acceptance run on the production SHA after deployment |
| Studio single-label access | Fail-closed access controls and tests present | Verified in the staging release | Legacy version only | Post-deploy authorization smoke test with non-production test identities |
| Checkout and PayPal idempotency | Return e webhook condividono fulfillment atomico; firma, ambiente, importo, valuta ed event ID verificati | Sandbox OAuth e creazione ordine verificati; prova provider webhook ancora richiesta | Sandbox-only configuration present | Secret store Live, evento webhook Sandbox firmato, alert revisione manuale e URL Live; nessun pagamento reale autorizzato |
| Privacy, GDPR and data-subject processes | Routes, audit trail, terminal-resolution and incident-closure guards, retention, incident documentation e probe SLA aggregato senza PII presenti | Technical controls available | Not installed | DPO/legal approval, named owners, alert delivery, SLA and processor/subprocessor decisions |
| AI governance and human review | Registry and fail-closed human-review controls present | Technical workflow available | Not installed | Legal classification, AI literacy evidence, approved provider/DPA before activation |
| Account and administration security | CSRF, rate limiting, session and role checks covered | Compliance and staging checks green | Legacy version only | Post-deploy smoke test and operational alert ownership |
| Accessibility | Automated checks and a fail-closed manual acceptance protocol cover essential flows | Technical review completed; protocol not yet executed on current candidate | Not installed | Complete `ACCESSIBILITY_ACCEPTANCE_2026-10-29.md` with keyboard, screen reader and 200%/400% zoom evidence on the installed SHA |
| SEO and AI discoverability | Technical metadata, public-route coverage and read-only HTTP preflight present | Installed | Legacy version only | Staging and production-domain preflight/indexability readback after deployment |
| Backup, restore and rollback | Release scripts, migration checks and fail-closed preflight con validazione approvazioni SHA/PR present | Staging backup/restore evidence recorded | Fresh production backup and isolated restore verified | Complete approvals, then run `check_release_preflight.py` against exact candidate, fresh backup and current rollback tree immediately before deployment |
| Monitoring and transactional email | Mittente centralizzato; errori SMTP sanitizzati; probe composti da aggregatore read-only e wrapper alert fail-closed senza payload/PII | Technical path implemented | Not verified for the release candidate | Named on-call owner, runtime recipient, scheduler, real alert delivery test and transactional-email delivery evidence |
| Historical QR preservation | Migration is exact, fail-closed, transactional and audited | Historical staging QR verified | 48 QR items preserved in restore rehearsal | Public QR sample and complete count readback after deployment |

## Automated evidence

- Local regression suite: 385 passed, 6 skipped
- Static project security audit: 0 findings
- Dependency audit: no known vulnerabilities
- Secret scan: 305 tracked files, no findings
- Python compilation/import checks: successful
- SQL transaction-boundary check: successful
- Production migration parse and isolated execution: successful
- Initial GitHub Compliance CI: run `40905902204`, successful on the initial integrated SHA; use the live PR head for the current CI evidence

## Mandatory external gates

The PR must remain Draft and production sales must remain disabled until all of the following are recorded with a name, role, date, and scope:

- commercial approval of the published offer and claims;
- accounting approval of prices, VAT handling, invoices, reconciliation, refunds, and supported customer jurisdictions;
- legal/DPO approval of Terms, Privacy information, DPA, retention, data-subject procedures, and AI governance;
- operational ownership and SLA for privacy requests, incidents, backups, monitoring, customer support, and payment reconciliation;
- evidence that PayPal Live credentials and webhook configuration already exist in the authorized secret store.

No real payment is part of the release procedure. If a credential is absent, it must be provisioned by an authorized human and must never be placed in Git, logs, or chat.

## Canonical next step

Record the external approvals above and confirm the authorized Live secret-store path. Then re-check that PR #12, remote branch, CI head, backup, and production baseline still match the exact SHAs before converting the PR from Draft to Ready.

Prepared operator documents:

- `PRODUCTION_APPROVALS_2026-10-29.md`
- `PAYPAL_LIVE_READINESS_2026-10-29.md`
- `PRODUCTION_DEPLOY_RUNBOOK_2026-10-29.md`
- `ACCESSIBILITY_ACCEPTANCE_2026-10-29.md`
- `PAYMENT_REFUND_DISPUTE_RUNBOOK_2026-10-29.md`
