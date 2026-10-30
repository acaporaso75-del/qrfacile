# QRFacile — richiesta di verifica contabile e fiscale

Documento da sottoporre al commercialista di Enolab prima dell'apertura delle
vendite. Non contiene credenziali, dati cliente o prove di pagamento. La firma
del professionista non certifica il software: approva esclusivamente il
perimetro contabile e fiscale descritto.

## Offerta da verificare

Vendita B2B self-service, nella prima fase limitata a cantine italiane con
profilo fiscale completo.

| Pacchetto | Unità Wine | Imponibile | IVA 22% | Totale |
| --- | ---: | ---: | ---: | ---: |
| Start | 15 | €99,00 | €21,78 | €120,78 |
| Cantina | 50 | €179,00 | €39,38 | €218,38 |
| Business | 100 | €299,00 | €65,78 | €364,78 |

Le offerte mostrano la dicitura `Prezzo netto + IVA 22%`. Le unità non usate
scadono dopo 12 mesi; il rinnovo è manuale e non esiste addebito automatico.
Un QR creato usa 1 unità per 10 anni oppure 2 unità per 25 anni e resta attivo
per la durata scelta anche senza un nuovo acquisto.

## Flusso ordine implementato

1. La cantina compila e conferma denominazione, Paese, partita IVA, codice SDI
   o PEC e gli altri dati richiesti dal profilo fiscale.
2. Prima di PayPal vengono mostrati imponibile, IVA e totale.
3. L'ordine conserva uno snapshot non retroattivo di prezzo, aliquota, importi,
   valuta, quantità, durata e dati fiscali usati al momento dell'acquisto.
4. I crediti vengono erogati una sola volta esclusivamente dopo una capture
   PayPal `COMPLETED` con ordine, importo, valuta e ambiente coerenti.
5. Eventi pendenti, negati, rimborsati, reversed o contestati non erogano nuovi
   crediti e passano a revisione manuale.
6. Rimborsi, chargeback e rettifiche non vengono eseguiti automaticamente.

Il dettaglio operativo è in
`PAYMENT_REFUND_DISPUTE_RUNBOOK_2026-10-29.md`. I tre ordini storici già
presenti hanno ambiente `unknown`: il software non li riclassifica e richiede
una decisione contabile esplicita.

## Verifiche richieste al professionista

Confermare o correggere esplicitamente:

- applicabilità dell'IVA ordinaria italiana al 22% nel perimetro iniziale;
- correttezza di imponibile, IVA, arrotondamenti e totale per i tre pacchetti;
- dati fiscali obbligatori da raccogliere prima del pagamento;
- tipo di documento fiscale da emettere e momento di emissione/esigibilità;
- processo autorizzato per fatturazione elettronica, SDI/PEC e conservazione;
- riconciliazione fra ordine QRFacile, capture PayPal, fattura e accredito;
- trattamento di pagamento fallito, pendente, duplicato o non riconciliato;
- procedura per rimborso totale/parziale, chargeback e rettifica dei crediti;
- trattamento dei tre ordini storici con ambiente `unknown`;
- periodo di conservazione di ordini, snapshot fiscali e prove di pagamento;
- esclusione oppure regole per clienti esteri, esenti, reverse charge e regimi
  diversi dall'ordinario italiano;
- eventuali testi obbligatori da mostrare in offerta, checkout o fattura.

## Risposta da compilare

- Decisione: [ ] APPROVATO  [ ] APPROVATO CON CONDIZIONI  [ ] RESPINTO
- Nome e cognome:
- Qualifica e numero di iscrizione all'Albo:
- Studio:
- Data e fuso orario:
- Paesi e regimi autorizzati al self-service:
- Documento fiscale e momento di emissione:
- Processo SDI/PEC e conservazione approvato:
- Processo di riconciliazione approvato:
- Processo di rimborso/chargeback approvato:
- Decisione sugli ordini storici `unknown`:
- Condizioni o modifiche richieste:
- Riferimento del parere o verbale:
- Firma o evidenza equivalente:

In caso di approvazione condizionata, ogni condizione deve essere trasformata
in una modifica o procedura verificabile prima del GO. Nessun dato fiscale o
ordine storico verrà modificato automaticamente in base a questo documento.
