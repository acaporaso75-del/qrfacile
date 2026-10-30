# QRFacile — richiesta di approvazione operativa

Documento da compilare dal responsabile operativo di Enolab prima del rilascio
di QRFacile. Non contiene credenziali, dati cliente o payload di pagamento e
non certifica il software. Registra proprietari, sostituti, SLA ed evidenze
necessari a gestire il servizio dopo il GO.

## Candidato e vincoli di rilascio

- PR: `#12` da `codex/production-integration-20261029` verso `main`, ancora
  Draft;
- baseline di produzione da preservare fino al GO:
  `de0a4f1d848e68b5ea4113b3b80d2fa94cc23ffd`;
- nessun pagamento reale durante collaudo o rilascio;
- nessun segreto in Git, log, documenti o chat;
- PayPal Live utilizzabile solo tramite credenziali già presenti nel secret
  store autorizzato;
- dati storici, ordini, crediti, accettazioni e QR devono essere preservati.

Lo SHA candidato, la CI, il backup fresco, il rollback e la baseline devono
essere riletti immediatamente prima di rendere la PR Ready, fare merge o
deploy. Questa approvazione non sostituisce i gate contabile/fiscale e
legale/DPO.

## Evidenze richieste prima del GO

- Compliance CI verde sullo SHA esatto;
- backup recente con restore isolato verificato e rollback praticabile;
- migrazioni additive controllate e ledger verificato sul database effettivo;
- health check, monitoraggio e alert con consegna reale provata;
- email transazionali con consegna e gestione errori provate;
- webhook PayPal Sandbox firmato, fail-closed, con retry/replay sicuro;
- collaudo accessibilità essenziale sul runtime candidato;
- smoke test non distruttivi di cantina, Studio, amministrazione e QR pubblico;
- canale di incidente, reperibilità e criteri di escalation confermati.

## Matrice di responsabilità

Compilare ogni riga. Lo SLA deve indicare presa in carico, risoluzione o
escalation; la prova deve essere un riferimento verificabile senza segreti o
dati personali.

| Processo | Responsabile principale | Sostituto | SLA | Canale di escalation | Prova |
| --- | --- | --- | --- | --- | --- |
| Monitoraggio disponibilità |  |  |  |  |  |
| Alert applicazione e database |  |  |  |  |  |
| Backup e restore |  |  |  |  |  |
| Richieste privacy |  |  |  |  |  |
| Incidenti di sicurezza |  |  |  |  |  |
| Revisione umana AI |  |  |  |  |  |
| Assistenza clienti |  |  |  |  |  |
| Fatturazione |  |  |  |  |  |
| Riconciliazione PayPal |  |  |  |  |  |
| Rimborsi e chargeback |  |  |  |  |  |

## Decisione di rilascio

- Decisione: [ ] GO  [ ] GO CON CONDIZIONI  [ ] NO-GO
- Nome e cognome del responsabile:
- Ruolo e organizzazione:
- Data e fuso orario:
- SHA autorizzato:
- Finestra di rilascio:
- Responsabile del rilascio:
- Responsabile del rollback:
- Durata dell'osservazione post-deploy:
- Canale incidenti ed escalation:
- Percorso logico del secret store PayPal Live, senza valori segreti:
- Condizioni o azioni residue:
- Riferimento del verbale o ticket:
- Firma o evidenza equivalente:

In caso di GO condizionato, ogni condizione deve diventare un'attività con
responsabile, scadenza e prova verificabile. Se backup, rollback, health check
o smoke test critici non sono disponibili o falliscono, la decisione effettiva
resta NO-GO; dopo un deploy fallito si applica il rollback previsto.
