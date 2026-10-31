# QRFacile — readback discoverability produzione 2026-10-30

Questa ricevuta descrive esclusivamente il runtime di produzione precedente al
release candidate. Non certifica SEO, indicizzazione o disponibilità futura.

## Identità della verifica

- Data e ora: 2026-10-30 16:06 Europe/Rome
- Origine: `https://www.qrfacile.it`
- Baseline produzione dichiarata: `de0a4f1d848e68b5ea4113b3b80d2fa94cc23ffd`
- Release candidate: non installato
- Operazione: richieste HTTP in sola lettura, senza autenticazione
- Runner: `scripts/check_public_discoverability.py` e `scripts/verify_release_health.py`

## Esito

Il controllo fail-closed non è superato sul runtime attualmente installato:

- `/` e `/pricing` rispondono HTTP 200, ma non espongono i metadati canonici,
  Open Graph, description e JSON-LD richiesti dal release candidate;
- `/robots.txt`, `/sitemap.xml`, `/llms.txt` e `/ai-policy` rispondono HTTP 404;
- le altre pagine pubbliche controllate non espongono ancora i metadati
  richiesti dal preflight.

Questo risultato è coerente con la baseline legacy e non costituisce una
regressione del release candidate, che non è stato distribuito. Dimostra però
che la produzione corrente non soddisfa ancora il gate di discoverability.

## Health readback

`https://www.qrfacile.it/healthz` restituisce HTTP 500 tramite Caddy/Uvicorn,
mentre `/` continua a restituire HTTP 200. Il runtime pubblico non espone quindi
il JSON fail-closed richiesto con stato, database, ambiente e SHA. La causa
interna non è stata inferita dal solo readback e non è stata eseguita alcuna
mutazione del runtime. Anche questo esito riguarda la baseline legacy e deve
essere risolto o sostituito dal candidato verificato prima del GO.

## Evidenza di chiusura richiesta

Dopo un eventuale deploy autorizzato dello SHA esatto, eseguire nuovamente:

```text
python scripts/check_public_discoverability.py --base-url https://www.qrfacile.it --timeout 15
```

Il gate si chiude soltanto con `PUBLIC_DISCOVERABILITY_OK`, readback dello SHA
installato e assenza di rollback o divergenze del runtime.

Il gate di health si chiude soltanto con HTTP 200 e:

```text
python scripts/verify_release_health.py --url https://www.qrfacile.it/healthz --expected-environment production --expected-release <SHA_INSTALLATO>
```
