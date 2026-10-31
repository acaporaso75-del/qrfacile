# QRFacile — accettazione SMTP e monitoraggio operativo

Questo documento registra la prova reale di consegna delle email transazionali e degli alert operativi sul runtime candidato. Non autorizza il deploy e non deve contenere indirizzi personali, credenziali, token, payload PayPal o PII.

## Identita della prova

- Ambiente: [ ] staging  [ ] produzione
- SHA installato (40 caratteri):
- URL origine:
- Data, ora e fuso:
- Operatore:
- Riferimento destinatario interno autorizzato:
- Riferimento scheduler/monitor:
- Riferimento evidenze interne:

## Controlli obbligatori

- [ ] `check_transactional_email.py` ha restituito `TRANSACTIONAL_EMAIL_CONFIG_OK`.
- [ ] Un messaggio transazionale di prova e stato consegnato alla casella interna autorizzata.
- [ ] Un alert sintetico non verde e stato consegnato al responsabile operativo nominato.
- [ ] L'alert contiene soltanto nomi e stati aggregati, senza payload, event ID o PII.
- [ ] Il monitor schedulato esegue i probe PayPal webhook e privacy SLA con il runtime previsto.
- [ ] Un errore di consegna SMTP produce un esito fail-closed osservabile.
- [ ] Le anomalie residue hanno responsabile e SLA documentati.
- [ ] Le evidenze non contengono indirizzi personali, credenziali, token o segreti.

## Esito

Decisione: [ ] PASS  [ ] FAIL

- Nome e ruolo del verificatore:
- Data e fuso orario:
- Anomalie residue:
- Firma o evidenza equivalente:
