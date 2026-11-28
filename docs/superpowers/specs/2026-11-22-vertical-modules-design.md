# QRFacile — moduli verticali: base comune e QRFacile Link (`/d`)

Data: 2026-11-22. Stato: design in approvazione. Primo modulo: **QRFacile Link**.

## Perché

QRFacile oggi vende soltanto l'etichetta digitale del vino. I moduli verticali
servono ad **aprire QRFacile a nuovi tipi di clienti** (negozi, professionisti,
ristoranti, associazioni, eventi, aziende). Il titolare vuole partire da un
modulo **semplice, utilizzabile da chiunque**: QRFacile Link. Gli altri moduli
(Menu Ristorante `/r`, Quiz/Formazione, Magazzino, Eventi/Votazioni, vCard…)
verranno costruiti e **attivati uno alla volta**, senza mai bloccare o
rallentare il sito già funzionante.

## Obiettivi

1. Una **base comune** riusabile da tutti i moduli verticali: codice QR e
   indirizzo pubblico per modulo, crediti e pagamenti, scelta del contenuto,
   statistiche, export per la stampa, attivazione per modulo.
2. **QRFacile Link** completo, per qualsiasi attività:
   - un QR fisso, indirizzo `https://www.qrfacile.it/d/<codice>`;
   - il cliente **sceglie il tipo di contenuto** e può **cambiarlo quando vuole**
     senza ristampare: **Link** (qualsiasi URL), **PDF** (listino, menu,
     catalogo, istruzioni), **Mini-pagina** (logo, titolo, testo breve e
     pulsanti: Chiama, WhatsApp, Email, Mappa, Sito, Instagram/Facebook);
   - i tipi sono **estendibili "a cassetti"**: aggiungerne uno (es. vCard,
     WhatsApp diretto, Recensione Google) non richiede di toccare gli altri;
   - il cliente **sceglie le statistiche per ogni QR** e può cambiarle:
     nessuna / solo conteggi / dettagliate (vedi sotto);
   - prezzo: **1 credito "QR Link" per QR**, qualunque tipo; restano i 3 QR
     gratuiti e il pacchetto esistente "QR Link 10" (€29);
   - export per la stampa (PNG, SVG, PDF) come per il vino.
3. **Registrazione "Azienda o professionista"** per chi non è cantina né
   studio; cantine e studi già registrati usano Link dal loro account.

## Non obiettivi (per questo progetto)

- Costruire Menu Ristorante, Quiz, Magazzino, Eventi o vCard come moduli
  separati: arriveranno dopo, sulla stessa base.
- Editor grafico libero o costruttore di siti: la Mini-pagina ha un formato
  fisso.
- Statistiche con geolocalizzazione da IP o profilazione.
- Modificare il modulo Wine (`/e`), i suoi prezzi o i suoi flussi.

## Anti-obiettivi (sarebbe un fallimento anche se "funziona")

- Rompere o rallentare un QR già stampato (vino `/e`, vecchio sito WordPress,
  QR Link beta).
- Mostrare un modulo incompleto ai clienti prima che sia attivato.
- Introdurre cookie, banner cookie o raccolta di dati personali dei visitatori.
- Duplicare crediti, pagamenti, export o statistiche per ogni modulo.

## Vincoli

- Applicazione esistente: FastAPI + PostgreSQL, HTML generato lato server
  (`ui_shell.page`), CSRF su ogni POST autenticato, accessibilità WCAG 2.1 AA,
  test pytest con PostgreSQL in CI, migrazioni SQL transazionali in `sql/`.
- Il rilascio di produzione in corso (PR #12) non deve dipendere da questo
  progetto: il lavoro va su un branch separato e arriva in produzione spento.
- I QR Link beta esistono già in `qr_items` (`qr_type='external'`,
  `payload.url`); quelli stampati come `/e/<slug>` vengono inoltrati a `/d/`
  (già nel rilascio, commit `a3f97a3`). Devono continuare a funzionare dopo
  la migrazione al nuovo modulo.
- Lettere riservate agli indirizzi dei moduli (`d`, `r`, …) non possono
  coincidere con le pagine del vecchio sito (verificato da
  `scripts/check_historic_qr.py` e dall'elenco in `legacy_routes`).
- Privacy: nessun indirizzo IP, user-agent completo, cookie o identificativo
  del visitatore salvato, in nessuna modalità di statistica.
- Le pagine pubbliche dei moduli non usano cookie né script di terze parti.

## Approcci considerati

| Approccio | Sintesi | Esito |
|---|---|---|
| **1. Base comune + moduli** | Una base condivisa (QR, crediti, statistiche, export, attivazione) e ogni modulo che aggiunge solo prefisso, tipi di contenuto e pagine | **Scelto** dal titolare: il primo modulo costa un po' di più, ogni modulo successivo molto meno; tutti si comportano allo stesso modo per il cliente; il vino resta intatto |
| 2. Ogni modulo per conto suo | Copia e adattamento del codice del vino per ogni modulo | Scartato: sei copie di crediti, statistiche ed export da mantenere |
| 3. Applicazione separata per i moduli | Secondo sito accanto al vino | Scartato: doppi account, pagamenti e server, troppo per l'azienda oggi |

## Decisioni del titolare

- Primo modulo: **QRFacile Link**, semplice, per tutti.
- Il cliente **sceglie il tipo di contenuto** (Link, PDF, Mini-pagina; altri in
  seguito) e può cambiarlo.
- Il cliente **sceglie il livello di statistiche** per ogni QR.
- **Prefisso per modulo**: `/e` resta al vino, `/d` per Link, `/r` per Menu
  Ristorante, e così via.
- I moduli si **attivano uno alla volta**, senza bloccare il sito funzionante;
  si può far lavorare anche Codex (collaudi su staging).
- **Vendita online a tutti**: aziende e professionisti con Partita IVA,
  privati e associazioni con codice fiscale, clienti UE ed extra-UE.
- **Prezzo "QR Link 10": €29 IVA inclusa** (imponibile €23,77 con IVA 22%).

## Design

### Base comune (riusata da tutti i moduli)

- **Registro dei moduli** (`qrfacile_app/modules/registry.py`): per ogni modulo
  chiave, nome, prefisso (`d`, `r`…), tipi di contenuto ammessi, tipo di
  credito, stato di attivazione. Un modulo **spento** non compare nel menu né
  nel listino, le sue pagine di gestione rispondono 404 e il suo indirizzo
  pubblico serve solo i QR già esistenti (mai rompere un QR stampato).
- **Attivazione** (scelta del costruttore, rivista dopo il controllo del
  revisore): interruttori salvati nel database e gestiti dall'area Admin
  (`/admin/modules`), con registro di chi li ha cambiati e quando; nessun
  riavvio né deploy per accendere o spegnere un modulo o le sue vendite.
  In staging si attivano per i collaudi, in produzione quando decide il titolare.
- **Il beta QR Link attuale** (pagine `/app/new-external`, `/app/external/<id>`,
  pacchetto `generic_10`) resta **esattamente com'è** finché Link è spento;
  quando si accende, le vecchie pagine reindirizzano a `/app/link/...` e i QR
  migrati compaiono nella nuova dashboard.
- **Proprietà**: ogni QR Link appartiene all'account che lo crea
  (`owner_user_id`), come oggi; i 3 gratuiti valgono per account; uno studio
  crea QR Link per sé, non per conto delle cantine clienti (estensione futura).
- **QR dei moduli**: si riusa `qr_items` (slug univoco già garantito,
  proprietario, stato). Nuova colonna `module` (es. `link`) e il contenuto
  nella colonna `payload` (JSON versionato per tipo). I QR beta
  `qr_type='external'` vengono migrati a `module='link'`, tipo `link`, con lo
  stesso slug.
- **Tipi di contenuto "a cassetti"** (`qrfacile_app/modules/content_types/`):
  ogni tipo dichiara validazione del modulo, form di modifica, comportamento
  pubblico (redirect o pagina) e campi. Primi tre: `link`, `pdf`, `minipage`.
- **Risolutore pubblico per prefisso**: `/d/<slug>` (e in futuro `/r/<slug>`…)
  legge il QR, controlla stato e modulo, applica il tipo di contenuto
  (redirect 302 no-store per `link`; servizio del file per `pdf`; pagina HTML
  per `minipage`). Pagina neutra "QR non attivo" se manca o è in bozza.
- **Statistiche** (tabella `qr_scan_daily`: qr_item_id, giorno, ora, categoria
  dispositivo, lingua, contatore): scritte con un `UPDATE … +1` per riga
  aggregata. Livelli scelti dal cliente per QR:
  - *nessuna*: nessuna scrittura;
  - *solo conteggi*: giorno + contatore;
  - *dettagliate*: giorno, ora, categoria dispositivo (telefono/tablet/
    computer, iOS/Android/altro) ricavata dallo user-agent e subito scartata,
    lingua principale da `Accept-Language`.
  Mai salvati IP, user-agent completo, cookie o identificativi. Paragrafo
  dedicato nell'informativa privacy (statistiche aggregate per conto del
  cliente).
- **Crediti e pagamenti**: tipo di credito `generic` già esistente; 3 QR
  gratuiti per account, poi 1 credito per QR; nessun credito per cambiare tipo
  o contenuto. Acquisto con il checkout PayPal esistente e passaggio a Danea
  con snapshot fiscale congelato nell'ordine, come per Wine.
- **Profilo di fatturazione per utente** (nuova tabella `billing_profiles`,
  usata da `business` e `studio`; le cantine continuano a usare `wineries`):
  tipo cliente (azienda/professionista con P.IVA, privato, associazione/ente),
  paese, denominazione o nome e cognome, P.IVA e/o codice fiscale, indirizzo,
  SDI o PEC per l'Italia, email per le fatture. Richiesto al primo acquisto.
- **Trattamento IVA del pacchetto €29 IVA inclusa** (decisione del titolare;
  la tabella va **confermata dal commercialista prima dell'attivazione estero**):

  | Cliente | IVA | Totale | Fattura Easyfatt-Xml |
  |---|---|---|---|
  | Italia (P.IVA, codice fiscale, enti) | 22% inclusa | €29,00 | SDI/PEC o codice destinatario `0000000` per privati, codice fiscale |
  | UE privato | 22% italiana sotto la soglia OSS di €10.000/anno; oltre, aliquota del paese (configurabile) | €29,00 | privato estero, codice destinatario `XXXXXXX` |
  | UE azienda con P.IVA valida (verifica VIES) | non imponibile, inversione contabile | €23,77 | dicitura di inversione contabile, `XXXXXXX` |
  | Extra-UE | fuori campo IVA | €23,77 | fuori campo, `XXXXXXX` |

  Il calcolo è in una sola funzione con test per ogni riga; codici IVA e
  diciture Easyfatt per i casi esteri vengono da una tabella di configurazione
  da validare con il commercialista. Lo snapshot dell'ordine conserva categoria,
  aliquota, base e motivo dell'esenzione.
- **Due interruttori di vendita**: `link_sales_it` (Italia, attivabile con il
  modulo) e `link_sales_foreign` (UE ed extra-UE, attivabile solo dopo l'ok del
  commercialista). Quando l'estero è spento, chi non è in Italia vede
  "Richiedi un preventivo".
- **Export**: riuso delle funzioni di `export_qr_ui` (PNG, SVG, PDF A4) con
  l'indirizzo `/d/<slug>`.

### QRFacile Link: esperienza del cliente

- **Registrazione "Azienda o professionista"**: email, password, conferma,
  nome attività, Termini e Privacy; dati di fatturazione facoltativi (richiesti
  al primo acquisto, come per la Cantina); verifica email obbligatoria. Nuovo
  ruolo `business` (vincolo `users_role_check` esteso).
- **Dashboard Link** (`/app/link`): elenco dei QR con nome, tipo, stato e
  inquadrature degli ultimi 30 giorni (se le statistiche sono attive);
  pulsante "Crea un QR". Primo accesso: guida in 3 passi (scegli il tipo,
  inserisci il contenuto, scarica il QR).
- **Creazione/modifica** (`/app/link/<id>`): nome interno, tipo di contenuto
  (scheda per tipo), livello di statistiche, anteprima del QR, download
  PDF/PNG/SVG, "Prova il QR", Pubblica/Metti in bozza. Cambiare tipo conserva
  il contenuto degli altri tipi finché il cliente non salva.
- **Tipi iniziali**:
  - *Link*: URL http(s), max 2000 caratteri.
  - *PDF*: file PDF fino a 10 MB, controllo della firma `%PDF` e dimensione,
    servito con `Content-Type: application/pdf`, `Content-Disposition: inline`,
    nome file sicuro; sostituire il PDF non cambia il QR.
  - *Mini-pagina*: logo (immagine come per i loghi cantina), titolo, testo
    breve (max ~600 caratteri), fino a 6 pulsanti scelti da un elenco
    (Chiama, WhatsApp, Email, Mappa, Sito, Instagram, Facebook); colori della
    palette QRFacile; nessun cookie, nessuno script esterno.
- **Accesso**: anche ruoli `winery` e `studio` possono usare Link dal proprio
  menu (stesso credito `generic`).

### Migrazioni e compatibilità

- `sql/2026_vertical_modules_base.sql`: colonna `qr_items.module`, tabella
  `qr_scan_daily`, indici, ruolo `business` nel vincolo utenti, conversione dei
  QR `external` esistenti in `module='link'`, tipo `link`. Transazionale,
  idempotente, con verifica dei conteggi.
- `/e/<slug>` continua a inoltrare a `/d/<slug>` i QR Link.
- `scripts/check_historic_qr.py` esteso ai QR dei moduli (`/d`).

### Testi legali

- Bozza preparata dal costruttore e approvata dal titolare prima
  dell'attivazione: clausola nei Termini sui contenuti caricati dai clienti
  (PDF, mini-pagine, link: responsabilità del cliente, divieto di contenuti
  illeciti o ingannevoli, rimozione su segnalazione) e paragrafo nella Privacy
  sulle statistiche aggregate trattate per conto del cliente.
- Nuove versioni dei documenti legali nel sistema versionato esistente;
  pubblicazione al momento dell'attivazione di Link; i nuovi account le
  accettano alla registrazione, gli account esistenti al primo uso di Link.
- Segnalazione abusi: link "Segnala contenuto" sulle mini-pagine e sulla
  pagina "QR non attivo", con coda nell'area Admin.

### Rilascio "spento" e attivazione

1. Sviluppo su branch dedicato, test e CI come per il resto.
2. Merge e deploy con `QRFACILE_MODULES_ENABLED` vuota: nessun cambiamento
   visibile; i QR Link esistenti continuano a funzionare.
3. Attivazione su staging, collaudo (Codex: UX, accessibilità, sicurezza
   upload, statistiche, pagamenti Sandbox).
4. Attivazione in produzione quando il titolare decide.

## Lasciato al costruttore

- Struttura interna dei file del registro e dei tipi di contenuto, purché
  aggiungere un tipo non richieda modifiche agli altri.
- Dettagli grafici entro lo stile esistente (`static/app.css`, componenti
  già usati per Wine).
- Granularità esatta delle categorie dispositivo e normalizzazione della
  lingua.
- Ordine interno dei lavori e suddivisione in commit.
