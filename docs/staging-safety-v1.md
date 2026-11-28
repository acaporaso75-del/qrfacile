# QRFacile PR #2 — staging safety v1

Questa fase prepara la stabilizzazione senza applicarla al server. Il riferimento è
`feature/legal-ai-compliance-2026` al commit
`131acbf390fae30a753815f5b96945e4639d9a92`.

## Configurazione staging obbligatoria

La configurazione proposta richiede valori espliciti:

```dotenv
APP_ENV=staging
APP_ROOT=/opt/qrfacile-staging
UPLOADS_DIR=/opt/qrfacile-staging/uploads
TEMPLATES_DIR=/opt/qrfacile-staging/templates
STATIC_DIR=/opt/qrfacile-staging/static
APP_BASE_URL=https://staging.qrfacile.it
DATABASE_URL=postgresql://qrfacile_staging_user:<PASSWORD>@192.168.1.143:5432/qrfacile_staging_db
```

Il dominio è una proposta: DNS e reverse proxy devono essere verificati prima di
modificare `.env`. Il controllo runtime non stampa password o URL di connessione
completi.

In staging l'avvio fallisce se:

- `APP_ENV` non è dichiarato;
- una directory risolve dentro `/opt/qrfacile`;
- l'origine è `https://qrfacile.it`;
- host, nome o utente database non corrispondono allo staging verificato;
- statici o upload non sono montabili.

## Router obbligatori e opzionali

I router obbligatori sono quelli necessari per autenticazione, onboarding,
health-check, shell applicativa, upload, inviti, mutazioni protette e validazioni
che devono precedere le route legacy:

```text
qrfacile_app.auth_routes
qrfacile_app.email_verification_ui
qrfacile_app.landing_routes
qrfacile_app.health
qrfacile_app.start_ui
qrfacile_app.dashboard_ui
qrfacile_app.label_media_ui
qrfacile_app.collaboration_management_ui
qrfacile_app.invitation_management_ui
qrfacile_app.invitations_ui
qrfacile_app.invitation_acceptance_ui
qrfacile_app.invitation_center_ui
qrfacile_app.secure_publish_ui
qrfacile_app.recycling_validation_ui
qrfacile_app.wine_compliance_engine_ui
qrfacile_app.studio_register_routes
qrfacile_app.winery_register_routes
qrfacile_app.public
qrfacile_app.uploads_routes
```

Un errore di importazione o un attributo `router` mancante in questo insieme
interrompe l'avvio. Gli altri router rimangono opzionali e producono un warning
esplicito. La classificazione deve essere rivalutata quando un modulo opzionale
diventa parte di un flusso di sicurezza o di persistenza obbligatorio.

## Privilegio CONNECT preparato, non eseguito

Da una connessione amministrativa a PostgreSQL:

```sql
REVOKE CONNECT ON DATABASE qrfacile_db FROM qrfacile_staging_user;
```

Verifica successiva:

```sql
SELECT has_database_privilege(
    'qrfacile_staging_user',
    'qrfacile_db',
    'CONNECT'
);
```

Se il risultato resta `true`, il privilegio arriva da `PUBLIC`: PostgreSQL non
supporta un `DENY` per singolo ruolo. In quel caso occorre un intervento separato
e autorizzato su `PUBLIC` e sui ruoli produttivi, preceduto dall'inventario di
tutti gli utenti del database.

## Migrazione correttiva

Ordine previsto:

1. `2026_staging_safety_reconciliation_v1_precheck.sql`;
2. `2026_staging_safety_reconciliation_v1.sql`;
3. `2026_staging_safety_reconciliation_v1_postcheck.sql`.

Il rollback dedicato è
`2026_staging_safety_reconciliation_v1_rollback.sql`.

La migrazione:

- usa advisory lock e transazione;
- accetta per default soltanto `qrfacile_staging_db`;
- permette un database temporaneo futuro solo tramite il parametro di sessione
  `qrfacile.target_database`;
- registra stato e metadati in `qrfacile_schema_migrations`;
- crea la tabella email mancante;
- aggiunge le quattordici colonne lifecycle/rate-limit mancanti;
- classifica gli inviti senza creare token;
- rifiuta un inventario staging diverso da quello verificato;
- non tocca `qr_wines`.

Per un database temporaneo autorizzato:

```sql
SELECT set_config(
    'qrfacile.target_database',
    current_database(),
    false
);
```
