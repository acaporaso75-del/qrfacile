# QRFacile — accettazione SMTP e monitoraggio operativo

Questo documento registra la prova reale di consegna delle email transazionali e degli alert operativi sul runtime candidato. Non autorizza il deploy e non deve contenere indirizzi personali, credenziali, token, payload PayPal o PII.

## Identita della prova

- Ambiente: [x] staging  [ ] produzione
- SHA installato (40 caratteri): a50b03acb4861e46a74ea640a56fc9b0bae1626d
- URL origine: http://192.168.1.139:8001
- Data, ora e fuso: 2026-11-27, 21:15–21:18 CET (Europe/Rome)
- Operatore: Codex, su autorizzazione del titolare al checkpoint «destinatari»
- Riferimento destinatario interno autorizzato: responsabile primario e sostituto confermati nella chat QRFacile il 27 novembre; ruolo e SLA in `PRODUCTION_APPROVALS_2026-10-29.md`. Recapiti non riportati.
- Riferimento scheduler/monitor: `qrfacile-staging-operational-monitor.timer` (ogni 15 minuti, sola osservazione), unità versionate in `2c8bd45`, Compliance CI `46062598205`.
- Riferimento evidenze interne: `QRF-STG-OPS-20261127-211638`; readback SMTP, systemd e rollback riportati sotto.

## Controlli obbligatori

- [x] `check_transactional_email.py` ha restituito `TRANSACTIONAL_EMAIL_CONFIG_OK`.
- [ ] Un messaggio transazionale di prova e stato consegnato alla casella interna autorizzata.
  Relay SMTP OK; conferma di arrivo in casella non ancora acquisita.
- [ ] Un alert sintetico non verde e stato consegnato al responsabile operativo nominato.
  Relay SMTP OK; conferma di arrivo in casella non ancora acquisita.
- [x] L'alert contiene soltanto nomi e stati aggregati, senza payload, event ID o PII.
- [x] Il monitor schedulato esegue i probe PayPal webhook e privacy SLA con il runtime previsto.
- [x] Un errore di consegna SMTP produce un esito fail-closed osservabile.
- [x] Le anomalie residue hanno responsabile e SLA documentati.
  Riferimento: sezione 4 di `PRODUCTION_APPROVALS_2026-10-29.md`, presa in carico alert entro quattro ore lavorative e riconciliazione settimanale.
- [x] Le evidenze non contengono indirizzi personali, credenziali, token o segreti.

## Esito

Decisione: [ ] PASS  [ ] FAIL

- Nome e ruolo del verificatore: Codex, verifica tecnica in staging; decisione non ancora assegnata
- Data e fuso orario: 2026-11-27, Europe/Rome
- Anomalie residue: attesa conferma di arrivo in casella di entrambi i messaggi; tre ordini storici pagati con ambiente `unknown`. Il timer esegue i probe ma non è abilitato a spedire automaticamente.
- Firma o evidenza equivalente: readback dello SHA, accettazione SMTP, log della prima esecuzione del timer e verifica del backup sotto riportati.

## Evidenze — 27 novembre 2026, Europe/Rome

- Alle **21:15:27 CET**, `GET /healthz` restituisce la release sopra e DB
  OK. `git rev-parse HEAD` e confronto byte per byte con Git dei sette
  file usati dai probe e dal mittente confermano il runtime. Il destinatario
  configurato coincide con quello autorizzato; nessuna modifica a `.env`.
- `check_transactional_email.py`: `TRANSACTIONAL_EMAIL_CONFIG_OK
  transport=implicit_tls port=465`. Alle **21:16:38 CET** un solo invio
  dall'implementazione esistente di `run_operational_monitor.py` con
  esiti sintetici e la riga `collaudo_sintetico_staging: alert`: un
  destinatario accettato, zero rifiuti. L'alert standard non prevede CC.
- Una sola email transazionale di prova tramite `send_email_message`,
  riferimento `QRF-STG-OPS-20261127-211638`: due destinatari accettati
  in un unico invio (primario e copia), zero rifiuti. L'accettazione del
  relay non dimostra l'arrivo in casella. Nessun reinvio.
- Prova negativa controllata sul codice installato: rifiuto SMTP
  simulato nel solo processo di prova, senza contattare il relay.
  `OPERATIONAL_MONITOR_DELIVERY_ERROR`, exit `2`; nessuna modifica
  persistente alle impostazioni SMTP.
- `systemd-analyze verify` riuscito; `systemctl show` e
  `journalctl -u qrfacile-staging-operational-monitor.service` confermano
  prima esecuzione da timer alle **21:18:56 CET**: SMTP, coda PayPal e SLA
  privacy `ok`; riconciliazione `alert`, exit `1`. Timer attivo in attesa,
  prima ricorrenza successiva alle 21:30 CET. I tre ordini storici restano
  visibili come anomalia con soglia invariata a zero; DB in sola lettura.
  Per evitare ripetizioni dello stesso avviso, il timer esegue soltanto
  `check_operational_readiness.py`: gli invii automatici non sono attivi.
- Stato precedente delle unità (assenti), copie delle unità nuove e
  `ROLLBACK.txt` verificati con `sha256sum -c SHA256SUMS` in
  `/opt/qrfacile-backups/staging/20261127_211835_staging_operational_monitor_before_a50b03acb486`.
  Il rollback disabilita e ferma solo il timer e il servizio dei probe,
  trasferisce le unità aggiunte nella directory di rollback e rilegge le
  unità systemd. PID del servizio applicativo, SHA e health invariati
  dopo l'installazione. Nessuna azione su produzione, Caddy o PayPal Live.
