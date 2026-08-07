# Runbook di applicazione staging safety v1

Tutti i passi sono preparati ma non eseguiti. Servono nuova autorizzazione,
commit locale definitivo e finestra di manutenzione del solo staging.

## Precondizioni

1. Verificare il backup `20260806_180117_staging_131acbf390fa` con
   `sha256sum -c SHA256SUMS`.
2. Copiare il backup cifrato off-host e verificarne il checksum.
3. Confermare DNS e reverse proxy per `https://staging.qrfacile.it`.
4. Rieseguire l'intera CI sul commit correttivo.
5. Verificare che produzione sia ancora su `main` e non venga inclusa nella
   finestra operativa.

## Preparazione release senza alterare la directory corrente

```bash
release_id="$(date +%Y%m%d_%H%M%S)"
git clone --no-local https://github.com/acaporaso75-del/qrfacile.git \
  "/opt/qrfacile-staging-next-${release_id}"
git -C "/opt/qrfacile-staging-next-${release_id}" checkout --detach <COMMIT_CORRETTIVO>
test "$(git -C "/opt/qrfacile-staging-next-${release_id}" rev-parse HEAD)" = \
  "<COMMIT_CORRETTIVO>"
```

Creare il virtualenv nella directory `next`, installare dipendenze e copiare il
file `.env` staging con permessi `0600`, senza stamparlo. Aggiornare `.env`
soltanto dopo autorizzazione con i valori documentati in `staging-safety-v1.md`.

## Collaudo prima dell'applicazione

1. Ripristinare il dump in un database temporaneo `qrfacile_test_*`.
2. Impostare `qrfacile.target_database` al nome temporaneo.
3. Eseguire pre-check, migrazione, post-check e rollback.
4. Ripetere migrazione e post-check per verificare l'idempotenza.
5. Non usare mai `qrfacile_staging_db` o `qrfacile_db` per i test.

## Applicazione futura sul solo staging

```bash
systemctl stop qrfacile-staging.service
```

Con le credenziali staging protette e `ON_ERROR_STOP=1`:

```bash
psql -X -v ON_ERROR_STOP=1 -f sql/2026_staging_safety_reconciliation_v1_precheck.sql
psql -X -v ON_ERROR_STOP=1 -f sql/2026_staging_safety_reconciliation_v1.sql
psql -X -v ON_ERROR_STOP=1 -f sql/2026_staging_safety_reconciliation_v1_postcheck.sql
```

Se tutti i controlli passano:

```bash
mv /opt/qrfacile-staging "/opt/qrfacile-staging.quarantine-${release_id}"
mv "/opt/qrfacile-staging-next-${release_id}" /opt/qrfacile-staging
systemctl start qrfacile-staging.service
curl --fail http://127.0.0.1:8001/healthz
```

Collaudare login, dashboard, upload su percorso staging, inviti, Compliance
Advisor e route pubbliche. Non inviare e-mail reali né effettuare chiamate PayPal
finché sandbox e origin staging non sono verificati.

## Rollback futuro

Se la migrazione fallisce, la sua transazione esegue rollback automatico e la
directory corrente non viene scambiata.

Se il nuovo codice fallisce dopo lo scambio:

```bash
systemctl stop qrfacile-staging.service
psql -X -v ON_ERROR_STOP=1 \
  -f sql/2026_staging_safety_reconciliation_v1_rollback.sql
mv /opt/qrfacile-staging "/opt/qrfacile-staging.failed-${release_id}"
mv "/opt/qrfacile-staging.quarantine-${release_id}" /opt/qrfacile-staging
systemctl start qrfacile-staging.service
curl --fail http://127.0.0.1:8001/healthz
```

Se il rollback SQL non è sufficiente, usare il ripristino con swap del database
descritto nel backup verificato. Non eliminare directory o database di quarantena
prima dell'approvazione del collaudo.
