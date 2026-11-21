# QRFacile — readback deploy e collaudo staging Fase 2

Data deploy e readback: 2026-11-21, Europe/Rome.

Questo documento riguarda esclusivamente lo staging QRFacile. Non contiene
segreti, token, contenuto degli `.env`, indirizzi email completi o altri dati
personali. Produzione, Caddy, DNS e PayPal Live non sono stati modificati.

## Esito sintetico

Il deploy dello SHA `3da7d35654ed2bc9b74cc8865c11cf293d70473f` è
**PASS**: servizio attivo, `/healthz` coerente e backup/rollback verificati.

Il collaudo SMTP è **PASS**, ma il click del collegamento di verifica email è
**FAIL**. Lo schema staging conserva `users.email_verified` come `integer`,
mentre il codice installato tenta di assegnare il booleano `TRUE`. PostgreSQL
restituisce `DatatypeMismatch` e l'account non viene sbloccato. Non è stato
usato SQL per aggirare il controllo. Checkout autenticato e flusso vino restano
quindi `NOT_VERIFIED`.

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
2. Checkout Sandbox e flusso vino completo restano `NOT_VERIFIED`.
3. Shellcheck non è disponibile sulla workstation; `bash -n` e il test LF sono
   stati eseguiti.
4. Nessuna capture, approvazione PayPal o pagamento completato.

## Conclusione

Deploy staging PASS e SMTP reale PASS; collaudo applicativo complessivo non
chiudibile finché la verifica email non viene resa compatibile con lo schema
staging e distribuita con una nuova autorizzazione puntuale.
