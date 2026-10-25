# Copia cifrata off-host del backup staging

Backup sorgente:

```text
/opt/qrfacile-backups/staging/20260806_180117_staging_131acbf390fa
```

La procedura non è stata eseguita perché non è ancora disponibile una
destinazione autorizzata. Destinazione proposta:

```text
backup@backup-vault:/srv/backups/qrfacile/staging/2026/08/
```

Il vault deve essere separato dall'host applicativo, cifrato a riposo, con accesso
limitato agli amministratori del backup e autenticazione mediante chiave dedicata.

## Cifratura con age

La chiave privata age deve restare off-host. Sul server applicativo è ammessa
soltanto la chiave pubblica destinataria.

```bash
backup_id=20260806_180117_staging_131acbf390fa
source_dir=/opt/qrfacile-backups/staging/${backup_id}
encrypted=/var/backups/${backup_id}.tar.age

cd "${source_dir}"
sha256sum -c SHA256SUMS

tar -C /opt/qrfacile-backups/staging -cf - "${backup_id}" |
  age -r '<AGE_RECIPIENT_PUBLIC_KEY>' -o "${encrypted}"

chmod 0600 "${encrypted}"
sha256sum "${encrypted}" > "${encrypted}.sha256"
```

L'archivio include `.env`: non deve mai essere prodotto o trasferito in chiaro.

## Trasferimento e verifica

Solo dopo approvazione della destinazione e della sua impronta SSH:

```bash
scp -o StrictHostKeyChecking=yes \
  "${encrypted}" "${encrypted}.sha256" \
  backup@backup-vault:/srv/backups/qrfacile/staging/2026/08/
```

Sul vault:

```bash
cd /srv/backups/qrfacile/staging/2026/08
sha256sum -c "${backup_id}.tar.age.sha256"
```

Il checksum locale e quello remoto devono coincidere byte per byte. Il file di
trasferimento locale può essere eliminato soltanto dopo verifica remota e nuova
autorizzazione; il backup sorgente verificato resta invariato.

## Decifratura controllata

Su un host di ripristino isolato:

```bash
age -d -i /secure/path/qrfacile-backup.agekey \
  -o "${backup_id}.tar" \
  "${backup_id}.tar.age"

tar -tf "${backup_id}.tar"
tar -xf "${backup_id}.tar" -C /secure/restore-area
cd "/secure/restore-area/${backup_id}"
sha256sum -c SHA256SUMS
```

L'area di ripristino deve avere permessi `0700`; file decifrati e `.env` non
devono essere copiati su postazioni personali o servizi cloud generici.

## Conservazione proposta

- backup giornalieri: 30 giorni;
- backup mensili: 12 mesi;
- almeno una copia immutabile o object-lock;
- prova di ripristino trimestrale;
- cancellazione documentata alla scadenza, nel rispetto degli obblighi legali.
