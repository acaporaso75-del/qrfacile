# QRFacile — readback deploy staging Fase 2

Data readback: 2026-11-21 11:30 CET, Europe/Rome.

Questo documento registra esclusivamente fatti verificati in lettura sul
runtime staging e nel repository. Non contiene segreti, token, contenuto degli
`.env`, email complete o dati personali. Non autorizza né registra modifiche a
produzione, database, Caddy, DNS o PayPal Live.

## Esito sintetico

**FAIL — il target `3da7d35654ed2bc9b74cc8865c11cf293d70473f`
non risulta installato sullo staging.**

Il checkout e `/healthz` espongono ancora
`ed7f0b0663f620d8c35afb58adc5f446073e0285`. Il servizio non risulta riavviato
per il target e non sono stati trovati backup o directory di rollback del
2026-11-21. In questa Fase F non è stato rieseguito né corretto il deploy.

## Identità runtime

- host applicativo: `192.168.1.139` (`golden-debian`);
- directory canonica: `/opt/qrfacile-staging`;
- servizio: `qrfacile-staging.service`, `active`;
- avvio processo osservato: 2026-11-15 20:34:10 CET;
- SHA precedente dichiarato: `ed7f0b0663f620d8c35afb58adc5f446073e0285`;
- SHA target: `3da7d35654ed2bc9b74cc8865c11cf293d70473f`;
- SHA osservato dopo il presunto deploy: ancora
  `ed7f0b0663f620d8c35afb58adc5f446073e0285`;
- data/ora effettiva del deploy del target: `NOT_VERIFIED` (nessun deploy del
  target osservato).

Readback `GET http://127.0.0.1:8001/healthz`, HTTP `200`:

`{"status":"OK","environment":"staging","database":"OK","release":"ed7f0b0663f620d8c35afb58adc5f446073e0285"}` <!-- pragma: allowlist secret -->

Il JSON conferma ambiente e database sani per la release precedente, ma non il
target Fase 2.

## Backup

Non è presente un backup riconducibile al target `3da7d35` o al 2026-11-21.
L'ultimo backup staging disponibile è precedente e non viene presentato come
backup di questo deploy:

- percorso:
  `/opt/qrfacile-backups/staging/20261102_075131_staging_59cf70a834db`;
- release dichiarata nel backup:
  `59cf70a834dbdd300fc93af35898e7c455753f73`;
- dump `database.dump`, SHA-256:
  `542e845d84d7687568e8340dd9f30ae06146145761689b2e0ce4fbba9e0cde68`;
- archivio `filesystem.tar.gz`, SHA-256:
  `81888d9b14d100957217c71a5729c9f93a5a6025d654c270169ab9154cad3112`.

Verifiche in sola lettura rieseguite il 2026-11-21:

| Verifica | Esito |
| --- | ---: |
| `sha256sum -c SHA256SUMS` | PASS, 6/6 file `OK` |
| `pg_restore --list database.dump` | PASS, exit `0` |
| `gzip -t filesystem.tar.gz` | PASS, exit `0` |

Queste verifiche dimostrano l'integrità dell'ultimo backup disponibile del 2
novembre, non l'esistenza di un backup pre-deploy per `3da7d35`.

## Rollback

Non è presente una directory rollback del 2026-11-21 o del target `3da7d35`.
L'ultima directory conservata è:

```text
/opt/qrfacile-staging.rollback-20261102_075344-59cf70a834db
```

È relativa alla release precedente e non costituisce rollback del target Fase
2. Rollback specifico `3da7d35`: `NOT_VERIFIED`.

## Release

Le seguenti verifiche sono state eseguite sul checkout locale del target durante
il readback documentale; non esiste una ricevuta che le collochi prima di uno
swap runtime:

| Controllo | Esito | Evidenza sintetica |
| --- | ---: | --- |
| `compileall` | PASS | moduli applicazione, script, test e `main.py` compilati |
| import applicazione fail-closed | PASS | `APP_ENV=test`, 77 route caricate |
| security audit | PASS | 0 finding |
| SQL transaction check | PASS | `SQL transaction boundaries: OK` |
| esecuzione pre-swap sul server | NOT_VERIFIED | nessun log/ricevuta e nessuno swap osservato |

Il runtime risponde come `staging`; la query catalogo ha confermato il database
`qrfacile_staging_db`. Nessun valore di connessione è stato letto o riportato.

## Collaudo Fase E

Account di prova previsto: prefisso `qa-fase2-*`. Nel database staging ne sono
stati trovati `0`; nessuna email completa è stata letta o riportata.

| # | Punto | Esito | Evidenza sintetica |
| ---: | --- | ---: | --- |
| 1 | Home focalizzata sul vino | **FAIL** | `/` HTTP 200 ma contiene ancora il marker della hero generica precedente; manca la hero Fase 2 con `3 QR` |
| 2 | Registrazione Cantina minima | **FAIL** | HTML runtime mostra 14 attributi `required`, nessun `<details>` fiscale; il target ne prevede 6 |
| 3 | Profilo fiscale incompleto rifiutato prima della scrittura | `NOT_VERIFIED` | nessun POST mutativo eseguito; target non installato |
| 4 | Profilo fiscale completo normalizzato | `NOT_VERIFIED` | nessun POST mutativo eseguito; target non installato |
| 5 | Checkout profilo vuoto → impostazioni → PayPal Sandbox | `NOT_VERIFIED` | nessun flusso checkout eseguito; target non installato |
| 6 | Vino 7 step, `/e/` ed export QR | `NOT_VERIFIED` | nessun collaudo end-to-end eseguito |
| 7 | Regressione login/reset/Studio/pagine pubbliche | `NOT_VERIFIED` | nessun collaudo end-to-end completo eseguito |
| 8 | Discoverability | `NOT_VERIFIED` | `/robots.txt` e `/sitemap.xml` rispondono 200, ma contenuto/target Fase 2 non validati |
| 9 | Produzione invariata | `NOT_VERIFIED` | applicazione prod invariata e sana; assenza di modifiche a DB/Caddy/DNS/PayPal Live non dimostrabile con un ledger di fase |

## Conteggi database staging

I conteggi precedenti al presunto deploy non sono presenti in una ricevuta e
sono quindi `NOT_VERIFIED`. I valori correnti letti dopo il mancato deploy sono:

| Tabella | Prima | Corrente al readback |
| --- | ---: | ---: |
| `users` | `NOT_VERIFIED` | 13 |
| `wineries` | `NOT_VERIFIED` | 9 |
| `orders` | `NOT_VERIFIED` | 61 |
| `qr_items` | `NOT_VERIFIED` | 52 |
| `qr_wines` | `NOT_VERIFIED` | 31 |

Questi numeri non possono essere descritti come confronto prima/dopo del target,
perché il target non è stato installato.

## Produzione

- checkout `/opt/qrfacile` ancora a
  `de0a4f1d848e68b5ea4113b3b80d2fa94cc23ffd`;
- `qrfacile.service`: `active`, stesso processo avviato il 2026-11-15
  20:34:10 CET;
- `GET http://127.0.0.1:8000/`: `200` nel readback precedente e `200` nel
  readback corrente;
- `GET http://127.0.0.1:8000/pricing`: `200` corrente;
- nessuna modifica osservata nel checkout `/opt/qrfacile` o nel servizio.

Per `qrfacile_db`, Caddy, DNS e PayPal Live non è disponibile un ledger
prima/dopo specifico di questa fase: assenza di modifiche `NOT_VERIFIED`. In
questa lavorazione documentale non è stata eseguita alcuna operazione su tali
sistemi.

## Anomalie e limiti

1. **FAIL:** staging ancora su `ed7f0b0`, non su `3da7d35`.
2. **FAIL:** home e registrazione espongono ancora l'UX precedente.
3. **FAIL:** backup pre-deploy e rollback specifici del target non esistono nei
   percorsi canonici osservati.
4. `qrfacile-staging.service` non risulta riavviato il 2026-11-21.
5. Nessun account `qa-fase2-*`; collaudo mutativo Fase E non eseguito.
6. Le verifiche locali del codice sono PASS, ma non provano una release runtime.
7. Nessun deploy è stato rieseguito durante questa chiusura documentale.

## Conclusione

La Fase F documentale è completata con esito **FAIL** per il deploy staging del
target. Il singolo prossimo passo autorizzabile è predisporre un nuovo piano di
deploy staging di `3da7d35` con backup fresco verificato, rollback specifico e
collaudo Fase E; non deve essere eseguito senza nuova autorizzazione esplicita.
