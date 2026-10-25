# QRFACILE sell-ready audit — 25 ottobre 2026

## Scopo e confine

Audit del codice sul ramo isolato `codex/qrfacile-sell-ready`. Questo documento
non prova che le modifiche siano installate su staging o produzione. Non autorizza
push, deploy, PayPal Live, modifica di credenziali, merge o pubblicazione.

## Esito sintetico

QRFACILE ha una base tecnica utilizzabile, ma non è ancora corretto dichiararlo
commercialmente e legalmente "completo". La tranche locale chiude quattro difetti
misurabili, poi estese con il listino annuale e il rafforzamento degli accessi Studio:

1. rimuove fingerprint e conteggio delle scansioni dalle pagine e-label `/e/`;
2. registra accettazione dei Termini e presa visione Privacy con versione ed evidenza;
3. separa incassi PayPal Live, Sandbox, manuali e storici non classificati;
4. aggiunge metadati SEO, sitemap, robots e informazioni per crawler AI.
5. introduce pacchetti annuali Wine B2B con prezzi netti, IVA italiana esposta,
   condizioni ordine congelate e unità inutilizzate in scadenza senza alterare i QR;
6. richiede agli Studi sia il collegamento alla cantina sia l’assegnazione
   esplicita della singola etichetta sui percorsi operativi.
7. elimina le route duplicate di modifica/revoca dei collegamenti Studio: resta
   un solo percorso auditato, con verifica CSRF o origine e sincronizzazione delle etichette.
8. rende unico il salvataggio Compliance validato lato server e protegge con token
   CSRF i salvataggi, l'aggiunta di ingredienti/allergeni e la richiesta di override.
9. rimuove le route mutative legacy duplicate per assegnazione Studio e pubblicazione:
   i form inviano token CSRF e raggiungono soltanto i servizi canonici auditati.
10. applica il controllo CSRF/origine alle mutazioni amministrative ad alto impatto:
    crediti, payout, override, registro/revisione AI, incidenti e richieste privacy.
11. estende lo stesso controllo a tutte le route mutative autenticate rimanenti
    (creazione, upload, export/invio, selezione contesto, payout e accettazioni legali)
    e aggiunge un test che impedisce future route autenticate prive del gate.
12. richiede la verifica email ai nuovi account Cantina e Studio senza riclassificare
    gli account storici; invio iniziale e reinvio protetto sono presenti, ma SMTP va provato in staging.
13. applica anche lato server la scadenza delle sessioni dopo 14 giorni, inclusi
    i due schemi legacy supportati, senza affidarsi soltanto alla durata del cookie.

## Matrice di conformità

| Area | Stato dopo questa tranche | Evidenza / lavoro residuo |
|---|---|---|
| E-label vino | Codice corretto, non installato | `/e/` senza cookie, analytics, fingerprint, IP/user-agent o contatore; resta obbligatorio testare staging e produzione dopo un deploy autorizzato. |
| GDPR informativa e prova contrattuale | Parziale avanzato | Informativa aggiornata e accettazioni versionate; da formalizzare ruoli titolare/responsabile, registro art. 30, DPA sottoscritti e lista sub-responsabili. |
| Diritti interessati / incidenti | Presente nel codice, processo non provato | Workflow e tabelle esistono; servono responsabili, SLA, prova periodica ed evidenze organizzative. |
| Retention | Documentata, non certificata | Le durate proposte richiedono approvazione privacy/fiscale e prova del job in produzione. |
| Cookie/ePrivacy | Coerente con lo stato attuale | Le pagine pubbliche osservate non impostano cookie né caricano script. Nuovi analytics/pixel richiederanno nuova valutazione e, se applicabile, consenso. |
| AI Act | Framework presente, attivazione da governare | Registro sistemi AI, policy, revisione umana e divieto auto-publish per dati sensibili presenti; prima di attivare un provider servono scheda caso d'uso, DPA, trasferimenti, retention e formazione AI literacy. |
| Accessibilità | Parziale | Aggiunti nomi accessibili e autocomplete ai form di registrazione; manca un audit WCAG completo con tastiera, screen reader, contrasto, zoom e flussi autenticati in staging. |
| Sicurezza account | Parziale avanzato | Password reset, scadenza sessione server-side a 14 giorni e verifica dei nuovi account presenti; gli account storici sono preservati. Invio SMTP e recupero vanno provati in staging; MFA admin non risulta implementata. |
| Continuità | Evidenza staging esistente | Esistono runbook e restore staging; occorre prova periodica di restore del perimetro produttivo e owner operativo. |
| Pagamenti e fatture | Sandbox-ready nel codice, non pronto per Live | Il checkout annuale calcola imponibile, IVA ordinaria italiana e totale, congela condizioni e profilo fiscale nell'ordine e blocca prima di PayPal profili italiani incompleti o formalmente incoerenti. Verifica ufficiale P.IVA, documento fiscale, riconciliazione, rimborsi e casi fiscali non ordinari richiedono processo contabile e test end-to-end. |

## Requisiti prima di poter dire "vendibile"

- conferma contabile del flusso B2B Italia a prezzi IVA esclusa e procedura per casi fiscali speciali/esteri;
- processo di fatturazione/ricevuta e riconciliazione ordine-pagamento-documento fiscale;
- validazione legale finale di Termini, Privacy e DPA sui rapporti reali;
- MFA amministratori e piano coerente di verifica email;
- staging con migrazioni applicate, test end-to-end cantina/studio/admin e prova PayPal Sandbox;
- audit accessibilità dei flussi principali e correzione delle non conformità;
- backup/restore produttivo provato e monitoraggio disponibilità;
- autorizzazione separata per push, PR, deploy e ogni attivazione Live.

## Fonti normative primarie

- GDPR, Regolamento (UE) 2016/679: https://eur-lex.europa.eu/eli/reg/2016/679/oj
- Etichettatura vino, Q&A Commissione C/2023/1190: https://eur-lex.europa.eu/eli/C/2023/1190/oj/eng
- AI Act, Regolamento (UE) 2024/1689: https://eur-lex.europa.eu/eli/reg/2024/1689/oj
- European Accessibility Act, Direttiva (UE) 2019/882: https://eur-lex.europa.eu/eli/dir/2019/882/oj
- Linee guida cookie del Garante: https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/9677876

