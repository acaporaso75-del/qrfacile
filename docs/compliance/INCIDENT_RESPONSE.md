# QRFacile Incident Response

## Obiettivo
Gestire incidenti di sicurezza, perdita dati, accessi non autorizzati, indisponibilità, errori AI e possibili violazioni di dati personali.

## Classificazione
- P1 Critico: dati personali esposti, compromissione admin, indisponibilità generale, alterazione e-label pubblicate.
- P2 Alto: accesso non autorizzato limitato, perdita parziale, backup non ripristinabile, errore AI pubblicato.
- P3 Medio: vulnerabilità senza evidenza di sfruttamento, degradazione del servizio.
- P4 Basso: anomalia senza impatto su dati o disponibilità.

## Flusso
1. rilevazione e apertura incidente;
2. contenimento immediato;
3. conservazione evidenze e log;
4. valutazione dati, interessati e impatto;
5. ripristino sicuro;
6. comunicazioni interne ed esterne;
7. analisi causa radice;
8. azioni correttive e chiusura.

## Data breach GDPR
La valutazione deve documentare:
- natura della violazione;
- categorie e volume dei dati;
- interessati coinvolti;
- conseguenze probabili;
- misure adottate;
- necessità di notifica al Garante entro 72 ore;
- necessità di comunicazione agli interessati.

## Errori AI
Per output AI errati o ingannevoli:
- disabilitare la funzione o il contenuto;
- identificare modello, versione, prompt e approvatore;
- effettuare rollback;
- verificare prodotti/etichette coinvolti;
- correggere e notificare gli utenti interessati quando necessario.

## Evidenze minime
- data e ora;
- scopritore;
- sistemi coinvolti;
- timeline;
- log e commit;
- dati coinvolti;
- decisioni e responsabili;
- comunicazioni;
- test di ripristino;
- azioni preventive.

## Monitoraggio SLA aggregato

Il monitor operativo può eseguire, con il `DATABASE_URL` già montato nel runtime:

```bash
python scripts/check_privacy_sla.py --privacy-warning-days 7 --incident-assessment-hours 24
```

Il probe non restituisce ID, email, dettagli delle richieste, sintesi degli incidenti o altre PII. Esce con codice `1` per richieste scadute/in scadenza, incidenti alti o critici aperti, incidenti senza responsabile, notifiche richieste ma non registrate o valutazioni su dati personali non completate entro la soglia. Esce con codice `2` se configurazione, schema o database non sono verificabili. L’allerta non sostituisce la valutazione del DPO né determina automaticamente l’obbligo di notifica.
