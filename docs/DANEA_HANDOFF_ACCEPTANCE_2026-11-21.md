# QRFacile — accettazione hand-off Danea su staging

Data del collaudo: 2026-11-21, 21:05–21:11 CET (Europe/Rome)

Runtime: solo staging, `192.168.1.139:8001`

Release installata: `10fda8c56e6ab9c1dcc89a00938f30a028743704`

## Perimetro e criterio di evidenza

La prova è stata avviata con l'autorizzazione a creare un solo ordine PayPal
Sandbox e a completarne la capture. È arrivata fino alla pagina di approvazione
PayPal Sandbox, ma il titolare non era al PC e ha chiesto di fermarsi. Non sono
quindi avvenuti approvazione, capture, pagamento, invio Danea o reinvio.

Il presente documento registra esclusivamente fatti osservati. I risultati che
richiedono un ordine pagato sono `NOT_VERIFIED`, non `PASS`. Nessuna operazione
ha interessato produzione o PayPal Live.

## Account e profilo fiscale QA

- account: prefisso `qa-danea-20261121-210512-*`;
- verifica email: completata mediante il link ricevuto realmente, senza bypass SQL;
- profilo fiscale: dati interamente fittizi e formalmente validi, salvati dalla UI;
- valori fiscali, indirizzo completo e credenziali non sono riportati.

## Ordine Start

| Campo | Evidenza |
| --- | --- |
| ID interno | `NOT_VERIFIED` in questa sessione documentale |
| Pacchetto | Start |
| Imponibile | € 99,00 |
| IVA 22% | € 21,78 |
| Totale | € 120,78 |
| Ambiente | PayPal Sandbox; redirect verificato su `sandbox.paypal.com` |
| Stato finale | Non pagato; approvazione/capture non eseguite |
| Capture PayPal | Assente; nessun prefisso disponibile |

È stato creato un solo ordine e non è stato ripetuto il submit. La pagina PayPal
Sandbox è stata predisposta, ma non confermata.

## Email e allegato

L'hand-off email viene eseguito solo dopo un pagamento completato. Poiché la
capture non è avvenuta:

- numero di invii Danea: `NOT_VERIFIED` a database; nessuna ricezione è stata
  confermata dal titolare;
- oggetto atteso: `[TEST SANDBOX - NON FATTURARE] Fattura da emettere -
  QRFACILE ordine <id> - ...`;
- destinatari attesi: fatturazione + copia;
- allegato atteso: `qrfacile-ordine-<id>.DefXml`;
- conferma di ricezione del titolare: **no**, non richiesta perché il pagamento
  non è stato completato; orario: non applicabile.

Oggetto, destinatari e nome allegato sono contratti attesi dal codice e non
costituiscono prova di consegna.

## `/admin/invoices` e contenuto XML

Non essendoci un ordine pagato con hand-off eseguito, i controlli seguenti non
sono stati effettuati:

- stato “Inviato a fatturazione”: `NOT_VERIFIED`;
- download `.DefXml`: `NOT_VERIFIED`;
- `DocumentType`, nome cliente fittizio, `CustomerVatCode`,
  `CustomerEInvoiceDestCode`, `TotalWithoutTax`, `VatAmount`, `Total` e
  `Payment Paid=true`: `NOT_VERIFIED`.

## Idempotenza

| Momento | `invoice_handoff_attempts` | Evidenza |
| --- | ---: | --- |
| Dopo pagamento | `NOT_VERIFIED` | pagamento non completato |
| Dopo reload ritorno PayPal | `NOT_VERIFIED` | ritorno non raggiunto |
| Dopo eventuale webhook | `NOT_VERIFIED` | nessuna capture eseguita |
| Dopo “Reinvia” | `NOT_VERIFIED` | azione non eseguita |

`invoice_handoff_last_error` a fine prova: `NOT_VERIFIED`.

## Import in Danea Easyfatt

**NOT_VERIFIED.** Il titolare non ha ricevuto un file derivante da questo
ordine e non ha eseguito l'import. Non è quindi verificato se il file venga
importato come fattura o come altro documento, né la correttezza dei campi o
l'assenza di errori. Nessuna fattura di questa prova è stata creata, inviata
allo SDI o eliminata da Easyfatt.

## Esito finale

| Punto | Esito | Evidenza sintetica |
| --- | ---: | --- |
| Release staging `10fda8c` | **PASS** | identità runtime già registrata nel readback staging |
| Account QA e verifica email | **PASS** | link reale completato, nessun bypass SQL |
| Profilo fiscale fittizio formalmente valido | **PASS** | salvataggio UI riuscito |
| Riepilogo Start € 99,00 / € 21,78 / € 120,78 | **PASS** | valori verificati prima del submit |
| Un solo ordine e redirect PayPal Sandbox | **PASS** | submit singolo e dominio Sandbox verificato |
| Capture e stato `paid` | **NOT_VERIFIED** | titolare non al PC; prova fermata prima della conferma |
| Un solo invio email con `.DefXml` | **NOT_VERIFIED** | hand-off post-pagamento non attivato |
| Stato e download in `/admin/invoices` | **NOT_VERIFIED** | ordine non pagato |
| XML Danea e totali | **NOT_VERIFIED** | file non generato/scaricato |
| Idempotenza ritorno/webhook/reinvio | **NOT_VERIFIED** | sequenza non eseguita |
| Import in Danea Easyfatt | **NOT_VERIFIED** | nessun file importato |

## Anomalie e limiti

Non è stato osservato un errore applicativo. Il limite è operativo: il conto
acquirente Sandbox richiedeva l'interazione del titolare, che non era al PC.
L'ordine è rimasto non pagato e non è una prova end-to-end dell'hand-off Danea.

## Prova completata del 2026-11-27 — ordine interno #72

Questa è una sessione separata da quella del 21 novembre. Il titolare ha
completato il pagamento PayPal Sandbox su staging e ha confermato in chat
il ritorno a QRFacile, la ricezione della mail e il buon esito della prova
di importazione in Danea.

Readback del 27 novembre alle **20:20:59 CET (Europe/Rome)**, staging
`192.168.1.139:8001`, SHA installato
`0830971362716079391007766e5ff7d41bc95713`. Il readback non prova lo SHA
che era attivo al momento originario del pagamento.

| Verifica | Esito | Evidenza |
| --- | --- | --- |
| Pagamento Sandbox | PASS | Ordine interno `72`, `paid`, `sandbox`, `12078` centesimi EUR, capture presente. |
| Accredito Wine al ritorno da PayPal | PASS | Una sola riga del ledger per l'ordine, `+15` unità Wine. |
| Hand-off Danea | PASS | `invoice_handoff_sent_at` valorizzato (18:48:52 CET), `invoice_handoff_attempts=1`, nessun errore. |
| Ricezione mail e import in Danea | PASS, dichiarazione del titolare | Il titolare ha confermato entrambi in chat; nessun accesso a caselle o a Danea da parte di Codex. |
| File originale, campi importati e azioni successive in Danea | NOT_VERIFIED | Nessuna copia della mail o del file è stata letta. Non si deduce una trasmissione allo SDI, né l'eliminazione del documento. |
| Idempotenza dopo webhook verificato | PASS | Dopo il retry firmato sullo staging `a50b03a`, alle 21:07:56 CET risultano ancora una sola riga Wine da `+15`, un tentativo Danea e lo stesso `invoice_handoff_sent_at`, senza errori. Vedere `PAYPAL_SANDBOX_ACCEPTANCE_2026-10-31.md`. |

Comandi di evidenza: `GET /healthz`; `git rev-parse HEAD` e confronto
dell'hash del modulo PayPal installato con quello versionato; `SELECT` in
transazione `READ ONLY` su `orders`, `credit_ledger` e
`paypal_webhook_events`, limitati all'ordine interno `72`. Nessun ID PayPal
completo, payload, recapito o dato fiscale riportato.
