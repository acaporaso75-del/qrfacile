# QRFacile — handoff canonico

Checkpoint preparato il 2026-08-07 14:28 CEST. Questo documento è la fonte di
continuità operativa dopo l'aggiornamento di ChatGPT/Codex. Non contiene
credenziali, token o segreti.

## Repository e Git

- Repository locale: `C:\Users\enola\Documents\Codex\2026-08-06\scrivimi-una-relazione-per-giustificare-mutuo\qrfacile`.
- Remote: `https://github.com/acaporaso75-del/qrfacile.git`.
- Branch corrente: `fix/qrfacile-pr2-staging-safety-v1`.
- HEAD applicativo verificato prima del checkpoint documentale:
  `2f29c3c0edb58873de1b374d386d42cc89bdc961`.
- HEAD di continuità: il commit locale che contiene questo documento. Verificarlo
  con `git rev-parse HEAD` alla ripresa; non deve essere sostituito da uno SHA
  ricostruito dalla chat.
- Base remota corrente: `origin/feature/legal-ai-compliance-2026` a
  `012499471b0043eee66bdef20a2adba3889f3dc7` (merge della PR #3).
- Merge-base corrente tra base e branch: `a29ba9b413da39e7054db72e7968a450e124d728`.
- Tracking branch: `origin/fix/qrfacile-pr2-staging-safety-v1`.
- Prima del checkpoint locale: tracking ahead/behind `0/0`; rispetto alla base
  remota `1 behind / 2 ahead`. Dopo il checkpoint documentale il branch sarà
  intenzionalmente ahead del tracking finché non sarà autorizzato un push.
- Ultimi commit rilevanti:
  - `2f29c3c` — `fix: restore PayPal checkout navigation`;
  - `147da39` — `fix: repair compliance report and history pages`;
  - `a29ba9b` — `test: verify migration reapplies after rollback`;
  - `715293d` — `ci: validate corrective PR target and SQL`;
  - `8dba75e` — `fix: harden staging isolation and migration safety`.
- Draft PR aperta: [#4 — Fix staging compliance report and verification history](https://github.com/acaporaso75-del/qrfacile/pull/4).
  Base `feature/legal-ai-compliance-2026`, head
  `fix/qrfacile-pr2-staging-safety-v1`, remota head `2f29c3c`; PR open, draft,
  non merged e dichiarata mergeable da GitHub al checkpoint.
- CI remota della PR: `Compliance CI`, run `31176425663`, commit `2f29c3c`,
  conclusione `success`, job `compliance` completato. Il checkpoint locale non è
  coperto da questa run finché non viene autorizzato e pubblicato.
- Working tree atteso dopo il checkpoint: pulito.

## Ambiente

### Produzione

- Host applicativo: `192.168.1.139`.
- Directory: `/opt/qrfacile`.
- Servizio: `qrfacile.service`, verificato `active` il 2026-08-07.
- Runtime: Gunicorn con worker Uvicorn, porta `8000`.
- Git: branch `main`; ultimo HEAD del checkout verificato in lettura il
  2026-08-06: `de0a4f1d848e68b5ea4113b3b80d2fa94cc23ffd`.
- Database: PostgreSQL su `192.168.1.143:5432`, database `qrfacile_db`, utente
  applicativo produttivo separato. Nessuna credenziale riportata.
- Stato: servizio verificato attivo; codice, database e configurazione non sono
  stati modificati in questa lavorazione. HEAD e schema produzione non sono
  stati ricontrollati oltre i controlli in lettura già registrati.

### Staging

- Host applicativo: `192.168.1.139`.
- Directory: `/opt/qrfacile-staging`.
- Servizio: `qrfacile-staging.service`, verificato `active` il 2026-08-07.
- Runtime: Gunicorn con worker Uvicorn, porta `8001` in ascolto.
- Commit distribuito: detached HEAD pulito a
  `2f29c3c0edb58873de1b374d386d42cc89bdc961`.
- Database: PostgreSQL su `192.168.1.143:5432`, database
  `qrfacile_staging_db`, utente `qrfacile_staging_user`.
- Percorsi configurati e verificati in precedenza: `APP_ROOT` sotto
  `/opt/qrfacile-staging`, statici e upload sotto la stessa root. I valori
  correnti del file `.env` non sono riportati né copiati.
- PayPal: staging verificato in modalità Sandbox. La CSP live espone
  `form-action 'self' https://www.sandbox.paypal.com`; un click reale da Billing
  ha raggiunto la pagina di accesso Sandbox. Nessun pagamento completato.
- Origin pubblico dedicato, DNS e reverse proxy staging: `NOT_VERIFIED`; il
  collaudo attuale usa `http://192.168.1.139:8001`.
- Database privilege isolation: la revoca esplicita di `CONNECT` dall'utente
  staging al database produzione è documentata ma non eseguita.

### Dipendenze esterne

- GitHub/GitHub Actions: operativo al checkpoint.
- PayPal Sandbox: raggiungibile dal browser staging.
- SMTP/e-mail reali: configurazione non esposta; invio reale non verificato in
  questo checkpoint.
- DNS/reverse proxy per un origin staging dedicato: non verificati.

## Stato funzionale QRFacile

Gli stati seguenti descrivono evidenza tecnica e collaudi eseguiti; non sono una
certificazione legale del prodotto.

| Area | Stato | Evidenza e limite |
|---|---|---|
| Dashboard | PARTIAL | Route e regressioni presenti; accesso staging visto, ma nessun collaudo completo di tutti i ruoli in questo checkpoint. |
| Workflow/stepper | PARTIAL | Test sui sette step, CTA e regressioni runtime presenti; flusso browser completo non rieseguito. |
| Creazione/modifica prodotto | PARTIAL | Route e test di creazione/review presenti; non verificato end-to-end per tutte le varianti sul database staging. |
| Ingredienti | PARTIAL | Persistenza e controlli compliance presenti; copertura browser completa non rieseguita. |
| Allergeni | PARTIAL | Campi e regole presenti; verifica legale e browser completa non eseguite. |
| Nutrizione | PARTIAL | Validazioni su negativi, decimali e coerenza energia testate; non certificata la completezza normativa. |
| Riciclabilità | PARTIAL | Catalogo, persistenza, gate pubblicazione e test presenti; catalogo legale non certificato esternamente. |
| Immagini/upload | PARTIAL | Round-trip e isolamento staging testati; nessun accesso o lettura degli upload produzione. |
| Compliance report/storico | DONE | Route report e storico corrette, ACL/IDOR e assenza JSON grezzo testate; commit distribuito in staging. |
| Compliance generale | PARTIAL | Engine, score, catalogo regole, replay e advisor presenti; migrazioni correttive non applicate al DB staging. |
| Anteprima | PARTIAL | Renderer condiviso, draft/published, header e casi mancanti coperti da test; smoke browser completo non ripetuto. |
| Pubblicazione | PARTIAL | Gate server-side, override e sicurezza coperti da test; collaudo live di tutti i casi non eseguito. |
| QR | PARTIAL | QR vino e QR generici esistenti; piattaforma multi-modulo e resolver comune non iniziati per espresso divieto. |
| Privacy | PARTIAL | Baseline richieste privacy e registro incidenti presenti nel codice/test; processo organizzativo non verificato. |
| Cookie | NOT_VERIFIED | Nessun audit completo di consenso, categorie e comportamento browser registrato in questo checkpoint. |
| Accessibilità | NOT_VERIFIED | Nessun audit WCAG/EAA completo o test assistivo registrato. |
| GDPR | PARTIAL | Controlli privacy, consensi/evidenze e audit parziali; conformità organizzativa e legale non verificata. |
| GPSR | NOT_VERIFIED | Nessuna verifica legale completa registrata; non dichiarare conformità. |
| EAA | NOT_VERIFIED | Nessuna verifica completa registrata; non dichiarare conformità. |
| AI Act | PARTIAL | Registry AI, policy di human review e test presenti; migrazione/stato reale staging e valutazione legale non completi. |
| Compliance Advisor/AI | PARTIAL | UI e spiegazioni funzionanti e testate; resta uno strumento di supporto, non una certificazione o decisione autonoma. |
| Billing/checkout PayPal | DONE | Form, CSRF, anti doppio click, error UX, CSP Sandbox e redirect browser reale verificati. |

## Bug e blocker aperti

### Correzione runtime locale non ancora pubblicata

- Gravità: media, fail-closed/configurazione staging.
- Descrizione: su un host dove `/opt/qrfacile/*` esiste ma non è leggibile,
  `runtime_config` sollevava `PermissionError` prima del `RuntimeError` esplicito
  previsto per i percorsi produttivi.
- Componenti: `qrfacile_app/runtime_config.py` e
  `tests/test_staging_runtime_safety.py`.
- Ambiente: riprodotto con utente non privilegiato sull'host staging.
- Riproducibilità: 3 failure su upload, template e statici produttivi; il caso
  `APP_ROOT` era già intercettato.
- Test: test regressivo esistente; dopo la correzione minima il gruppo mirato ha
  dato `72 passed` in clone temporaneo isolato.
- Correzione: interrompere il controllo del singolo percorso subito dopo averlo
  classificato come produttivo, senza tentare `stat()`.
- Prossimo passo: dopo l'aggiornamento verificare il checkpoint locale, ottenere
  autorizzazione al push e attendere la CI prima di qualsiasi deploy.

### Isolamento catalogico database incompleto

- Gravità: alta, separazione ambienti.
- Descrizione: la revoca esplicita del privilegio `CONNECT` per
  `qrfacile_staging_user` su `qrfacile_db` è preparata ma non eseguita; il ruolo
  `PUBLIC` deve essere considerato prima di qualsiasi modifica.
- Componenti: configurazione privilegi PostgreSQL, non codice applicativo.
- Ambiente: database server `192.168.1.143`.
- Riproducibilità: inventario privilegi svolto in sola lettura; nessuna modifica
  autorizzata o applicata.
- Test esistente: nessun test automatico applicabile ai privilegi operativi.
- Correzione tentata: solo comando e verifica documentati.
- Prossimo passo: nuova autorizzazione specifica e inventario amministrativo dei
  ruoli prima di qualunque `REVOKE`.

### Origin staging dedicato non verificato

- Gravità: media, operatività e isolamento.
- Descrizione: lo staging è collaudato via IP/porta; DNS e reverse proxy per un
  origin dedicato non sono verificati.
- Componenti: DNS, Nginx/reverse proxy, `APP_BASE_URL`.
- Ambiente: staging.
- Riproducibilità: accesso corrente verificato su
  `http://192.168.1.139:8001`.
- Test esistente: i test runtime rifiutano l'origin produttivo in ambiente
  staging.
- Correzione tentata: validazione applicativa e documentazione; nessuna modifica
  DNS/proxy.
- Prossimo passo: verifica read-only della configurazione corrente e separata
  autorizzazione infrastrutturale.

## Database e migrazioni

- Ultimo inventario staging in sola lettura: 66 tabelle public, database
  `qrfacile_staging_db`, circa 13 MB. Produzione: 58 tabelle public nel database
  separato `qrfacile_db`, circa 13 MB, alla data dell'inventario.
- Schema rilevante staging pre-reconciliation: `qr_items`, `qr_wines`, `invites`
  e `studio_invites`; quest'ultima aveva lo schema legacy senza le colonne
  lifecycle complete. Non era presente una tabella ledger delle migrazioni.
- Migrazione correttiva preparata e versionata:
  `2026_staging_safety_reconciliation_v1.sql`, con pre-check, post-check e
  rollback dedicati.
- Stato sul DB staging operativo: migrazione correttiva non applicata.
- Stato delle altre migrazioni: il repository contiene migrazioni legal/AI,
  inviti, privacy, replay e hardening; l'insieme esatto applicato ai database
  operativi non è attestabile perché il ledger mancava prima della
  reconciliation. Non inferire applicazione dalla sola presenza dei file.
- Validazione su database temporaneo ripristinato dal dump reale: restore,
  pre-check, migrazione, post-check, seconda esecuzione controllata, rollback e
  nuova applicazione conclusi favorevolmente. Nessuna modifica distruttiva a
  `qr_wines` e nessun token generato.
- Inviti legacy verificati: 17 totali, 0 token presenti, 17 token nulli, 15 non
  utilizzati, 2 utilizzati, 16 scaduti. La migrazione li classifica senza
  inventare token o riattivare scaduti.
- Backup staging verificato:
  `/opt/qrfacile-backups/staging/20260806_180117_staging_131acbf390fa`.
- Dump di test da preservare:
  `/home/enolab/qrfacile-test-input/qrfacile_staging_verified.dump`.
- Cluster/directory PostgreSQL di test da preservare:
  `/home/enolab/.pg16-qrfacile-test` se questo è il percorso risolto sull'host;
  non eliminarlo senza autorizzazione.
- Copia cifrata off-host: procedura documentata, trasferimento non eseguito per
  assenza di destinazione autorizzata.
- Rollback: verificato sul database temporaneo; non eseguito sui database
  operativi.

## Test

- Suite locale precedente sul branch prima del checkout PayPal: `238 passed, 1
  skipped`.
- CI GitHub sul commit remoto `2f29c3c`: `239 passed`, run `31176425663`, job
  `compliance` concluso `success`. Superati compile, import con warning come
  errori, security gate, dependency audit, secret scan, regressioni complete,
  transazioni SQL e parsing migrazioni.
- Checkpoint mirato sul codice corretto: `72 passed` il 2026-08-07 in clone
  temporaneo isolato, senza cache/bytecode e senza database operativo.
- Primo tentativo checkpoint: `53 passed, 19 errori di setup`, bloccato da una
  directory pytest in `/tmp` appartenente a un altro utente; non classificato
  come failure del codice.
- Secondo tentativo prima della correzione: `69 passed, 3 failed`; failure reale
  e riproducibile del validatore percorsi, poi corretta localmente.
- Security audit statico checkpoint: nessun finding critical/high; 16 finding
  medium esistenti (principalmente accesso studio ampio e un possibile token
  legacy in chiaro) da riesaminare, non automaticamente classificati come bug
  confermati.
- Browser staging checkout: superato, redirect alla pagina PayPal Sandbox.
- Report/storico compliance: route 200 per vino 16 e 620, bozza, storico vuoto e
  presente, snapshot, ACL proprietario/studio, IDOR, CSRF e assenza JSON grezzo
  coperti dai test mirati.
- Migrazioni/rollback: superati sul database temporaneo ripristinato dal dump;
  non eseguiti su staging o produzione.
- CI del commit di checkpoint locale: non eseguita, perché non è autorizzato il
  push.

## Stato legale/compliance

- Implementato nel codice: engine compliance vino, score, catalogo regole e
  conoscenza versionati, report spiegabile, storico verifiche/replay, advisor,
  gate di pubblicazione, evidenze di accettazione legale, registry AI e human
  review, baseline richieste privacy/incidenti.
- Documentato: isolamento staging, migrazione correttiva, rollback, backup
  off-host e limiti dell'automazione.
- Da verificare: applicazione reale e ledger delle migrazioni, completezza delle
  basi normative, cookie/consensi, accessibilità EAA/WCAG, GPSR, processi GDPR,
  retention, gestione incidenti e governance AI organizzativa.
- Bloccato: piena attestazione di conformità legale. Non esiste evidenza
  sufficiente per dichiarare QRFacile completamente conforme a GDPR, GPSR, EAA o
  AI Act.

# QRFACILE NEXT ACTION AFTER UPDATE

`Riprendere dal branch fix/qrfacile-pr2-staging-safety-v1 al commit locale che contiene questo handoff, verificare prima git status/HEAD e che base e Draft PR #4 non siano cambiate, quindi chiedere autorizzazione al push dell'unico checkpoint locale e attendere la relativa CI prima di qualunque merge o deploy.`
