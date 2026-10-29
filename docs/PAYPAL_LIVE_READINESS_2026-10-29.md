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

## Stato webhook preparato

La release candidate espone ora `/paypal/webhook`, verifica la firma tramite l’API ufficiale PayPal e conserva un ledger minimale senza payload completo. Il fulfillment `PAYMENT.CAPTURE.COMPLETED` riusa la stessa procedura atomica del ritorno browser; eventi pendenti, negati, rimborsati, reversed e dispute non erogano crediti e vengono registrati per revisione.

Sono implementati:

1. `PAYPAL_WEBHOOK_ID` obbligatorio quando `PAYPAL_MODE=live`;
2. verifica firma con `/v1/notifications/verify-webhook-signature`;
3. associazione fail-closed fra capture, ordine, importo, valuta e ambiente;
4. deduplica su event ID, audit e hash del payload;
5. riconciliazione della capture completata quando il cliente non torna al sito;
6. stato `manual_review` per rimborsi, denial, reversal e dispute;
7. migrazione additiva/idempotente del ledger, inclusa la tabella legacy già presente.

Restano da provare o completare prima di Live:

1. registrazione del webhook nella REST app Sandbox;
2. evento Sandbox firmato end-to-end;
3. retry reale PayPal e replay dello stesso event ID;
4. vista/alert operativo per gli eventi `manual_review` e `failed`;
5. procedura approvata di rimborso, reversal, disputa e chargeback;
6. registrazione del webhook nella REST app Live soltanto dopo tutti i gate.

Finché le prove Sandbox e i gate operativi non sono chiusi, `PAYPAL_MODE` deve restare `sandbox` e la vendita Live non deve essere abilitata.

Riferimenti ufficiali:

- https://developer.paypal.com/api/rest/webhooks/
- https://developer.paypal.com/api/rest/webhooks/rest/
- https://developer.paypal.com/payment-methods/webhooks/

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
