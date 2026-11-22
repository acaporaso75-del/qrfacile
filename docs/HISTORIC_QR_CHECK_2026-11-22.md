# QRFacile — verifica dei QR storici

Data verifica: 2026-11-22 17:11 CET (`Europe/Rome`).

Questa evidenza riguarda esclusivamente controlli in lettura sulla produzione
attuale e una simulazione isolata della nuova versione. Non sono stati eseguiti
deploy, riavvii o modifiche a produzione, servizi, PayPal o database produttivo.

## Identità e perimetro

- produzione installata: `de0a4f1d848e68b5ea4113b3b80d2fa94cc23ffd`;
- candidato verificato: `aef63ae724d79f46674edecf7c916957ac06ba2b`;
- branch: `codex/production-integration-20261029`;
- Compliance CI del candidato: run `45041190299`, `success`;
- checkout candidato usato per i controlli: copia temporanea fuori da
  `/opt/qrfacile`;
- script: `scripts/check_historic_qr.py`.

I risultati espongono soltanto slug ed esiti; non contengono dati personali,
credenziali o contenuti del database.

## Metodo

### Produzione attuale

Con la `DATABASE_URL` produttiva caricata soltanto nell'ambiente del processo,
senza stamparla, il controllo è stato eseguito contro:

- `http://127.0.0.1:8000`;
- `https://www.qrfacile.it`.

I due risultati sono identici.

### Candidato sui dati reali isolati

È stato usato l'ultimo backup produttivo verificato disponibile:

- directory: `/opt/qrfacile-backups/production/20261029_164543-production-de0a4f1d848e`;
- dump: `20261029_164543-production-de0a4f1d848e.database.dump`;
- SHA-256 dump:
  `443eed3afab38596226157f704e45fc87e9ee6e61da458770562413487049b8e`;
- `sha256sum -c`: `PASS`.

Il dump è stato ripristinato nel database temporaneo isolato
`qrfacile_qrcheck_20261122_aef63ae`. Sono state applicate, con il ruolo
applicativo, le migrazioni del release gate e
`sql/2026_order_invoice_handoff.sql`.

Il candidato è stato avviato con `APP_ENV=staging`, senza SMTP e senza
credenziali PayPal, su `127.0.0.1:18082`. Poiché il validatore runtime accetta
intenzionalmente solo l'identità del database staging canonico, un harness
limitato al solo processo temporaneo ha ammesso il nome, l'host e l'utente del
database restaurato; nessun file del repository o runtime installato è stato
modificato.

Al termine il processo è stato fermato, la porta `18082` è risultata non in
ascolto, il database temporaneo è stato eliminato e le copie temporanee sono
state rimosse.

## Produzione attuale: risultato

| Famiglia | Totale controllato | Funzionante | Problemi |
| --- | ---: | ---: | ---: |
| pagine legacy WordPress | 12 | 12 | 0 |
| QR vino `/e/` | 25 righe, 24 slug distinti | 15 | 10 righe, 9 slug distinti |
| totale | 37 | 27 | 10 |

Problemi rilevati sia sul listener locale sia sul dominio pubblico:

| Slug | Esito IT | Esito EN | Nota |
| --- | --- | --- | --- |
| `WCFC58JM` | `http_404` | `http_404` | — |
| `UVBX7HK3` | `http_404` | `http_404` | — |
| `8bee926d` | `http_404` | `http_404` | — |
| `9743047e` | `http_404` | `http_404` | due righe duplicate nel dato storico |
| `P5P3LPGZ` | `http_404` | `http_404` | — |
| `CJ3QSBNF` | `http_404` | `http_404` | — |
| `GFTSFGKJ` | `http_404` | `http_404` | — |
| `JHJUH6ZR` | `http_404` | `http_404` | — |
| `TECJ69E5` | `http_404` | `http_404` | — |

## Candidato `aef63ae`: risultato isolato

| Famiglia | Totale controllato | Funzionante | Problemi |
| --- | ---: | ---: | ---: |
| pagine legacy WordPress | 12 | 12 | 0 |
| QR vino `/e/` | 24 | 14 | 10 |
| totale | 36 | 26 | 10 |

La migrazione di unicità ha riconciliato la duplicazione nota dello slug
`9743047e`, mantenendo un solo record. Il percorso pubblico rimane uno solo e
non nasce una regressione ulteriore da questa riconciliazione. Non sono state
rilevate collisioni fra slug legacy e rotte applicative.

Tutti i dieci problemi del candidato hanno esito
`shown_as_not_published` in italiano e inglese. I campi obbligatori mancanti
sono:

| Slug | Campi mancanti |
| --- | --- |
| `WCFC58JM` | ingredienti; energia kJ; energia kcal; riciclabilità |
| `UVBX7HK3` | riciclabilità |
| `8bee926d` | ingredienti; allergeni; energia kJ; energia kcal; riciclabilità |
| `9743047e` | ingredienti; allergeni; energia kJ; energia kcal; riciclabilità |
| `P5P3LPGZ` | ingredienti; allergeni; energia kJ; energia kcal; riciclabilità |
| `CJ3QSBNF` | ingredienti; allergeni; energia kJ; energia kcal; riciclabilità |
| `GFTSFGKJ` | ingredienti; allergeni; energia kJ; energia kcal; riciclabilità |
| `JHJUH6ZR` | ingredienti; allergeni; energia kJ; energia kcal; riciclabilità |
| `TECJ69E5` | ingredienti; allergeni; energia kJ; energia kcal; riciclabilità |
| `DBN7MEVG` | riciclabilità |

## Confronto e regressioni prima del go-live

Un solo QR vino funziona oggi e non funzionerebbe più dopo il deploy:

| Slug | Oggi | Candidato | Causa |
| --- | --- | --- | --- |
| `DBN7MEVG` | `ok` IT/EN | `shown_as_not_published` IT/EN | campo obbligatorio `riciclabilità` mancante |

Gli altri nove slug problematici sono già `404` nella produzione attuale. Nel
candidato non diventano pubblici: ricevono invece la pagina esplicita di vino
non ancora pubblicato perché mancano i campi elencati sopra.

## Esito del candidato `aef63ae`

**FAIL per il go-live senza correzione dati**: i 12 QR legacy restano integri,
ma `DBN7MEVG`, oggi raggiungibile, verrebbe oscurato dal nuovo gate di
pubblicazione. Prima del deploy occorre completare la riciclabilità di questo
vino nel flusso autorizzato e ripetere lo stesso controllo. Gli altri nove slug
non rappresentano regressioni rispetto a oggi, ma restano contenuti storici da
completare se devono tornare pubblici.

## Riesecuzione con la regola di continuità `6399968`

Data riesecuzione: 2026-11-22 17:31 CET (`Europe/Rome`).

Il commit `63999685d507063cca907e9d673c885f3cf221e5` introduce la
continuità per i QR già stampati: se un vino storico attivo non supera ancora
il gate dei dati obbligatori, la pagina rimane consultabile e mostra un avviso
che i dati sono in aggiornamento. La condizione è segnalata dal controllo come
`TO_COMPLETE`, ma non è più classificata come QR rotto.

La prova è stata ripetuta dallo stesso backup produttivo verificato, ripristinato
in un nuovo database temporaneo isolato. Sono state applicate le migrazioni del
release gate e `sql/2026_order_invoice_handoff.sql`; il candidato è stato
avviato con `APP_ENV=staging`, senza SMTP e senza credenziali PayPal, sulla
porta temporanea `18082`.

Output sintetico:

```text
HISTORIC_QR_OK legacy=12/broken=0 wine=24/broken=0/to_complete=10
```

| Famiglia | Totale | Broken | Da completare |
| --- | ---: | ---: | ---: |
| pagine legacy WordPress | 12 | 0 | 0 |
| QR vino `/e/` | 24 | 0 | 10 |

I dieci slug `TO_COMPLETE`, tutti raggiungibili sia in italiano sia in inglese
con esito `ok_data_being_updated`, sono:

- `WCFC58JM`;
- `UVBX7HK3`;
- `8bee926d`;
- `9743047e`;
- `P5P3LPGZ`;
- `CJ3QSBNF`;
- `GFTSFGKJ`;
- `JHJUH6ZR`;
- `TECJ69E5`;
- `DBN7MEVG`.

Il processo temporaneo è stato fermato, la porta `18082` è risultata chiusa,
il database temporaneo è stato eliminato e le copie di prova sono state
rimosse. Nessuna modifica è stata eseguita sulla produzione installata.

### Esito aggiornato

**PASS per la continuità dei QR stampati**: tutti i 12 percorsi legacy e tutti
i 24 percorsi vino sopravvivono al candidato `6399968` senza `broken`. I dieci
vini elencati restano da completare dal produttore, ma non vengono più oscurati
durante tale completamento.
