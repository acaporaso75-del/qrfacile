# QRFacile Link — integrazione a Termini e Privacy (BOZZA)

> **Stato: bozza da approvare** (titolare + consulente legale) prima di accendere
> il modulo `link` in produzione. Versioni previste: `terms: 2026-12-link`,
> `privacy: 2026-12-link` (`qrfacile_app/legal_core.py`, `LINK_LEGAL_DOCUMENTS`).
> Al primo accesso a `/app/link` il cliente accetta questo testo con una casella
> non preselezionata; l'accettazione è registrata in `legal_acceptances`
> (metodo `link_first_use`, IP e user agent come per la registrazione).

## A. Integrazione ai Termini di servizio

**A.1 Oggetto.** QRFacile Link permette di creare QR code dinamici che aprono un
contenuto scelto dal cliente: un indirizzo web (Link), un documento (PDF) o una
pagina semplice ospitata da QRFacile (Mini-pagina). Il cliente può cambiare il
contenuto in ogni momento; il QR stampato resta lo stesso.

**A.2 Responsabilità sui contenuti.** Il cliente è l'unico responsabile dei
contenuti collegati ai propri QR e garantisce di averne il diritto di uso. È
vietato collegare contenuti:
- illeciti, diffamatori, offensivi o che incitano all'odio o alla violenza;
- ingannevoli, truffe, phishing, richieste fraudolente di denaro o dati;
- malware o siti che danneggiano dispositivi o dati;
- che violano diritti d'autore, marchi o altri diritti di terzi;
- pornografici o comunque non adatti a un pubblico generale.

**A.3 Segnalazioni e sospensione.** Chiunque può segnalare un contenuto dalla
pagina `/segnala/<codice>`. QRFacile esamina le segnalazioni e può mettere il QR
in stato "bozza" (non raggiungibile) quando il contenuto è manifestamente
contrario al punto A.2 o su richiesta di un'autorità, informando il cliente. Il
cliente può correggere il contenuto e chiedere la riattivazione.

**A.4 Prezzi e IVA.** I pacchetti QR Link sono venduti a prezzo IVA inclusa
(QR Link 10: € 29,00, di cui IVA 22% € 5,23 per clienti italiani). Per clienti
UE con partita IVA verificata su VIES si applica l'inversione contabile; per
clienti extra UE l'operazione è fuori campo IVA italiana; per privati UE oltre
la soglia OSS si applica l'aliquota del Paese del cliente. Fattura elettronica
emessa da Enolab S.r.l. dopo il pagamento.

**A.5 Durata.** Il QR resta attivo finché l'account è attivo e il contenuto
rispetta questi termini. I primi 3 QR sono gratuiti; i successivi usano un
credito QR Link ciascuno.

## B. Integrazione all'informativa privacy

**B.1 Dati di chi scansiona.** Quando qualcuno apre un QR Link, QRFacile non
registra indirizzi IP, identificativi, cookie o impronte del dispositivo.

**B.2 Statistiche (facoltative).** Se il cliente le attiva, QRFacile conta le
scansioni solo in forma aggregata, per giorno e — nel livello "dettagliato" —
per ora del giorno, categoria di dispositivo (iPhone, Android, tablet, computer)
e lingua principale del browser. Questi conteggi non permettono di identificare
le persone e sono forniti al solo cliente titolare del QR. Base giuridica:
legittimo interesse del cliente a misurare l'uso dei propri materiali; i dati
aggregati non sono dati personali.

**B.3 Mini-pagine e PDF.** I file caricati dal cliente (PDF, logo) sono
conservati sui server QRFacile in Italia/UE e cancellati alla chiusura
dell'account. Il cliente è titolare dei dati personali eventualmente presenti
nei propri contenuti (es. numero di telefono aziendale nella mini-pagina);
QRFacile li tratta come responsabile solo per ospitarli.

**B.4 Segnalazioni.** La pagina di segnalazione non chiede nome né email: sono
registrati solo il motivo e la descrizione scritta dal segnalante, conservati
12 mesi.

**B.5 Dati di fatturazione.** Per gli acquisti sono raccolti i dati del
profilo di fatturazione (nome o ragione sociale, codice fiscale o partita IVA,
indirizzo, codice SDI o PEC) e, per i clienti UE, l'esito della verifica VIES.
Base giuridica: obbligo di legge (fatturazione). Conservazione: 10 anni.

## Punti da confermare con il consulente

1. Formulazione dell'esonero di responsabilità per contenuti di terzi (A.2/A.3)
   e richiamo alla disciplina dei servizi di hosting (DSA, Reg. UE 2022/2065).
2. Codici natura IVA per reverse charge / extra UE / OSS in Danea
   (`FOREIGN_VAT_CODES` in `pricing_config.py`, segnati "validate with accountant").
3. Periodo di conservazione delle segnalazioni (proposta: 12 mesi).
