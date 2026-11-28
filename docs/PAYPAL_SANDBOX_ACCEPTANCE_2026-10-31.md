# QRFacile — accettazione webhook PayPal Sandbox

Questo documento registra il collaudo end-to-end del webhook firmato sul runtime candidato. Non autorizza PayPal Live e non deve contenere client ID, secret, webhook ID, event ID, order/capture ID completi, payload, dati personali o credenziali.

## Identita della prova

- Ambiente runtime: [x] staging  [ ] produzione
- Ambiente PayPal: [x] Sandbox  [ ] Live
- SHA installato (40 caratteri): a50b03acb4861e46a74ea640a56fc9b0bae1626d
- URL listener HTTPS: https://paypal-sandbox.qrfacile.it/paypal/webhook
- Data, ora e fuso: 2026-11-27, 20:23–21:07 CET, Europe/Rome
- Operatore: Codex, su autorizzazione del titolare
- Riferimento REST app Sandbox: app di staging verificata in sola lettura; valori non esposti
- Riferimento webhook registrato: SHA-256 prefisso `cb3ab11cae3f`
- Riferimento ordine Sandbox sanitizzato: ordine interno `72`; prefisso SHA-256 dell'evento `f5250e62468b`
- Riferimento evidenze interne: `PAYPAL_SANDBOX_RUNTIME_READBACK_2026-11-02.md` (storico) e `DANEA_HANDOFF_ACCEPTANCE_2026-11-21.md` (prova del #72)

## Controlli obbligatori

- [x] Il listener e registrato sulla stessa REST app Sandbox usata dal checkout di prova.
  Lo stesso accesso in sola lettura a PayPal Sandbox trova il listener configurato e l'evento della capture del #72.
- [x] Un evento Sandbox reale, non simulato, ha superato la verifica firma PayPal.
- [x] Header firma mancanti o alterati sono stati rifiutati senza fulfillment.
  Header mancanti provati sul runtime storico del 2 novembre; sul candidato i test confermano il rifiuto se la verifica PayPal fallisce. Variante alterata di un evento reale non provata.
- [x] Ambiente, event ID, ordine, capture, importo e valuta sono stati correlati esattamente.
  Letti in Sandbox e nel DB staging senza esporre gli ID; corrisponde un solo `PAYMENT.CAPTURE.COMPLETED`.
- [x] Solo `PAYMENT.CAPTURE.COMPLETED` ha erogato i crediti previsti, una sola volta.
  Un solo accredito da 15 sul #72 dopo ritorno e retry; primo accredito da webhook e duplicato coperti anche dalla CI su PostgreSQL.
- [ ] Il reinvio dello stesso evento dal dashboard PayPal e stato acquisito senza duplicare crediti.
  La riconsegna automatica dello stesso evento è riuscita sul candidato. Non è stato eseguito un nuovo reinvio manuale dal pannello.
- [x] Un tentativo non verificabile o non correlabile resta fail-closed e osservabile.
  Un POST non verificabile ha restituito HTTP `400`, con ledger invariato e nessun credito erogato.
- [ ] Eventi diversi da `PAYMENT.CAPTURE.COMPLETED` non hanno erogato crediti e restano auditabili.
  La suite PostgreSQL isolata copre `PAYMENT.CAPTURE.PENDING`, `PAYMENT.CAPTURE.DENIED`,
  `PAYMENT.CAPTURE.REFUNDED`, `CHECKOUT.PAYMENT-APPROVAL.REVERSED` e `CUSTOMER.DISPUTE.CREATED`:
  evento e audit registrati, ordine invariato, nessun credito e nessun invio Danea.
  Sono eventi sintetici con verifica PayPal simulata; non attestano la consegna da PayPal sul runtime.
- [ ] Ledger, coda di revisione e alert non espongono payload, event ID, PII o credenziali.
  Readback e probe aggregato sanitizzati. Ricezione dell'alert sintetico sanitizzato confermata dal titolare: vedere `OPERATIONAL_ACCEPTANCE_2026-10-31.md`. La prova di consegna non chiude da sola il controllo complessivo.

## Esito

Decisione: [ ] PASS  [ ] FAIL

- Nome e ruolo del verificatore: Codex, verifica tecnica; PASS del retry runtime, attestazione completa ancora aperta
- Data e fuso orario: 2026-11-27, Europe/Rome
- Anomalie residue: il validatore storico richiede ancora la prova del reinvio manuale, degli altri tipi di evento e il controllo complessivo dei dati esposti. La consegna dell'alert sintetico è documentata separatamente; il validatore non è stato modificato.
- Firma o evidenza equivalente: Compliance CI `46056205589`, readback staging e Caddy riportati sotto.

## Readback della correzione 42P18 e baseline del retry

- Gateway, prima di questo deploy: `POST` alle 19:31:22 CET → HTTP `400`
  con host certificato `api.sandbox.paypal.com`; alle 20:03:26 CET → HTTP
  `500` dopo la verifica firma. Il journal di staging collega il 500 a
  `IndeterminateDatatype` (SQLSTATE `42P18`) nell'audit. Nessuno dei due
  tentativi vale come accettazione sul candidato attuale.
- Query audit tipizzate nei commit `1efdf04` e `a50b03a`; copertura del
  primo accredito nel commit `ca80b8f`. PostgreSQL reale in CI isolata:
  ordine pendente elaborato una volta; ordine già pagato senza nuovo grant,
  con `already_sent`; chiusura admin di `manual_review` una sola volta.
  Compliance CI `46056205589`: **617 passati**. Nessun test sintetico sul
  DB di staging.
- Deploy solo staging, `scripts/deploy_staging.sh`, 27 novembre alle
  20:23:54 CET. `GET /healthz`, `git rev-parse HEAD` e SHA-256 dei due
  moduli PayPal coincidono con il commit; checkout installato pulito.
  Backup `/opt/qrfacile-backups/staging/20261127_202325_staging_083097136271`:
  `sha256sum -c`, `pg_restore --list` e `gzip -t` superati. Rollback
  conservato: `/opt/qrfacile-staging.rollback-20261127_202325-083097136271`.
- `SELECT` in transazione `READ ONLY` su staging alle 20:24:08 CET: #72
  `paid`, `sandbox`, `12078` centesimi EUR, una sola riga Wine da
  `+15`, `invoice_handoff_attempts=1`,
  `invoice_handoff_sent_at=2026-11-27T18:48:52.337121+01:00`, nessun
  errore. Nessuna riga webhook correlata a quell'ora.
- `GET /v1/notifications/webhooks/{id}` e
  `GET /v1/notifications/webhooks-events` su PayPal **Sandbox**:
  associazione al listener HTTPS confermata, evento reale a importo
  e valuta corrispondenti, nessun nuovo reinvio. Probe aggregato
  `check_paypal_webhook_queue.py` in sola lettura alle 20:27:36 CET:
  `open=0 failed=0 stale=0`; non prova una consegna.

## Retry automatico dell'ordine #72 — PASS runtime

| Prova | Readback del 2026-11-27 (Europe/Rome) |
| --- | --- |
| Gateway | Journal Caddy del solo listener Sandbox: 21:07:30 CET, `POST 200`, host certificato `api.sandbox.paypal.com`. |
| Identità release | `GET /healthz`, `git rev-parse HEAD`, stato checkout pulito e SHA-256 dei moduli PayPal coincidono con `a50b03acb4861e46a74ea640a56fc9b0bae1626d` prima e dopo. |
| Firma e correlazione | `SELECT` in transazione `READ ONLY`: una riga `processed` per l'ordine interno `72`, `verified_at` e `processed_at` valorizzati alle 21:07:23.503527 CET, ambiente `sandbox` e hash evento `f5250e62468b` uguale a PayPal. Una riga di audit `paypal_webhook_processed`. |
| Crediti e Danea | Readback alle 21:07:56 CET: una sola riga Wine da `+15`; `invoice_handoff_attempts=1`, timestamp `2026-11-27T18:48:52.337121+01:00` invariato e nessun errore. |

Il retry è la prima elaborazione verificata del webhook, per questo la
riga è `processed`, non `duplicate`. L'ordine era già pagato dal ritorno
del browser: il webhook non ha prodotto un secondo accredito o invio.
Nessun reinvio, nuovo ordine, pagamento o capture eseguito da Codex.
Il PASS runtime non spunta i controlli rimanenti del protocollo documentale.

## Riferimenti ufficiali PayPal

- https://developer.paypal.com/api/rest/webhooks/
- https://developer.paypal.com/api/rest/webhooks/rest/
- https://developer.paypal.com/api/rest/webhooks/events-dashboard/
