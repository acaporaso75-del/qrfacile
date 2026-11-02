# QRFacile — readback runtime webhook PayPal Sandbox

Data: 2026-11-02, Europe/Rome.

Questo documento registra esclusivamente fatti verificati sul runtime staging.
Non autorizza PayPal Live, merge o deploy in produzione e non contiene
credenziali, payload, webhook ID, event ID o riferimenti completi a ordini e
capture.

## Runtime e rollback

- runtime: staging canonico `/opt/qrfacile-staging`;
- servizio: `qrfacile-staging.service`, stato `active`;
- SHA installato e riportato da `/healthz`:
  `ed7f0b0663f620d8c35afb58adc5f446073e0285`;
- backup staging verificato:
  `/opt/qrfacile-backups/staging/20261102_075131_staging_59cf70a834db`;
- backup protetto dell'ambiente precedente alla registrazione webhook:
  `/opt/qrfacile-backups/staging/paypal-webhook-20261102T083402Z`;
- rollback del deploy staging:
  `/opt/qrfacile-staging.rollback-20261102_075344-59cf70a834db`.

La produzione e rimasta sulla porta `8000` e ha risposto HTTP `200` prima e
dopo le operazioni. Non sono stati eseguiti merge, deploy produttivi, pagamenti
reali o capture Live.

## DNS e listener HTTPS

- record A creato: `paypal-sandbox.qrfacile.it`;
- risoluzione autorevole e pubblica verificata verso il gateway gia in uso;
- backup Caddy precedente:
  `/root/codex-backups/qrfacile-paypal-sandbox-20261102T083238Z`;
- hash SHA-256 Caddy precedente:
  `7e01ba372c636502acee6e26f329c627e118da691c2afc8494be14d96453d9d2`;
- hash SHA-256 Caddy installato:
  `a6dec9f3ea84dbe9eb26ad97c9b15ecb8959323d576dc26a8d72ce5f16c8cec9`;
- configurazione Caddy validata prima del reload; servizio `active` dopo il
  reload;
- il virtual host espone soltanto `/paypal/webhook` verso lo staging; ogni
  altro percorso risponde `404` con `Cache-Control: no-store`.

Readback pubblico:

| Richiesta | Esito |
| --- | ---: |
| `GET https://qrfacile.it/` | `200` |
| `GET https://www.qrfacile.it/` | `200` |
| `GET https://paypal-sandbox.qrfacile.it/` | `404` |
| `GET https://paypal-sandbox.qrfacile.it/paypal/webhook` | `405` |
| `POST` JSON non firmato al listener | `400` |

## Registrazione PayPal Sandbox

Il listener e stato creato tramite la Webhooks Management API usando la REST
app Sandbox gia configurata nel runtime. L'ID restituito non e stato mostrato
o copiato: e stato scritto soltanto in `/opt/qrfacile-staging/.env`, proprieta
`qrfacile:qrfacile`, modalita `0600`. Riferimento sanitizzato del webhook:
SHA-256 prefisso `cb3ab11cae3f`.

Eventi richiesti e verificati nella risposta PayPal (`6/6`):

- `PAYMENT.CAPTURE.COMPLETED`;
- `PAYMENT.CAPTURE.DENIED`;
- `PAYMENT.CAPTURE.PENDING`;
- `PAYMENT.CAPTURE.REFUNDED`;
- `CHECKOUT.PAYMENT-APPROVAL.REVERSED`;
- `CUSTOMER.DISPUTE.CREATED`.

Dopo la configurazione il servizio staging e stato riavviato ed e tornato
`active`; `/healthz` ha confermato ambiente `staging`, database `OK` e lo SHA
esatto del candidato.

## Prove fail-closed

- un `POST` senza header firma e stato rifiutato con HTTP `400`;
- il ledger `paypal_webhook_events` e rimasto a `0` righe;
- nessun credito e stato erogato;
- il simulatore ufficiale PayPal ha accettato l'accodamento di un evento mock
  (`202`), ma non e stata osservata una consegna nella finestra di verifica e
  non viene usato come prova positiva.

La documentazione PayPal precisa che gli eventi mock usano l'ID speciale
`WEBHOOK_ID`, non appartengono a una REST app, non sono reinviabili e non
possono essere verificati tramite l'endpoint REST
`verify-webhook-signature`. Per questo motivo il mock non chiude il gate del
webhook firmato reale.

## Gate ancora aperto

Per il PASS servono ancora, senza pagamenti reali:

1. un ordine e una capture nell'ambiente Sandbox, approvati con un account
   acquirente Sandbox;
2. la ricezione dell'evento reale firmato sulla stessa REST app;
3. correlazione esatta di ambiente, event ID, ordine, capture, importo e
   valuta;
4. prova che i crediti siano erogati una sola volta;
5. reinvio dell'evento dal dashboard PayPal e prova di idempotenza;
6. verifica degli eventi non `COMPLETED` e della coda di revisione.

Riferimenti ufficiali:

- https://developer.paypal.com/api/rest/webhooks/rest/
- https://developer.paypal.com/api/rest/webhooks/simulator/
- https://developer.paypal.com/api/webhooks/v1/simulate-event-post/
