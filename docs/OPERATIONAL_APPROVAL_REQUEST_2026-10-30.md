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

| Processo | Responsabile principale proposto | Sostituto | SLA proposto | Canale di escalation | Prova richiesta |
| --- | --- | --- | --- | --- | --- |
| Monitoraggio disponibilità | Angelo Caporaso, CEO Enolab, da confermare | da nominare | P1: presa in carico 30 min; P2: 4 ore lavorative | canale incidenti Enolab da indicare | test alert e reperibilità |
| Alert applicazione e database | Angelo Caporaso, da confermare | da nominare | presa in carico entro 1 ora | canale incidenti Enolab da indicare | consegna alert reale senza PII |
| Backup e restore | Angelo Caporaso, da confermare | da nominare | backup giornaliero; avvio restore entro 4 ore da P1 | canale incidenti Enolab da indicare | backup fresco e restore isolato |
| Richieste privacy | Angelo Caporaso come referente interno, con legale/DPO da nominare | da nominare | presa in carico 2 giorni lavorativi; risposta entro 30 giorni | canale privacy Enolab da indicare | prova workflow e registro SLA |
| Incidenti di sicurezza | Angelo Caporaso come referente interno, con consulente/DPO da nominare | da nominare | P1 immediato; valutazione privacy entro 24 ore | canale incidenti Enolab da indicare | simulazione e registro incidente |
| Revisione umana AI | Angelo Caporaso, da confermare | da nominare | sempre prima della pubblicazione; obiettivo 1 giorno lavorativo | coda revisione amministrativa | prova approvazione/rifiuto fail-closed |
| Assistenza clienti | Angelo Caporaso, da confermare | da nominare | risposta iniziale entro 1 giorno lavorativo | canale assistenza Enolab da indicare | ticket di prova |
| Fatturazione | Angelo Caporaso come referente, con commercialista da indicare | da nominare | secondo termine approvato dal commercialista | canale contabile Enolab da indicare | fattura di prova Sandbox/non fiscale |
| Riconciliazione PayPal | Angelo Caporaso, da confermare | da nominare | controllo giornaliero; anomalie entro 1 giorno lavorativo | canale contabile Enolab da indicare | report di riconciliazione senza PII |
| Rimborsi e chargeback | Angelo Caporaso con commercialista, da confermare | da nominare | presa in carico entro 1 giorno lavorativo; decisione entro 5 giorni lavorativi | canale contabile/incidenti da indicare | prova procedura manuale |

## Decisione di rilascio

Stato della bozza: **PRECOMPILATA — NO-GO TECNICO TEMPORANEO**. Il NO-GO non
respinge il progetto: impedisce soltanto il rilascio finché le evidenze elencate
non sono completate.

- Decisione: [ ] GO  [ ] GO CON CONDIZIONI  [x] NO-GO
- Nome e cognome del responsabile: Angelo Caporaso, da confermare
- Ruolo e organizzazione: CEO, Enolab
- Data e fuso orario: 2026-10-30, Europe/Rome — bozza tecnica non firmata
- SHA autorizzato: nessuno finché i gate restano aperti; candidato corrente da
  rileggere prima del GO
- Finestra di rilascio: da concordare dopo chiusura gate, con presenza del
  responsabile del rilascio e del rollback
- Responsabile del rilascio: Angelo Caporaso, proposto e da confermare
- Responsabile del rollback: Angelo Caporaso, proposto; sostituto tecnico da
  nominare prima del GO
- Durata dell'osservazione post-deploy: proposta minima 2 ore con monitoraggio
  attivo, più verifica il primo giorno lavorativo
- Canale incidenti ed escalation: da indicare e provare prima del GO
- Percorso logico del secret store PayPal Live, senza valori segreti: da
  comunicare prima del GO
- Condizioni o azioni residue: approvazioni contabile e legale/DPO; responsabili
  e sostituti; webhook Sandbox firmato; SMTP/alert; accessibilità; secret store;
  backup fresco, restore, preflight e smoke test sullo SHA esatto
- Riferimento del verbale o ticket: chat QRFacile e PR `#12`; verbale operativo
  finale da creare
- Firma o evidenza equivalente: da confermare esplicitamente da Angelo Caporaso

In caso di GO condizionato, ogni condizione deve diventare un'attività con
responsabile, scadenza e prova verificabile. Se backup, rollback, health check
o smoke test critici non sono disponibili o falliscono, la decisione effettiva
resta NO-GO; dopo un deploy fallito si applica il rollback previsto.
