# QRFacile — protocollo di accettazione accessibilità

Questo protocollo raccoglie l'evidenza manuale richiesta prima del rilascio Wine B2B. Non è una certificazione WCAG o EAA e non può essere chiuso dai soli test automatici.

## Identità della prova

- Ambiente: [ ] staging  [ ] produzione
- URL origine:
- SHA installato (40 caratteri):
- Run ID Compliance CI:
- Data, ora e fuso:
- Operatore:
- Browser e versione:
- Sistema operativo:
- Screen reader e versione:
- Zoom verificato: [ ] 200%  [ ] 400%
- Account di prova cantina:
- Account di prova Studio:
- Etichetta assegnata allo Studio:

Non inserire password, token, dati personali reali o credenziali PayPal in questo documento. In produzione usare soltanto identità di prova autorizzate e azioni non distruttive. Non completare pagamenti reali.

## Regole di esecuzione

1. Verificare prima `/healthz` con `scripts/verify_release_health.py` e registrare lo SHA esatto.
2. Ripetere ogni percorso usando soltanto tastiera; il puntatore può essere usato solo per confrontare il risultato.
3. Ripetere i percorsi essenziali con screen reader e almeno una combinazione browser/tecnologia assistiva documentata.
4. Verificare zoom 200% e 400%, reflow, orientamento e assenza di scorrimento bidimensionale non necessario.
5. Registrare risultato, evidenza e difetto riproducibile senza includere PII o segreti.
6. Un blocco di tastiera, focus invisibile, nome accessibile errato, errore non annunciato, perdita di contenuto o azione finanziaria ambigua è `BLOCKER`.

## Controlli trasversali

Per ogni pagina verificare:

- ordine del focus coerente e focus sempre visibile;
- nessuna trappola da tastiera; `Esc` chiude eventuali dialoghi quando previsto;
- titoli, landmark, intestazioni e lingua della pagina comprensibili;
- link e pulsanti con nome, ruolo e stato annunciati correttamente;
- campi con etichetta, istruzioni, autocomplete e messaggi di errore associati;
- stato asincrono annunciato senza spostamenti imprevisti del focus;
- contrasto e uso del colore non esclusivo per comunicare stato o errore;
- contenuto utilizzabile a 200% e 400% senza perdita di funzioni;
- timeout o scadenza sessione comprensibili e recuperabili;
- nessun avvio automatico di audio, video o movimento essenziale.

## Matrice dei percorsi essenziali

| ID | Percorso | Azioni da verificare | Esito | Evidenza / difetto |
| --- | --- | --- | --- | --- |
| A01 | `/`, `/wine`, `/pricing` | Navigazione, skip/focus, CTA, struttura e zoom | [ ] PASS [ ] FAIL | |
| A02 | `/privacy`, `/cookies`, `/terms`, `/ai-policy`, `/support` | Lettura, landmark, link e reflow | [ ] PASS [ ] FAIL | |
| A03 | `/register-winery` | Compilazione, errori, consenso e riepilogo prezzi/IVA | [ ] PASS [ ] FAIL | |
| A04 | `/register-studio` | Compilazione, errori e conferma | [ ] PASS [ ] FAIL | |
| A05 | `/login`, `/forgot-password`, `/reset-password` | Etichette, errori, status e gestione focus | [ ] PASS [ ] FAIL | |
| A06 | `/app/start`, `/app/dashboard`, `/app/new-wine` | Navigazione cantina, wizard, salvataggio ed errori | [ ] PASS [ ] FAIL | |
| A07 | `/app/wine/{id}/review` e preview | Revisione umana, stato pubblicazione e immagini | [ ] PASS [ ] FAIL | |
| A08 | `/app/billing` e avvio checkout Sandbox | Prezzi, IVA, stato occupato, annullamento prima del pagamento | [ ] PASS [ ] FAIL | |
| A09 | `/studio` e cantina assegnata | Accesso alla sola etichetta autorizzata e diniego comprensibile | [ ] PASS [ ] FAIL | |
| A10 | `/admin` | Navigazione principale, tabelle, filtri e stato errori | [ ] PASS [ ] FAIL | |
| A11 | `/e/{slug}` in italiano e inglese | Lingua, contenuti e immagini del QR pubblico senza tracker | [ ] PASS [ ] FAIL | |
| A12 | Sessione scaduta e rate limit | Messaggio annunciato, recupero e assenza di perdita ambigua | [ ] PASS [ ] FAIL | |

## Registro difetti

| ID | Gravità | Percorso | Passi di riproduzione | Risultato atteso | Risultato osservato | Issue / commit correttivo | Retest |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |

Gravità consentite: `BLOCKER`, `HIGH`, `MEDIUM`, `LOW`. Ogni `BLOCKER` o `HIGH` aperto impedisce il GO. I difetti `MEDIUM` o `LOW` richiedono decisione, responsabile e scadenza documentati.

## Esito

- [ ] Tutti i percorsi essenziali sono stati provati sullo SHA indicato.
- [ ] Nessun `BLOCKER` o `HIGH` è aperto.
- [ ] Le eccezioni residue hanno responsabile, scadenza e approvazione.
- [ ] Le evidenze non contengono PII, password, token o segreti.

Decisione: [ ] PASS  [ ] PASS CON LIMITI  [ ] FAIL

- Nome e ruolo del verificatore:
- Data e fuso orario:
- Limiti residui:
- Riferimenti alle evidenze:
- Firma o evidenza equivalente:
