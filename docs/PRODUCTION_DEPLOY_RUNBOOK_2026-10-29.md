# QRFacile — runbook produzione

Il runbook estende il modello di rilascio già usato per staging. Non sostituisce i gate in `PRODUCTION_APPROVALS_2026-10-29.md`.

## Parametri canonici

- Host applicativo: VM QRFacile 121
- Root applicativa attuale: `/opt/qrfacile`
- Servizio: `qrfacile.service`
- Porta locale: `8000`
- Database: `qrfacile_db` su VM database 120
- Branch produzione: `main`
- Baseline installata: `de0a4f1d848e68b5ea4113b3b80d2fa94cc23ffd`
- PR di rilascio: `#12`
- Release candidate preparata: `a2c8874276c0e256891483eccdf2d7533f4fe8af`
- Backup verificato: `/opt/qrfacile-backups/production/20261029_164543-production-de0a4f1d848e`

Prima del rilascio sostituire la release candidate con lo SHA di merge effettivo di `main`. Non distribuire uno SHA diverso da quello verificato in CI.

## Gate GO/NO-GO

- [ ] Approvazioni commerciale, contabile, legale/DPO e operativa complete.
- [ ] PR #12 Ready, mergeable e CI verde sullo SHA esatto.
- [ ] Backup produttivo recente, leggibile e con restore verificato.
- [ ] Spazio disco sufficiente su host applicativo e database.
- [ ] Baseline installata e servizio attivo registrati immediatamente prima del deploy.
- [ ] Percorso rollback e responsabile rollback confermati.
- [ ] Nessun ordine o riconciliazione in corso durante la finestra.
- [ ] SMTP transazionale e monitoraggio verificabili.
- [ ] `python scripts/check_transactional_email.py` restituisce `TRANSACTIONAL_EMAIL_CONFIG_OK` senza mostrare host, mittente, utente o password.
- [ ] Il monitor esegue `scripts/check_paypal_webhook_queue.py` con il `DATABASE_URL` già montato nel runtime e consegna l’alert al responsabile operativo nominato.
- [ ] Il monitor esegue `scripts/check_privacy_sla.py` senza esportare PII e consegna l’alert al responsabile privacy/incidenti nominato.
- [ ] `scripts/check_payment_reconciliation.py` è verde con l’eventuale soglia degli ordini storici `unknown` approvata e registrata dalla contabilità.
- [ ] PayPal resta Sandbox finché il relativo gate Live non è chiuso.

## Stato pre-deploy da registrare

Registrare senza stampare configurazioni o segreti:

- timestamp e fuso orario;
- SHA locale, remoto, head PR e SHA merge;
- SHA attualmente installato;
- stato `qrfacile.service`;
- stato database e numero connessioni;
- spazio disco e inode;
- conteggi utenti, ordini, QR e `qr_wines`;
- ID e checksum del backup;
- campione di QR storici verificabili;
- valore non sensibile di ambiente: `production`;
- modalità PayPal prevista: `sandbox` oppure `live`.

## Preparazione release isolata

1. Creare una directory release nuova sotto `/opt`, senza modificare `/opt/qrfacile`.
2. Effettuare checkout detached dell’esatto SHA di merge di `main`.
3. Installare dipendenze usando il lock/requirements del repository.
4. Conservare upload e dati persistenti fuori dallo swap o collegarli al percorso canonico già usato.
5. Validare la configurazione senza stamparne i valori.
6. Eseguire compilazione, import applicazione, audit sicurezza e SQL transaction check.
7. Verificare che il nuovo runtime non punti a staging.

## Migrazioni

Applicare, sotto il ruolo applicativo e nell’ordine registrato in `PRODUCTION_RELEASE_GATE_2026-10-29.md`, esclusivamente le migrazioni non ancora presenti nel database effettivo.

Regole:

- non usare `2026_qr_wines_qr_item_unique.sql`, perché è staging-only;
- usare `2026_production_qr_wines_qr_item_unique.sql` per il database produttivo;
- ogni errore deve interrompere la procedura;
- non ignorare guard, vincoli o mismatch dei dati;
- acquisire conteggi e schema prima e dopo;
- non cancellare backup o directory di quarantena durante la finestra di osservazione.

La migrazione è stata provata due volte su restore, ma deve essere rivalidata contro un backup acquisito immediatamente prima del deploy se i dati produttivi sono cambiati.

## Attivazione applicazione

1. Fermare soltanto `qrfacile.service`.
2. Rinominare la directory corrente come quarantena con timestamp e SHA.
3. Portare la release preparata nel percorso `/opt/qrfacile`.
4. Avviare `qrfacile.service`.
5. Verificare subito:

```text
python scripts/verify_release_health.py \
  --url http://127.0.0.1:8000/healthz \
  --expected-environment production \
  --expected-release <SHA_MERGE_COMPLETO>
```

Un valore `not-versioned`, `unavailable`, ambiente errato, database non OK o SHA differente impone rollback.

## Smoke test non distruttivi

- [ ] `/healthz` restituisce ambiente e SHA corretti.
- [ ] HTTPS e redirect canonicali funzionano.
- [ ] Home, pricing, Termini, Privacy, robots e sitemap rispondono correttamente.
- [ ] QR storici campionati restituiscono 200 in italiano e inglese.
- [ ] Pagina QR pubblica non installa cookie o tracker non autorizzati.
- [ ] Login/logout/reset password e rate limit rispondono correttamente.
- [ ] Registrazione mostra prezzi, IVA e versioni legali corrette.
- [ ] Accesso Studio resta limitato alla singola etichetta assegnata.
- [ ] Admin distingue ordini Sandbox, Live, manuali e unknown.
- [ ] Flusso AI non può pubblicare senza revisione umana.
- [ ] Navigazione tastiera, focus, zoom ed errori essenziali sono utilizzabili.
- [ ] SMTP transazionale viene verificato con un destinatario interno autorizzato.
- [ ] `python scripts/check_paypal_webhook_queue.py --max-open-age-minutes 15 --max-open-count 10` restituisce `PAYPAL_WEBHOOK_QUEUE_OK`; è provata anche la consegna di un alert sintetico senza payload, event ID o credenziali.
- [ ] `python scripts/check_privacy_sla.py --privacy-warning-days 7 --incident-assessment-hours 24` restituisce `PRIVACY_SLA_OK`; è provata la consegna di un alert sintetico privo di PII.
- [ ] `python scripts/check_payment_reconciliation.py` restituisce `PAYMENT_RECONCILIATION_OK`; eventuali ordini storici `unknown` sono riconciliati e la soglia esplicita è approvata dalla contabilità.
- [ ] PayPal segue esclusivamente la modalità approvata.

Non creare ordini pagati e non effettuare pagamenti reali durante lo smoke test.

## Rollback

Rollback immediato se falliscono health, database, accesso, QR storici, isolamento Studio, sicurezza, checkout o integrità dei dati.

Prima della prima vendita annuale Live:

1. fermare il servizio QRFacile;
2. rimettere la directory applicativa precedente nel percorso canonico;
3. ripristinare il database dal backup verificato solo se le migrazioni hanno modificato il database e non esistono nuovi dati da preservare;
4. riavviare il servizio;
5. verificare `/healthz` contro lo SHA precedente;
6. ricontrollare QR storici e conteggi;
7. documentare causa e risultato.

Dopo il primo ordine reale o nuovi dati produttivi, non ripristinare ciecamente un backup precedente: usare un forward fix o una riconciliazione approvata per non perdere ordini, pagamenti, crediti o accettazioni.

## Rapporto finale

Registrare:

- SHA precedente, merge, installato e verificato;
- PR e run ID CI;
- backup e checksum;
- migrazioni effettivamente applicate;
- timestamp deploy e durata indisponibilità;
- risultato health e smoke test;
- stato PayPal Sandbox/Live;
- campione QR storici;
- eventuale rollback;
- rischi residui e responsabile dell’osservazione post-deploy.
