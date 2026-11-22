# QRFacile Link — collaudo su staging

Branch: `claude/qrfacile-link-module` (separato dal rilascio Wine, PR #12).
Esegue: Codex su staging (192.168.1.139 / DB 192.168.1.143). **Nessuna azione in
produzione.** Segreti mai stampati. Ogni punto: PASS / FAIL con evidenza breve.

## 0. Prima di tutto
- [ ] Backup DB staging (dump) e tag del commit attuale di staging.
- [ ] Deploy del branch su staging con `scripts/deploy_staging.sh`.
- [ ] Migrazione: `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/2026_vertical_modules_base.sql`
      due volte (idempotente). Verificare: 4 switch tutti `false`, righe `qr_type='external'`
      con `module='link'` e `payload.type='link'`.
- [ ] `python scripts/check_sql_transactions.py`, `pytest -q` sul server: verdi.

## 1. Switch spento = nulla cambia
- [ ] `/`, `/link`, `/pricing`: Link "In arrivo", nessun prezzo Link, nessun link a `/register-business`.
- [ ] `/register-business`, `/app/link` → 404 per un utente non admin.
- [ ] QR Link beta già stampati: `/d/<slug>` → 302 alla destinazione; `/e/<slug>` beta → 301 a `/d/`.
- [ ] `python scripts/check_historic_qr.py --base-url http://127.0.0.1:8001` →
      `HISTORIC_QR_OK`, con `link=N/broken=0`.

## 2. Switch `link` acceso (da `/admin/modules`)
- [ ] Home: card "Link Diretto" Attivo; `/link` con CTA "Crea il tuo account gratuito"; `/pricing` con "€ 29 IVA inclusa".
- [ ] Registrazione `/register-business` → mail di verifica → login → atterra su `/app/link`.
- [ ] Primo accesso: modulo di accettazione condizioni Link; senza spunta non si prosegue.
- [ ] Sidebar account Azienda: solo "I miei QR", "Crediti", "Dati di fatturazione"; nessuna voce vino.
- [ ] Crea 3 QR gratis (Link, PDF, Mini-pagina); il 4° senza crediti → pagina Crediti.
- [ ] Link: `javascript:` rifiutato; URL valido → pubblica → "Prova il QR" apre la destinazione.
- [ ] PDF: file non PDF rinominato `.pdf` rifiutato; PDF > 10 MB rifiutato; PDF valido si apre inline.
- [ ] Mini-pagina: titolo obbligatorio; pulsanti tel/WhatsApp/email/mappa/sito corretti; testo con `<script>` mostrato come testo; nessun `<script>` nella pagina pubblica.
- [ ] Cambio tipo (Link → PDF → Link): il link precedente è ancora compilato.
- [ ] Download PNG/SVG/PDF: il QR contiene `https://<host>/d/<slug>`.
- [ ] Statistiche: livello "Solo numero" → 10 scansioni = una riga con `scans=10`; livello "Dettagliate" → righe per ora/dispositivo/lingua; nessuna colonna con IP o user agent (`\d qr_scan_daily`).
- [ ] Utente Cantina: voce sidebar "QR Link" porta a `/app/link`; `/app/new-external` e `/app/external/<id>` reindirizzano.
- [ ] Accesso a QR di un altro utente → 403.

## 3. Accessibilità
- [ ] axe-core 4.10 su `/link`, `/register-business`, `/app/link`, `/app/link/new`, `/app/link/<id>`, `/app/billing-profile`, `/segnala/<slug>`: 0 violazioni serious/critical.
- [ ] Zoom 400 % / 320 px: nessuno scroll orizzontale; tutti i controlli raggiungibili da tastiera con focus visibile.

## 4. Acquisto in PayPal **Sandbox** (switch `link_sales_it` acceso)
- [ ] Senza profilo di fatturazione → rimando a `/app/billing-profile`.
- [ ] Privato italiano (codice fiscale) → ordine € 29,00; mail Danea con file `.DefXml`:
      `CustomerFiscalCode` valorizzato, `CustomerEInvoiceDestCode` `0000000`, IVA 22 % € 5,23, oggetto con "[TEST SANDBOX - NON FATTURARE]".
- [ ] Azienda italiana (P.IVA + SDI) → € 29,00, IVA 22 %.
- [ ] Profilo extra-UE con `link_sales_foreign` **spento** → acquisto rifiutato con messaggio chiaro.
- [ ] Con `link_sales_foreign` acceso: extra-UE → € 23,77 senza IVA, nota "non soggetta"; azienda UE con VIES valido → € 23,77 reverse charge.
- [ ] Dopo il pagamento: +10 crediti QR Link nel registro crediti.
- [ ] Riportare `link_sales_foreign` a spento (resta spento fino all'ok del commercialista).

## 5. Segnalazioni
- [ ] `/segnala/<slug>` senza login: invio OK; 6ª segnalazione nella stessa ora non registrata; campo nascosto compilato → nessuna riga.
- [ ] `/admin/abuse-reports`: "Sospendi il QR e chiudi" → QR in bozza, `/d/<slug>` → 404 con link "Segnala contenuto"; voce in `audit_log`.

## 6. Spegnimento
- [ ] Switch `link` spento → punto 1 di nuovo tutto PASS; i QR `/d/` pubblicati continuano a funzionare.

## Report finale
`LINK_STAGING_ACCEPTANCE: PASS|FAIL` + elenco FAIL con passo, evidenza, file/riga se noti.
Non accendere nulla in produzione: serve l'ok del titolare (testi legali in
`docs/legal/2026-11-22-link-terms-privacy-draft.md` e tabella IVA del commercialista).
