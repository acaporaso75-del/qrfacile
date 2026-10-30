# QRFacile — richiesta di verifica legale e DPO

Documento da sottoporre al consulente legale e/o DPO di Enolab prima
dell'apertura delle vendite. Non contiene credenziali, dati cliente o payload
di pagamento. Non costituisce una certificazione di conformità: serve a
registrare una decisione professionale sul perimetro indicato, distinta dalle
verifiche tecniche già eseguite.

## Perimetro da esaminare

- Termini e condizioni versione `2026-10-29`, inclusa la durata dei QR di 10 o
  25 anni, il rinnovo manuale e la conservazione dei diritti già acquistati;
- informativa Privacy versione `2026-10-25`;
- DPA e ruoli di titolare/responsabile fra Enolab, cantine e utenti Studio;
- pagine pubbliche QR, area autenticata e sito commerciale, incluse le scelte
  cookie/ePrivacy;
- trattamenti assistiti da AI e relativo registro, senza pubblicazione
  automatica e con revisione umana obbligatoria fail-closed;
- procedure per diritti degli interessati, retention, incidenti e data breach;
- accessibilità e limiti delle dichiarazioni commerciali o di conformità.

Il candidato è la PR `#12` verso `main`; la PR deve restare Draft finché i gate
esterni non sono chiusi. L'approvazione non autorizza da sola merge, deploy,
attivazione PayPal Live o pagamenti reali.

## Controlli tecnici disponibili

Il codice include flussi tracciati per richieste privacy, esportazione,
cancellazione e chiusura incidenti; retention documentata; audit trail;
isolamento degli accessi Studio; registro dei trattamenti AI e revisione umana
fail-closed. Questi controlli sono coperti da test, ma non sostituiscono la
valutazione dei ruoli, delle basi giuridiche, dei testi, dei fornitori e delle
procedure organizzative.

I QR pubblici sono progettati senza profilazione o cookie non necessari. Prima
del GO occorre comunque verificare sul runtime installato il comportamento
effettivo, le informative mostrate e gli eventuali servizi terzi.

## Decisioni richieste

Confermare o correggere esplicitamente:

- ruoli privacy di Enolab, cantine e utenti Studio e relativo DPA;
- finalità, basi giuridiche, categorie di dati, destinatari e trasferimenti;
- testi e versioni di Termini, Privacy, DPA e cookie/ePrivacy;
- periodi di conservazione, cancellazione, export e trattamento nei backup;
- procedura, responsabili e SLA per i diritti degli interessati;
- procedura, responsabili e SLA per incidenti e notifiche di data breach;
- fornitori/subresponsabili, DPA, trasferimenti, retention e misure applicabili;
- classificazione degli usi AI, registro, trasparenza, supervisione umana,
  alfabetizzazione AI e condizioni per attivare eventuali provider;
- adeguatezza del divieto di autopubblicazione dei contenuti AI;
- requisiti cookie/ePrivacy delle pagine pubbliche, autenticate e dei QR;
- testi e limiti delle dichiarazioni su GDPR, AI Act e accessibilità.

Non verrà dichiarata piena conformità GDPR, AI Act, ePrivacy o accessibilità in
assenza di approvazione professionale documentata e delle relative prove
operative.

## Risposta da compilare

Stato della bozza: **PRECOMPILATA — IN ATTESA DEL LEGALE/DPO**.

- Decisione: [ ] APPROVATO  [ ] APPROVATO CON CONDIZIONI  [ ] RESPINTO
- Nome e cognome: da indicare dal professionista
- Ruolo e organizzazione: da indicare dal professionista
- Data e fuso orario: da indicare dal professionista
- Documenti e versioni esaminati: proposta `Termini 2026-10-29`, `Privacy
  2026-10-25`, DPA, cookie/ePrivacy, `DATA_RETENTION.md`, `AI_POLICY.md` e
  `INCIDENT_RESPONSE.md`
- Ruoli titolare/responsabile approvati: proposta da validare — Enolab titolare
  per account, contratto, assistenza e fatturazione; cantina titolare dei
  contenuti/dati pubblicati per i propri vini; Enolab responsabile quando tratta
  tali dati per conto della cantina; Studio autorizzato esclusivamente nel
  perimetro assegnato dalla cantina
- DPA e fornitori/subresponsabili approvati: DPA Enolab-cantina da sottoscrivere;
  elenco fornitori, localizzazione, trasferimenti, retention e misure da
  completare e approvare prima dell'attivazione
- Basi giuridiche, finalità e retention approvate: proposta di esecuzione del
  contratto, obblighi legali e legittimo interesse ove documentato; retention
  tecnica come in `DATA_RETENTION.md`, con durate fiscali e privacy definitive
  da approvare
- Procedura diritti e SLA approvati: proposta di presa in carico entro 2 giorni
  lavorativi e risposta entro 30 giorni, salvo estensione motivata e registrata
- Procedura incidenti/data breach e SLA approvati: proposta di presa in carico
  immediata per criticità, valutazione privacy entro 24 ore e decisione/notifica
  nei termini di legge, inclusa la soglia delle 72 ore quando applicabile
- Usi AI e condizioni di attivazione approvati: nessuna autopubblicazione;
  revisione umana obbligatoria; provider attivabile solo dopo scheda caso d'uso,
  DPA, valutazione trasferimenti/retention/rischio e formazione AI literacy
- Cookie/ePrivacy approvati: proposta di nessun cookie o tracciamento non
  necessario sulle pagine QR pubbliche; consenso preventivo per eventuali
  tecnologie non necessarie; verifica effettiva obbligatoria sul runtime
- Condizioni o modifiche richieste: validare testi, ruoli, DPA, fornitori,
  retention, SLA, cookie e classificazione AI prima del GO
- Riferimento del parere o verbale: da indicare dal professionista
- Firma o evidenza equivalente: da apporre dal professionista

In caso di approvazione condizionata, ogni condizione deve diventare una
modifica, una procedura o un'evidenza verificabile prima del GO. Nessuna
approvazione verrà inferita dal silenzio o dalla sola presenza dei controlli
tecnici.
