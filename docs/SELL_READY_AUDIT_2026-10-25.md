# QRFACILE sell-ready audit — 25 ottobre 2026

## Scopo e confine

Audit del codice sul ramo isolato `codex/qrfacile-sell-ready`. Questo documento
non prova che le modifiche siano installate su staging o produzione. Non autorizza
push, deploy, PayPal Live, modifica di credenziali, merge o pubblicazione.

## Esito sintetico

QRFACILE ha una base tecnica utilizzabile, ma non è ancora corretto dichiararlo
commercialmente e legalmente "completo". La tranche locale chiude quattro difetti
misurabili:

1. rimuove fingerprint e conteggio delle scansioni dalle pagine e-label `/e/`;
2. registra accettazione dei Termini e presa visione Privacy con versione ed evidenza;
3. separa incassi PayPal Live, Sandbox, manuali e storici non classificati;
4. aggiunge metadati SEO, sitemap, robots e informazioni per crawler AI.

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
| Sicurezza account | Non completo | Password reset e sessioni presenti; MFA admin non risulta implementata. Verifica email non è applicata in modo uniforme e richiede piano di migrazione. |
| Continuità | Evidenza staging esistente | Esistono runbook e restore staging; occorre prova periodica di restore del perimetro produttivo e owner operativo. |
| Pagamenti e fatture | Non pronto per Live | Il codice distingue gli ambienti, ma PayPal Live, IVA, documento fiscale, riconciliazione e rimborsi richiedono decisione contabile e test end-to-end. |

## Requisiti prima di poter dire "vendibile"

- decisione scritta se i prezzi esposti sono IVA inclusa o esclusa e per quali paesi/clienti;
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

