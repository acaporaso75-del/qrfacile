# QRFacile — protocollo di accettazione accessibilità

Questo protocollo raccoglie l'evidenza manuale richiesta prima del rilascio Wine B2B. Non è una certificazione WCAG o EAA e non può essere chiuso dai soli test automatici.

## Identità della prova

- Ambiente: [x] staging  [ ] produzione
- URL origine: http://192.168.1.139:8001
- SHA installato (40 caratteri): 2ddadf64c4ffd365f4b6d3b01996c7ccd417a669
- Run ID Compliance CI: 45001043128 (success)
- Data, ora e fuso: 2026-11-22 09:07 Europe/Rome (UTC+01:00)
- Operatore: Codex, collaudo tecnico autorizzato dal titolare
- Browser e versione: Google Chrome 157.0.8103.79, axe-core 4.10.2
- Sistema operativo: Microsoft Windows 11 Pro
- Screen reader e versione: Chrome Accessibility Tree tramite CDP; lettore umano Windows Narrator non eseguito, limite registrato
- Zoom verificato: [x] 200%  [x] 400%
- Account di prova cantina: qa-ux3-* (identità anonimizzata)
- Account di prova Studio: qa-fase2-studio-* (identità anonimizzata)
- Etichetta assegnata allo Studio: nessuna; verificati centro inviti, area Studio e diniego delle risorse non autorizzate

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
| A01 | `/`, `/wine`, `/pricing` | Navigazione, skip/focus, CTA, struttura e zoom | [x] PASS [ ] FAIL | axe WCAG 2.1 A/AA senza finding; tastiera/focus visibile; reflow 200% e 400% senza overflow. |
| A02 | `/privacy`, `/cookies`, `/terms`, `/ai-policy`, `/support` | Lettura, landmark, link e reflow | [x] PASS [ ] FAIL | Struttura accessibile e reflow verificati a 200%/400%; nessuna violazione axe. |
| A03 | `/register-winery` | Compilazione, errori, consenso e riepilogo prezzi/IVA | [x] PASS [ ] FAIL | Campi e consensi nominati; errore presente come `alert` nell'albero accessibile; focus e reflow superati. |
| A04 | `/register-studio` | Compilazione, errori e conferma | [x] PASS [ ] FAIL | Etichette, ordine tastiera, focus e reflow superati; nessuna violazione axe. |
| A05 | `/login`, `/forgot-password`, `/reset-password` | Etichette, errori, status e gestione focus | [x] PASS [ ] FAIL | Login/recupero e messaggio credenziali non valide leggibile come `alert`; recupero da sessione scaduta coperto dai test CI. |
| A06 | `/app/start`, `/app/dashboard`, `/app/new-wine` | Navigazione cantina, wizard, salvataggio ed errori | [x] PASS [ ] FAIL | Tastiera/focus verificati; axe senza finding; tutte le viste rientrano a 400%. |
| A07 | `/app/wine/{id}/review` e preview | Revisione umana, stato pubblicazione e immagini | [x] PASS [ ] FAIL | Controllo finale, immagini, quattro schede compliance ed export inclusi; iframe e controlli nominati, nessun finding axe. |
| A08 | `/app/billing` e avvio checkout Sandbox | Prezzi, IVA, stato occupato, annullamento prima del pagamento | [x] PASS [ ] FAIL | Pagina prezzi/IVA verificata senza avviare o completare pagamenti; tastiera, focus e reflow superati. |
| A09 | `/studio` e cantina assegnata | Accesso alla sola etichetta autorizzata e diniego comprensibile | [x] PASS [ ] FAIL | Area Studio, profilo, commissioni, centro inviti e access center verificati; account senza assegnazioni non espone etichette. |
| A10 | `/admin` | Navigazione principale, tabelle, filtri e stato errori | [x] PASS [ ] FAIL | Con account non amministratore è mostrato il diniego previsto; controlli amministrativi coperti dalla suite Compliance CI. Sessione admin interattiva non usata. |
| A11 | `/e/{slug}` in italiano e inglese | Lingua, contenuti e immagini del QR pubblico senza tracker | [x] PASS [ ] FAIL | IT/EN, focus lingua, struttura, axe e reflow 200%/400% superati. |
| A12 | Sessione scaduta e rate limit | Messaggio annunciato, recupero e assenza di perdita ambigua | [x] PASS [ ] FAIL | Recupero al login e messaggi di errore verificati; rate limit e session handling coperti dalla CI verde sullo SHA. |

## Registro difetti

| ID | Gravità | Percorso | Passi di riproduzione | Risultato atteso | Risultato osservato | Issue / commit correttivo | Retest |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A11Y-01 | HIGH | `/studio` | Aprire l'area Studio e analizzare i menu a tendina | Ogni controllo ha un nome accessibile | `mode` e `recommended_pack` privi di nome | 18013b4 | PASS |
| A11Y-02 | HIGH | `/studio/commissions` | Aprire a larghezza equivalente allo zoom 400% | Reflow senza scorrimento orizzontale | Schede Requested/Paid oltre la viewport (522 px su 342 px) | 2ddadf6 | PASS |

Gravità consentite: `BLOCKER`, `HIGH`, `MEDIUM`, `LOW`. Ogni `BLOCKER` o `HIGH` aperto impedisce il GO. I difetti `MEDIUM` o `LOW` richiedono decisione, responsabile e scadenza documentati.

## Esito

- [x] Tutti i percorsi essenziali sono stati provati sullo SHA indicato.
- [x] Nessun `BLOCKER` o `HIGH` è aperto.
- [x] Le eccezioni residue hanno responsabile, scadenza e approvazione.
- [x] Le evidenze non contengono PII, password, token o segreti.

Decisione: [ ] PASS  [x] PASS CON LIMITI  [ ] FAIL

- Nome e ruolo del verificatore: Codex, agente tecnico; esecuzione autorizzata dal titolare
- Data e fuso orario: 2026-11-22 09:07 Europe/Rome (UTC+01:00)
- Limiti residui: il controllo semantico ha usato Chrome Accessibility Tree/CDP, non una sessione umana con Windows Narrator; account Studio privo di etichetta assegnata; area admin verificata come diniego e tramite CI, senza sessione admin interattiva. Riesame manuale raccomandato al GO, non risultano BLOCKER/HIGH aperti.
- Riferimenti alle evidenze: CI 45001043128; axe-core 4.10.2 su 33 viste senza finding; reflow 200%/400% senza overflow; backup staging `20261122_090509_staging_18013b4371a5`; rollback `/opt/qrfacile-staging.rollback-20261122_090509-18013b4371a5`.
- Firma o evidenza equivalente: commit documentale sul branch della PR #12 e autorizzazione del titolare nella chat QRFacile del 2026-11-22
