# QRFACILE Product & UX Audit

Data: 2026-05-16  
Modalita: analisi prudente, statica, senza lettura/stampa di `.env` o `.env.*`.  
Scritture effettuate: solo questo report.

## Executive summary

QRFACILE ha gia una base prodotto reale: ruoli Cantina/Studio/Admin, QR vino dinamici, compliance, pagine pubbliche, export tipografico, crediti, PayPal, inviti studio e una logica di pubblicazione con blocco dei dati obbligatori. Non sembra un prototipo vuoto.

La valutazione prudente, pero, e che oggi non appare ancora un riferimento premium/enterprise del settore. Il prodotto e funzionalmente interessante, ma l'esperienza e costruita in modo molto artigianale: HTML inline diffuso, copy non sempre coerente, multilingua non strutturato, assenza evidente di test, assistenza non ancora trattata come servizio enterprise, fiducia commerciale incompleta e componenti legacy ancora presenti.

## Voti

| Area | Voto | Motivazione sintetica |
|---|---:|---|
| Estetica | 6.5/10 | UI moderna, luminosa e leggibile; pero molte card, emoji, inline style, gerarchia non sempre premium, look piu "SaaS artigianale" che enterprise. |
| Funzionale | 7/10 | Dashboard, compliance, export QR, inviti studio, billing e admin esistono davvero. Mancano rifinitura flussi, i18n reale, onboarding guidato e maggiore coerenza. |
| Commerciale/monetizzazione | 6.5/10 | Pricing a crediti chiaro e PayPal integrato; mancano trust proof, contratti, SLA, fatturazione/IVA esplicita, canale enterprise, trial/onboarding piu guidato. |
| Affidabilita / production readiness | 5/10 | Buone intenzioni su ACL, pubblicazione e upload in alcune aree; ma niente test evidenti, dipendenze duplicate, DB diretto, molti moduli legacy/backup, errori runtime possibili. |

## Puo sembrare un riferimento del settore?

Non ancora. Puo sembrare un prodotto verticale promettente per cantine e studi grafici, ma non ancora il riferimento del settore.

I punti forti sono:

- focus verticale molto chiaro su vino, QR normativi, lotti, etichette e tipografie;
- export tipografico con PNG/SVG/PDF/ZIP, molto rilevante per studi grafici;
- collaborazione Studio-Cantina con inviti e permessi;
- pagina pubblica QR senza pubblicita, aspetto fondamentale per contenuto normativo;
- modello a crediti comprensibile: 1 credito 10 anni, 2 crediti 25 anni.

I punti che abbassano la percezione sono:

- interfaccia non ancora abbastanza sobria e istituzionale per enterprise;
- molte microcopy tecniche: "wine", "generic", "slug", "view/edit/create", "lang";
- multilingua quasi solo come campo dati, non come esperienza;
- assenza di prove pubbliche di affidabilita: SLA, backup policy dettagliata, uptime, audit, sicurezza, DPA, privacy operativa;
- pagine pubbliche QR belle ma ancora in italiano e con warning tecnici visibili se incompleta;
- pricing credibile ma non ancora confezionato per studi, consorzi, gruppi, tipografie e grandi cantine.

## Cosa manca per apparire premium/enterprise

1. Un design system coerente: componenti riusabili, meno inline style, meno emoji nei punti istituzionali, stati chiari, tabelle e form piu densi dove serve.
2. Onboarding guidato per cantine non tecniche: checklist "1. crea lotto, 2. completa obblighi, 3. verifica pagina, 4. esporta QR, 5. pubblica".
3. Area Studio piu commerciale: kit cliente, link invito brandizzato, proposta piano, stato onboarding cantina, materiali per vendere QRFACILE al cliente.
4. Fiducia commerciale: pagina sicurezza, SLA, retention, backup, responsabilita normativa, DPA/GDPR, supporto, canali di contatto, ragione sociale sempre visibile.
5. Multilingua vero: contenuti pubblici, UI, campi normativi, export e metadati tradotti con fallback controllati.
6. Processo enterprise: preventivi, fatturazione, team/utenti, audit log visibile, ruoli granulari, assistenza prioritaria, import massivo, account manager.
7. Qualita operativa: test automatici, smoke test route, migrazioni DB, logging strutturato, monitoraggio errori, backup verificati, ambiente staging.

## Dashboard Cantina

La dashboard in `qrfacile_app/dashboard_ui.py` e una delle parti piu forti: mostra lotti, fronte/retro, stato, slug, lotto, compliance e azioni rapide. Il semaforo "Compliance OK / Quasi completo / Da completare" e utile per una cantina non tecnica.

Problemi UX:

- usa termini tecnici come "slug", "wine", "generic";
- su mobile la sidebar diventa un blocco lungo prima del contenuto operativo;
- le card sono ricche ma possono diventare alte e ripetitive;
- manca una checklist di onboarding persistente per il primo lotto;
- non e chiarissimo cosa sia obbligatorio per normativa e cosa sia opzionale/marketing.

Valutazione: buona base SaaS verticale, ma va resa piu guidata e meno tecnica.

## Area Studio

`qrfacile_app/studio_area.py` ha un flusso concreto: inviti, permessi, email, copia link, piani consigliati, elenco cantine, accesso operativo, etichette e payout/bonus in moduli dedicati.

Punti forti:

- risolve un caso reale degli studi grafici: collegare la cantina e lavorare sui QR;
- link invito copiabile e testo manuale pronto;
- piano consigliato dallo Studio, utile per monetizzazione indiretta;
- permessi separati view/edit/create.

Debolezze:

- l'appeal per studi grafici e ancora funzionale, non aspirazionale/professionale;
- manca un "workspace cliente" con stato avanzamento, consegne, export recenti, file inviati;
- copy e permessi usano parole da database;
- commissioni/bonus devono essere spiegati meglio in chiave partner program;
- mancano materiali commerciali scaricabili o pagina "Partner per studi grafici".

Valutazione: molto interessante per il posizionamento, da trasformare in vero programma partner.

## Admin

`qrfacile_app/admin_home_ui.py` offre KPI, ricerca cantine, contesto attivo e navigazione verso scheda cliente, dashboard filtrata, payout e override. E adeguato per una fase iniziale.

Limiti:

- KPI essenziali ma non ancora da business console;
- mancano funnel, MRR/ricavi per periodo, conversioni, ordini falliti, ticket, scansioni aggregate;
- gestione cliente ancora operativa, non CRM;
- non emerge un audit trail amministrativo leggibile;
- alcune route admin/legacy risultano molteplici o residue.

Valutazione: sufficiente per gestione interna iniziale, non enterprise console.

## Billing e monetizzazione

`pricing_config.py`, `billing_ui.py`, `pricing_ui.py` e `paypal_ui.py` indicano un modello commerciale chiaro:

- registrazione cantina: 3 crediti wine gratuiti;
- pacchetti Start 29 EUR / Cantina 79 EUR / Business 199 EUR;
- 1 credito = QR vino 10 anni;
- 2 crediti = QR vino 25 anni;
- assistenza opzionale;
- PayPal carica crediti dopo capture.

Punti forti:

- no abbonamento obbligatorio: messaggio semplice per PMI;
- durata 10/25 anni e adatta al problema della bottiglia stampata;
- pricing a crediti comprensibile;
- servizi assistiti aprono margine.

Punti deboli:

- manca chiarezza su IVA/fattura;
- manca piano enterprise/consorzio/tipografia;
- mancano garanzie su conservazione pagina, dominio, continuita, SLA;
- "Assistenza" e presente ma non ha flusso commerciale forte;
- il pricing pubblico non segmenta abbastanza Cantina, Studio, Grande cantina.

Valutazione: monetizzazione valida, ma confezionamento commerciale ancora medio.

## Pagine pubbliche QR

`qrfacile_app/public.py` genera pagine pulite, responsive, senza pubblicita e con temi minimal/classic/modern. Questo e corretto per la conformita: la pagina normativa non deve sembrare una landing promozionale.

Punti positivi:

- niente advertising;
- `meta robots noindex,nofollow`;
- sezioni ingredienti, allergeni, nutrizione, riciclo;
- logo cantina opzionale;
- warning su dati sospetti e incompleti;
- tracking scansioni deduplicato giornaliero.

Rischi/limiti:

- hardcoded in italiano;
- `html lang="it"` fisso;
- testi normativi, label nutrizionali e riciclo non sono localizzati;
- se incompleta, la pagina mostra watermark/warning tecnico: utile per verifica, non adatto al pubblico finale;
- manca una modalita preview separata da pagina pubblica definitiva;
- i temi sono gradevoli ma non abbastanza brandizzabili per cantine premium.

Valutazione: concetto corretto, serve i18n e separazione netta tra preview tecnica e pagina pubblica.

## Multilingua

Il multilingua non risulta davvero implementato come prodotto. Risulta parziale.

Evidenze:

- molti documenti HTML hanno `lang="it"` fisso;
- `public.py` usa `Accept-Language` solo nel fingerprint scansioni, non per tradurre;
- `premium_ui.py` permette di scegliere `language` per etichette: it/en/de/fr/es;
- moduli come `label_hub_ui.py`, `studio_area.py`, `send_print.py`, `labels_search.py` leggono o mostrano `wl.language`;
- non emerge un dizionario i18n, middleware locale, route `/en`, parametro `?lang=`, fallback traduzioni o traduzione dei master data;
- le pagine QR pubbliche mostrano label e testi in italiano.

Conclusione: oggi la lingua e soprattutto un metadato dell'etichetta premium, non un'esperienza multilingua completa.

Parti da tradurre o rendere dinamiche:

- pagina pubblica `/e/{slug}`: ingredienti, allergeni, nutrizione, riciclo, warning, status, meta labels;
- shell app: menu, sidebar, pulsanti, errori, note;
- onboarding e registrazione cantina/studio;
- dashboard cantina e studio;
- pricing pubblico e billing;
- email invito studio-cantina;
- export e filename/cover PDF dove contiene testo;
- legal/privacy/cookie/terms se si vendono fuori Italia;
- master data ingredienti/allergeni/materiali, con traduzioni per IT/EN e struttura estendibile FR/DE/ES.

Approccio consigliato:

- introdurre `locales/it.json`, `locales/en.json`, poi FR/DE/ES;
- salvare lingua preferita su cantina/QR/label;
- usare fallback IT se manca traduzione;
- per la pagina QR pubblica consentire `?lang=en` e/o auto-detect con selettore visibile;
- distinguere lingua UI interna da lingua normativa pubblica.

## UX mobile

La CSS ha breakpoint e le griglie collassano correttamente. Tuttavia:

- sidebar e topbar occupano molto spazio prima del contenuto;
- molti pulsanti diventano full-width, bene per tap, ma creano pagine lunghe;
- tabelle admin/studio/billing sono scrollabili ma non sempre ottimali per mobile;
- form lunghi di registrazione e compliance sono pesanti su telefono;
- card e ombre ampie riducono densita informativa.

Per cantine non tecniche il mobile dovrebbe diventare "task-first": cosa manca, cosa devo premere, posso pubblicare, posso inviare allo studio. Meno dashboard generica, piu percorso guidato.

## Qualita visiva

La qualita visiva e superiore a una UI grezza: palette chiara, gradienti morbidi, card, gerarchie, CTA e responsive. Pero l'effetto complessivo e molto "costruito velocemente in HTML inline".

Per apparire premium:

- ridurre emoji in navigazione istituzionale;
- usare icone coerenti;
- rendere typography meno aggressiva;
- uniformare radius/spaziature;
- evitare card dentro card dove non serve;
- trasformare i form lunghi in wizard;
- dare alle pagine pubbliche QR uno stile piu sobrio, quasi documentale.

## Affidabilita e production readiness

Punti buoni:

- password hashate con `passlib`;
- sessioni server-side;
- ACL per ruoli in molte route;
- pubblicazione bloccata se mancano dati obbligatori;
- PayPal con capture e lock ordine;
- upload immagini vino in alcune pipeline con controlli;
- export QR in formati professionali;
- niente `.env` letto in questa analisi.

Rischi:

- nessun test automatico rilevato;
- `requirements.txt` contiene duplicati;
- connessione DB diretta senza pool;
- molti moduli backup/legacy nella root applicativa;
- HTML/CSS inline rende fragile la manutenzione;
- error handling spesso via redirect stringhe percent-encoded manualmente;
- i18n assente;
- migrazioni DB non evidenti;
- osservabilita, audit commerciale e monitoring non evidenti.

## Priorita per varo commerciale

### P0 - Prima del lancio pagato

- Bloccare definitivamente pagina pubblica se QR non pubblicato o dati obbligatori mancanti; preview separata dalla pagina pubblica reale.
- Implementare i18n minimo IT/EN per pagina QR pubblica, con struttura pronta per FR/DE/ES.
- Rendere dinamiche tutte le label normative pubbliche: ingredienti, allergeni, nutrizione, riciclo, status, warning.
- Smoke test route critiche: `/`, `/login`, `/register-winery`, `/register-studio`, `/pricing`, `/app/dashboard`, `/app/billing`, `/paypal/start`, `/e/{slug}`.
- Consolidare entrypoint e route legacy, evitando moduli duplicati in produzione.
- Verificare PayPal live/sandbox, ordini, crediti, idempotenza e fallback errore.
- Aggiungere privacy/terms/cookie/DPA coerenti con vendita SaaS e QR normativi.
- Ripulire deploy da backup, cache, venv, file `.save`, moduli obsoleti.

### P1 - Per sembrare premium e scalare

- Design system applicativo con componenti condivisi e meno HTML inline.
- Onboarding guidato per cantina: checklist primo QR e stato pronto/non pronto.
- Area Studio partner: pipeline clienti, inviti, materiali commerciali, stato cantina, export recenti.
- Pricing segmentato: Cantina, Studio, Business/Enterprise, Import massivo, Assistenza.
- Supporto commerciale visibile: email, tempi risposta, assistenza premium, onboarding assistito.
- Dashboard admin con funnel, scansioni, ricavi, ordini falliti, clienti attivi, alert compliance.
- Traduzione UI interna principale IT/EN: dashboard, billing, studio, registrazione, email.
- Brandizzazione pagina QR: logo, tema sobrio, colori limitati, nessuna pubblicita.

### P2 - Dopo lancio iniziale

- FR/DE/ES completi per pagina QR e master data.
- Import massivo CSV/XLSX per cantine grandi e studi.
- Team multiutente per cantina e studio.
- Audit log visibile a clienti enterprise.
- Webhook/email notifiche: dati mancanti, QR pubblicato, export inviato, pagamento riuscito.
- Analytics scansioni per cantina/studio con privacy by design.
- Integrazione fatturazione elettronica/gestionale.
- Template white-label o co-branding per studi grafici selezionati.

## Giudizio finale

QRFACILE ha una direzione di prodotto corretta e un vantaggio verticale: parla davvero di vino, lotti, QR normativi, studi grafici e tipografia. Questo e piu forte di un generico generatore QR.

Per il varo commerciale, la priorita non e aggiungere molte feature nuove. La priorita e rendere affidabile, coerente e premium cio che esiste: pagina pubblica conforme e multilingua, onboarding cantina piu guidato, area studio piu partner-oriented, pricing piu fiducioso, e una base tecnica piu testata e ripulita.
