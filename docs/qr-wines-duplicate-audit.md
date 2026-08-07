# Audit duplicati `qr_wines.qr_item_id`

Aggiornato il 31 luglio 2026 sul solo database staging
`qrfacile_staging_db`.

## Stato prima della correzione

- Unico gruppo duplicato: `qr_item_id=22`, associato a `wine_id=7` e
  `wine_id=8`.
- `wine_id=7`: nessuna riga in nutrizione, ingredienti, allergeni,
  riciclabilità, asset, metadati o etichette.
- `wine_id=8`: 2 asset da conservare. La verifica diretta ha rilevato anche
  una riga in `wine_labels`, che deve essere conservata insieme al vino.
- Nessun altro `qr_item_id` duplicato.
- Nessun vincolo UNIQUE su `qr_wines(qr_item_id)`.

## Correzione

La migrazione `sql/2026_qr_wines_qr_item_unique.sql`:

1. rifiuta database diversi da `qrfacile_staging_db`;
2. acquisisce un lock esclusivo su `qr_wines`;
3. abortisce se record, relazioni o duplicati non coincidono con lo stato
   verificato;
4. elimina esclusivamente `wine_id=7`;
5. ricontrolla `wine_id=8`, i suoi 2 asset e l’assenza di duplicati;
6. aggiunge `uq_qr_wines_qr_item_id`;
7. registra l’operazione in `audit_log` nella stessa transazione.

Il codice di creazione intercetta il solo conflitto sul nuovo vincolo,
esegue rollback dell’intera creazione e restituisce un messaggio controllato.
