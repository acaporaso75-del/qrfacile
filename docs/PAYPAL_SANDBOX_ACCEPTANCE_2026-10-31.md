# QRFacile — accettazione webhook PayPal Sandbox

Questo documento registra il collaudo end-to-end del webhook firmato sul runtime candidato. Non autorizza PayPal Live e non deve contenere client ID, secret, webhook ID, event ID, order/capture ID completi, payload, dati personali o credenziali.

## Identita della prova

- Ambiente runtime: [ ] staging  [ ] produzione
- Ambiente PayPal: [ ] Sandbox  [ ] Live
- SHA installato (40 caratteri):
- URL listener HTTPS:
- Data, ora e fuso:
- Operatore:
- Riferimento REST app Sandbox:
- Riferimento webhook registrato:
- Riferimento ordine Sandbox sanitizzato:
- Riferimento evidenze interne:

## Controlli obbligatori

- [ ] Il listener e registrato sulla stessa REST app Sandbox usata dal checkout di prova.
- [ ] Un evento Sandbox reale, non simulato, ha superato la verifica firma PayPal.
- [ ] Header firma mancanti o alterati sono stati rifiutati senza fulfillment.
- [ ] Ambiente, event ID, ordine, capture, importo e valuta sono stati correlati esattamente.
- [ ] Solo `PAYMENT.CAPTURE.COMPLETED` ha erogato i crediti previsti, una sola volta.
- [ ] Il reinvio dello stesso evento dal dashboard PayPal e stato acquisito senza duplicare crediti.
- [ ] Un tentativo non verificabile o non correlabile resta fail-closed e osservabile.
- [ ] Eventi diversi da `PAYMENT.CAPTURE.COMPLETED` non hanno erogato crediti e restano auditabili.
- [ ] Ledger, coda di revisione e alert non espongono payload, event ID, PII o credenziali.

## Esito

Decisione: [ ] PASS  [ ] FAIL

- Nome e ruolo del verificatore:
- Data e fuso orario:
- Anomalie residue:
- Firma o evidenza equivalente:

## Riferimenti ufficiali PayPal

- https://developer.paypal.com/api/rest/webhooks/
- https://developer.paypal.com/api/rest/webhooks/rest/
- https://developer.paypal.com/api/rest/webhooks/events-dashboard/
