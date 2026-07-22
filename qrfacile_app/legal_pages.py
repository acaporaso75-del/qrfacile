from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from qrfacile_app.ui_shell import page_public

router = APIRouter()


def _actions() -> str:
    return """
    <a class="btn" href="/">Home</a>
    <a class="btn" href="/pricing">Prezzi</a>
    <a class="btn" href="/trust">Affidabilità</a>
    <a class="btn" href="/support">Supporto</a>
    <a class="btn btn-primary" href="/login">Accedi</a>
    """


LEGAL_STYLE = """
<style>
.legalWrap {
  max-width:1000px;
  margin:0 auto;
}

.legalHero {
  border:1px solid rgba(2,8,23,.08);
  border-radius:28px;
  overflow:hidden;
  box-shadow:0 24px 80px rgba(2,8,23,.08);
  background:
    radial-gradient(circle at 8% 12%, rgba(191,245,230,.58), transparent 34%),
    radial-gradient(circle at 92% 8%, rgba(207,232,255,.58), transparent 34%),
    linear-gradient(135deg,rgba(255,255,255,.96),rgba(248,252,250,.92));
  padding:30px;
}

.legalEyebrow {
  display:inline-flex;
  padding:7px 12px;
  border-radius:999px;
  background:rgba(20,184,166,.10);
  color:#0f766e;
  font-size:12px;
  font-weight:950;
  letter-spacing:.08em;
  text-transform:uppercase;
}

.legalTitle {
  margin-top:14px;
  font-size:clamp(32px,5vw,54px);
  line-height:1;
  font-weight:950;
  letter-spacing:-1.7px;
  color:#0f172a;
}

.legalSub {
  margin-top:14px;
  color:#475569;
  font-size:15px;
  font-weight:720;
  line-height:1.55;
}

.legalCard {
  margin-top:18px;
  border:1px solid rgba(2,8,23,.08);
  border-radius:24px;
  background:rgba(255,255,255,.86);
  box-shadow:0 14px 45px rgba(2,8,23,.055);
  padding:22px;
}

.legalCard h2 {
  margin:0 0 10px;
  font-size:22px;
  font-weight:950;
  color:#0f172a;
}

.legalCard h3 {
  margin:18px 0 8px;
  font-size:17px;
  font-weight:950;
  color:#0f172a;
}

.legalCard p,
.legalCard li {
  color:#475569;
  font-size:14px;
  font-weight:720;
  line-height:1.65;
}

.legalCard ul,
.legalCard ol {
  padding-left:21px;
}

.legalInfo {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:12px;
  margin-top:16px;
}

.legalInfo div {
  border:1px solid rgba(2,8,23,.07);
  background:rgba(248,250,252,.78);
  border-radius:18px;
  padding:14px;
}

.legalInfo span {
  display:block;
  color:#64748b;
  font-size:11px;
  font-weight:950;
  text-transform:uppercase;
  letter-spacing:.07em;
}

.legalInfo b {
  display:block;
  margin-top:6px;
  color:#0f172a;
  font-size:14px;
  line-height:1.4;
}

.legalNotice {
  margin-top:18px;
  border:1px solid rgba(20,184,166,.16);
  background:rgba(236,253,245,.78);
  color:#0f766e;
  border-radius:22px;
  padding:16px;
  font-size:14px;
  font-weight:780;
  line-height:1.55;
}

.legalWarn {
  margin-top:18px;
  border:1px solid rgba(245,158,11,.22);
  background:rgba(255,251,235,.82);
  color:#92400e;
  border-radius:22px;
  padding:16px;
  font-size:14px;
  font-weight:780;
  line-height:1.55;
}

.legalToc {
  margin-top:18px;
  display:flex;
  gap:10px;
  flex-wrap:wrap;
}

.legalToc a {
  display:inline-flex;
  padding:9px 12px;
  border-radius:999px;
  border:1px solid rgba(2,8,23,.08);
  background:rgba(255,255,255,.80);
  font-size:13px;
  font-weight:900;
  color:#0f766e;
  text-decoration:none;
}

@media(max-width:760px) {
  .legalHero,
  .legalCard {
    padding:22px;
  }

  .legalInfo {
    grid-template-columns:1fr;
  }
}
</style>
"""


def _company_box() -> str:
    return """
    <div class="legalInfo">
      <div>
        <span>Gestore del servizio</span>
        <b><a href="https://www.enolab.it" target="_blank" rel="noopener">Enolab S.r.l.</a></b>
      </div>

      <div>
        <span>P.IVA / C.F.</span>
        <b>01413300623</b>
      </div>

      <div>
        <span>REA</span>
        <b>BN118353</b>
      </div>

      <div>
        <span>Capitale sociale</span>
        <b>€90.000,00</b>
      </div>

      <div>
        <span>Sede legale</span>
        <b>Via Campoli-Friuni snc, Campoli del Monte Taburno (BN)</b>
      </div>

      <div>
        <span>Sede operativa</span>
        <b>Via Giovanni Agnelli, 16, Benevento (BN)</b>
      </div>

      <div>
        <span>PEC</span>
        <b>enolab@pcert.it</b>
      </div>

      <div>
        <span>Email</span>
        <b>info@enolab.it</b>
      </div>
    </div>
    """


def _updated() -> str:
    return "Ultimo aggiornamento: 11 maggio 2026"


@router.get("/legal", response_class=HTMLResponse)
def legal(request: Request):
    body = """
    <section class="legalWrap">
      <div class="legalHero">
        <div class="legalEyebrow">QRFACILE · Note legali</div>
        <div class="legalTitle">Note legali</div>
        <div class="legalSub">
          Informazioni legali e societarie relative al servizio QRFACILE.
        </div>
      </div>

      <div class="legalNotice">
        """ + _updated() + """
      </div>

      <div class="legalToc">
        <a href="/privacy">Privacy Policy</a>
        <a href="/cookies">Cookie Policy</a>
        <a href="/terms">Termini di servizio</a>
        <a href="/trust">Affidabilità e continuità</a>
        <a href="/support">Supporto e assistenza</a>
      </div>

      <div class="legalCard">
        <h2>Gestore del servizio</h2>
        <p>
          QRFACILE è una piattaforma tecnica per la creazione e gestione di QR dinamici,
          etichette digitali, pagine informative e strumenti di esportazione collegati
          a prodotti vitivinicoli e, più in generale, a contenuti digitali associati a QR.
        </p>
        """ + _company_box() + """
      </div>

      <div class="legalCard">
        <h2>Finalità del servizio</h2>
        <p>
          Il servizio consente agli utenti registrati di creare QR code dinamici, gestire dati
          relativi a lotti vino, immagini etichetta, ingredienti, allergeni, valori nutrizionali,
          riciclabilità, file di esportazione per la stampa e pagine pubbliche consultabili tramite QR.
        </p>
        <p>
          QRFACILE fornisce strumenti tecnici di compilazione, verifica operativa, esportazione e pubblicazione.
          Non sostituisce la consulenza normativa, legale, fiscale o professionale eventualmente necessaria
          per verificare la correttezza delle informazioni pubblicate.
        </p>
      </div>

      <div class="legalCard">
        <h2>Responsabilità sui dati inseriti</h2>
        <p>
          I dati pubblicati nelle pagine QR sono inseriti, gestiti e approvati dagli utenti della piattaforma.
          La responsabilità della correttezza, completezza, aggiornamento, liceità e conformità dei dati
          resta in capo al soggetto che li inserisce, li approva e ne richiede la pubblicazione.
        </p>
        <p>
          QRFACILE può impedire o segnalare la pubblicazione di schede incomplete sulla base di controlli tecnici,
          ma tali controlli non costituiscono certificazione legale o garanzia assoluta di conformità.
        </p>
      </div>

      <div class="legalCard">
        <h2>Proprietà intellettuale</h2>
        <p>
          Il marchio, il nome, la struttura grafica, il software, i testi, gli elementi di interfaccia
          e il layout della piattaforma QRFACILE appartengono al gestore del servizio o ai rispettivi aventi diritto.
          È vietata la riproduzione non autorizzata del servizio, dell’interfaccia o dei contenuti proprietari.
        </p>
        <p>
          I contenuti caricati dagli utenti, inclusi loghi, immagini etichetta e dati di prodotto, restano
          nella disponibilità e responsabilità degli utenti che li caricano, salvo i diritti tecnici necessari
          a QRFACILE per erogare il servizio.
        </p>
      </div>

      <div class="legalCard">
        <h2>Comunicazioni</h2>
        <p>
          Per comunicazioni operative è possibile scrivere a <b>info@enolab.it</b>.
          Per comunicazioni formali o aventi valore legale è disponibile la PEC <b>enolab@pcert.it</b>.
        </p>
      </div>

      """ + LEGAL_STYLE + """
    </section>
    """

    return HTMLResponse(page_public(
        title="QRFACILE · Note legali",
        subtitle="Note legali",
        body_html=body,
        actions_html=_actions(),
    ))


@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    body = """
    <section class="legalWrap">
      <div class="legalHero">
        <div class="legalEyebrow">QRFACILE · Privacy</div>
        <div class="legalTitle">Privacy Policy</div>
        <div class="legalSub">
          Informativa sul trattamento dei dati personali degli utenti della piattaforma QRFACILE.
        </div>
      </div>

      <div class="legalNotice">
        """ + _updated() + """
      </div>

      <div class="legalCard">
        <h2>1. Titolare del trattamento</h2>
        <p>
          Il titolare del trattamento dei dati personali trattati tramite la piattaforma QRFACILE è:
        </p>
        """ + _company_box() + """
      </div>

      <div class="legalCard">
        <h2>2. Tipologie di dati trattati</h2>
        <p>QRFACILE può trattare le seguenti categorie di dati:</p>
        <ul>
          <li>dati di registrazione e accesso: email, password cifrata, ruolo utente, stato account;</li>
          <li>dati aziendali: ragione sociale, P.IVA/C.F., indirizzo, città, provincia, CAP, PEC, SDI, telefono, referenti;</li>
          <li>dati relativi a cantine, studi grafici, clienti collegati, inviti e permessi;</li>
          <li>dati di prodotto: nome vino, annata, lotto, ingredienti, allergeni, valori nutrizionali, riciclabilità, immagini etichetta, logo cantina;</li>
          <li>dati tecnici: log applicativi, indirizzo IP, user-agent, data/ora accesso, sessioni, informazioni necessarie alla sicurezza;</li>
          <li>dati di scansione QR, ove presenti, trattati preferibilmente in forma tecnica, deduplicata o aggregata.</li>
        </ul>
      </div>

      <div class="legalCard">
        <h2>3. Finalità del trattamento</h2>
        <p>I dati sono trattati per:</p>
        <ul>
          <li>creare e gestire account utente;</li>
          <li>erogare il servizio QRFACILE e le relative funzionalità;</li>
          <li>generare, gestire e pubblicare QR dinamici e pagine informative;</li>
          <li>consentire la collaborazione tra cantine, studi grafici e amministratori;</li>
          <li>gestire crediti, piani, ordini, fatturazione o richieste commerciali, ove applicabile;</li>
          <li>garantire sicurezza, prevenzione abusi, manutenzione tecnica e continuità del servizio;</li>
          <li>adempiere a obblighi di legge, contabili, fiscali o richieste delle autorità competenti.</li>
        </ul>
      </div>

      <div class="legalCard">
        <h2>4. Base giuridica del trattamento</h2>
        <p>Il trattamento può fondarsi, a seconda dei casi, su:</p>
        <ul>
          <li>esecuzione di misure precontrattuali o contrattuali richieste dall’utente;</li>
          <li>adempimento di obblighi di legge;</li>
          <li>legittimo interesse del titolare alla sicurezza, gestione tecnica, prevenzione frodi e tutela dei propri diritti;</li>
          <li>consenso dell’interessato, ove richiesto per specifiche funzionalità non tecniche o comunicazioni facoltative.</li>
        </ul>
      </div>

      <div class="legalCard">
        <h2>5. Modalità di trattamento e sicurezza</h2>
        <p>
          I dati sono trattati con strumenti informatici, logiche organizzative e misure tecniche proporzionate
          alla natura del servizio. QRFACILE adotta controlli sugli upload, limitazioni sui formati file,
          ridimensionamento immagini, gestione delle sessioni e protezioni tecniche volte a ridurre rischi
          di perdita, accesso non autorizzato, alterazione o uso improprio dei dati.
        </p>
      </div>

      <div class="legalCard">
        <h2>6. Comunicazione dei dati</h2>
        <p>
          I dati possono essere comunicati a soggetti che operano come fornitori tecnici, hosting provider,
          consulenti, fornitori di servizi informatici, soggetti incaricati della manutenzione, consulenti fiscali
          o legali, autorità competenti e altri soggetti quando necessario per l’erogazione del servizio o per obbligo di legge.
        </p>
        <p>
          I dati pubblicati volontariamente dall’utente sulle pagine QR diventano accessibili a chiunque disponga
          del relativo link o scansioni il QR.
        </p>
      </div>

      <div class="legalCard">
        <h2>7. Conservazione dei dati</h2>
        <p>
          I dati sono conservati per il tempo necessario all’erogazione del servizio, alla gestione degli account,
          alla conservazione delle pagine QR attive, agli obblighi contabili/fiscali e alla tutela dei diritti del titolare.
          I dati tecnici e di log possono essere conservati per periodi proporzionati a finalità di sicurezza e manutenzione.
        </p>
      </div>

      <div class="legalCard">
        <h2>8. Diritti degli interessati</h2>
        <p>
          Nei casi previsti dalla normativa, l’interessato può esercitare i diritti di accesso, rettifica,
          cancellazione, limitazione del trattamento, opposizione, portabilità dei dati e revoca del consenso
          ove il trattamento sia basato sul consenso.
        </p>
        <p>
          Le richieste possono essere inviate a <b>info@enolab.it</b> o, per comunicazioni formali, a <b>enolab@pcert.it</b>.
        </p>
      </div>

      <div class="legalCard">
        <h2>9. Reclamo all’autorità di controllo</h2>
        <p>
          L’interessato ha diritto di proporre reclamo all’autorità di controllo competente in materia di protezione dei dati personali,
          ove ritenga che il trattamento violi la normativa applicabile.
        </p>
      </div>

      <div class="legalWarn">
        Questa informativa è redatta per il funzionamento attuale della piattaforma QRFACILE.
        Prima dell’apertura commerciale definitiva è opportuno verificarla con consulente privacy/legale,
        soprattutto in caso di attivazione di strumenti analytics, marketing, pagamento online o integrazioni terze.
      </div>

      """ + LEGAL_STYLE + """
    </section>
    """

    return HTMLResponse(page_public(
        title="QRFACILE · Privacy Policy",
        subtitle="Privacy",
        body_html=body,
        actions_html=_actions(),
    ))


@router.get("/cookies", response_class=HTMLResponse)
def cookies(request: Request):
    body = """
    <section class="legalWrap">
      <div class="legalHero">
        <div class="legalEyebrow">QRFACILE · Cookie</div>
        <div class="legalTitle">Cookie Policy</div>
        <div class="legalSub">
          Informativa sull’utilizzo di cookie e strumenti tecnici nella piattaforma QRFACILE.
        </div>
      </div>

      <div class="legalNotice">
        """ + _updated() + """
      </div>

      <div class="legalCard">
        <h2>1. Cosa sono i cookie</h2>
        <p>
          I cookie sono piccoli file o identificatori tecnici che possono essere salvati nel dispositivo dell’utente
          o utilizzati dal browser per consentire il funzionamento di un sito o di un servizio online.
        </p>
      </div>

      <div class="legalCard">
        <h2>2. Cookie tecnici necessari</h2>
        <p>
          QRFACILE può utilizzare cookie tecnici e strumenti equivalenti necessari per:
        </p>
        <ul>
          <li>gestire login e sessione utente;</li>
          <li>mantenere l’utente autenticato nell’area riservata;</li>
          <li>garantire sicurezza e prevenire accessi non autorizzati;</li>
          <li>memorizzare preferenze tecniche essenziali dell’interfaccia;</li>
          <li>consentire il corretto funzionamento del servizio richiesto dall’utente.</li>
        </ul>
        <p>
          I cookie tecnici non richiedono consenso preventivo, ma devono essere indicati nell’informativa.
        </p>
      </div>

      <div class="legalCard">
        <h2>3. Statistiche QR e dati tecnici</h2>
        <p>
          Le scansioni dei QR possono essere conteggiate per finalità tecniche e statistiche del servizio,
          ad esempio per mostrare dati aggregati o deduplicati sulle consultazioni delle pagine QR.
          Tali conteggi sono progettati per ridurre l’identificazione diretta dell’utente finale.
        </p>
      </div>

      <div class="legalCard">
        <h2>4. Cookie analytics, marketing o profilazione</h2>
        <p>
          Alla data di aggiornamento di questa pagina, QRFACILE è progettato per funzionare con cookie tecnici
          essenziali. Se in futuro saranno introdotti strumenti analytics di terze parti, marketing, profilazione
          o tracciamenti non tecnici, verranno aggiornate le informative e, ove necessario, verrà richiesto
          il consenso dell’utente tramite apposito banner o sistema di gestione preferenze.
        </p>
      </div>

      <div class="legalCard">
        <h2>5. Gestione dei cookie dal browser</h2>
        <p>
          L’utente può gestire, bloccare o cancellare i cookie tramite le impostazioni del browser utilizzato.
          La disabilitazione dei cookie tecnici può però compromettere login, sessione e funzionamento dell’area riservata.
        </p>
      </div>

      <div class="legalWarn">
        La Cookie Policy dovrà essere aggiornata se verranno attivati strumenti di analytics, remarketing,
        pixel social, sistemi di pagamento con tracciamenti propri o altri servizi terzi.
      </div>

      """ + LEGAL_STYLE + """
    </section>
    """

    return HTMLResponse(page_public(
        title="QRFACILE · Cookie Policy",
        subtitle="Cookie",
        body_html=body,
        actions_html=_actions(),
    ))


@router.get("/terms", response_class=HTMLResponse)
def terms(request: Request):
    body = """
    <section class="legalWrap">
      <div class="legalHero">
        <div class="legalEyebrow">QRFACILE · Termini</div>
        <div class="legalTitle">Termini di servizio</div>
        <div class="legalSub">
          Condizioni generali di utilizzo della piattaforma QRFACILE.
        </div>
      </div>

      <div class="legalNotice">
        """ + _updated() + """
      </div>

      <div class="legalCard">
        <h2>1. Oggetto del servizio</h2>
        <p>
          QRFACILE è una piattaforma tecnica che consente agli utenti registrati di creare e gestire QR dinamici,
          pagine digitali informative, etichette digitali vino, dati di prodotto, immagini etichetta, export QR
          e strumenti di collaborazione tra cantine, studi grafici e amministratori.
        </p>
      </div>

      <div class="legalCard">
        <h2>2. Destinatari del servizio</h2>
        <p>
          Il servizio è rivolto principalmente a operatori professionali, imprese, cantine, produttori,
          studi grafici, consulenti e soggetti che operano nel settore vitivinicolo o in ambiti collegati.
        </p>
      </div>

      <div class="legalCard">
        <h2>3. Account e credenziali</h2>
        <p>
          L’utente è responsabile della correttezza dei dati forniti in fase di registrazione,
          della custodia delle credenziali e di tutte le attività svolte tramite il proprio account.
          L’utente si impegna a comunicare tempestivamente eventuali accessi non autorizzati o usi impropri.
        </p>
      </div>

      <div class="legalCard">
        <h2>4. QR gratuiti, piani e crediti</h2>
        <p>
          QRFACILE può prevedere un numero iniziale di QR gratuiti, pacchetti, piani annuali o crediti utilizzabili
          secondo le condizioni commerciali vigenti al momento dell’attivazione.
        </p>
        <p>
          Le condizioni economiche, i limiti dei piani, il numero di QR inclusi, eventuali funzionalità premium
          e modalità di pagamento possono essere aggiornati nel tempo e saranno indicati nelle pagine commerciali
          o nelle comunicazioni contrattuali applicabili.
        </p>
      </div>

      <div class="legalCard">
        <h2>5. Creazione, bozza e pubblicazione dei QR</h2>
        <p>
          Il QR può essere creato e preparato anche prima del completamento di tutti i dati.
          La pubblicazione definitiva può essere bloccata quando risultano mancanti dati obbligatori o informazioni
          ritenute essenziali per la corretta presentazione della pagina digitale.
        </p>
        <p>
          In presenza di dati incompleti, la cantina può richiedere sblocco o valutazione da parte dell’admin.
          L’eventuale pubblicazione forzata resta un’eccezione operativa e non costituisce certificazione
          di conformità normativa.
        </p>
      </div>

      <div class="legalCard">
        <h2>6. Responsabilità dell’utente sui contenuti</h2>
        <p>
          L’utente è l’unico responsabile dei dati inseriti, caricati, modificati e pubblicati tramite QRFACILE,
          inclusi ma non limitati a: ingredienti, allergeni, valori nutrizionali, riciclabilità, immagini, loghi,
          testi, dati aziendali, lotti, annate e contenuti collegati ai QR.
        </p>
        <p>
          L’utente garantisce di disporre dei diritti necessari sui contenuti caricati e si impegna a non caricare
          contenuti illeciti, falsi, lesivi di diritti altrui, contrari a norme applicabili o potenzialmente dannosi
          per la piattaforma.
        </p>
      </div>

      <div class="legalCard">
        <h2>7. Ruoli: cantina, studio grafico e admin</h2>
        <p>
          La cantina è il soggetto che gestisce e approva i dati di prodotto e può procedere alla pubblicazione
          secondo le regole del servizio. Lo studio grafico può collaborare alla preparazione di etichette, immagini
          ed export QR, nei limiti dei permessi concessi. L’admin può gestire funzioni di controllo, assistenza,
          verifica e sblocco operativo.
        </p>
      </div>

      <div class="legalCard">
        <h2>8. Upload di immagini e file</h2>
        <p>
          QRFACILE può consentire il caricamento di loghi, immagini etichetta e altri contenuti ammessi.
          La piattaforma applica controlli tecnici su formato, dimensione e validità dei file, ma l’utente resta
          responsabile dei contenuti caricati e deve evitare file dannosi, non autorizzati o non conformi.
        </p>
      </div>

      <div class="legalCard">
        <h2>9. Disponibilità del servizio</h2>
        <p>
          Il gestore si impegna a mantenere il servizio funzionante e sicuro secondo standard ragionevoli,
          ma non garantisce disponibilità ininterrotta, assenza totale di errori o compatibilità perpetua
          con ogni dispositivo, browser, servizio terzo o aggiornamento normativo.
        </p>
        <p>
          Interventi di manutenzione, aggiornamenti, guasti, problemi di rete, eventi di forza maggiore,
          attacchi informatici o dipendenze da fornitori terzi possono comportare sospensioni o limitazioni temporanee.
        </p>
      </div>

      <div class="legalCard">
        <h2>10. Limitazione di responsabilità</h2>
        <p>
          QRFACILE è uno strumento tecnico. Il gestore non risponde per errori, omissioni, inesattezze,
          aggiornamenti mancati o usi impropri dei dati inseriti dagli utenti, né per conseguenze derivanti
          da contenuti pubblicati dagli utenti senza adeguata verifica.
        </p>
        <p>
          Restano salvi i casi di dolo o colpa grave e i limiti inderogabili previsti dalla legge.
        </p>
      </div>

      <div class="legalCard">
        <h2>11. Sospensione o limitazione dell’account</h2>
        <p>
          Il gestore può sospendere, limitare o disabilitare account o contenuti in caso di uso illecito,
          violazione dei presenti termini, mancato pagamento, rischio di sicurezza, caricamento di file dannosi,
          abuso del servizio o richiesta dell’autorità competente.
        </p>
      </div>

      <div class="legalCard">
        <h2>12. Proprietà intellettuale</h2>
        <p>
          Software, interfaccia, nome, logo, layout e contenuti proprietari di QRFACILE appartengono al gestore
          del servizio o ai rispettivi aventi diritto. È vietato copiare, replicare, decompilare, rivendere,
          distribuire o utilizzare il servizio al di fuori delle modalità consentite.
        </p>
      </div>

      <div class="legalCard">
        <h2>13. Modifiche al servizio e ai termini</h2>
        <p>
          Il gestore può aggiornare funzionalità, interfaccia, piani, prezzi, policy e condizioni di servizio.
          Le modifiche rilevanti saranno rese disponibili tramite il sito, la piattaforma o comunicazioni agli utenti.
        </p>
      </div>

      <div class="legalCard">
        <h2>14. Legge applicabile e foro competente</h2>
        <p>
          I presenti termini sono regolati dalla legge italiana. Per eventuali controversie relative all’utilizzo
          del servizio tra operatori professionali, salvo norme inderogabili, il foro competente sarà quello previsto
          dalla normativa applicabile in relazione al soggetto gestore.
        </p>
      </div>

      <div class="legalCard">
        <h2>15. Contatti</h2>
        <p>
          Per assistenza o informazioni: <b>info@enolab.it</b>.
          Per comunicazioni formali: <b>enolab@pcert.it</b>.
        </p>
      </div>

      <div class="legalWarn">
        Questi termini sono una base operativa completa per la piattaforma. Prima della commercializzazione pubblica
        su larga scala è consigliata una validazione legale, soprattutto per pagamenti online, SLA, consorzi,
        piani enterprise o trattamenti dati più complessi.
      </div>

      """ + LEGAL_STYLE + """
    </section>
    """

    return HTMLResponse(page_public(
        title="QRFACILE · Termini di servizio",
        subtitle="Termini",
        body_html=body,
        actions_html=_actions(),
    ))

@router.get("/trust", response_class=HTMLResponse)
def trust(request: Request):
    body = """
    <section class="legalWrap">
      <div class="legalHero">
        <div class="legalEyebrow">QRFACILE · Affidabilità</div>
        <div class="legalTitle">Affidabilità e continuità del servizio</div>
        <div class="legalSub">
          Informazioni operative sulle misure organizzative e tecniche adottate per proteggere
          il lavoro delle cantine e preservare nel tempo la consultabilità dei QR stampati.
        </div>
      </div>

      <div class="legalNotice">
        """ + _updated() + """
      </div>

      <div class="legalToc">
        <a href="/legal">Note legali</a>
        <a href="/privacy">Privacy Policy</a>
        <a href="/terms">Termini di servizio</a>
        <a href="/support">Supporto e assistenza</a>
      </div>

      <div class="legalCard">
        <h2>Continuità dei QR dinamici</h2>
        <p>
          QRFACILE nasce per gestire QR dinamici destinati alla stampa su etichette, materiali commerciali
          e supporti fisici. Per questo l’attenzione alla continuità nel tempo dei link pubblicati è parte
          integrante del servizio: l’obiettivo operativo è mantenere stabili gli indirizzi QR e ridurre il rischio
          che un QR già stampato diventi inutilizzabile per cambiamenti tecnici ordinari.
        </p>
        <p>
          I QR dinamici permettono di aggiornare dati, pagine informative, contenuti collegati e stato di pubblicazione
          senza ristampare il codice quando l’indirizzo pubblico rimane invariato.
        </p>
      </div>

      <div class="legalCard">
        <h2>Backup e copie operative</h2>
        <p>
          Il servizio è progettato con attenzione alla conservazione tecnica dei dati e alla ripristinabilità operativa.
          Possono essere previste misure quali backup periodici, copie della macchina virtuale, copie cloud e procedure
          interne di manutenzione, secondo criteri proporzionati alla fase evolutiva della piattaforma e alle esigenze
          di continuità del servizio.
        </p>
        <p>
          Le copie tecniche hanno finalità di sicurezza, manutenzione, recupero e continuità. Non sostituiscono
          gli obblighi dell’utente di conservare documentazione aziendale, materiali grafici originali e dati
          amministrativi eventualmente necessari alla propria attività.
        </p>
      </div>

      <div class="legalCard">
        <h2>Pubblicazione controllata e preview tecnica</h2>
        <p>
          QRFACILE distingue il lavoro tecnico di preparazione dalla pagina pubblica finale. La pubblicazione dei QR
          può essere controllata tramite stati, verifiche di completezza e workflow dedicati, in modo da evitare
          l’esposizione pubblica involontaria di pagine incomplete o ancora in verifica.
        </p>
        <p>
          La preview tecnica separata consente a cantine, studi grafici e amministratori di controllare i contenuti
          prima della pubblicazione finale, mantenendo la pagina pubblica più pulita e orientata alla consultazione
          da parte dell’utente che scansiona il QR.
        </p>
      </div>

      <div class="legalCard">
        <h2>Workflow studio/cantina</h2>
        <p>
          Il servizio supporta un workflow collaborativo tra cantina e studio grafico. La cantina mantiene il controllo
          sui dati di prodotto e sulla pubblicazione, mentre lo studio può collaborare su immagini, etichette, export,
          preparazione operativa e attività autorizzate nei limiti dei permessi concessi.
        </p>
        <p>
          Questo modello è pensato per ridurre errori di coordinamento, rendere più tracciabile il lavoro e separare
          le responsabilità operative tra compilazione, controllo, grafica ed esportazione.
        </p>
      </div>

      <div class="legalCard">
        <h2>Export professionale e multilingua</h2>
        <p>
          QRFACILE include strumenti di export professionale per QR e materiali collegati, pensati per l’uso operativo
          da parte di cantine e studi grafici. La piattaforma supporta inoltre contenuti multilingua IT/EN, così da
          rendere più semplice la gestione di pagine informative destinate a mercati e consultazioni internazionali.
        </p>
      </div>

      <div class="legalWarn">
        Le misure descritte rappresentano l’impostazione operativa del servizio e non costituiscono una garanzia di
        disponibilità assoluta o ininterrotta. Per condizioni contrattuali, limiti di responsabilità e disponibilità
        del servizio si rimanda ai Termini di servizio.
      </div>

      """ + LEGAL_STYLE + """
    </section>
    """

    return HTMLResponse(page_public(
        title="QRFACILE · Affidabilità e continuità del servizio",
        subtitle="Affidabilità",
        body_html=body,
        actions_html=_actions(),
    ))


@router.get("/support", response_class=HTMLResponse)
def support(request: Request):
    body = """
    <section class="legalWrap">
      <div class="legalHero">
        <div class="legalEyebrow">QRFACILE · Supporto</div>
        <div class="legalTitle">Supporto e assistenza</div>
        <div class="legalSub">
          Canali e modalità di supporto per cantine, studi grafici e utenti della piattaforma QRFACILE.
        </div>
      </div>

      <div class="legalNotice">
        """ + _updated() + """
      </div>

      <div class="legalToc">
        <a href="/legal">Note legali</a>
        <a href="/trust">Affidabilità e continuità</a>
        <a href="/privacy">Privacy Policy</a>
        <a href="/terms">Termini di servizio</a>
      </div>

      <div class="legalCard">
        <h2>Canali di contatto</h2>
        <p>
          Per richieste operative, informazioni sul servizio, onboarding e assistenza ordinaria è possibile scrivere a
          <b>info@enolab.it</b>.
        </p>
        <p>
          Per comunicazioni formali o aventi valore legale è disponibile la PEC <b>enolab@pcert.it</b>.
        </p>
        """ + _company_box() + """
      </div>

      <div class="legalCard">
        <h2>Onboarding cantine</h2>
        <p>
          QRFACILE può supportare le cantine nella fase iniziale di configurazione: creazione account, impostazione
          dei dati aziendali, caricamento dei primi lotti, compilazione delle informazioni obbligatorie, gestione
          immagini etichetta, verifica preview e pubblicazione controllata.
        </p>
      </div>

      <div class="legalCard">
        <h2>Supporto studi grafici</h2>
        <p>
          Gli studi grafici possono ricevere supporto operativo sul workflow partner: inviti alle cantine, collegamento
          cliente/studio, gestione dei permessi, preparazione delle immagini, verifica delle etichette digitali ed export
          dei QR per la stampa.
        </p>
      </div>

      <div class="legalCard">
        <h2>Supporto operativo QRFACILE</h2>
        <p>
          Il supporto riguarda l’utilizzo tecnico e operativo della piattaforma: accesso, dashboard, lotti, ingredienti,
          allergeni, valori nutrizionali, riciclabilità, preview, pubblicazione, QR dinamici, export e collaborazione
          tra cantina e studio.
        </p>
        <p>
          QRFACILE non sostituisce consulenti legali, consulenti privacy, consulenti fiscali o professionisti incaricati
          di validare la conformità normativa dei dati inseriti e pubblicati dagli utenti.
        </p>
      </div>

      <div class="legalCard">
        <h2>Tempi di risposta</h2>
        <p>
          Le richieste vengono gestite secondo priorità operativa, disponibilità del team e tipologia di piano o servizio
          attivo. I tempi di risposta possono variare in base al volume delle richieste, alla complessità del caso e
          all’eventuale necessità di verifiche tecniche.
        </p>
      </div>

      <div class="legalCard">
        <h2>Supporto standard e supporto assistito</h2>
        <p>
          Il supporto standard comprende indicazioni operative generali, chiarimenti sull’uso della piattaforma e gestione
          di problemi tecnici ordinari.
        </p>
        <p>
          Il supporto assistito può includere attività più guidate, onboarding dedicato, affiancamento nella configurazione,
          preparazione dei primi QR o supporto operativo più continuativo. Eventuali modalità, disponibilità e costi del
          supporto assistito sono concordati caso per caso o indicati nelle condizioni commerciali applicabili.
        </p>
      </div>

      <div class="legalNotice">
        Per velocizzare l’assistenza è utile indicare email account, nome cantina, lotto o slug QR coinvolto,
        descrizione del problema e screenshot se disponibili.
      </div>

      """ + LEGAL_STYLE + """
    </section>
    """

    return HTMLResponse(page_public(
        title="QRFACILE · Supporto e assistenza",
        subtitle="Supporto",
        body_html=body,
        actions_html=_actions(),
    ))

