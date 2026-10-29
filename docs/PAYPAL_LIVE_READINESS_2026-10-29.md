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
7. migrazione additiva/idempotente del ledger, inclusa la tabella legacy già presente;
8. vista amministrativa separata per presa in carico e chiusura manuale degli eventi `manual_review` e `failed`, senza azioni finanziarie automatiche e con audit dell’operatore.

La migrazione del ledger e dei campi di revisione è stata applicata due volte su un restore isolato del backup produzione `20261029_164543-production-de0a4f1d848e` (SHA-256 verificato `443eed3afab38596226157f704e45fc87e9ee6e61da458770562413487049b8e`). Una riga nello schema legacy è stata preservata e convertita in `manual_review`; colonne, vincolo e indice parziale di revisione sono risultati presenti una sola volta. Il database temporaneo è stato eliminato dopo la prova. Questa evidenza valida la migrazione, non costituisce deploy in produzione.

Restano da provare o completare prima di Live:

1. registrazione del webhook nella REST app Sandbox;
2. evento Sandbox firmato end-to-end;
3. retry reale PayPal e replay dello stesso event ID;
4. consegna dell’alert operativo esterno per gli eventi `manual_review` e `failed`: la vista amministrativa e il probe aggregato fail-closed `scripts/check_paypal_webhook_queue.py` sono implementati, ma non ancora installati, collegati al monitor o collaudati in ambiente;
5. procedura approvata di rimborso, reversal, disputa e chargeback;
6. registrazione del webhook nella REST app Live soltanto dopo tutti i gate.

Il probe `scripts/check_payment_reconciliation.py` verifica in sola lettura e senza stampare identificativi: capture mancanti o duplicate, timestamp/importi/valuta non validi, ambiente pagamento sconosciuto oltre la soglia approvata, accrediti orfani o associati all’utente/stato errato, condizioni commerciali non ricostruibili, unità accreditate incoerenti e rimborsi ancora aperti in revisione. Qualsiasi tolleranza per ordini storici con ambiente `unknown` deve essere documentata e approvata dalla contabilità; il probe non la inferisce e non modifica dati.

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
