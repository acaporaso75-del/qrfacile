# QRFacile — pacchetto approvazioni produzione

Release candidate: `eb0278636dff8614498dfd29eac0ba6ee0e18b43`
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

- prezzi esposti IVA esclusa;
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
- Perimetro approvato: offerta Wine B2B, pacchetti annuali, prezzi IVA esclusa e opzione QR 25 anni sul release candidate indicato
- Claim commerciali autorizzati: formulazione commerciale proposta nel presente documento; esclusi claim assoluti sul primato di prezzo
- Condizioni o modifiche richieste: nessuna
- Riferimento documento/e-mail/verbale: autorizzazione esplicita nella chat QRFacile del 2026-10-30
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

- Decisione: [ ] APPROVATO  [ ] APPROVATO CON CONDIZIONI  [ ] RESPINTO
- Nome e cognome:
- Qualifica/Albo:
- Studio:
- Data e fuso orario:
- Paesi e regimi fiscali autorizzati al self-service:
- Processo di fatturazione approvato:
- Processo di riconciliazione/rimborso approvato:
- Condizioni o modifiche richieste:
- Riferimento parere/verbale:
- Firma o evidenza equivalente:

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

- Decisione: [ ] APPROVATO  [ ] APPROVATO CON CONDIZIONI  [ ] RESPINTO
- Nome e cognome:
- Ruolo e organizzazione:
- Data e fuso orario:
- Documenti/versioni approvati:
- Trattamenti e casi d’uso AI approvati:
- SLA diritti interessati:
- SLA incidenti:
- Condizioni o modifiche richieste:
- Riferimento parere/verbale:
- Firma o evidenza equivalente:

## 4. Responsabilità operative

| Processo | Responsabile primario | Sostituto | SLA | Canale di escalation | Evidenza prova |
| --- | --- | --- | --- | --- | --- |
| Monitoraggio disponibilità |  |  |  |  |  |
| Alert applicativi/database |  |  |  |  |  |
| Backup e restore |  |  |  |  |  |
| Richieste privacy |  |  |  |  |  |
| Incidenti sicurezza |  |  |  |  |  |
| Revisione umana AI |  |  |  |  |  |
| Supporto clienti |  |  |  |  |  |
| Fatturazione |  |  |  |  |  |
| Riconciliazione PayPal |  |  |  |  |  |
| Rimborsi/chargeback |  |  |  |  |  |

### Approvazione operativa

- Decisione: [ ] APPROVATO  [ ] APPROVATO CON CONDIZIONI  [ ] RESPINTO
- Responsabile del rilascio:
- Responsabile del rollback:
- Finestra di rilascio autorizzata:
- Durata osservazione post-deploy:
- Canale incidenti:
- Data e fuso orario:
- Firma o evidenza equivalente:

## 5. Conferma tecnica finale

- [ ] Tutte le sezioni precedenti sono compilate e approvate.
- [ ] Eventuali condizioni sono state trasformate in issue verificabili e chiuse.
- [ ] Il percorso del secret store PayPal Live è stato comunicato senza esporre segreti.
- [ ] Backup, baseline, PR, SHA e CI coincidono ancora con il release gate.
- [ ] La PR #12 può essere convertita da Draft a Ready.

Esito finale: [ ] GO  [ ] NO-GO

- Nome responsabile GO/NO-GO:
- Ruolo:
- Data e fuso orario:
- Note:
