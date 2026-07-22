# QRFACILE Audit prudente read-only

Data: 2026-05-16 11:29 Europe/Rome  
Modalita: analisi statica filesystem, senza lettura/stampa di `.env` o `.env.*`.  
Scritture effettuate: solo questo report.

## Executive summary

QRFACILE e una web app Python/FastAPI con UI server-side, PostgreSQL via `psycopg`, upload locali, QR dinamici, pagamenti PayPal e gestione ruoli Cantina/Studio/Admin. Il prodotto ha molte funzioni gia presenti, ma non e ancora in uno stato prudente per andare online e monetizzare senza un ciclo di stabilizzazione.

I blocchi principali sono:

- entrypoint duplicati e divergenti: `main.py` root e `qrfacile_app/main.py` includono router diversi; se in produzione parte `main:app`, PayPal e pagine legal non risultano incluse;
- pubblicazione QR vino non realmente privata: i nuovi QR vino vengono creati con `qr_items.status='attiva'` e `/e/{slug}` mostra anche le bozze;
- dipendenze runtime mancanti in `requirements.txt`: il codice usa `passlib` e `requests`, ma non sono dichiarate;
- upload etichetta legacy non validato: `label_media_ui.py` scrive bytes senza limite dimensione, verifica formato o ottimizzazione;
- enorme accumulo di backup/cache/file legacy dentro progetto, con rischio deploy/import/confusione operativa;
- flussi auth e admin duplicati: `auth.py` e `auth_core.py` hanno semantiche diverse; alcuni moduli usano ancora auth legacy.

## Struttura progetto

Root principali:

- `main.py`: entrypoint FastAPI root, monta `/static` e `/uploads`, include molti router ma non tutti.
- `qrfacile_app/main.py`: entrypoint alternativo piu completo; include `paypal_ui`, `legal_pages`, `legacy_routes` e altri admin.
- `qrfacile_app/`: applicazione principale attiva.
- `app/`: vecchia struttura parallela FastAPI/Jinja, apparentemente non integrata e incompleta (`app.db.conn` non presente).
- `static/`: asset statici.
- `uploads/`: file caricati e serviti pubblicamente.
- `templates/`: template legacy.
- `qrfacile_legacy_export/` e `qrfacile_legacy_export.tar.gz`: export legacy.
- `_backup_20260222_101411/`: copia completa vecchia.
- `venv/`, `__pycache__/`, `qrfacile_app/__pycache__/`: runtime/cache dentro al progetto.
- `_codex_reports/`: report Codex.

Dipendenze dichiarate in `requirements.txt`:

- `fastapi`, `uvicorn[standard]`, `psycopg[binary]`, `python-multipart`, `qrcode`, `segno`, `pillow`, `aiosmtplib`, `reportlab`.

Dipendenze importate ma non dichiarate:

- `passlib` in `auth_routes.py`, `studio_register_routes.py`, `winery_register_routes.py`;
- `requests` in `paypal_ui.py` e stress test;
- `jinja2` in `app/routers/public.py` legacy.

## P0 - Bloccanti prima di andare online

### P0.1 Entrypoint divergenti: rischio PayPal/Legal non attivi

File:

- `main.py`
- `qrfacile_app/main.py`

`main.py` root non include almeno:

- `qrfacile_app.paypal_ui`
- `qrfacile_app.legal_pages`
- vari admin nuovi inclusi invece in `qrfacile_app/main.py`

La pagina prezzi/billing genera form verso `/paypal/start`, ma se il processo avvia `main:app`, la route PayPal puo essere 404. Prima del go-live serve decidere un solo entrypoint ufficiale e allinearlo a service/gunicorn/uvicorn.

Priorita operativa:

1. verificare quale modulo viene avviato in produzione;
2. mantenere un solo `app = FastAPI(...)`;
3. rimuovere o deprecare l'altro entrypoint;
4. aggiungere smoke test route: `/`, `/login`, `/pricing`, `/app/billing`, `/paypal/debug`, `/privacy`, `/e/{slug}`.

### P0.2 QR vino pubblici gia alla creazione

File:

- `qrfacile_app/premium_ui.py`
- `qrfacile_app/bulk_tools.py`
- `qrfacile_app/public.py`
- `qrfacile_app/publish_routes.py`

In creazione QR vino:

- `premium_ui.py` inserisce `qr_items.status='attiva'`;
- `bulk_tools.py` fa lo stesso;
- `public.py` serve `/e/{slug}` anche se lo status non e attivo, marcandolo solo come "Bozza tecnica".

Questo significa che un QR appena creato puo essere raggiungibile se lo slug e noto, anche prima della pubblicazione formale e anche con dati incompleti. La pubblicazione in `publish_routes.py` controlla campi obbligatori, ma non e l'unico gate effettivo della pagina pubblica.

Priorita operativa:

1. creare QR vino come `bozza`, non `attiva`;
2. in `/e/{slug}` restituire 404/410/403 per bozze non pubblicate;
3. usare `wine_labels.public_enabled` o uno stato pubblicato coerente come gate reale;
4. verificare export QR: deve essere disponibile solo quando il QR e pubblicabile/pubblicato, oppure chiaramente marcato bozza.

### P0.3 Dipendenze runtime mancanti

File:

- `requirements.txt`
- `qrfacile_app/auth_routes.py`
- `qrfacile_app/paypal_ui.py`
- `qrfacile_app/studio_register_routes.py`
- `qrfacile_app/winery_register_routes.py`

`passlib` e `requests` sono necessari per login/registrazione/PayPal ma non sono nel requirements. Un deploy pulito puo fallire all'import.

Priorita operativa:

1. aggiungere dipendenze mancanti;
2. creare procedura install/deploy ripetibile;
3. eseguire smoke import in ambiente pulito.

### P0.4 Upload etichette legacy non validato

File:

- `qrfacile_app/label_media_ui.py`
- `qrfacile_app/media_labels.py`
- `qrfacile_app/wine_images_ui.py`
- `qrfacile_app/media.py`

`wine_images_ui.py` e `media.py` hanno controlli buoni: limite 5 MB, content-type, verifica PIL, anti decompression bomb, salvataggio normalizzato.

Pero `label_media_ui.py` usa ancora una pipeline legacy:

- legge tutto `image.file.read()` senza limite;
- salva direttamente su disco;
- accetta estensione dal filename;
- non verifica bytes immagine;
- non genera ottimizzate/thumb;
- espone poi il file via `/uploads`.

Priorita operativa:

1. sostituire il POST di `label_media_ui.py` con `process_label_image()` o pipeline equivalente hardenizzata;
2. applicare limite dimensione e pixel;
3. vietare file non immagine anche se hanno estensione valida;
4. rimuovere originali non normalizzati se non necessari.

### P0.5 PayPal duplicato rispetto alla configurazione prezzi

File:

- `qrfacile_app/pricing_config.py`
- `qrfacile_app/paypal_ui.py`
- `qrfacile_app/pricing_ui.py`
- `qrfacile_app/billing_ui.py`

`pricing_config.py` dichiara una fonte unica dei prezzi, ma `paypal_ui.py` mantiene un dizionario `PACKS` separato con importi/crediti. Questo puo generare divergenze tra prezzo mostrato e prezzo incassato.

Priorita operativa:

1. fare leggere PayPal da `pricing_config.py`;
2. testare che `/pricing`, `/app/billing` e `/paypal/start` usino stessi pack/importi;
3. registrare in `orders` snapshot di prezzo e nome pack al momento acquisto.

## P1 - Alta priorita

### P1.1 Autenticazione duplicata e incoerente

File:

- `qrfacile_app/auth.py`
- `qrfacile_app/auth_core.py`

Esistono due moduli auth:

- `auth.py`: controlla scadenza sessione, usa solo `sessions`, restituisce 401 grezzi.
- `auth_core.py`: prova `app_sessions` poi `sessions`, redirect pulito a login, supporta permessi studio su `studio_clients`, ma non applica scadenza sessione.

Alcuni moduli usano ancora `auth.py`: `label_media_ui.py`, `label_compliance_ui.py`, `label_history_ui.py`, `studio_payout_ui.py`, `admin_payouts_ui.py`. Questo rende esperienza, sicurezza e autorizzazioni non uniformi.

Azioni:

- consolidare un solo modulo auth;
- mantenere scadenza sessione e redirect pulito;
- applicare sempre controllo studio per winery/label/wine quando serve;
- aggiungere test ruoli per Cantina, Studio, Admin.

### P1.2 Route duplicate o morte

Esempi:

- `/admin` esiste in `admin_area.py`, `admin_home_ui.py`, `admin_stats_ui.py`; solo alcuni sono inclusi.
- `/app/settings/studios` esiste sia in `studio_settings_ui.py` sia in `winery_settings_ui.py`, entrambi inclusi.
- `app/routers/public.py` definisce una vecchia home admin su `/`, ma non sembra integrata.
- `app_area.py`, `app_area_labels_patch.py`, `admin_area.py`, `admin_stats_ui.py` sembrano residui o compat legacy.

Azioni:

- produrre inventario route ufficiali;
- eliminare/deprecare moduli non inclusi;
- evitare due handler per stesso path/metodo;
- aggiungere test che fallisca su route duplicate non volute.

### P1.3 Backup/safe/cache dentro deploy

Rilevati 204 file tra `.safe*`, `.bak*`, `.backup*`, `.broken*`, `.save*`, `.pyc`, tar/cache entro profondita 3.

Esempi:

- molti `qrfacile_app/*.safe_*` e `*.bak_*`;
- `qrfacile_app/wine_compliance_ui.py.broken_...`;
- `main.py.save`, `main.py.save.1`;
- `_backup_20260222_101411/`;
- `qrfacile_legacy_export.tar.gz`;
- `venv/`;
- `__pycache__/`;
- file `nano`.

Rischi:

- deploy piu pesante e confuso;
- import accidentali;
- esposizione di vecchie logiche;
- backup con codice vulnerabile vicino al codice live.

Azioni:

- spostare backup fuori dalla root applicativa;
- aggiungere `.gitignore`/manifest deploy;
- distribuire solo sorgenti live, static necessari, requirements e configurazione;
- non versionare `venv`, `__pycache__`, upload runtime.

### P1.4 Sistema crediti coerente ma con residui legacy

File:

- `qrfacile_app/credits.py`
- `qrfacile_app/pricing_config.py`
- `qrfacile_app/premium_ui.py`
- `qrfacile_app/paypal_ui.py`
- `qrfacile_app/billing_ui.py`

Regola business dichiarata:

- 1 credito wine = QR vino 10 anni;
- 2 crediti wine = QR vino 25 anni;
- registrazione cantina = 3 crediti free;
- nessun abbonamento obbligatorio.

Coerenze:

- registrazione cantina aggiunge 3 crediti `wine`;
- creazione QR vino scala 1 o 2 crediti;
- PayPal carica crediti.

Residui:

- `credits.py` default seed ancora 5 wine + 1 generic, diverso da `pricing_config.FREE_WINE_CREDITS_ON_REGISTER = 3`;
- `premium_ui.py` contiene ancora `_subscription_gate_for_new_wine()` e messaggi "rinnova piano";
- `paypal_ui.py` conserva funzioni subscription legacy;
- `billing_ui.py` mantiene richieste piano manuali e wording parzialmente legacy.

Azioni:

- rendere `pricing_config.py` fonte unica anche per seed e messaggi;
- decidere se subscription e davvero legacy e isolarla;
- rinominare messaggi "piano" in "crediti" dove non si vendono abbonamenti;
- testare saldo prima/dopo registrazione, acquisto, creazione QR 10/25 anni.

### P1.5 Registrazione e inviti Studio/Cantina

File:

- `qrfacile_app/winery_register_routes.py`
- `qrfacile_app/studio_register_routes.py`
- `qrfacile_app/studio_area.py`
- `qrfacile_app/studio_settings_ui.py`

Funziona a livello logico:

- Cantina crea user role `winery`, record `wineries`, seed crediti;
- Studio crea user role `studio`, record `studios`;
- inviti studio-cantina con token, scadenza, permessi view/edit/create;
- accettazione invito crea/aggiorna `studio_clients`;
- pubblicazione resta solo Cantina/Admin.

Criticita:

- `email_verified=1` alla registrazione, senza verifica email;
- mancano protezioni anti-spam/rate limit su registrazioni;
- invite token non e stampato, ma e conservato in chiaro nel DB;
- error redirect costruiti in parte con replace manuale invece di quoting robusto;
- serve verificare univocita DB su email, studio_clients, invite token.

Azioni:

- email verification o almeno double opt-in prima di monetizzare;
- rate limit login/register/invite;
- hashing token inviti se si vuole ridurre impatto DB leak;
- test end-to-end: Studio invita Cantina, Cantina registra, Studio vede solo cliente assegnato.

### P1.6 PayPal manca webhook/server-to-server finale

File:

- `qrfacile_app/paypal_ui.py`

Il flusso cattura pagamento su `/paypal/return` richiedendo utente loggato. Non ho trovato route webhook PayPal. Se l'utente paga ma non torna correttamente, o la sessione scade, il pagamento puo restare non registrato.

Azioni:

- implementare webhook PayPal con verifica firma;
- rendere idempotente accredito crediti su capture id;
- lasciare `/paypal/return` come UX, non come unica fonte contabile;
- monitorare ordini `pending` con riconciliazione.

## P2 - Medio/basso, ma utile per qualita operativa

### P2.1 Pagine pubbliche QR vino

File:

- `qrfacile_app/public.py`

La pagina pubblica mostra:

- dati vino/cantina;
- ingredienti;
- allergeni;
- nutrizione;
- riciclabilita;
- logo cantina;
- tracciamento scan deduplicato per giorno.

Buoni segnali:

- escaping tramite `ui.esc` in molte uscite;
- warning per testi sospetti;
- scan dedup senza salvare IP in chiaro, solo hash breve.

Da migliorare:

- gate bozza/pubblicato come P0;
- valutare cookie/privacy banner se vengono aggiunti tracking esterni;
- indicare chiaramente dati mancanti solo in preview privata, non su QR pubblico reale.

### P2.2 Compliance vino

File:

- `qrfacile_app/wine_compliance_ui.py`
- `qrfacile_app/validators.py`
- `qrfacile_app/publish_routes.py`

Sono presenti controlli minimi per ingredienti, allergeni, energia kJ/kcal, riciclo. La pubblicazione normale viene bloccata se mancano dati obbligatori; admin puo forzare.

Da completare prima del go-live normativo:

- revisione legale/regolatoria dei campi effettivamente obbligatori per mercati target;
- versionamento/snapshot della compliance pubblicata;
- audit trail per modifiche post-pubblicazione;
- disclaimer e responsabilita dati in Terms.

### P2.3 Upload logo/immagini vino

File:

- `qrfacile_app/media.py`
- `qrfacile_app/winery_logo_ui.py`
- `qrfacile_app/wine_images_ui.py`

Logo e immagini vino sono abbastanza hardenizzati: limiti, verifica immagine reale, ridimensionamento, rimozione metadata tramite risalvataggio. Restano da uniformare path, retention vecchi file e cleanup.

Azioni:

- cancellare vecchi logo non piu referenziati;
- separare upload privati/pubblici se in futuro ci sono asset non pubblici;
- servire upload dietro CDN o Nginx con MIME/headers corretti.

### P2.4 Deploy e osservabilita

Non ho trovato Dockerfile, compose, systemd, alembic o script migrazioni. La presenza di `.env` e `gunicorn.ctl` suggerisce deploy manuale.

Mancanze operative:

- migrazioni DB versionate;
- healthcheck;
- backup/restore DB e uploads;
- logging strutturato;
- error monitoring;
- policy retention logs/upload;
- CSP/security headers;
- HTTPS/HSTS a livello reverse proxy;
- test automatici minimi.

## Cosa manca per andare online e monetizzare

Checklist minima:

1. scegliere entrypoint unico e verificare tutte le route critiche;
2. sistemare gate pubblicazione QR: bozza non pubblica;
3. dichiarare tutte le dipendenze runtime;
4. consolidare auth e session expiry;
5. hardenizzare upload etichette legacy;
6. centralizzare prezzi/pack in `pricing_config.py`;
7. aggiungere webhook PayPal e riconciliazione ordini;
8. pulire deploy da backup/cache/venv/export;
9. configurare privacy/terms/cookie/contatti fiscali reali;
10. creare migrazioni DB e backup;
11. smoke test per registrazione, login, acquisto, credito, creazione QR, compliance, publish, pagina pubblica;
12. monitoraggio errori e log accessi pagamento.

## Priorita operative sintetiche

P0:

- entrypoint unico e route PayPal/Legal attive;
- QR bozza non accessibile su `/e/{slug}`;
- `requirements.txt` completo;
- upload etichetta legacy sicuro;
- PayPal usa prezzi da unica fonte.

P1:

- consolidare `auth.py`/`auth_core.py`;
- rimuovere route duplicate/dead code;
- ripulire backup/cache dal deploy;
- uniformare sistema crediti e wording;
- completare inviti con verifica email/rate limit;
- implementare webhook PayPal.

P2:

- revisione normativa compliance vino;
- cleanup vecchi upload;
- CDN/reverse proxy headers;
- migrazioni DB;
- test automatici e osservabilita.

## Note sui limiti dell'audit

- Non ho letto `.env` o `.env.save`.
- Non ho interrogato il database perche richiederebbe credenziali/config runtime.
- Non ho avviato server o test che modificano cache; un tentativo `python -m compileall` e fallito per binario `python` assente e non e stato rilanciato con `python3` per rispettare la modalita read-only.
- Le conclusioni derivano da analisi statica dei sorgenti e della struttura filesystem.
