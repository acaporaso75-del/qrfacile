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

- Decisione: [ ] APPROVATO  [ ] APPROVATO CON CONDIZIONI  [ ] RESPINTO
- Nome e cognome:
- Ruolo e organizzazione:
- Data e fuso orario:
- Documenti e versioni esaminati:
- Ruoli titolare/responsabile approvati:
- DPA e fornitori/subresponsabili approvati:
- Basi giuridiche, finalità e retention approvate:
- Procedura diritti e SLA approvati:
- Procedura incidenti/data breach e SLA approvati:
- Usi AI e condizioni di attivazione approvati:
- Cookie/ePrivacy approvati:
- Condizioni o modifiche richieste:
- Riferimento del parere o verbale:
- Firma o evidenza equivalente:

In caso di approvazione condizionata, ogni condizione deve diventare una
modifica, una procedura o un'evidenza verificabile prima del GO. Nessuna
approvazione verrà inferita dal silenzio o dalla sola presenza dei controlli
tecnici.
