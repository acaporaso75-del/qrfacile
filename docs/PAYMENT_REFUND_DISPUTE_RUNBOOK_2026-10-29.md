# QRFacile — procedura rimborsi, reversal e dispute

Questa procedura definisce il percorso tecnico-operativo fail-closed. Non autorizza rimborsi, rettifiche contabili, revoche di crediti o pagamenti reali e deve essere approvata dal responsabile contabile e operativo prima di PayPal Live.

## Principi

- Gli eventi `PAYMENT.CAPTURE.REFUNDED`, `PAYMENT.CAPTURE.DENIED`, `PAYMENT.CAPTURE.PENDING`, `CHECKOUT.PAYMENT-APPROVAL.REVERSED` e `CUSTOMER.DISPUTE.CREATED` non erogano crediti.
- Un evento di rimborso, reversal o disputa non revoca automaticamente crediti già utilizzati e non modifica retroattivamente ordini, fatture o accettazioni.
- Il webhook conserva identificatori minimi e hash del payload, non il payload completo.
- L'azione finanziaria avviene soltanto sul provider, da parte di un operatore autorizzato. QRFacile registra la riconciliazione, non esegue automaticamente il rimborso.
- Un evento resta aperto finché non esiste prova della risoluzione sul provider o prova che sia un falso positivo.
- La semplice presa in carico non è un esito di chiusura.

## Presa in carico

1. Il monitor segnala la coda con `scripts/check_paypal_webhook_queue.py` senza esportare payload, event ID o dati personali.
2. L'operatore autorizzato apre `/admin/paypal-webhooks?view=open` e identifica ordine, ambiente ed evento.
3. Verifica che l'ambiente sia quello atteso (`sandbox` o `live`) e confronta ordine interno, capture e stato sul provider.
4. Registra la presa in carico nel sistema operativo/ticket autorizzato, senza chiudere l'evento QRFacile.
5. Se identità, importo, valuta, ordine o ambiente non coincidono, interrompe la procedura ed esegue escalation sicurezza/contabilità.

## Verifiche obbligatorie

- ordine interno e cliente corretti;
- PayPal order ID e capture ID coerenti;
- importo lordo, eventuale importo rimborsato e valuta;
- rimborso totale o parziale;
- stato del documento fiscale e rettifica richiesta;
- unità già accreditate e unità eventualmente utilizzate;
- eventuali QR già creati o pubblicati, che non devono essere cancellati automaticamente;
- ambiente di pagamento e merchant account corretti;
- riferimento del ticket, del caso PayPal o del documento contabile.

Non copiare credenziali, payload completi, dati carta o dati personali non necessari nelle note di revisione.

## Decisioni consentite nell'admin

### Risolto sul provider

Usare `resolved_external` soltanto dopo che l'azione richiesta è conclusa e verificata sul provider e che la conseguenza contabile è stata registrata o assegnata. La nota obbligatoria deve contenere il riferimento interno non segreto, il tipo di esito e il responsabile, senza dati finanziari sensibili.

### Falso positivo

Usare `false_positive` soltanto quando l'evento è stato verificato come duplicato innocuo, non applicabile o già riconciliato. La nota deve spiegare l'evidenza della classificazione.

Non esiste un esito “preso in carico” che chiuda la coda. Se il caso è ancora in lavorazione, deve restare aperto.

## Rimborsi e crediti

- Non eliminare righe dal `credit_ledger` e non modificare direttamente il database.
- Non revocare unità che hanno già generato QR o contenuti pubblicati.
- Qualunque rettifica di unità richiede una decisione contabile/commerciale, una causale, un operatore e una registrazione append-only separata.
- Un rimborso parziale richiede decisione esplicita sulla quota di unità e sul documento fiscale; non inferirla dal solo evento webhook.
- Chargeback e dispute richiedono conservazione delle evidenze e coordinamento con il responsabile privacy/sicurezza quando contengono dati personali o sospetto abuso.

## Chiusura e controllo

1. Chiudere nell'admin soltanto con `resolved_external` o `false_positive` e nota obbligatoria.
2. Verificare la presenza dell'audit `paypal_webhook_reviewed` e l'identità dell'operatore.
3. Eseguire `scripts/check_paypal_webhook_queue.py` e confermare che non restino eventi scaduti oltre lo SLA.
4. Eseguire `scripts/check_payment_reconciliation.py` e confermare che ordini, capture, crediti e rimborsi siano coerenti.
5. Collegare l'evidenza contabile o il ticket senza inserire segreti nel repository.

## Approvazione esterna richiesta

- Responsabile contabile:
- Responsabile operativo:
- SLA presa in carico:
- SLA risoluzione:
- Regola rimborso totale:
- Regola rimborso parziale:
- Regola rettifica unità:
- Processo documento fiscale:
- Canale escalation dispute/chargeback:
- Data, fuso orario e perimetro:
- Esito: [ ] APPROVATO  [ ] APPROVATO CON CONDIZIONI  [ ] RESPINTO
- Firma o evidenza equivalente:
