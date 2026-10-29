# QRFacile — PayPal Live readiness

Questo documento prepara l’attivazione senza contenere segreti e senza autorizzare pagamenti reali.

## Configurazione usata dall’applicazione

Variabili richieste dal runtime:

- `PAYPAL_MODE=live`
- `PAYPAL_CLIENT_ID`
- `PAYPAL_SECRET`
- `APP_BASE_URL=https://www.qrfacile.it`

Le credenziali devono già esistere nel secret store autorizzato. Non devono essere copiate nel repository, nella chat, nei log, nella cronologia shell o in un nuovo `.env` creato autonomamente.

## Conferma secret store

- Secret store/profilo autorizzato:
- Host/servizio che lo monta:
- Nomi delle chiavi presenti, senza valori:
- Merchant account atteso, identificato senza dati sensibili:
- Responsabile delle credenziali:
- Data ultima validazione:
- Evidenza accesso limitato:
- Evidenza rotazione/revoca disponibile:

## URL e comportamento attesi

- API Live: `https://api-m.paypal.com`
- Approval host Live: `https://www.paypal.com`
- Return URL generata: `https://www.qrfacile.it/paypal/return?order_id=<ID_INTERNO>`
- Cancel URL generata: `https://www.qrfacile.it/app/billing?err=Pagamento%20annullato`
- Valuta: EUR
- Ambiente salvato nell’ordine: `live`
- Idempotenza creazione: `PayPal-Request-Id: qrfacile-order-<ID_INTERNO>`
- Idempotenza capture: `PayPal-Request-Id: qrfacile-capture-<ID_INTERNO>`

## Gate tecnico attualmente mancante

La release candidate gestisce creazione ordine e capture tramite il ritorno browser, ma non espone ancora un endpoint webhook PayPal e non configura un `PAYPAL_WEBHOOK_ID`.

Per un esercizio Live robusto occorre decidere e implementare prima dell’attivazione:

1. eventi PayPal da ricevere;
2. verifica crittografica della firma mediante API PayPal;
3. associazione fail-closed fra capture, ordine, importo, valuta e ambiente;
4. idempotenza e audit dell’evento;
5. riconciliazione quando il cliente non torna al sito;
6. gestione rimborso, reversal, disputa e chargeback;
7. retry, dead-letter operativa e alert;
8. test Sandbox end-to-end del webhook.

Finché questo gate non è chiuso, `PAYPAL_MODE` deve restare `sandbox` e la vendita Live non deve essere abilitata.

## Prova Live senza pagamento reale

Dopo la chiusura dei gate e usando esclusivamente credenziali già montate:

- [ ] ottenere un token OAuth Live senza stamparlo;
- [ ] creare un ordine Live per l’importo previsto;
- [ ] verificare stato `CREATED`, valuta, importo e merchant account;
- [ ] verificare che l’approval URL appartenga a `www.paypal.com`;
- [ ] verificare return e cancel URL sul dominio produttivo;
- [ ] annullare o lasciare scadere l’ordine senza approvarlo e senza capture;
- [ ] verificare che nessun ordine QRFacile sia marcato `paid`;
- [ ] registrare esclusivamente ID non segreti, timestamp, SHA e risultato.

Non effettuare un pagamento reale per completare questa checklist.
