# QRFacile Link (`/d`) e base dei moduli verticali — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a shared base for vertical modules and the first module, QRFacile Link: one fixed QR at `/d/<slug>` whose content (Link, PDF, Mini-pagina) and statistics level the customer chooses, sold to everyone, shipped switched off.

**Architecture:** a `qrfacile_app/modules/` package holds the module registry, the admin on/off switches (database), pluggable content types, privacy-safe scan statistics and the public resolver; `qrfacile_app/modules/link/` holds the Link app pages. QR rows stay in `qr_items` (new `module`, `stats_level` columns; content in `payload`). Billing reuses the PayPal checkout and the Danea hand-off, extended with a per-user billing profile and a VAT quote per customer category.

**Tech Stack:** Python 3.12, FastAPI, psycopg 3, PostgreSQL 16, server-rendered HTML (`qrfacile_app/ui_shell.page`), Pillow, segno/qrcode, pytest (PostgreSQL integration tests via `QRFACILE_TEST_DATABASE_URL`).

**Spec:** `docs/superpowers/specs/2026-11-22-vertical-modules-design.md`

## Global Constraints

- Work on branch `claude/qrfacile-link-module` created from `origin/codex/production-integration-20261029` (contains `a3f97a3`); never push to the release branch; the release must not depend on this work.
- Everything ships **off**: with all switches off nothing visible changes and the beta pages (`/app/new-external`, `/app/external/<id>`, pack `generic_10`) behave exactly as in `a3f97a3`.
- Never break a printed QR: `/e/<slug>` (wine, and beta Link forward), legacy WordPress `/<slug>`, `/d/<slug>` of existing beta codes.
- Module prefixes: `e` = Wine (unchanged), `d` = Link, `r` = reserved for Menu Ristorante.
- Statistics: never store IP address, full user-agent, cookies or visitor identifiers; no cookies and no third-party scripts on public module pages.
- Prices: pack `generic_10` = 10 QR Link credits, **€29.00 VAT included** (net €23.77, VAT €5.23 at 22%); 3 free QR Link per account, then 1 `generic` credit per QR; changing type or content costs nothing.
- VAT table (to be validated by the accountant before `link_sales_foreign` is switched on): Italy any customer 22% included = €29.00; EU consumer 22% Italian under the OSS threshold of €10,000/year (above: destination rate from configuration); EU business with VIES-valid VAT number: non-taxable reverse charge, €23.77; extra-EU: outside the scope of Italian VAT, €23.77.
- Limits: Link URL http(s) ≤ 2000 chars; PDF ≤ 10 MB with `%PDF` signature; Mini-pagina title ≤ 80, text ≤ 600 chars, ≤ 6 buttons from {Chiama, WhatsApp, Email, Mappa, Sito, Instagram, Facebook}.
- Every authenticated POST uses CSRF (`csrf_input` / `require_csrf_or_same_origin`); every form control has an accessible name (tests in `tests/test_accessibility_fixes.py` already scan all non-admin modules); no inline fixed-column grids.
- SQL migrations are transactional (`scripts/check_sql_transactions.py`); tests stay green with PostgreSQL configured before every commit.

## Review Focus

1. A printed beta QR (`qr_type='external'`, payload `{"url": ...}`, created before migration) scanned after the migration and with module `link` off → still redirects to its URL.
2. A customer switches type from PDF to Link and back → the QR keeps working at each step and the previous PDF is still served after switching back without re-upload.
3. Hostile Mini-pagina input (`javascript:` URL in a button, `<script>` in text, 5,000-char text, 7 buttons) → rejected or escaped; never rendered as markup.
4. A file named `.pdf` that is an HTML or ZIP, or an 11 MB PDF → rejected with a clear message, nothing stored.
5. A bot or crawler storm on `/d/<slug>` with statistics "dettagliate" → one aggregated row per (day, hour, device, language), no per-request rows, response time unaffected if the stats write fails.

---

### Task 1: Branch, schema migration and switches table

**Files:**
- Create: `sql/2026_vertical_modules_base.sql`
- Test: `tests/test_vertical_modules_migration.py`

**Interfaces:**
- Produces (database): `qr_items.module text NULL` (index), `qr_items.stats_level text NOT NULL DEFAULT 'none' CHECK (stats_level IN ('none','counts','detailed'))`; table `qr_scan_daily(qr_item_id bigint REFERENCES qr_items(id) ON DELETE CASCADE, day date, hour smallint NOT NULL DEFAULT -1, device text NOT NULL DEFAULT '', lang text NOT NULL DEFAULT '', scans integer NOT NULL DEFAULT 0, PRIMARY KEY (qr_item_id, day, hour, device, lang))`; table `module_switches(key text PRIMARY KEY, enabled boolean NOT NULL DEFAULT false, updated_by bigint NULL, updated_at timestamptz NOT NULL DEFAULT now())` seeded with `link`, `link_sales_it`, `link_sales_foreign` all false; table `billing_profiles(user_id bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, customer_type text CHECK IN ('company','private','association'), country char(2), name text, vat_number text, fiscal_code text, address text, postcode text, city text, province text, sdi text, pec text, invoice_email text, vies_valid boolean, vies_checked_at timestamptz, updated_at timestamptz)`; table `abuse_reports(id bigserial, qr_item_id bigint, reason text, details text, created_at timestamptz DEFAULT now(), handled_at timestamptz, handled_by bigint)`; `users_role_check` extended with `'business'`; existing rows `qr_type='external'` get `module='link'` and payload `{"url": <old>, "type": "link", "content": {"link": {"url": <old>}}}` (keep top-level `url` for the beta code path).

- [ ] **Step 1:** `git fetch origin && git checkout -b claude/qrfacile-link-module origin/codex/production-integration-20261029`
- [ ] **Step 2: Write the failing integration test** `test_vertical_modules_migration_is_idempotent_and_keeps_beta_codes`: on a fresh schema with minimal `users(id, email, role)` + current `users_role_check`, `qr_items(id, owner_user_id, qr_type, status, slug, payload jsonb)` and one external row `{"url": "https://example.com"}`, apply the migration twice; assert switches `link`, `link_sales_it`, `link_sales_foreign` exist and are false, the external row has `module='link'`, `stats_level='none'`, `payload->>'url' == 'https://example.com'`, `payload->'content'->'link'->>'url' == 'https://example.com'`, and inserting a user with role `business` succeeds while role `xyz` fails.
- [ ] **Step 3:** Run `pytest tests/test_vertical_modules_migration.py -v` → FAIL (file missing).
- [ ] **Step 4:** Write `sql/2026_vertical_modules_base.sql` (`BEGIN; … COMMIT;`, `IF NOT EXISTS` everywhere, role constraint dropped and re-created with `'admin','winery','studio','collaborator','business'`).
- [ ] **Step 5:** Run the test → PASS; run `python scripts/check_sql_transactions.py` → `SQL transaction boundaries: OK`.
- [ ] **Step 6:** Commit `feat(modules): base schema, switches and beta Link migration`.

### Task 2: Module registry, switches and admin page

**Files:**
- Create: `qrfacile_app/modules/__init__.py`, `qrfacile_app/modules/registry.py`, `qrfacile_app/modules/switches.py`, `qrfacile_app/modules/admin_ui.py`
- Modify: `qrfacile_app/main.py` (include `qrfacile_app.modules.admin_ui` as optional router), `qrfacile_app/admin_home_ui.py` (link "Moduli")
- Test: `tests/test_modules_registry_switches.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) class Module: key: str; label: str; prefix: str; content_types: tuple[str, ...]; credit_type: str`; `MODULES: dict[str, Module]` with `link = Module("link", "QRFacile Link", "d", ("link", "pdf", "minipage"), "generic")`; `RESERVED_PREFIXES = frozenset({"e", "d", "r"})`.
- Produces: `is_enabled(key: str) -> bool` (reads `module_switches`, 10 s in-process cache, returns False on any database error); `set_enabled(key: str, enabled: bool, *, user_id: int) -> None` (updates row, writes `audit_log` action `module_switch_changed`, clears cache); `require_module(key: str, user: dict) -> None` (raises `HTTPException(404)` when off unless `user["role"] == "admin"`).
- Routes: `GET /admin/modules` (admin only: table of switches with state, last change, toggle forms), `POST /admin/modules/{key}` (CSRF, admin, form `enabled=on|off`).

- [ ] **Step 1: Tests:** `test_registry_declares_link_on_d_with_three_types` (asserts `MODULES["link"].prefix == "d"`, types tuple equals `("link","pdf","minipage")`, `"r" in RESERVED_PREFIXES`); `test_is_enabled_false_when_database_unavailable` (monkeypatch `pg` to raise → `False`); `test_require_module_hides_off_module_except_admin` (off → 404 for winery, no raise for admin); integration `test_set_enabled_persists_and_audits` (on test DB: toggles `link` on, `is_enabled("link")` True after cache clear, one `audit_log` row).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS; full suite green.
- [ ] **Step 5:** Commit `feat(modules): registry and admin on/off switches`.

### Task 3: Content types (Link, PDF, Mini-pagina)

**Files:**
- Create: `qrfacile_app/modules/content_types/__init__.py`, `base.py`, `link.py`, `pdf.py`, `minipage.py`
- Test: `tests/test_module_content_types.py`

**Interfaces:**
- Produces: `class ContentError(ValueError)` (message in Italian, safe to show); protocol `ContentType` with `key: str`, `label: str`, `def parse(form: Mapping[str, str], files: Mapping[str, UploadFile | None], previous: dict | None, *, qr_item_id: int) -> dict` (returns the content dict to store, raises `ContentError`), `def public_response(content: dict, *, slug: str) -> Response`, `def editor_html(content: dict | None, *, field_prefix: str) -> str` (labelled controls); `CONTENT_TYPES: dict[str, ContentType]`; `get_type(key: str) -> ContentType` (KeyError for unknown).
- Link: content `{"url": str}`; reuse `external_qr_ui._valid_target`; `public_response` = 302 `Cache-Control: no-store`.
- PDF: stored under `get_uploads_dir()/modules/link/<qr_item_id>/<sha256[:16]>.pdf`; content `{"file": "<relative path>", "name": "<original name sanitized>", "size": int, "sha256": str}`; max `10 * 1024 * 1024` bytes; first 5 bytes `b"%PDF-"`; when no new file is uploaded and `previous` has a file, keep it; `public_response` = `FileResponse` with `media_type="application/pdf"`, `Content-Disposition: inline; filename="<name>"`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`.
- Mini-pagina: content `{"title", "text", "logo"?, "buttons": [{"kind", "value"}]}`; kinds `call` (phone digits/+/space, 6–20 chars), `whatsapp` (digits 8–15 after normalization), `email` (one @, ≤ 254), `map` (free text address → `https://www.google.com/maps/search/?api=1&query=<urlencoded>`) and `site`/`instagram`/`facebook` (http(s) URL); logo uses the same image validation as `wine_images_ui._validate_image_bytes` (≤ 5 MB) saved under the same folder; `public_response` = standalone HTML page (no cookies, no external scripts, `lang="it"`, escaped values, footer link "Segnala contenuto" to `/segnala/<slug>`).

- [ ] **Step 1: Tests** (each asserting exact values from Global Constraints): `test_link_rejects_javascript_and_long_urls`; `test_pdf_rejects_non_pdf_and_over_10mb` (HTML bytes named `x.pdf` → `ContentError`; 10 MB + 1 byte → `ContentError`; valid → file exists, content `size` and `sha256` set); `test_pdf_keeps_previous_file_when_none_uploaded`; `test_pdf_public_response_headers` (`application/pdf`, `inline`, `nosniff`); `test_minipage_limits_and_escaping` (81-char title, 601-char text, 7 buttons → `ContentError`; `<script>` in text rendered escaped; `javascript:` site URL → `ContentError`); `test_minipage_button_links` (call → `tel:`, whatsapp → `https://wa.me/<digits>`, email → `mailto:`, map → Google Maps search URL); `test_editor_controls_are_labelled` (every `<input|select|textarea>` in each `editor_html` has an id with matching `for=` or `aria-label`).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(modules): link, pdf and mini-page content types`.

### Task 4: Privacy-safe scan statistics

**Files:**
- Create: `qrfacile_app/modules/stats.py`
- Test: `tests/test_module_stats.py`

**Interfaces:**
- Produces: `STATS_LEVELS = ("none", "counts", "detailed")`; `device_category(user_agent: str) -> str` returning one of `"iphone"`, `"android"`, `"tablet"`, `"computer"`, `"other"`; `primary_language(accept_language: str) -> str` (2-letter lowercase or `""`); `record_scan(cur, *, qr_item_id: int, level: str, user_agent: str, accept_language: str, now: datetime) -> None` (level `none` → no statement; `counts` → row (day, hour=-1, '', '') +1; `detailed` → row (day, hour, device, lang) +1; single `INSERT … ON CONFLICT … DO UPDATE SET scans = qr_scan_daily.scans + 1`); `summary(cur, *, qr_item_id: int, days: int = 30) -> dict` with keys `total`, `by_day` (list of (date, int)), `by_device`, `by_lang`, `by_hour`.

- [ ] **Step 1: Tests:** `test_device_and_language_normalization` (iPhone UA → `iphone`, Android phone → `android`, iPad → `tablet`, Windows desktop → `computer`, `""` → `other`; `"it-IT,it;q=0.9,en;q=0.8"` → `"it"`); `test_none_level_writes_nothing` (fake cursor records no execute); integration `test_detailed_level_aggregates_without_personal_data` (100 calls same hour/device/lang → one row with `scans == 100`; table columns are exactly qr_item_id, day, hour, device, lang, scans); `test_summary_counts_level` (counts rows summed per day).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(modules): aggregated scan statistics without personal data`.

### Task 5: Public resolver for `/d/<slug>`

**Files:**
- Create: `qrfacile_app/modules/public.py`
- Modify: `qrfacile_app/external_qr_ui.py` (remove `direct_link_public`, keep `_valid_target`, `_NOT_FOUND_HTML`), `qrfacile_app/main.py` (mandatory router `qrfacile_app.modules.public`, replacing the `/d` duty of `external_qr_ui`)
- Test: `tests/test_module_public_resolver.py`; update `tests/test_direct_link_beta.py` to call the new resolver

**Interfaces:**
- Consumes: `get_type`, `record_scan`, `_valid_target`.
- Produces: `GET /d/{slug}` → `resolve_module_qr(request: Request, slug: str, *, module: str = "link") -> Response`: looks up `qr_items` by slug with `module='link'` or `qr_type='external'`; status must be `attiva`; content type from `payload->>'type'` (default `link` using `payload->>'url'` for unmigrated rows); stats recorded in its own short transaction wrapped in `try/except` (a failure never blocks the response); 404 `_NOT_FOUND_HTML` (with "Segnala contenuto" link) otherwise. Works whether or not the `link` switch is on (never break a printed QR).

- [ ] **Step 1: Tests:** `test_unmigrated_beta_row_still_redirects` (payload `{"url": ...}` only, switch off → 302); `test_pdf_and_minipage_are_served`; `test_draft_or_unknown_slug_is_404`; `test_stats_failure_does_not_block_redirect` (monkeypatch `record_scan` to raise → still 302); `test_e_forward_still_points_to_d` (existing assertion in `public.py`).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS; `tests/test_direct_link_beta.py` green.
- [ ] **Step 5:** Commit `feat(modules): public resolver for /d with content types and stats`.

### Task 6: Billing profile and VAT quote

**Files:**
- Create: `qrfacile_app/services/billing_profile.py`, `qrfacile_app/services/vat.py`, `qrfacile_app/modules/billing_ui.py`
- Modify: `qrfacile_app/pricing_config.py` (constants below)
- Test: `tests/test_billing_profile_vat.py`

**Interfaces:**
- `pricing_config`: `LINK_PACK_KEY = "generic_10"`, `generic_10["amount_cents"] = 2900` unchanged, new `generic_10["prices_include_vat"] = True`; `OSS_THRESHOLD_CENTS = 1_000_000`; `EU_VAT_RATES: dict[str, str]` (country → rate string, marked `# validate with accountant`); `FOREIGN_VAT_CODES: dict[str, dict]` keys `eu_reverse_charge`, `extra_eu`, `eu_consumer_oss` each `{"perc": int, "class": str, "description": str, "note": str}` (placeholder values flagged for the accountant).
- `billing_profile`: `normalize_billing_profile(data: Mapping[str, str]) -> dict` (Italy company: P.IVA via `italian_vat_is_well_formed`, SDI 7 chars or PEC; Italy private: codice fiscale 16 chars, destination code `0000000`; association: codice fiscale 11 or 16; foreign: country ≠ IT, name, address, optional EU VAT number); raises `HTTPException(422, <italiano>)`; `load_billing_profile(cur, user_id: int) -> dict | None`; `save_billing_profile(cur, user_id: int, profile: dict) -> None`; `vies_check(country: str, vat_number: str, *, timeout: float = 8.0) -> bool | None` (EU VIES REST `https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number`; `None` when unreachable).
- `vat`: `link_quote(*, profile: dict, gross_cents: int = 2900, oss_threshold_exceeded: bool, foreign_enabled: bool) -> dict` returning `{"category", "vat_rate", "net_cents", "vat_cents", "gross_cents", "vat_code", "exemption_note"}` with categories `it`, `eu_consumer`, `eu_business_reverse_charge`, `extra_eu`; raises `HTTPException(422)` when the customer is foreign and `foreign_enabled` is False, or EU business with `vies_valid is not True`.
- Routes: `GET/POST /app/billing-profile` (any logged role; CSRF; labelled form; used before Link purchases).

- [ ] **Step 1: Tests with exact values:** `test_italy_any_customer_pays_2900_with_22` (net 2377, vat 523); `test_eu_consumer_under_threshold_uses_italian_22`; `test_eu_consumer_over_threshold_uses_destination_rate` (DE 19% → net 2437, vat 463, gross 2900); `test_eu_business_vies_valid_reverse_charge` (gross 2377, vat 0, category `eu_business_reverse_charge`); `test_eu_business_without_vies_is_refused`; `test_extra_eu_outside_scope` (gross 2377, vat 0); `test_foreign_refused_when_foreign_sales_off`; `test_profile_normalization` (Italian private: CF 16 chars and destination `0000000`; company without SDI and PEC → 422).
- [ ] **Step 2:** FAIL. **Step 3:** Implement (all money in integer cents, `ROUND_HALF_UP`; net = round(gross × 100 / (100 + rate))). **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(billing): per-user billing profile and VAT quote for Link`.

### Task 7: Checkout and Danea hand-off for Link packs

**Files:**
- Modify: `qrfacile_app/paypal_ui.py` (`paypal_start`), `qrfacile_app/services/invoice_handoff.py`
- Test: `tests/test_link_checkout_invoice.py`

**Interfaces:**
- Consumes: `link_quote`, `load_billing_profile`, `is_enabled`.
- `paypal_start`: when `pack == LINK_PACK_KEY` and `is_enabled("link_sales_it")`: require a billing profile (redirect `/app/billing-profile?next=/app/billing` if missing or invalid), build `snapshot = {"version": "link-2026-11-22", "kind": "link", "pack", "name", "generic_credits": 10, "wine_credits": 0, **link_quote(...), "customer": profile}`, `total_cents = snapshot["gross_cents"]`; roles `business`, `winery`, `studio` allowed. When `link_sales_it` is off: unchanged beta behaviour.
- `invoice_handoff.invoice_data`: accept snapshots with `kind == "link"`: customer name, VAT or fiscal code, country, destination code (`SDI`, `0000000` Italian private, `XXXXXXX` foreign), VAT row from `vat_code`/`vat_rate`, exemption note in `InternalComment` and row description; Wine snapshots unchanged.
- Fulfilment: `_fulfill_completed_order` already credits `generic_credits`; no change except reading them from the snapshot via `load_order_product`.

- [ ] **Step 1: Tests:** `test_link_purchase_requires_billing_profile_when_sales_on`; `test_link_purchase_unchanged_when_sales_off` (no snapshot, amount 2900); `test_link_snapshot_amount_matches_quote` (extra-EU profile → order amount 2377); `test_invoice_xml_for_italian_private` (`CustomerFiscalCode` set, `CustomerEInvoiceDestCode` `0000000`, Total 29.00, VAT 22); `test_invoice_xml_for_reverse_charge` (`CustomerEInvoiceDestCode` `XXXXXXX`, VatCode Perc 0, exemption note present); `test_wine_invoice_unchanged` (existing tests stay green).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(link): checkout snapshot and Danea hand-off for Link packs`.

### Task 8: "Azienda o professionista" registration and role routing

**Files:**
- Create: `qrfacile_app/modules/link/register_ui.py`
- Modify: `qrfacile_app/auth_routes.py` (business lands on `/app/link`), `qrfacile_app/ui_shell.py` (business sidebar: Link, Crediti, Dati di fatturazione, Esci), `qrfacile_app/billing_ui.py` and `paypal_ui.py` role tuples include `business`
- Test: `tests/test_business_registration.py`

**Interfaces:**
- Routes: `GET/POST /register-business` (404 when `link` off): email, password, confirm, business name, Terms, Privacy; creates `users(role='business', email_verification_required=TRUE)`, seeds no wine credits, `record_registration_acceptances`, `create_verification`; redirect `/login?created=1`.

- [ ] **Step 1: Tests:** `test_register_business_404_when_link_off`; `test_register_business_creates_verified_required_user` (fake DB: role `business`, no `credit_ledger` wine row); `test_business_login_lands_on_link`; `test_business_sidebar_has_no_wine_entries`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(link): business registration and navigation`.

### Task 9: Link app area

**Files:**
- Create: `qrfacile_app/modules/link/__init__.py`, `qrfacile_app/modules/link/app_ui.py`
- Modify: `qrfacile_app/main.py` (optional router), `qrfacile_app/external_qr_ui.py` (when `link` is on: `/app/new-external` → 303 `/app/link/new`, `/app/external/<id>` → 303 `/app/link/<id>`), `qrfacile_app/ui_shell.py` (sidebar "QR Link" → `/app/link` when on)
- Test: `tests/test_link_app_area.py`

**Interfaces:**
- Routes (all `require_module("link", user)`, roles `business`, `winery`, `studio`, `admin`, owner-only access like `_owned_external`):
  - `GET /app/link` — list (name, type label, state, 30-day scans when stats on), "Crea un QR", first-use 3-step guide when empty.
  - `GET/POST /app/link/new` — name + type; consumes 1 `generic` credit after the 3 free (same count as beta: rows with `module='link'` or `qr_type='external'` owned by the user); slug from `util.new_slug`; `public_path=/d/<slug>`; status `bozza`.
  - `GET /app/link/{id}` — editor: type tabs (`editor_html` per type), stats level radio (`none`/`counts`/`detailed` with one-line explanations), preview image, downloads, "Prova il QR", Pubblica / Metti in bozza, stats summary.
  - `POST /app/link/{id}/content` (multipart, CSRF) — `get_type(type).parse(...)`; stores `payload = {"type", "content": {type: content, ...other types kept}, "url"?: link url}`.
  - `POST /app/link/{id}/stats` (CSRF) — level in `STATS_LEVELS`.
  - `POST /app/link/{id}/status` (CSRF) — `attiva` only if current type content is valid.
  - `GET /app/link/{id}/qr.{png,svg,pdf}` — via `export_qr_ui._qr_png/_qr_svg/_qr_pdf_a4` with `/d/<slug>`.

- [ ] **Step 1: Tests:** `test_link_area_404_when_off_for_customers`; `test_create_uses_free_quota_then_credit` (4th QR inserts a `-1 generic` ledger row; with 0 balance → redirect billing); `test_switching_type_keeps_other_content` (Review Focus 2); `test_publish_refuses_invalid_content`; `test_downloads_use_d_url`; `test_beta_pages_redirect_only_when_on`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS; accessibility scan tests green.
- [ ] **Step 5:** Commit `feat(link): customer area to create, edit and publish Link QR codes`.

### Task 10: Legal addendum, abuse reports and first-use acceptance

**Files:**
- Create: `docs/legal/2026-11-22-link-terms-privacy-draft.md` (owner approval), `qrfacile_app/modules/abuse_ui.py`
- Modify: `qrfacile_app/modules/link/app_ui.py` (first-use acceptance gate), `qrfacile_app/legal_core.py` (constants for the new versions, unused until activation)
- Test: `tests/test_link_legal_abuse.py`

**Interfaces:**
- Draft text: Terms clause on customer content (responsibility, forbidden content, removal on report) and Privacy paragraph on aggregated statistics processed for the customer; new versions `terms: "2026-12-link"`, `privacy: "2026-12-link"` declared as `LINK_LEGAL_DOCUMENTS` and activated together with the `link` switch.
- Routes: `GET/POST /segnala/{slug}` (public, no login, honeypot field, max 5 reports per slug per hour, stores `abuse_reports`), `GET /admin/abuse-reports` + `POST /admin/abuse-reports/{id}/handled` (admin, CSRF), admin can set a QR to `bozza` from the report.
- First use: `/app/link` shows an acceptance form when the user has no acceptance row for `LINK_LEGAL_DOCUMENTS`; recorded like `record_registration_acceptances`.

- [ ] **Step 1: Tests:** `test_abuse_report_rate_limited_and_honeypot`; `test_admin_can_handle_and_unpublish`; `test_first_use_requires_link_terms`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(link): legal addendum draft, abuse reports and first-use acceptance`.

### Task 11: Historic QR check, public pages and handover

**Files:**
- Modify: `scripts/check_historic_qr.py` (include `/d` rows: `module='link'` or `qr_type='external'`, active; outcome `ok` for 2xx/3xx), `qrfacile_app/landing_routes.py` (`/link` page: "Attivo", CTA to `/register-business` when `link` on; unchanged when off), `qrfacile_app/pricing_ui.py` (Link section with €29 IVA inclusa when on)
- Create: `docs/LINK_MODULE_STAGING_ACCEPTANCE.md` (Codex checklist: migration on staging, switch on, UX/axe/400 % zoom, PDF upload abuse cases, stats aggregation, Sandbox purchase IT + extra-EU profile with Danea mail, abuse report, switch off → nothing visible)
- Test: `tests/test_historic_qr_check.py` (extend), `tests/test_link_public_pages.py`

- [ ] **Step 1: Tests:** `test_historic_check_includes_link_codes` (redirect counted as ok); `test_link_landing_changes_only_when_on`; `test_pricing_shows_link_pack_vat_included_when_on`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS; full suite, `project_security_audit.py --fail-on critical`, `check_sql_transactions.py`, detect-secrets, `git diff --check`.
- [ ] **Step 5:** Commit `feat(link): public pages, historic QR check and staging checklist`; push `claude/qrfacile-link-module`.
