# QRFacile — readback deploy e collaudo staging Fase 2

Data deploy e readback: 2026-11-21, Europe/Rome.

Questo documento riguarda esclusivamente lo staging QRFacile. Non contiene
segreti, token, contenuto degli `.env`, indirizzi email completi o altri dati
personali. Produzione, Caddy, DNS e PayPal Live non sono stati modificati.

## Esito sintetico

Il primo deploy dello SHA `3da7d35654ed2bc9b74cc8865c11cf293d70473f`
ha evidenziato il difetto storico `integer`/`boolean` sulla verifica email. La
successiva ridistribuzione autorizzata dello SHA
`32cf797d126259114917dccc0d3f1b53c83769b9` ha corretto il difetto ed è
**PASS**: servizio attivo, `/healthz` coerente, backup/rollback verificati e
collaudo Fase E completato senza bypass SQL, capture o pagamento completato.

## Identità runtime

- host: `192.168.1.139`;
- root: `/opt/qrfacile-staging`;
- servizio: `qrfacile-staging.service`;
- porta: `8001`;
- database: `qrfacile_staging_db`;
- SHA precedente: `ed7f0b0663f620d8c35afb58adc5f446073e0285`;
- SHA installato: `3da7d35654ed2bc9b74cc8865c11cf293d70473f`;
- ultimo avvio riuscito: 2026-11-21 11:47:14 CET.

Readback `GET /healthz`, HTTP 200:

```json
{"status":"OK","environment":"staging","database":"OK","release":"3da7d35654ed2bc9b74cc8865c11cf293d70473f"} <!-- pragma: allowlist secret -->
```

## Backup verificato

Percorso:

```text
/opt/qrfacile-backups/staging/20261121_114411_staging_ed7f0b0663f6
```

| Artefatto | SHA-256 |
| --- | --- |
| dump PostgreSQL | `347c28a8de09da08dc51915d79869c7eae74c69dd9c297ba819292a64a37c841` |
| archivio filesystem | `537a078fdc2b5ba54a8ea696082cae52bc250e139a14f9daa57740b461ccf002` |

Verifiche: `sha256sum -c` PASS, `pg_restore --list` PASS con 734
voci, restore logico verso `/dev/null` PASS e `gzip -t` PASS.

## Rollback

Directory conservata:

```text
/opt/qrfacile-staging.rollback-20261121_114522-ed7f0b0663f6
```

La directory contiene la release precedente `ed7f0b0` e il piano di rollback.
Il meccanismo è stato esercitato realmente durante l'incidente CRLF.

## Release e verifiche pre-swap

Ambiente `staging` e database `qrfacile_staging_db` sono stati confermati prima
dello swap. Il target ha superato:

| Controllo | Esito |
| --- | ---: |
| `compileall` | PASS |
| import applicazione fail-closed | PASS, 79 route |
| `project_security_audit.py --fail-on critical` | PASS, 0 finding |
| `check_sql_transactions.py` | PASS |
| `/healthz` dopo restart | PASS, ambiente/database/SHA coerenti |

## Incidente CRLF e recupero

Il primo avvio del target aveva superato health, home e identità release, ma
un carattere `CR` nell'ultima istruzione dello script remoto ha fatto fallire
`trap - ERR` dopo i controlli positivi. Il trap già armato ha eseguito
correttamente il rollback automatico a `ed7f0b0`.

Il target è stato reinstallato usando input normalizzato LF. Il secondo avvio
ha confermato `/healthz`, home e SHA. Il journal risultava privo di errori dopo
la reinstallazione. L'errore applicativo successivo delle 16:50 CET riguarda
esclusivamente la verifica email descritta nel collaudo.

Per impedire la ricorrenza, il repository include ora `.gitattributes`, uno
script di deploy LF e un test che rifiuta `CR` negli script shell tracciati.

## Collaudo Fase E

| # | Punto | Esito | Evidenza sintetica |
| ---: | --- | ---: | --- |
| 1 | Home e CTA vino | **PASS** | `/` HTTP 200; CTA `Inizia gratis, 3 QR inclusi` verso `/register-winery` |
| 2 | Registrazione Cantina minima | **PASS** | sei soli campi obbligatori; POST reale 303; account e 3 crediti creati |
| 3 | Profilo fiscale incompleto | **PASS** | profilo parziale rifiutato prima di qualsiasi scrittura |
| 4 | Profilo fiscale completo | **PASS** | P.IVA, SDI e provincia normalizzati nel test staging precedente |
| 5 | Checkout vuoto → impostazioni → Sandbox | `NOT_VERIFIED` | account reale non sbloccabile per il FAIL email; 0 ordini e nessun contatto PayPal |
| 6 | Vino 7 step, preview, pubblicazione, `/e/`, export e QR | `NOT_VERIFIED` | richiede login dell'account verificato; nessun bypass SQL eseguito |
| 7 | Login/reset/Studio/pagine pubbliche | **PASS** | pagine pubbliche 200; `/studio` protetto con redirect 303; 57 test mirati verdi |
| 8 | Discoverability | **PASS** | `robots.txt`, `sitemap.xml`, `llms.txt` e demo pubblica rispondono 200 |
| 9 | Produzione invariata | **PASS** | SHA `de0a4f1d848e68b5ea4113b3b80d2fa94cc23ffd`, home 200 prima/dopo |

## Prova SMTP reale

- destinatario: casella di test controllata dal titolare;
- invio registrato dal ledger applicativo: 1, senza errore;
- ricezione: **PASS**, 2026-11-21 16:49:26 CET;
- dominio mittente osservato: `qrfacile.it`;
- origine del link: `http://192.168.1.139:8001`;
- click e sblocco: **FAIL**, HTTP 500 per incompatibilità `integer`/`boolean`;
- forzatura SQL dell'account: **NON ESEGUITA**.

Nessun indirizzo completo e nessun token sono riportati.

## Conteggi database staging

| Tabella | Prima del deploy | Dopo test iniziali | Dopo collaudo SMTP |
| --- | ---: | ---: | ---: |
| `users` | 13 | 15 | 16 |
| `wineries` | 9 | 11 | 12 |
| `orders` | 61 | 61 | 61 |
| `qr_items` | 52 | 52 | 52 |
| `qr_wines` | 31 | 31 | 31 |

L'account SMTP mantiene 3 crediti e 0 ordini. Non è stato avviato o completato
alcun pagamento.

## Account QA creati

Sono riportati solo ID e prefissi:

| ID | Prefisso | Stato |
| ---: | --- | --- |
| 426 | `qa-fase2-20261121114829-min` | non verificato |
| 427 | `qa-fase2-20261121114829-full` | non verificato |
| 428 | `qa-fase2-e2e-20261121154920` | mail ricevuta, verifica FAIL |

Proposta di disattivazione conservativa, **non eseguita**:

```sql
BEGIN;
DELETE FROM sessions WHERE user_id IN (426, 427, 428);
UPDATE email_verification_tokens
SET revoked_at = now()
WHERE user_id IN (426, 427, 428) AND used_at IS NULL AND revoked_at IS NULL;
UPDATE users
SET pass_hash = '!qa-disabled!',
    email_verified = 0,
    email_verified_at = NULL,
    email_verification_required = TRUE
WHERE id IN (426, 427, 428);
-- Verificare i tre record e sostituire ROLLBACK con COMMIT solo dopo autorizzazione.
ROLLBACK;
```

La rimozione fisica non è proposta senza un inventario completo delle chiavi
esterne, perché ordini, crediti, accettazioni e QR devono essere preservati.

## Produzione e confini

La produzione è rimasta a `de0a4f1d848e68b5ea4113b3b80d2fa94cc23ffd` e
ha risposto HTTP 200 prima e dopo il deploy. Non sono stati modificati
`/opt/qrfacile`, `qrfacile.service`, `qrfacile_db`, Caddy, DNS, `.env` di
produzione o PayPal Live.

## Anomalie e limiti

1. **FAIL bloccante:** verifica email incompatibile con il tipo storico
   `integer` della colonna `users.email_verified`.
   **Risolto in `32cf797`, vedi Ridistribuzione.**
2. Checkout Sandbox e flusso vino completo restano `NOT_VERIFIED`.
3. Shellcheck non è disponibile sulla workstation; `bash -n` e il test LF sono
   stati eseguiti.
4. Nessuna capture, approvazione PayPal o pagamento completato.

## Conclusione del primo deploy

Questa conclusione descrive il checkpoint storico su `3da7d35`. Il difetto è
stato corretto e verificato dalla ridistribuzione documentata nella sezione
seguente.

## Ridistribuzione 32cf797

### Identità e perimetro

- data e ora di attivazione: 2026-11-21 17:15:32 CET (Europe/Rome);
- host: `192.168.1.139`;
- root: `/opt/qrfacile-staging`;
- servizio: `qrfacile-staging.service`, `active`;
- database: `qrfacile_staging_db`;
- SHA prima: `3da7d35654ed2bc9b74cc8865c11cf293d70473f`;
- SHA dopo: `32cf797d126259114917dccc0d3f1b53c83769b9`;
- produzione: invariata a `de0a4f1d848e68b5ea4113b3b80d2fa94cc23ffd`.

Readback `GET /healthz`, HTTP 200:

```json
{"status":"OK","environment":"staging","database":"OK","release":"32cf797d126259114917dccc0d3f1b53c83769b9"} <!-- pragma: allowlist secret -->
```

Il journal del servizio non contiene errori dal nuovo avvio. Home e login
staging rispondono HTTP 200. La home produzione risponde ancora HTTP 200.

### Backup e rollback

Backup fresco conservato:

```text
/opt/qrfacile-backups/staging/20261121_171518_staging_3da7d35654ed
```

| Artefatto | SHA-256 |
| --- | --- |
| dump PostgreSQL | `13862eb0fc4a55e3882d1d47a8a74f2438064d4fd47e16d5901b3c0c2d9eaeee` |
| archivio filesystem | `7362a7553f626f9ded4c72558af343dc7bcaa3287def87e44afb301d01b85aa0` |

Verifiche: `sha256sum -c` PASS su entrambi gli artefatti,
`pg_restore --list` PASS e `gzip -t` PASS.

Rollback dedicato conservato:

```text
/opt/qrfacile-staging.rollback-20261121_171518-3da7d35654ed
```

Il readback Git della directory di rollback restituisce lo SHA precedente
`3da7d35654ed2bc9b74cc8865c11cf293d70473f`.

### Release

Prima dello swap il target ha superato `compileall`, import applicazione,
security audit (0 finding) e controllo transazioni SQL. Ambiente `staging` e
database `qrfacile_staging_db` sono stati confermati. Il primo health probe
eseguito immediatamente dopo il restart ha incontrato il breve intervallo di
avvio; il retry previsto dallo script ha poi restituito
`RELEASE_HEALTH_OK` sullo SHA esatto.

La copia versionata dello script ha richiesto una correzione operativa
temporanea: il clone locale eseguito da `root` era rifiutato da Git per
`dubious ownership` sul repository appartenente all'utente di servizio. La
copia runtime LF ha eseguito soltanto clone e checkout come proprietario del
repository; backup, swap, health check e rollback sono rimasti invariati. I
tentativi precedenti si sono fermati prima dello swap e non hanno riavviato il
servizio. La correzione permanente dello script resta da versionare.

### Collaudo Fase E aggiornato

| # | Punto | Esito | Evidenza sintetica |
| ---: | --- | ---: | --- |
| 1 | Home e CTA vino | **PASS** | `/` HTTP 200; CTA di prova gratuita verso `/register-winery` |
| 2 | Registrazione Cantina minima | **PASS** | account minimo creato da interfaccia, mail ricevuta, 3 crediti iniziali |
| 3 | Profilo fiscale incompleto | **PASS** | profilo parziale rifiutato prima della scrittura; profilo vuoto ammesso per la prova |
| 4 | Profilo fiscale completo | **PASS** | dati di test formalmente validi salvati e normalizzati tramite interfaccia |
| 5 | Checkout vuoto → impostazioni → Sandbox | **PASS** | account con profilo vuoto: redirect a `#profilo-fiscale` e 0 ordini; account completo: redirect PayPal Sandbox, ordine 67 `pending`, nessun login/approvazione/capture |
| 6 | Vino 7 step, preview, pubblicazione, `/e/`, export e QR | **PASS** | vino 623: fronte/retro, ingredienti/allergeni, nutrizione, riciclabilità, review, preview e pubblicazione; IT/EN HTTP 200; PNG/SVG/PDF validi; QR decodificato sull'URL pubblico staging; crediti 3 → 2 |
| 7 | Login/reset/Studio/pagine pubbliche | **PASS** | login/logout Cantina e Studio riusciti; pagina reset 200; Studio creato e verificato via email; seconda apertura dei link rifiutata |
| 8 | Discoverability | **PASS** | `robots.txt`, `sitemap.xml` e `llms.txt` HTTP 200 dopo la ridistribuzione |
| 9 | Produzione invariata | **PASS** | SHA produzione `de0a4f1d848e68b5ea4113b3b80d2fa94cc23ffd`, servizio attivo e home HTTP 200 |

La pagina pubblica `/e/` non imposta cookie e non contiene riferimenti ai
tracker controllati (Google Analytics/Tag Manager, Meta Pixel, Matomo, Hotjar).

### Prova SMTP e verifica email

- destinatario: casella di test controllata dal titolare;
- dominio mittente osservato: `qrfacile.it`;
- origine dei link: `http://192.168.1.139:8001`;
- Cantina ID 428: stesso link del tentativo fallito riutilizzato con successo;
- readback DB ID 428: flag intero di verifica positivo e
  `email_verified_at` valorizzato;
- seconda apertura dello stesso link: HTTP 404, collegamento non valido;
- Studio ID 430: messaggio ricevuto, link aperto con successo e login riuscito;
- aggiornamenti SQL manuali: **NESSUNO**.

Nessun indirizzo completo o token è riportato.

### Conteggi DB staging

| Tabella | Prima della ridistribuzione | Dopo il collaudo |
| --- | ---: | ---: |
| `users` | 16 | 18 |
| `wineries` | 12 | 13 |
| `orders` | 61 | 62 |
| `qr_items` | 52 | 53 |
| `qr_wines` | 31 | 32 |

L'unico ordine aggiunto è `pending` in ambiente `sandbox`. Nessun pagamento è
stato approvato o completato.

### Account QA aggiornati

| ID | Prefisso | Stato |
| ---: | --- | --- |
| 426 | `qa-fase2-20261121114829-min` | non verificato |
| 427 | `qa-fase2-20261121114829-full` | non verificato |
| 428 | `qa-fase2-e2e-20261121154920` | verificato; vino e ordine Sandbox pending presenti |
| 429 | `qa-fase2-empty-202611211725` | verificato; profilo vuoto, 3 crediti, 0 ordini |
| 430 | `qa-fase2-studio-202611211735` | Studio verificato; login/logout riusciti |

Proposta conservativa aggiornata, **non eseguita**:

```sql
BEGIN;
DELETE FROM sessions WHERE user_id IN (426, 427, 428, 429, 430);
UPDATE email_verification_tokens
SET revoked_at = now()
WHERE user_id IN (426, 427, 428, 429, 430)
  AND used_at IS NULL AND revoked_at IS NULL;
UPDATE users
SET pass_hash = '!qa-disabled!',
    email_verified = 0,
    email_verified_at = NULL,
    email_verification_required = TRUE
WHERE id IN (426, 427, 428, 429, 430);
-- Verificare i record e sostituire ROLLBACK con COMMIT solo dopo autorizzazione.
ROLLBACK;
```

La rimozione fisica non è proposta: l'account 428 possiede crediti, un ordine
Sandbox pending e un vino pubblicato, quindi occorre preservare le relazioni.

### Limiti residui

1. **Risolto in `5f88b0f`:** `scripts/deploy_staging.sh` esegue Git come
   proprietario del checkout. La correzione è coperta dal test dedicato e da
   ShellCheck nella Compliance CI; la validazione sull'host avverrà al prossimo
   deploy staging autorizzato.
2. Non sono stati eseguiti login PayPal, approvazioni, capture o pagamenti.
3. Produzione, `.env`, Caddy, DNS, PayPal Live e database produzione non sono
   stati modificati.

## Deploy UX v2 e verifica Danea — `10fda8c`

### Identità e CI

- data di attivazione: 2026-11-21 20:30:04 CET (Europe/Rome);
- host/root/servizio: `192.168.1.139`, `/opt/qrfacile-staging`,
  `qrfacile-staging.service`;
- database: `qrfacile_staging_db`;
- SHA prima: `a49bed3a91796f61567a046303f4aea63b97f237`;
- SHA dopo: `10fda8c56e6ab9c1dcc89a00938f30a028743704`;
- Compliance CI prima del deploy: run `44940949949`, **SUCCESS**.

Readback HTTP 200:

```json
{"status":"OK","environment":"staging","database":"OK","release":"10fda8c56e6ab9c1dcc89a00938f30a028743704"} <!-- pragma: allowlist secret -->
```

### Backup, migrazione e rollback

Backup DB pre-migrazione, conservato e verificato:

```text
/opt/qrfacile-backups/staging/20261121_202909_pre_ux2_a49bed3a9179
```

- dump: `20261121_202909_qrfacile_staging_db.dump`;
- SHA-256:
  `fa8fd66d5152f15aca72b6cda90aaec1d0aa7a2181ba64ac3adb9706c8469340`;
- `sha256sum -c`, `pg_restore --list` e restore verso `/dev/null`: **PASS**.

Il primo nome generato dal wrapper remoto conteneva letteralmente variabili
shell a causa dell'escaping PowerShell. Prima di procedere il backup è stato
rinominato nel percorso sopra, il manifest è stato rigenerato e tutte le
verifiche sono state ripetute con esito positivo. Il proprietario del `.env`,
temporaneamente modificato dal replace atomico, è stato ripristinato a
`qrfacile:qrfacile`; modo finale `0600`.

La migrazione `sql/2026_order_invoice_handoff.sql` è stata applicata col ruolo
applicativo. Le tre colonne `invoice_handoff_*` erano già presenti: PostgreSQL
ha emesso solo notifiche “esiste già, saltata” e la transazione ha completato
con `COMMIT`. Nel `.env` staging risultano configurati i soli nomi
`QRFACILE_INVOICE_TO` e `QRFACILE_INVOICE_CC`; nessun valore è riportato.

Backup creato dallo script immediatamente prima dello swap:

```text
/opt/qrfacile-backups/staging/20261121_202949_staging_a49bed3a9179
```

| Artefatto | SHA-256 |
| --- | --- |
| dump PostgreSQL | `c400dcf56e7e6fd7c286d24566d7d840fdba92bd54573ee4bfecc081538236ef` |
| archivio filesystem | `eb4c637eb254a5855c418fe45878241f13ad14ebc0d5cb487cfa71ab2e663ff8` |

`sha256sum -c`, `pg_restore --list`, restore verso `/dev/null`, `gzip -t` e
lettura archivio: **PASS**.

Rollback dedicato conservato:

```text
/opt/qrfacile-staging.rollback-20261121_202949-a49bed3a9179
```

Readback del rollback come proprietario del checkout:
`a49bed3a91796f61567a046303f4aea63b97f237`.

### Deploy e comportamento Git

Il remote `origin` del checkout installato era autoreferenziale
(`/opt/qrfacile-staging`), quindi il primo fetch per nome ramo si è fermato
senza swap. È stato eseguito un fetch esplicito dall'URL pubblico del
repository, senza cambiare la configurazione del remote. Lo script versionato
non aveva il bit eseguibile nell'installazione precedente ed è stato invocato
con `bash` senza modificare permessi.

Il deploy ha poi superato backup, clone, checkout detached dello SHA esatto,
installazione dipendenze, `compileall`, security audit (0 finding), controllo
transazioni SQL, swap, restart e health check. Clone e checkout sono stati
eseguiti correttamente come proprietario `qrfacile:qrfacile`. Il primo probe
ha intercettato il breve avvio; il retry ha prodotto `RELEASE_HEALTH_OK`.

### Walkthrough UX v2

| Controllo | Esito | Evidenza sintetica |
| --- | ---: | --- |
| Account QA nuovo e verifica email | **PASS** | account `qa-ux2-*`, verifica via link ricevuto, nessun bypass SQL |
| Dashboard “Il tuo primo vino” | **PASS** | login diretto a `/app/dashboard`, checklist visibile |
| Saldo QR | **PASS** | `3` prima del lotto, `2` dopo, coerente nelle pagine successive |
| Stati dei passi | **PASS** | completamento aggiornato dopo ogni salvataggio |
| Calcolatore | **PASS** | 13,5% e 2 g/l → 312 kJ / 75 kcal; applicazione e salvataggio riusciti |
| Preset imballaggi | **PASS** | `GL 71`, `FOR 51`, `ALU 41`, `PAP 22`; nessuna duplicazione/avviso |
| Review/export | **PASS** | tre azioni finali; CTA “Scarica PDF per la tipografia”; PDF A4 e QR decodificato |
| Pagina pubblica IT/EN | **PASS** | nuovo vino `0 g / 0,2 g` (`0.2` EN); vecchio vino `0 g / 2,6 g` (`2.6` EN); codici corretti |
| Mobile | **PASS** | contenuto prima del menu laterale |
| Cookie/tracker | **PASS** | 0 cookie e solo host staging in contesto pulito |

Evidenza completa e screenshot:
`docs/UX_REVIEW_2026-11-21_v2.md` e
`docs/ux-review-2026-11-v2/`.

### Fatturazione Danea

Il 2026-11-21 è stato creato un nuovo account `qa-danea-*`, verificato mediante
email reale e completato con un profilo fiscale fittizio formalmente valido.
La UI ha mostrato correttamente il pacchetto Start (€ 99,00 + € 21,78 IVA =
€ 120,78), ha creato un solo ordine e ha raggiunto PayPal Sandbox. La prova si
è fermata prima dell'approvazione perché il titolare non era al PC: capture,
stato `paid`, email, allegato, UI Admin, idempotenza e import Easyfatt restano
**NOT_VERIFIED**, non `PASS`.

Evidenza completa: `docs/DANEA_HANDOFF_ACCEPTANCE_2026-11-21.md`.

Resta inoltre valida l'anomalia storica: gli ordini Sandbox pagati `32`, `31` e
`15`, precedenti allo snapshot fiscale, non sono utilizzabili per questa prova;
il tentativo già documentato sull'ordine `32` terminò con
`fiscal_snapshot_missing` e nessuna email.

### Confini

Nessuna operazione su produzione, PayPal Live, Caddy o DNS. Nessun pagamento
reale. La sola modifica di configurazione riguarda i due destinatari Danea
dello staging autorizzati; valori e segreti non sono riportati.

## Deploy e walkthrough UX v3 — `0afb234`

### Identità e protezioni

- data deploy: 2026-11-21 21:32 CET (Europe/Rome);
- host/root/servizio: `192.168.1.139`, `/opt/qrfacile-staging`,
  `qrfacile-staging.service`;
- database: `qrfacile_staging_db`;
- SHA prima: `10fda8c56e6ab9c1dcc89a00938f30a028743704`;
- SHA dopo: `0afb234327b66ad3a91e47402c9ba26a88f0aede`;
- Compliance CI pre-deploy: run `44946635708`, **SUCCESS**;
- backup verificato conservato:
  `/opt/qrfacile-backups/staging/20261121_213218_staging_10fda8c56e6a`;
- rollback conservato:
  `/opt/qrfacile-staging.rollback-20261121_213218-10fda8c56e6a`.

Lo script ha completato backup, release isolata, swap, restart e verifica dello
SHA atteso. Il primo probe HTTP ha intercettato il breve avvio del servizio; il
retry previsto ha restituito `RELEASE_HEALTH_OK` sullo SHA `0afb234`. Nessuna
migrazione nuova è stata applicata.

### Walkthrough UX v3

| Controllo | Esito | Evidenza sintetica |
| --- | ---: | --- |
| Account QA e verifica email | **PASS** | account `qa-ux3-*`, link reale, nessun bypass SQL |
| Stato vuoto iniziale | **PASS** | checklist, saldo `3`, Esci e link alla dashboard completa; assenza della scheda bozza corretta |
| Nuovo lotto | **PASS** | vino unico preselezionato, Studio chiuso, gestione cantina predefinita, saldo `3 → 2` |
| Bozza e checklist | **PASS** | “Il tuo vino in preparazione”, scheda vino e passo ingredienti successivo |
| Dati obbligatori | **PASS** | quattro schede progressive, Avanti, spunte e ancore corrette; errore riciclo riapre la sezione |
| Calcolatore e preset | **PASS** | 13,5% e 2 g/l → 312 kJ / 75 kcal; `GL 71`, nessun duplicato |
| Review e pubblicazione | **PASS** | tre azioni finali; pubblicazione riuscita; ritorno alla dashboard completa |
| Export | **PASS** | CTA PDF tipografia; PDF A4 15.127 byte; QR decodificato verso la pagina staging |
| Pubblico IT/EN | **PASS** | codici e valori corretti; nessun “da verificare” |
| Cookie/tracker pubblico | **PASS** | contesto anonimo: 0 cookie, 0 storage e 0 tracker |

La pagina mobile “Dati obbligatori”, misurata sullo stesso contenuto a 390 px,
passa da 11.275 px con tutte le sezioni aperte a 4.370 px con una scheda alla
volta: riduzione di 6.905 px, circa 61%.

Tempi comparabili per la persona con scheda tecnica pronta: 60-90 minuti prima
delle correzioni, 35-50 minuti in UX v2, 28-42 minuti in UX v3. I punti residui
di assistenza sono l'imballaggio non coperto dai preset, la conferma dei valori
nutrizionali e, in misura minore, il rapporto fra vino/etichetta e lotto.

Evidenza completa e screenshot:
`docs/UX_REVIEW_2026-11-21_v3.md` e
`docs/ux-review-2026-11-v3/`.

### Danea e confini

Il test Danea è **sospeso: pagamento Sandbox da completare con il titolare al
PC**. L'unico ordine predisposto resta non pagato; capture, email `.DefXml`, UI
Admin, idempotenza e import Easyfatt restano `NOT_VERIFIED`. Nessuna operazione
ha interessato produzione, database produzione, PayPal Live, Caddy o DNS.

## Configurazione e prova alert operativo — 2026-11-21

Solo su staging è stato configurato il nome
`QRFACILE_OPERATIONAL_ALERT_TO`, senza stampare il valore. Il file `.env` ha
mantenuto proprietario applicativo e modo `0600`. Prima della modifica è stata
creata e verificata la copia con checksum:

```text
/opt/qrfacile-backups/staging/20261121_224437_pre_operational_alert_0afb234327b6
```

Il servizio `qrfacile-staging.service` è stato riavviato; stato finale
`active`, `/healthz` `OK`, ambiente `staging`, release `0afb234`.

Il wrapper `scripts/run_operational_monitor.py` è stato eseguito in modalità di
prova con soglia contabile prudenziale pari a zero. Esito aggregato:

```text
transactional_email=ok
paypal_webhook_queue=ok
privacy_sla=ok
payment_reconciliation=alert
OPERATIONAL_MONITOR_ALERT_SENT checks=4
```

È stato inviato un solo alert sintetico contenente esclusivamente nomi e stati
aggregati, senza payload, identificativi o dati personali. Il titolare ne ha
confermato la ricezione nella chat QRFacile il 2026-11-21: **PASS** per la
consegna dell'alert staging. Nessuna modifica è stata eseguita su database,
produzione o PayPal.

## Deploy staging e verifica Home Chooser — 2026-11-22

- SHA staging prima: `abecf547c6b1ff09ee4b79e01c40492c76715d91`.
- SHA staging dopo e head PR #12 (Draft):
  `30c985f6786670f85177f9a332a9767fafea1d45`.
- Fetch esplicito: SHA verificato, remoto invariato. Diff `sql/` vuoto.
- Backup: tag creato, SHA-256 di dump e archivio verificati, indice
  `pg_restore --list` verificato. Rollback conservato.
- `RELEASE_HEALTH_OK` sullo SHA atteso.
- Server: `574 passed, 10 skipped`; transazioni SQL OK; audit 0 rilievi.
- Home: sezione e sei schede corrette; tutte le destinazioni HTTP 200;
  CTA a `#scegli`; nessun link a `/register-business`.
- Nessuno scroll orizzontale a 375 px o nel viewport equivalente al
  reflow 400% (320 px); tutte e sei le schede raggiunte con focus visibile.
  Zoom nativo del browser non verificato. Axe 4.10.2: 0 serious/critical.
  Screenshot desktop e mobile acquisiti.
- QR storici: `HISTORIC_QR_OK legacy=12/broken=0 wine=29/broken=0/to_complete=10`.
  Nessun QR rotto, ma lo staging ha 29 QR vino nel controllo invece dei
  24 attesi. Collaudo interrotto al passo 5; Link beta e pagine Wine non
  collaudati.
- Esito complessivo: `STAGING_HOME_CHOOSER: FAIL` per conteggio inatteso
  e collaudo non concluso. Nessun deploy in produzione.
