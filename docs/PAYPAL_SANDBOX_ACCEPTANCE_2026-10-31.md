# QRFacile — accettazione webhook PayPal Sandbox

Questo documento registra il collaudo end-to-end del webhook firmato sul runtime candidato. Non autorizza PayPal Live e non deve contenere client ID, secret, webhook ID, event ID, order/capture ID completi, payload, dati personali o credenziali.

## Identita della prova

- Ambiente runtime: [x] staging  [ ] produzione
- Ambiente PayPal: [x] Sandbox  [ ] Live
- SHA installato (40 caratteri): ed7f0b0663f620d8c35afb58adc5f446073e0285
- URL listener HTTPS: https://paypal-sandbox.qrfacile.it/paypal/webhook
- Data, ora e fuso: 2026-11-02, Europe/Rome
- Operatore: Codex, su autorizzazione di Angelo Caporaso, CEO Enolab
- Riferimento REST app Sandbox: credenziali gia presenti nel secret store staging; valori non esposti
- Riferimento webhook registrato: SHA-256 prefisso `cb3ab11cae3f`
- Riferimento ordine Sandbox sanitizzato:
- Riferimento evidenze interne: `docs/PAYPAL_SANDBOX_RUNTIME_READBACK_2026-11-02.md`

## Controlli obbligatori

- [x] Il listener e registrato sulla stessa REST app Sandbox usata dal checkout di prova.
  La registrazione e verificata; il checkout reale sulla stessa app resta da eseguire.
- [ ] Un evento Sandbox reale, non simulato, ha superato la verifica firma PayPal.
- [x] Header firma mancanti o alterati sono stati rifiutati senza fulfillment.
  Gli header mancanti sono provati sul runtime; la variante alterata resta da verificare su un evento reale sanitizzato.
- [ ] Ambiente, event ID, ordine, capture, importo e valuta sono stati correlati esattamente.
- [ ] Solo `PAYMENT.CAPTURE.COMPLETED` ha erogato i crediti previsti, una sola volta.
- [ ] Il reinvio dello stesso evento dal dashboard PayPal e stato acquisito senza duplicare crediti.
- [x] Un tentativo non verificabile o non correlabile resta fail-closed e osservabile.
  Un POST non verificabile ha restituito HTTP `400`, con ledger invariato e nessun credito erogato.
- [ ] Eventi diversi da `PAYMENT.CAPTURE.COMPLETED` non hanno erogato crediti e restano auditabili.
- [ ] Ledger, coda di revisione e alert non espongono payload, event ID, PII o credenziali.

## Esito

Decisione: [ ] PASS  [ ] FAIL

- Nome e ruolo del verificatore: verifica tecnica parziale automatizzata; PASS non assegnato
- Data e fuso orario: 2026-11-02, Europe/Rome
- Anomalie residue: manca un evento reale generato da transazione Sandbox e il relativo replay; il mock ufficiale non e valido per la verifica REST con l'ID registrato.
- Firma o evidenza equivalente:

## Riferimenti ufficiali PayPal

- https://developer.paypal.com/api/rest/webhooks/
- https://developer.paypal.com/api/rest/webhooks/rest/
- https://developer.paypal.com/api/rest/webhooks/events-dashboard/
