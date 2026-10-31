# QRFacile — readback runtime staging

Data: 2026-10-30, Europe/Rome.

Verifica eseguita esclusivamente in lettura tramite l'account SSH `enolab` e la
chiave di audit già autorizzata. Non sono stati modificati servizi, file,
configurazioni, database, DNS, proxy o segreti.

## Identità del runtime

- host applicativo: `192.168.1.139`;
- directory: `/opt/qrfacile-staging`;
- servizio `qrfacile-staging.service`: `active`;
- checkout: detached HEAD pulito;
- SHA installato: `59cf70a834dbdd300fc93af35898e7c455753f73`;
- lo SHA installato è un antenato del candidato della PR `#12`, non il
  candidato corrente.

## Health check

Richiesta locale al runtime staging:

```text
GET http://127.0.0.1:8001/healthz
HTTP 200
{"status":"OK","environment":"staging","database":"OK","release":"59cf70a834dbdd300fc93af35898e7c455753f73"} <!-- pragma: allowlist secret -->
```

La root locale della produzione sulla porta `8000` ha risposto HTTP `200`; non
sono stati eseguiti ulteriori probe produttivi e l'account di audit non ha letto
il checkout `/opt/qrfacile`.

## Backup e rollback in sola lettura

La verifica amministrativa è stata eseguita con la stessa chiave SSH già
autorizzata, senza creare o modificare file:

- spazio disponibile sul filesystem applicativo: circa `29 GB` (`17%` usato);
- backup staging più recente disponibile:
  `20261029_162239_staging_cd60fc338f57`;
- tutti i file elencati in `SHA256SUMS`: `OK`;
- archivio filesystem: test gzip superato;
- dump PostgreSQL: indice `pg_restore` leggibile, `728` voci;
- procedura di rollback presente;
- i probe registrati nel riepilogo sanitizzato negano le connessioni incrociate
  effettive fra utenze staging e produzione.

Il backup è integro ma rappresenta lo SHA `cd60fc3`, precedente allo staging
attuale `59cf70a`. Non viene quindi classificato come backup fresco del runtime
corrente e non sostituisce il backup da acquisire e verificare immediatamente
prima di un futuro deploy. In questa verifica non è stato eseguito un restore.

## Preflight configurazione senza esposizione di segreti

Sono stati letti esclusivamente valori non sensibili e stato presente/assente
delle variabili nell'ambiente effettivo del processo:

- `APP_ENV=staging`;
- `APP_BASE_URL=http://192.168.1.139:8001`;
- `PAYPAL_MODE=sandbox`;
- database, credenziali PayPal Sandbox e configurazione SMTP canonica: presenti;
- `PAYPAL_WEBHOOK_ID`: assente;
- `QRFACILE_OPERATIONAL_ALERT_TO`: assente;
- `CSRF_SECRET` e `SESSION_SECRET`: entrambi assenti.

Non è stato eseguito alcun invio email, webhook o pagamento. Il candidato è
stato corretto affinché staging e produzione rifiutino l'avvio quando entrambi
i segreti CSRF/sessione mancano; il runtime attuale non è stato modificato. Il
webhook firmato e la consegna degli alert restano fail-closed finché i relativi
parametri non vengono configurati nel secret store/runtime autorizzato e
collaudati.

## Esito

Lo staging esistente è raggiungibile e sano per il proprio SHA, ma non fornisce
evidenza runtime per le modifiche successive presenti nella PR `#12`, inclusi
webhook PayPal firmato, alert, email transazionali, accessibilità e
discoverability. Nessuno di questi gate viene quindi marcato come superato.

Il prossimo collaudo utile richiede il deploy autorizzato dell'esatto SHA della
PR nello staging canonico, preceduto da backup verificato e rollback pronto e
seguito dai test non distruttivi previsti dal runbook. Questo documento non
autorizza il deploy.
