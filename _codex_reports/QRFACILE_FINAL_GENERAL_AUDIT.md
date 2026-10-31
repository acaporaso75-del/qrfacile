# QRFACILE - Final General Audit

Data audit: 2026-05-19
Modalita: sola lettura sui file applicativi. Non e' stato letto `.env`. Unico file scritto: questo report.

## Executive Summary

La piattaforma e' vicina al varo, ma non e' ancora "DNS pubblico ready" senza almeno alcune chiusure P0/P1. Le route principali risultano incluse in `qrfacile_app/main.py`, i file target passano il controllo sintattico in memoria, i manuali PDF risultano presenti, e il flusso invito Cantina -> Studio e' stato irrigidito lato email.

Rischi principali:

- P0: link e navigazione verso `/studio/settings` senza route trovata nei moduli inclusi.
- P0: invito Studio -> Cantina tramite `/register-winery?invite=...` non verifica che l'email registrata corrisponda all'email invitata salvata in `studio_invites.studio_email`.
- P1: `qrfacile_app/db.py` fallisce all'import se `DATABASE_URL` non e' esportato nell'ambiente; `main.py` cattura e salta molti router, quindi un ambiente systemd configurato male puo' avviare un'app parziale invece di fallire chiaramente.
- P1: PayPal non verifica esplicitamente che il `token` di ritorno corrisponda a `orders.paypal_order_id` quando `order_id` e' presente.
- P1: preview tecnica `/preview/{slug}` richiede login ma non verifica ownership/ACL del singolo slug.

## Verifiche Eseguite

- Lettura route da `main.py` e `qrfacile_app/main.py`.
- Lettura mirata dei file richiesti.
- Controllo sintassi in memoria con `compile()` sui file target: OK.
- Import smoke con `venv/bin/python` e `PYTHONDONTWRITEBYTECODE=1`: fallisce per i moduli che importano `qrfacile_app.db` se `DATABASE_URL` non e' presente nell'ambiente del comando. Non e' stato letto `.env`.
- Verifica presenza manuali PDF: presenti in `static/manuali/`.

Nota operativa: un primo tentativo di scrittura del report e' fallito per collisione di delimitatore heredoc nel testo dei comandi consigliati; la shell ha interpretato alcune righe del blocco come comandi. Non sono stati modificati file applicativi.

## Route E Inclusione In Main

`main.py` root e' solo wrapper legacy verso `qrfacile_app.main:app`.

`qrfacile_app/main.py` include i router core richiesti:

- `auth_routes`, `landing_routes`, `pricing_ui`, `legal_pages`, `guide_pages`
- `dashboard_ui`, `billing_ui`, `paypal_ui`, `premium_ui`
- strumenti label e wine
- `studio_area`, `studio_home_ui`, `studio_settings_ui`, `studio_register_routes`
- `winery_register_routes`, `winery_settings_ui`
- admin, public, publish, uploads, export, search, bulk, wine master, legacy

Osservazioni:

- `include_router_safe()` cattura ogni eccezione di import e prosegue. Questo evita crash, ma puo' nascondere router mancanti in produzione.
- `studio_settings_ui.py` e `winery_settings_ui.py` definiscono entrambi `GET /app/settings/studios`. L'ordine di include mette prima `studio_settings_ui`, quindi dovrebbe vincere il redirect piu' completo con `msg`/`err`. Rimane fragile e va documentato.
- Link trovati a `/studio/settings` in `ui_shell.py`, `dashboard_ui.py`, `studio_area.py`, ma non e' stata trovata route `@router.get('/studio/settings')`. Questo e' P0 se il profilo studio e' raggiungibile da menu.

## Runtime Probabile

Sintassi:

- Tutti i file target passano `compile(source, file, 'exec')`.

Import runtime:

- Con Python di sistema: mancano dipendenze (`fastapi`, `PIL`). Atteso fuori venv.
- Con `venv/bin/python`: i moduli che importano `qrfacile_app.db` falliscono se `DATABASE_URL` non e' esportato. `db.py` legge solo `os.getenv('DATABASE_URL')` e solleva `RuntimeError`.

Impatto:

- Se systemd non esporta `DATABASE_URL`, `qrfacile_app/main.py` puo' partire con molte route saltate e solo alcune pagine pubbliche/statiche disponibili.
- Prima del DNS pubblico serve uno smoke test del processo reale, non solo import da shell.

## GET/POST E CTA

Criticita rilevate:

- `/studio/settings` linkato ma route non trovata.
- `dashboard_ui.py` mostra a utenti studio CTA testuale "Pubblica pagina ufficiale" ma la indirizza a export, perche' gli studi non possono pubblicare. Testo potenzialmente contraddittorio: meglio "Vai a export / richiedi pubblicazione".
- `billing_ui.py` ha endpoint `/app/billing/request-plan`, ma le card usano direttamente `/paypal/start`; non e' un bug, ma la route request-plan sembra secondaria/legacy.
- In `guide_pages.py` i link PDF sono diretti e i file esistono.

## Permessi Winery / Studio / Admin

Schema generale:

- `auth_core.require_any_role()` centralizza ruolo e permessi studio su `studio_clients` quando viene passato `winery_id`.
- `premium_ui.new_wine_post()` richiama `require_any_role(..., winery_id, need='create')`; quindi gli studi possono creare solo se autorizzati.
- `publish_routes._can_publish()` blocca sempre gli studi: solo cantina owner e admin con cantina attiva possono pubblicare/unpublish.
- Admin richiede `admin_active_winery_id` per molte operazioni operative, coerente.

Rischi:

- Molti controlli dipendono dal passaggio esplicito di `winery_id` a `require_any_role`; dove manca, il controllo deve essere locale. Nei file letti i punti principali sembrano coperti.
- `public.preview` richiede solo ruolo valido, non verifica ownership/ACL del singolo slug. Qualunque utente loggato winery/studio/admin potrebbe aprire `/preview/{slug}` se conosce lo slug. Per pre-DNS e clienti reali e' P1/P2 a seconda della sensibilita'.

## Inviti Cantina -> Studio

Stato corrente:

- `studio_settings_ui.py` crea invito con `studio_email` normalizzata.
- `GET /app/invite/studio/accept/{token}` mostra pagina pubblica se non loggato.
- Se loggato come studio/admin, accetta automaticamente.
- `_studio_invite_email_error()` impone email login uguale a `studio_invites.studio_email`, salvo admin.
- POST accept applica lo stesso controllo prima di `_accept_studio_invite_row()`.
- `register-studio` verifica `_studio_invite_error(inv, email)` prima di creare utente e prima di accettare invito.

Esito: la regressione segnalata `acaporaso75@gmail.com` -> `enolab@pcert.it` e' coperta nel flusso Studio se il codice corrente e' quello letto.

## Inviti Studio -> Cantina

P0 rilevato:

- `studio_area.py` usa `studio_invites.studio_email` per salvare l'email cantina invitata.
- `winery_register_routes.py` mostra "Email cantina invitata", ma `register_winery_post()` non confronta `email` con `inv['studio_email']`.
- Se il token viene inoltrato o aperto da un'altra email, puo' creare una cantina diversa e collegarla allo studio, marcando l'invito usato.

Correzione raccomandata:

- In `register_winery_post()`, prima di creare `users/wineries`, applicare la stessa regola strict: email registrazione uguale a `studio_invites.studio_email`.
- Messaggio: "Questo invito e' destinato a [email]. Stai usando [email]. Registrati con l'email corretta o chiedi un nuovo invito."

## Pubblicazione / Preview / Pagina Pubblica

Stato:

- Pubblicazione imposta `qr_items.status='attiva'` e `wine_labels.public_enabled=TRUE`.
- Pagina pubblica `/e/{slug}` richiede `status == 'attiva'` e blocca QR incompleti.
- Preview `/preview/{slug}` richiede login e mostra draft/incomplete con watermark.
- Pubblicazione normale blocca dati obbligatori mancanti; force solo admin.

Rischi:

- Preview non verifica ownership del slug, solo login. Da correggere se preview contiene dati cliente non ancora pubblici.
- `public.py` renderizza la pagina pubblica da `qr_items`/`qr_wines` e non sembra usare `wine_labels.public_enabled` per decidere visibilita'. La pubblicazione aggiorna entrambe le cose, ma la fonte effettiva e' `qr_items.status`. Coerente se ogni QR vino ha pagina unica; da documentare.

## QR Attivi Incompleti

Stato:

- `publish_routes._publication_missing_fields()` controlla ingredienti, allergeni, energia kJ/kcal, riciclabilita'.
- `public.py` ricontrolla incompletezza e fa 404 se pubblico non preview.
- Dashboard mostra semaforo compliance.

Rischi:

- Admin puo' forzare pubblicazione con dati incompleti. La pagina pubblica poi fa comunque 404 se incompleta, perche' `public.py` blocca `is_incomplete` anche se `status='attiva'`. Quindi il force publish admin potrebbe risultare "pubblicato" nel backoffice ma non visibile pubblicamente. Questo e' P1: decidere se force deve bypassare anche public incomplete oppure se non deve esistere.

## Manuali PDF E /guide

Stato:

- `/guide` incluso in `main.py`.
- File presenti:
  - `static/manuali/manuale_cantina.pdf`
  - `static/manuali/manuale_studio.pdf`
  - `static/manuali/manuale_qr_stampa.pdf`

Esito: OK.

## PayPal / Pricing / Billing

Stato:

- `pricing_config.py` e' fonte unica per QR packs e assisted services.
- `billing_ui.py` usa `list_billing_packs()` e invia a `/paypal/start`.
- `paypal_ui.py` crea ordine DB pending, crea ordine PayPal, poi cattura su `/paypal/return`.
- Crediti wine/generic vengono caricati da `get_purchase_pack()`.

Rischi:

- P1: `paypal_return(order_id, token)` cerca ordine per `id` e `user_id`, ma non verifica prima della capture che `orders.paypal_order_id == token`. Un utente autenticato non dovrebbe poter pagare ordine altrui per via di `user_id`, ma puo' esserci mismatch fra token PayPal e order_id dello stesso utente. Verificare e bloccare mismatch.
- P1: assenza apparente di webhook PayPal. Se l'utente paga ma non torna alla return, i crediti potrebbero non caricarsi.
- P2: `/paypal/debug` admin-only, OK, ma prima del DNS pubblico valutare di disabilitarla o limitarla a staging/IP.
- Import PayPal legge env vars ma non `.env` autonomamente; dipende dall'ambiente processo.

## Sicurezza

P0/P1:

- `/studio/settings` mancante puo' causare 404 da navigazione principale.
- Invito Studio -> Cantina non strict su email.
- Preview slug accessibile a qualsiasi utente loggato.
- `include_router_safe()` puo' mascherare errori di import e lasciare app parziale.
- Nessuna protezione CSRF visibile sui form POST. Se il sito sara' pubblico con session cookie, valutare token CSRF almeno per billing, publish, revoke, invite.

P2:

- Cookie sessione: `httponly`, `samesite=lax`, ma non `secure`. Dietro HTTPS pubblico conviene `secure=True` condizionato ad ambiente.
- Sessioni non verificano scadenza in `auth_core._session_user_id()`; `SESSION_MAX_AGE_SECONDS` e' solo cookie max-age. Se cookie resta o token rubato, DB session non scade lato server.

## Regressioni Da Ultimi Refactor

- `studio_settings_ui.py` corrente contiene gia' strict email per invito Studio: bene.
- `winery_settings_ui.py` corrente va ricontrollato rispetto al candidato UX2: se non applicato, gli inviti pendenti potrebbero non avere copia/apri link e potrebbe comparire copy contraddittoria.
- Il candidate UX2 non aggiunge annulla/reinvia perche' non sono state trovate route sicure esistenti: scelta corretta.

## Testi E CTA Contraddittorie

- Dashboard per studio: CTA "Pubblica pagina ufficiale" porta a export, perche' lo studio non puo' pubblicare. Cambiare testo.
- `winery_register_routes.py` invito Studio rilevato mostra permessi come `view/edit/create`, mentre UI italiana usa "vista/modifica/creazione". P2.
- Alcuni testi usano inglesismi tecnici (`generic`, `wine credits`, `workspace`) accettabili per backoffice ma da ripulire prima del pubblico se il target e' non tecnico.

## Prima Del DNS Pubblico

P0 da chiudere:

1. Definire o correggere route `/studio/settings`.
2. Rendere strict email anche per inviti Studio -> Cantina in `register_winery_post()`.
3. Smoke test reale con stesso environment di systemd: tutti i router devono caricarsi; se `DATABASE_URL` manca il servizio non deve andare online parziale.

P1 da chiudere:

1. Decidere comportamento force publish admin vs blocco public incompleto.
2. Limitare preview per ownership/ACL o accettarne il rischio.
3. Verificare PayPal return `token == orders.paypal_order_id` e pianificare webhook o reconciliation ordini pending.
4. Applicare UX2 a `winery_settings_ui.py` se non gia' fatto, per chiarezza inviti pendenti.

P2:

1. Migliorare microcopy inglese/tecnica.
2. Valutare `Secure` sui cookie in produzione HTTPS.
3. Valutare CSRF sui POST sensibili.

## Smoke Test Consigliati

Eseguire dal server con lo stesso utente/env del servizio, senza stampare segreti.

Route smoke:

```bash
cd /opt/qrfacile
PYTHONDONTWRITEBYTECODE=1 venv/bin/python -c "from qrfacile_app.main import app; routes=sorted({getattr(r,'path','') for r in app.routes}); wanted=['/login','/app/dashboard','/app/winery/settings','/app/settings/studios','/app/invite/studio/accept/{token}','/register-studio','/register-winery','/studio','/studio/settings','/guide','/legal','/pricing','/paypal/start','/paypal/return','/e/{slug}','/preview/{slug}']; [print(p, 'OK' if p in routes else 'MISSING') for p in wanted]; print('route_count', len(routes))"
```

Sintassi in memoria:

```bash
cd /opt/qrfacile
PYTHONDONTWRITEBYTECODE=1 venv/bin/python -c "from pathlib import Path; files=['qrfacile_app/main.py','qrfacile_app/public.py','qrfacile_app/dashboard_ui.py','qrfacile_app/premium_ui.py','qrfacile_app/winery_settings_ui.py','qrfacile_app/studio_settings_ui.py','qrfacile_app/studio_register_routes.py','qrfacile_app/winery_register_routes.py','qrfacile_app/studio_area.py','qrfacile_app/guide_pages.py','qrfacile_app/legal_pages.py','qrfacile_app/pricing_config.py','qrfacile_app/billing_ui.py','qrfacile_app/paypal_ui.py','qrfacile_app/publish_routes.py','qrfacile_app/auth_core.py','qrfacile_app/auth_routes.py']; [compile(Path(f).read_text(), f, 'exec') or print('syntax OK', f) for f in files]"
```

Manuali/static:

```bash
cd /opt/qrfacile
test -f static/manuali/manuale_cantina.pdf
test -f static/manuali/manuale_studio.pdf
test -f static/manuali/manuale_qr_stampa.pdf
test -f static/app.css
```

HTTP smoke locale, con servizio avviato:

```bash
curl -I http://127.0.0.1:8000/
curl -I http://127.0.0.1:8000/pricing
curl -I http://127.0.0.1:8000/guide
curl -I http://127.0.0.1:8000/legal
curl -I http://127.0.0.1:8000/login
curl -I http://127.0.0.1:8000/register-studio
curl -I http://127.0.0.1:8000/register-winery
```

DB consistency smoke da eseguire con psql/strumento interno, senza stampare dati sensibili:

```sql
SELECT si.id, si.studio_email, si.used_by_user_id, sc.studio_user_id
FROM studio_invites si
LEFT JOIN studio_clients sc ON sc.studio_user_id = si.used_by_user_id AND sc.winery_id = si.winery_id
WHERE si.used_at IS NOT NULL AND si.inviter_user_id IS NOT NULL AND sc.studio_user_id IS NULL
LIMIT 20;

SELECT qi.id, qi.slug, qw.id AS wine_id
FROM qr_items qi
JOIN qr_wines qw ON qw.qr_item_id = qi.id
WHERE qi.status='attiva'
LIMIT 50;
```

## Priorita Finale

### P0

- Route `/studio/settings` mancante o link errati.
- Strict email mancante in `register_winery_post()` per inviti Studio -> Cantina.
- Smoke reale systemd: tutti i router devono caricarsi; se `DATABASE_URL` manca il servizio non deve andare online parziale.

### P1

- Preview slug non limitata a owner/ACL.
- Force publish admin incoerente con public gate incompleto.
- PayPal return deve verificare token/order id e serve piano webhook/reconciliation.
- UX inviti pendenti cantina da applicare/verificare.

### P2

- Hardening cookie `Secure`, CSRF, scadenza server-side sessioni.
- Microcopy tecnico/inglese.
- Disabilitare o limitare `/paypal/debug` in produzione.
