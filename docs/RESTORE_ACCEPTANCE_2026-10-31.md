# QRFacile — accettazione ripristino pre-deploy

Questo documento registra la prova di ripristino isolata del backup fresco usato per il rilascio. Non autorizza il deploy e non deve contenere credenziali, dump, dati personali o payload PayPal.

## Identità della prova

- Ambiente: [ ] staging  [ ] produzione
- SHA candidato (40 caratteri):
- Percorso backup verificato:
- Destinazione isolata del restore:
- Data, ora e fuso:
- Operatore:
- Versione PostgreSQL di destinazione:
- Riferimento evidenze interne:

## Controlli obbligatori

- [ ] `SHA256SUMS` è stato verificato prima del restore.
- [ ] Il dump PostgreSQL è stato elencato e ripristinato senza errori in un database isolato.
- [ ] L’archivio filesystem è stato verificato ed estratto in un percorso isolato.
- [ ] Le migrazioni candidate sono state applicate due volte senza effetti duplicati.
- [ ] Precheck e postcheck hanno conservato ordini, accrediti, accettazioni, vini e QR storici.
- [ ] Il percorso di rollback è disponibile e distinto dal candidato.
- [ ] Nessuna azione della prova ha scritto su staging o produzione.
- [ ] Le evidenze non contengono segreti, PII, dump o payload di pagamento.

## Esito

Decisione: [ ] PASS  [ ] FAIL

- Nome e ruolo del verificatore:
- Data e fuso orario:
- Anomalie residue:
- Firma o evidenza equivalente:
