# QRFacile — pacchetto approvazioni produzione

Release candidate: `0afb234327b66ad3a91e47402c9ba26a88f0aede`
PR: `#12`, Draft verso `main`
Data preparazione: 2026-10-29

Questo documento raccoglie decisioni esterne necessarie prima di rendere la PR Ready. Non inserire password, credenziali PayPal, chiavi, token o dati personali dei clienti.

## 1. Offerta commerciale da approvare

| Pacchetto | Unità Wine | Prezzo netto | IVA 22% | Totale Italia ordinario |
| --- | ---: | ---: | ---: | ---: |
| Start | 15 | €99,00 | €21,78 | €120,78 |
| Cantina | 50 | €179,00 | €39,38 | €218,38 |
| Business | 100 | €299,00 | €65,78 | €364,78 |

Condizioni implementate:

- prezzi esposti come netti con dicitura esplicita `+ IVA 22%`;
- vendita self-service limitata alle cantine italiane con profilo fiscale completo;
- unità acquistate valide 12 mesi, con rinnovo manuale e nessun addebito automatico;
- 1 unità per creare un QR Wine con durata 10 anni;
- 2 unità per creare un QR Wine con durata 25 anni;
- QR già creati e pubblicati non vengono disattivati alla scadenza delle unità residue;
- un lotto o vino differente richiede un QR distinto;
- Studio, multi-cantina, volumi elevati e casi fiscali non ordinari sono gestiti su preventivo.

Formulazione commerciale proposta:

> Acquisti un pacchetto annuale di unità Wine. Ogni QR creato resta attivo per 10 o 25 anni, senza un canone annuale sul singolo QR. Il QR identifica una specifica referenza o lotto e non deve essere riutilizzato per vini diversi.

Non pubblicare senza evidenza aggiornata affermazioni assolute quali “il servizio più economico esistente”. La formulazione “una delle offerte più competitive” richiede comunque data, campione e fonti del confronto.

### Approvazione commerciale

- Decisione: [x] APPROVATO  [ ] APPROVATO CON CONDIZIONI  [ ] RESPINTO
- Nome e cognome: Angelo Caporaso
- Ruolo: CEO
- Organizzazione: Enolab
- Data e fuso orario: 2026-10-30, Europe/Rome
- Perimetro approvato: offerta Wine B2B, pacchetti annuali, prezzi netti con dicitura esplicita `+ IVA 22%` e opzione QR 25 anni sul release candidate indicato
- Claim commerciali autorizzati: formulazione commerciale proposta nel presente documento; esclusi claim assoluti sul primato di prezzo
- Condizioni o modifiche richieste: nessuna
- Riferimento documento/e-mail/verbale: autorizzazioni esplicite nella chat QRFacile del 2026-10-30, inclusa la richiesta di mostrare `+ IVA 22%` nelle offerte
- Firma o evidenza equivalente: dichiarazione diretta di Angelo Caporaso nella chat QRFacile

## 2. Approvazione contabile e fiscale

Il professionista deve confermare almeno:

- correttezza dei prezzi IVA esclusa e dell’IVA ordinaria italiana al 22%;
- dati obbligatori del profilo fiscale cantina;
- documento fiscale da emettere e momento di esigibilità;
- gestione SDI/PEC e riconciliazione con PayPal;
- procedura per annullamento, rimborso totale/parziale e chargeback;
- gestione di ordini falliti, pendenti, duplicati o riconciliati manualmente;
- trattamento di clienti esteri, esenti, reverse charge o altri casi non ordinari;
- conservazione di ordini, snapshot fiscali e prove di pagamento;
- separazione nei report tra Live, Sandbox, manuale e storico non classificato.

### Approvazione contabile

Parere aziendale del CEO, non professionale e senza attribuzione di qualifica
contabile o iscrizione a un Albo.

- Decisione: [ ] APPROVATO  [x] APPROVATO CON CONDIZIONI  [ ] RESPINTO
- Nome e cognome: Angelo Caporaso
- Qualifica/Albo: CEO Enolab S.r.l.; parere aziendale non professionale; nessun Albo dichiarato
- Studio: Enolab S.r.l.
- Data e fuso orario: 2026-11-21, Europe/Rome
- Paesi e regimi fiscali autorizzati al self-service: Italia, regime IVA ordinario, clienti B2B con P.IVA; esteri, esenti e reverse charge solo su preventivo
- Processo di fatturazione approvato: fattura elettronica emessa internamente con Danea Easyfatt; per ogni ordine pagato QRFacile invia una mail a fatturazione tramite `QRFACILE_INVOICE_TO`, con copia tramite `QRFACILE_INVOICE_CC`, contenente i dati e il file Easyfatt-Xml, rintracciabile in `/admin/invoices`
- Processo di riconciliazione/rimborso approvato: riconciliazione su PayPal e `/admin/invoices`; rimborsi e chargeback gestiti da Angelo Caporaso, sostituto Luigi, secondo `PAYMENT_REFUND_DISPUTE_RUNBOOK_2026-10-29.md`, con nota di credito in Danea
- Condizioni o modifiche richieste: chiusura del test Danea end-to-end registrato in `DANEA_HANDOFF_ACCEPTANCE_2026-11-21.md`
- Riferimento parere/verbale: decisione del titolare nella chat QRFacile del 2026-11-21
- Firma o evidenza equivalente: dichiarazione diretta di Angelo Caporaso nella chat QRFacile del 2026-11-21

## 3. Approvazione legale, privacy e AI

Il legale/DPO deve esaminare almeno:

- Termini versione `2026-10-29` e formulazione della durata QR;
- informativa Privacy versione `2026-10-25`;
- DPA e ruoli titolare/responsabile nei rapporti con cantine e Studio;
- cookie/ePrivacy del sito, delle aree autenticate e delle pagine QR pubbliche;
- basi giuridiche, finalità, categorie dati, destinatari e trasferimenti;
- retention, cancellazione, esportazione e gestione backup;
- procedura diritti interessati e relativi SLA;
- incident response e notifica data breach;
- registro sistemi AI, human review fail-closed e divieto di autopubblicazione;
- DPA dei provider AI, trasferimenti, retention, valutazione del rischio e AI literacy;
- accessibilità e dichiarazioni commerciali di conformità.

### Approvazione legale/DPO

Parere aziendale del CEO; nessun DPO nominato, ritenuto non obbligatorio per il
profilo di trattamento dichiarato. Il parere non attribuisce il ruolo
professionale di avvocato o DPO.

- Decisione: [ ] APPROVATO  [x] APPROVATO CON CONDIZIONI  [ ] RESPINTO
- Nome e cognome: Angelo Caporaso
- Ruolo e organizzazione: CEO Enolab S.r.l.; parere aziendale; nessun DPO nominato
- Data e fuso orario: 2026-11-21, Europe/Rome
- Documenti/versioni approvati: Termini 2026-10-29, Privacy 2026-10-25, DPA template
- Trattamenti e casi d’uso AI approvati: nessun provider AI attivo in produzione; registro e revisione umana restano fail-closed
- SLA diritti interessati: risposta entro 30 giorni ai sensi dell'art. 12 GDPR
- SLA incidenti: valutazione entro 24 ore; notifica al Garante entro 72 ore se dovuta ai sensi dell'art. 33 GDPR
- Condizioni o modifiche richieste: revisione legale esterna raccomandata, non bloccante; mantenere aggiornato il registro dei trattamenti ai sensi dell'art. 30 GDPR
- Riferimento parere/verbale: decisione del titolare nella chat QRFacile del 2026-11-21
- Firma o evidenza equivalente: dichiarazione diretta di Angelo Caporaso nella chat QRFacile del 2026-11-21

## 4. Responsabilità operative

| Processo | Responsabile primario | Sostituto | SLA | Canale di escalation | Evidenza prova |
| --- | --- | --- | --- | --- | --- |
| Monitoraggio disponibilità | Angelo Caporaso | Luigi | presa in carico entro 4 ore lavorative | email a angelo.caporaso@enolab.it, in copia luigi@enolab.it | da provare al GO |
| Alert applicativi/database | Angelo Caporaso | Luigi | presa in carico entro 4 ore lavorative | email a angelo.caporaso@enolab.it, in copia luigi@enolab.it | alert sintetico staging inviato e ricevuto dal titolare il 2026-11-21 |
| Backup e restore | Angelo Caporaso | Luigi | verifica mensile | email a angelo.caporaso@enolab.it, in copia luigi@enolab.it | da provare al GO |
| Richieste privacy | Angelo Caporaso | Luigi | risposta entro 30 giorni | email a angelo.caporaso@enolab.it, in copia luigi@enolab.it | da provare al GO |
| Incidenti sicurezza | Angelo Caporaso | Luigi | valutazione entro 24 ore; notifica entro 72 ore se dovuta | email a angelo.caporaso@enolab.it, in copia luigi@enolab.it | da provare al GO |
| Revisione umana AI | Angelo Caporaso | Luigi | non applicabile: nessun AI attivo | email a angelo.caporaso@enolab.it, in copia luigi@enolab.it | nessun AI attivo; gate fail-closed |
| Supporto clienti | Angelo Caporaso | Luigi | risposta entro 1 giorno lavorativo | email a angelo.caporaso@enolab.it, in copia luigi@enolab.it | da provare al GO |
| Fatturazione | Angelo Caporaso | Luigi | entro 2 giorni lavorativi dal pagamento | email a angelo.caporaso@enolab.it, in copia luigi@enolab.it | test Danea end-to-end da chiudere |
| Riconciliazione PayPal | Angelo Caporaso | Luigi | settimanale | email a angelo.caporaso@enolab.it, in copia luigi@enolab.it | da provare al GO |
| Rimborsi/chargeback | Angelo Caporaso | Luigi | entro 5 giorni lavorativi | email a angelo.caporaso@enolab.it, in copia luigi@enolab.it | da provare al GO |

### Approvazione operativa

- Decisione: [ ] APPROVATO  [x] APPROVATO CON CONDIZIONI  [ ] RESPINTO
- Responsabile del rilascio: Angelo Caporaso
- Responsabile del rollback: Angelo Caporaso
- Sostituto tecnico: Luigi
- Finestra di rilascio autorizzata: da concordare dopo la chiusura di tutti i gate sullo SHA esatto
- Durata osservazione post-deploy: minimo 2 ore con monitoraggio attivo e nuova verifica il primo giorno lavorativo
- Canale incidenti: email angelo.caporaso@enolab.it + luigi@enolab.it
- Data e fuso orario: 2026-11-21, Europe/Rome
- Firma o evidenza equivalente: dichiarazione diretta di Angelo Caporaso nella chat QRFacile «confermo tutti e tre»
- Condizioni: chiudere test Danea end-to-end, webhook Sandbox, accessibilità, percorso autorizzato dei segreti Live, backup fresco/restore, preflight e smoke test. Finché restano aperte, l'esito tecnico è NO-GO.

## 5. Conferma tecnica finale

- [ ] Tutte le sezioni precedenti sono compilate e approvate.
- [ ] Eventuali condizioni sono state trasformate in issue verificabili e chiuse.
- [ ] Il percorso del secret store PayPal Live è stato comunicato senza esporre segreti.
- [ ] Backup, baseline, PR, SHA e CI coincidono ancora con il release gate.
- [ ] La PR #12 può essere convertita da Draft a Ready.

Esito finale: [ ] GO  [x] NO-GO

- Nome responsabile GO/NO-GO: Angelo Caporaso
- Ruolo: CEO Enolab S.r.l.
- Data e fuso orario: 2026-11-21, Europe/Rome
- Note: NO-GO fino alla chiusura documentata delle condizioni, incluso il test Danea end-to-end, la ricezione dell'alert operativo, i gate PayPal Live e le verifiche tecniche finali.
