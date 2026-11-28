from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from qrfacile_app.ui_shell import page_public

router = APIRouter()


_CHOOSER_SOON = '<span class="chooserSoon">In arrivo</span>'
_WINE_GUIDE_PREVIEW = """
      <div class="chooserGuide">
        <svg viewBox="0 0 28 28" width="28" height="28" aria-hidden="true" focusable="false">
          <rect x="2" y="4" width="24" height="17" rx="4" fill="none" stroke="currentColor" stroke-width="2"/>
          <path d="m12 8 6 4.5-6 4.5z" fill="currentColor"/>
          <path d="M10 25h8m-4-4v4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <div>
          <strong>Guida video Wine</strong>
          <span>Dal primo accesso al QR, passo passo.</span>
          <small>In preparazione</small>
        </div>
      </div>
"""


def _chooser_card(
    vignette: str,
    title: str,
    text: str,
    footer: str,
    *,
    active: bool = False,
    guide: str = "",
) -> str:
    classes = "chooserCard active" if active else "chooserCard"
    return (
        f'<article class="{classes}"><div class="chooserArt" aria-hidden="true">'
        f'<img src="/static/module-vignettes/{vignette}.svg" alt="" width="160" height="92"></div>'
        f'<h2>{title}</h2><p>{text}</p><div class="chooserFooter">{footer}</div>{guide}</article>'
    )


def _chooser_discovery(path: str, module: str) -> str:
    return _CHOOSER_SOON + f'<a class="btn" href="{path}" aria-label="Scopri {module}">Scopri</a>'


def _module_chooser(link_on: bool) -> str:
    """One entry point per module, before any explanatory content."""
    link_footer = (
        '<span class="chooserFree">3 QR gratis</span>'
        '<a class="btn btn-primary" href="/register-business">Inizia</a>'
        if link_on
        else _chooser_discovery("/link", "Link")
    )
    cards = [
        _chooser_card("wine", "Ho una cantina",
                      "Etichette digitali del vino, senza canone annuale.",
                      '<span class="chooserFree">3 QR gratis</span>'
                      '<a class="btn btn-primary" href="/register-winery" aria-label="Inizia con Wine">Inizia</a>'
                      '<a class="btn" href="/wine">Scopri Wine</a>',
                      active=True, guide=_WINE_GUIDE_PREVIEW),
        _chooser_card("link", "Ho un'attività",
                      "Un QR per il tuo sito, un PDF o i tuoi contatti.",
                      link_footer, active=link_on),
        _chooser_card("menu", "Ho un ristorante", "Menu digitale aggiornabile in più lingue.",
                      _chooser_discovery("/menu", "Menu")),
        _chooser_card("quiz", "Quiz e formazione", "Domande e percorsi da un QR.",
                      _chooser_discovery("/quiz", "Quiz e formazione")),
        _chooser_card("warehouse", "Magazzino", "Schede e movimenti di prodotti e materiali.",
                      _chooser_discovery("/warehouse", "Magazzino")),
        _chooser_card("events", "Eventi", "Programmi, iscrizioni e votazioni.",
                      _chooser_discovery("/events", "Eventi")),
    ]
    return f"""
      <section class="moduleChooser" id="scegli" aria-labelledby="scegli-title">
        <div class="chooserHeading" id="moduli">
          <p class="chooserEyebrow">Piattaforma QR modulare</p>
          <h1 id="scegli-title">Cosa vuoi fare con il tuo QR?</h1>
          <p class="chooserLead">Scegli il modulo adatto alla tua attività.</p>
        </div>
        <div class="chooserGrid">{''.join(cards)}</div>
        <style>
          .moduleChooser {{
            padding:clamp(14px,3vw,28px);
            border:1px solid #d5e5e5;
            border-radius:24px;
            background:linear-gradient(135deg,#eff9f7,#f8fafc 68%);
          }}
          .chooserHeading {{ margin:0 0 18px; }}
          .chooserEyebrow {{
            margin:0 0 5px; color:#0f766e; font-size:.78rem; font-weight:850;
            letter-spacing:.06em; text-transform:uppercase;
          }}
          .chooserHeading h1 {{
            margin:0; color:#0f172a; font-size:clamp(1.65rem,3.1vw,4rem);
            line-height:1.12; letter-spacing:-.025em; overflow-wrap:anywhere;
          }}
          .chooserLead {{ color:#334155; margin:7px 0 0; line-height:1.45; }}
          .chooserGrid {{
            display:grid; gap:clamp(10px,1.1vw,24px);
            grid-template-columns:repeat(3,minmax(0,1fr));
          }}
          .chooserCard {{
            background:#fff; border:1px solid #d5e5e5; border-radius:16px;
            padding:clamp(12px,1.1vw,24px); display:flex; flex-direction:column; gap:9px;
          }}
          .chooserCard.active {{ border-color:#0f766e; background:#f0fdfa; }}
          .chooserCard h2 {{ margin:0; font-size:clamp(1rem,1.25vw,1.6rem); line-height:1.2; overflow-wrap:anywhere; }}
          .chooserArt {{
            position:relative; flex:none; height:clamp(55px,5.2vw,84px); overflow:hidden;
            border-radius:12px; background:linear-gradient(125deg,#f8fafc,#eef6f5);
          }}
          .chooserArt img {{
            position:absolute; inset:0; display:block; width:100%; height:100%; object-fit:contain;
          }}
          .chooserCard p {{
            margin:0; max-width:48ch; color:#334155; font-size:clamp(.94rem,1vw,1.15rem); line-height:1.4; flex:1;
          }}
          .chooserFooter {{ display:flex; gap:6px 8px; align-items:center; flex-wrap:wrap; }}
          .chooserFooter .btn {{ width:auto; min-height:44px; padding:7px 11px; font-size:.94rem; }}
          .chooserSoon, .chooserFree {{
            font-weight:800; border-radius:999px; padding:4px 8px; font-size:.8rem;
          }}
          .chooserSoon {{ color:#78350f; background:#fef3c7; }}
          .chooserFree {{ color:#115e59; background:#ccfbf1; }}
          .chooserGuide {{
            display:flex; gap:9px; align-items:flex-start; padding:10px;
            border:1px solid #90c9bd; border-radius:11px;
            background:#e3f6f1; color:#134e4a;
          }}
          .chooserGuide svg {{ flex:none; }}
          .chooserGuide strong,
          .chooserGuide span,
          .chooserGuide small {{ display:block; }}
          .chooserGuide strong {{ font-size:.94rem; line-height:1.25; }}
          .chooserGuide span {{ margin-top:3px; font-size:.82rem; line-height:1.35; }}
          .chooserGuide small {{ margin-top:4px; font-size:.76rem; font-weight:750; }}
          @media(min-width:1550px) {{
            .chooserGrid {{ grid-template-columns:repeat(6,minmax(0,1fr)); }}
          }}
          @media(max-width:850px) {{
            .chooserGrid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
          }}
          @media(max-width:560px) {{
            .chooserGrid {{ gap:8px; }}
            .chooserCard {{ padding:10px; gap:6px; }}
            .chooserCard p {{ font-size:.88rem; }}
            .chooserGuide {{ padding:8px; }}
            .chooserGuide svg {{ display:none; }}
          }}
          @media(max-width:350px) {{
            .chooserGrid {{ grid-template-columns:minmax(0,1fr); }}
          }}
        </style>
      </section>
    """


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    actions = """
    <a class="btn" href="/pricing">Prezzi</a>
    <a class="btn" href="/login">Accedi</a>
    <a class="btn btn-primary" href="#scegli">Scegli il tuo QR</a>
    """

    body = """
    <div class="modularHome">
      {module_chooser}

      <section class="moduleIntro" aria-labelledby="come-funziona-title">
        <h2 id="come-funziona-title">Stampi il QR una volta. Lo aggiorni quando vuoi.</h2>
        <p>Gestisci il contenuto dal tuo pannello, senza cambiare il codice che hai già stampato.</p>
        <div class="moduleActiveGrid">
          <div class="moduleFeature">
            <b>Contenuti aggiornabili</b>
            <span>Il codice rimanda a una pagina pubblica che puoi modificare.</span>
          </div>
          <div class="moduleFeature">
            <b>Pannello riservato</b>
            <span>Chi scansiona il QR vede la pagina pubblica, non il tuo pannello di gestione.</span>
          </div>
          <div class="moduleFeature">
            <b>Pronto da stampare</b>
            <span>Scarica il codice per etichette, confezioni o materiali promozionali.</span>
          </div>
        </div>
      </section>

      <style>
        .publicWrap.publicWrapWide {
          width:100%;
          max-width:none;
          padding-inline:clamp(12px,2.5vw,64px);
        }

        .publicWrapWide .publicMain { margin-top:clamp(12px,1.8vw,24px); }

        .moduleIntro {
          margin:26px 0 0;
          padding:clamp(16px,3vw,26px);
          border:1px solid #dce5e6;
          border-radius:22px;
          background:#fff;
        }

        .moduleIntro h2 {
          margin:0;
          font-size:clamp(22px,3vw,30px);
          line-height:1.2;
          color:#0f172a;
        }

        .moduleIntro p,
        .moduleFeature span { color:#475569; line-height:1.5; }

        .moduleIntro p { max-width:68ch; }

        .moduleActiveGrid {
          margin-top:16px;
          display:grid;
          grid-template-columns:repeat(auto-fit,minmax(min(100%,235px),1fr));
          gap:12px;
        }

        .moduleFeature {
          padding:14px;
          border:1px solid #dce5e6;
          border-radius:14px;
          background:#f8fafc;
        }

        .moduleFeature b,
        .moduleFeature span { display:block; }

        .moduleFeature span { margin-top:4px; font-size:14px; }
      </style>
    </div>
    """

    # QRFacile Link is not released yet: its tile shows "In arrivo".
    body = body.replace("{module_chooser}", _module_chooser(False))

    return HTMLResponse(page_public(
        title="QRFACILE · Piattaforma QR modulare",
        subtitle="Home",
        body_html=body,
        actions_html=actions,
        description="Scegli il QR adatto alla tua attività. Con QRFacile Wine crei etichette digitali per il vino e scarichi il QR per la stampa.",
        canonical_path="/",
        wide_layout=True,
        structured_data={
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "Enolab S.r.l.",
            "brand": {"@type": "Brand", "name": "QRFACILE"},
            "url": "https://www.qrfacile.it/",
            "email": "info@enolab.it",
            "vatID": "IT01413300623",
        },
    ))


@router.get("/wine", response_class=HTMLResponse)
def wine_home(request: Request):
    actions = """
    <a class="btn" href="/">QRFACILE</a>
    <a class="btn" href="/demo/public-label">Demo Wine</a>
    <a class="btn" href="/login">Accedi</a>
    <a class="btn" href="/register-studio">Studi Grafici</a>
    <a class="btn btn-primary" href="/register-winery">Registrati come Cantina</a>
    """

    body = """
    <section class="modularHome">
      <div class="moduleHero wineHero">
        <div class="moduleHeroOverlay">
          <div class="moduleEyebrow">Modulo attivo</div>
          <h1>QRFACILE Wine</h1>
          <p>
            Il modulo per cantine e studi grafici che devono gestire QR vino,
            etichettatura digitale, dati di compliance e file pronti per la stampa.
          </p>
          <div class="moduleHeroActions">
            <a class="btn btn-primary" href="/register-winery">Registrati come Cantina</a>
            <a class="btn" href="/login">Accedi</a>
            <a class="btn" href="/register-studio">Studi Grafici</a>
            <a class="btn" href="/demo/public-label">Vedi demo</a>
          </div>
          <div class="moduleHeroBadges">
            <span>Lotti vino</span>
            <span>Etichetta digitale</span>
            <span>Studi grafici collegati</span>
            <span>Export QR</span>
          </div>
        </div>
      </div>

      <section class="moduleIntro">
        <div>
          <div class="moduleEyebrow">Wine Compliance</div>
          <h2>Dal lotto al QR stampabile.</h2>
          <p>
            QRFACILE Wine aiuta la cantina a creare lotti, compilare ingredienti,
            allergeni, valori nutrizionali e riciclabilita, gestire immagini fronte/retro
            e pubblicare pagine QR vino solo quando i dati sono pronti.
          </p>
        </div>
        <div class="moduleStatus active">Attivo</div>
      </section>

      <section class="moduleActiveGrid">
        <div class="moduleFeature">
          <b>Per cantine</b>
          <span>Dashboard lotti, controlli di completezza, pubblicazione e gestione del QR nel tempo.</span>
        </div>
        <div class="moduleFeature">
          <b>Per studi grafici</b>
          <span>Collaborazione con cantine collegate, gestione operativa della grafica e download file.</span>
        </div>
        <div class="moduleFeature">
          <b>Etichettatura digitale</b>
          <span>Pagina pubblica pulita per informazioni obbligatorie e contenuti collegati al vino.</span>
        </div>
        <div class="moduleFeature">
          <b>QR per stampa</b>
          <span>Export PNG, SVG, PDF e ZIP per tipografia, retro etichetta e materiali commerciali.</span>
        </div>
      </section>

      <section class="moduleAudience">
        <div>
          <h2>Cantina</h2>
          <p>
            Crea account, prepara i primi lotti e mantieni il controllo su dati,
            pubblicazione e collaborazione con eventuali studi esterni.
          </p>
          <a class="btn btn-primary" href="/register-winery">Registrati come Cantina</a>
        </div>
        <div>
          <h2>Studio grafico</h2>
          <p>
            Lavora sui clienti collegati, prepara immagini e file QR, senza sostituirti
            alla cantina nelle decisioni normative.
          </p>
          <a class="btn" href="/register-studio">Registrati come Studio</a>
        </div>
      </section>

      <section class="winePlans">
        <div class="moduleCatalogHead">
          <div class="moduleEyebrow">Piani QRFACILE Wine</div>
          <h2>Paghi i QR quando ti servono, senza canone annuale.</h2>
          <p>
            Acquisti crediti utilizzabili entro 12 mesi. Nessun abbonamento obbligatorio,
            nessun rinnovo automatico: ogni QR creato resta online e modificabile per
            i 10 o 25 anni scelti, anche senza altri acquisti.
            Lo stesso QR può essere stampato su tutte le bottiglie della medesima referenza;
            un vino, un’annata o un lotto differente richiede un nuovo QR.
          </p>
        </div>

        <div class="winePlanGrid">
          <div class="winePlan">
            <b>3 crediti gratuiti</b>
            <span>Per iniziare a provare i primi QR vino con un account Cantina.</span>
          </div>
          <div class="winePlan">
            <b>QR vino 10 anni</b>
            <span>1 credito Wine per una referenza, su tutte le sue bottiglie.</span>
          </div>
          <div class="winePlan">
            <b>QR vino 25 anni</b>
            <span>2 crediti Wine per una referenza, su tutte le sue bottiglie.</span>
          </div>
          <div class="winePlan">
            <b>Pacchetti crediti</b>
            <span>Crediti validi 12 mesi per creare nuovi QR; nessun canone sui QR già creati.</span>
          </div>
        </div>

        <div class="winePlanActions">
          <a class="btn btn-primary" href="/pricing">Vedi pricing Wine</a>
          <a class="btn" href="/register-winery">Registrati come Cantina</a>
          <a class="btn" href="/login">Accedi</a>
          <a class="btn" href="/register-studio">Studi Grafici</a>
        </div>
      </section>

      <section class="moduleFinal">
        <div>
          <div class="moduleEyebrow">Accesso Wine</div>
          <h2>Porta i tuoi QR vino su pagine sempre aggiornabili.</h2>
          <p>Registrati come cantina oppure accedi se hai già un account QRFACILE.</p>
        </div>
        <div class="moduleFinalActions">
          <a class="btn btn-primary" href="/register-winery">Registrati come Cantina</a>
          <a class="btn" href="/login">Accedi</a>
          <a class="btn" href="/register-studio">Studi Grafici</a>
        </div>
      </section>

      <style>
        .modularHome {
          max-width:1180px;
          margin:0 auto;
        }

        .moduleHero {
          min-height:560px;
          border-radius:30px;
          overflow:hidden;
          position:relative;
          display:flex;
          align-items:flex-end;
          background:
            linear-gradient(90deg,rgba(8,47,73,.90),rgba(15,118,110,.62),rgba(255,255,255,.06)),
            url('/static/qr3d.png') center right / contain no-repeat,
            linear-gradient(135deg,#0f766e,#f8fafc);
          box-shadow:0 28px 90px rgba(2,8,23,.14);
        }

        .wineHero {
          background:
            linear-gradient(90deg,rgba(20,83,45,.90),rgba(15,118,110,.64),rgba(255,255,255,.08)),
            url('/static/qr3d.png') center right / contain no-repeat,
            linear-gradient(135deg,#14532d,#f8fafc);
        }

        .moduleHeroOverlay {
          width:100%;
          min-height:560px;
          padding:44px;
          display:flex;
          flex-direction:column;
          justify-content:flex-end;
          background:linear-gradient(180deg,rgba(2,8,23,.08),rgba(2,8,23,.42));
        }

        .moduleEyebrow {
          display:inline-flex;
          width:max-content;
          padding:8px 13px;
          border-radius:999px;
          background:rgba(236,253,245,.92);
          color:#0f766e;
          font-size:12px;
          font-weight:950;
          letter-spacing:.04em;
          text-transform:uppercase;
        }

        .moduleHero h1 {
          margin-top:16px;
          margin-bottom:0;
          font-size:clamp(48px,8vw,96px);
          line-height:.95;
          font-weight:950;
          letter-spacing:0;
          color:white;
        }

        .moduleHero p {
          margin-top:18px;
          max-width:720px;
          color:#ecfeff;
          font-size:18px;
          font-weight:720;
          line-height:1.55;
        }

        .moduleHeroActions,
        .moduleFinalActions {
          margin-top:24px;
          display:flex;
          gap:12px;
          flex-wrap:wrap;
        }

        .moduleHeroBadges {
          margin-top:20px;
          display:flex;
          gap:9px;
          flex-wrap:wrap;
        }

        .moduleHeroBadges span {
          display:inline-flex;
          padding:8px 11px;
          border-radius:999px;
          background:rgba(255,255,255,.18);
          border:1px solid rgba(255,255,255,.28);
          color:white;
          font-size:12px;
          font-weight:900;
        }

        .moduleIntro,
        .moduleFeature,
        .moduleAudience > div,
        .moduleFinal {
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          background:rgba(255,255,255,.84);
          box-shadow:0 18px 55px rgba(2,8,23,.06);
        }

        .moduleIntro {
          margin-top:22px;
          padding:26px;
          display:grid;
          grid-template-columns:minmax(0,1fr) auto;
          gap:18px;
          align-items:start;
        }

        .moduleIntro h2,
        .moduleCatalogHead h2,
        .moduleAudience h2,
        .moduleFinal h2 {
          margin:10px 0 0;
          font-size:clamp(28px,4vw,46px);
          line-height:1.05;
          font-weight:950;
          letter-spacing:0;
          color:#0f172a;
        }

        .moduleIntro p,
        .moduleCatalogHead p,
        .moduleAudience p,
        .moduleFinal p,
        .moduleFeature span {
          color:#475569;
          font-weight:730;
          line-height:1.55;
        }

        .moduleStatus {
          display:inline-flex;
          width:max-content;
          padding:7px 11px;
          border-radius:999px;
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
        }

        .moduleStatus.active {
          color:#0f766e;
          background:rgba(236,253,245,.95);
          border:1px solid rgba(20,184,166,.16);
        }

        .moduleActiveGrid {
          margin-top:18px;
          display:grid;
          grid-template-columns:repeat(4,minmax(0,1fr));
          gap:14px;
        }

        .moduleFeature {
          padding:20px;
        }

        .moduleFeature b {
          display:block;
          color:#0f172a;
          font-size:17px;
          font-weight:950;
        }

        .moduleFeature span {
          display:block;
          margin-top:8px;
          font-size:14px;
        }

        .moduleAudience {
          margin-top:22px;
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:16px;
        }

        .moduleAudience > div {
          padding:26px;
        }

        .moduleAudience .btn {
          margin-top:18px;
        }

        .winePlans {
          margin-top:28px;
        }

        .winePlanGrid {
          margin-top:18px;
          display:grid;
          grid-template-columns:repeat(4,minmax(0,1fr));
          gap:14px;
        }

        .winePlan {
          padding:20px;
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          background:rgba(255,255,255,.84);
          box-shadow:0 18px 55px rgba(2,8,23,.06);
        }

        .winePlan b {
          display:block;
          color:#0f172a;
          font-size:17px;
          font-weight:950;
        }

        .winePlan span {
          display:block;
          margin-top:8px;
          color:#475569;
          font-size:14px;
          font-weight:730;
          line-height:1.55;
        }

        .winePlanActions {
          margin-top:16px;
          display:flex;
          gap:12px;
          flex-wrap:wrap;
        }

        .moduleFinal {
          margin-top:24px;
          padding:28px;
          display:flex;
          justify-content:space-between;
          align-items:center;
          gap:20px;
          background:
            radial-gradient(circle at 0% 0%, rgba(191,245,230,.50), transparent 34%),
            rgba(255,255,255,.88);
        }

        @media(max-width:1050px) {
          .moduleActiveGrid,
          .moduleAudience,
          .moduleIntro,
          .winePlanGrid {
            grid-template-columns:1fr;
          }

          .moduleFinal {
            flex-direction:column;
            align-items:flex-start;
          }
        }

        @media(max-width:560px) {
          .moduleHero,
          .moduleHeroOverlay {
            min-height:620px;
          }

          .moduleHeroOverlay,
          .moduleIntro,
          .moduleAudience > div,
          .moduleFinal {
            padding:24px;
          }

          .moduleHeroActions .btn,
          .moduleFinalActions .btn {
            width:100%;
          }
        }
      </style>
    </section>
    """

    return HTMLResponse(page_public(
        title="QRFACILE Wine",
        subtitle="Wine",
        body_html=body,
        actions_html=actions,
        description="Etichetta digitale vino per cantine e studi grafici: ingredienti, allergeni, valori nutrizionali, riciclo, QR dinamico ed export per tipografia.",
        canonical_path="/wine",
        structured_data={
            "@context": "https://schema.org",
            "@type": "SoftwareApplication",
            "name": "QRFACILE Wine",
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "Web",
            "url": "https://www.qrfacile.it/wine",
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR", "description": "3 crediti iniziali gratuiti"},
            "provider": {"@type": "Organization", "name": "Enolab S.r.l."},
        },
    ))


@router.get("/link", response_class=HTMLResponse)
def link_home(request: Request):
    actions = """
    <a class="btn" href="/#moduli">Torna ai moduli</a>
    <a class="btn" href="/login">Accedi</a>
    <a class="btn btn-primary" href="/support">Richiedi informazioni</a>
    """

    body = """
    <section class="linkModule">
      <div class="linkHero">
        <div>
          <div class="linkStatus">In arrivo</div>
          <h1>QRFACILE Link</h1>
          <p>
            QR dinamici che puntano a link aggiornabili nel tempo. Preparato per
            campagne, contenuti digitali e destinazioni che possono cambiare senza
            ristampare il QR.
          </p>
          <div class="linkActions">
            <a class="btn btn-primary" href="/#moduli">Torna ai moduli</a>
            <a class="btn" href="/login">Accedi</a>
            <a class="btn" href="/support">Richiedi informazioni</a>
          </div>
        </div>
      </div>

      <section class="linkIntro">
        <div>
          <div class="linkEyebrow">Modulo Link Diretto</div>
          <h2>Un QR, destinazioni aggiornabili.</h2>
          <p>
            QRFACILE Link sarà pensato per chi vuole collegare un QR a contenuti
            digitali semplici, senza vincolarsi a una destinazione fissa stampata
            per sempre.
          </p>
        </div>
        <span>In arrivo</span>
      </section>

      <section class="linkUses">
        <div><b>Sito web</b><span>Porta clienti e visitatori verso una pagina aziendale o prodotto.</span></div>
        <div><b>WhatsApp</b><span>Apri una conversazione o un canale di contatto rapido.</span></div>
        <div><b>PDF</b><span>Condividi schede, listini, istruzioni o documenti aggiornabili.</span></div>
        <div><b>Cataloghi</b><span>Rimanda a collezioni, brochure o materiali commerciali.</span></div>
        <div><b>Social</b><span>Collega profili, pagine, contenuti e community.</span></div>
        <div><b>Campagne</b><span>Usa QR per materiali promozionali e iniziative temporanee.</span></div>
        <div><b>Eventi</b><span>Rimanda a programmi, iscrizioni, mappe o contenuti dedicati.</span></div>
      </section>

      <section class="linkNote">
        <div>
          <div class="linkEyebrow">In arrivo</div>
          <h2>Il modulo non è ancora attivo.</h2>
          <p>
            QRFACILE Link sarà disponibile a breve, con prezzi e registrazione dedicati.
            Scrivici per sapere quando parte o per provarlo in anteprima.
          </p>
        </div>
        <div class="linkActions">
          <a class="btn btn-primary" href="/support">Richiedi informazioni</a>
          <a class="btn" href="/#moduli">Torna ai moduli</a>
        </div>
      </section>

      <style>
        .linkModule {
          max-width:1180px;
          margin:0 auto;
        }

        .linkHero {
          min-height:500px;
          border-radius:30px;
          padding:44px;
          display:flex;
          align-items:flex-end;
          background:linear-gradient(135deg,#0f172a,#0f766e);
          box-shadow:0 28px 90px rgba(2,8,23,.14);
          overflow:hidden;
        }

        .linkHero h1 {
          margin:16px 0 0;
          color:white;
          font-size:clamp(46px,8vw,92px);
          line-height:.95;
          letter-spacing:0;
          font-weight:950;
        }

        .linkHero p {
          max-width:720px;
          margin-top:18px;
          color:#ecfeff;
          font-size:18px;
          line-height:1.55;
          font-weight:720;
        }

        .linkStatus,
        .linkEyebrow {
          display:inline-flex;
          width:max-content;
          padding:8px 13px;
          border-radius:999px;
          background:rgba(255,247,237,.96);
          color:#7c2d12;
          border:1px solid rgba(251,146,60,.20);
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
        }

        .linkActions {
          margin-top:24px;
          display:flex;
          gap:12px;
          flex-wrap:wrap;
        }

        .linkIntro,
        .linkUses div,
        .linkNote {
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          background:rgba(255,255,255,.84);
          box-shadow:0 18px 55px rgba(2,8,23,.06);
        }

        .linkIntro {
          margin-top:22px;
          padding:26px;
          display:grid;
          grid-template-columns:minmax(0,1fr) auto;
          gap:18px;
          align-items:start;
        }

        .linkIntro > span {
          display:inline-flex;
          padding:7px 11px;
          border-radius:999px;
          color:#7c2d12;
          background:rgba(255,247,237,.96);
          border:1px solid rgba(251,146,60,.20);
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
        }

        .linkIntro h2,
        .linkNote h2 {
          margin:10px 0 0;
          color:#0f172a;
          font-size:clamp(28px,4vw,46px);
          line-height:1.05;
          letter-spacing:0;
          font-weight:950;
        }

        .linkIntro p,
        .linkNote p,
        .linkUses span {
          color:#475569;
          font-weight:730;
          line-height:1.55;
        }

        .linkUses {
          margin-top:18px;
          display:grid;
          grid-template-columns:repeat(4,minmax(0,1fr));
          gap:14px;
        }

        .linkUses div {
          padding:20px;
        }

        .linkUses b {
          display:block;
          color:#0f172a;
          font-size:17px;
          font-weight:950;
        }

        .linkUses span {
          display:block;
          margin-top:8px;
          font-size:14px;
        }

        .linkNote {
          margin-top:22px;
          padding:28px;
          display:flex;
          justify-content:space-between;
          gap:20px;
          align-items:center;
        }

        @media(max-width:980px) {
          .linkIntro,
          .linkUses {
            grid-template-columns:1fr;
          }

          .linkNote {
            flex-direction:column;
            align-items:flex-start;
          }
        }

        @media(max-width:560px) {
          .linkHero,
          .linkIntro,
          .linkNote {
            padding:24px;
          }

          .linkActions .btn {
            width:100%;
          }
        }
      </style>
    </section>
    """

    return HTMLResponse(page_public(
        title="QRFACILE Link",
        subtitle="Link",
        body_html=body,
        actions_html=actions,
    ))


def _coming_soon_module_page(
    *,
    title: str,
    subtitle: str,
    description: str,
    module_label: str,
    intro_title: str,
    intro_copy: str,
    examples: list[tuple[str, str]],
):
    actions = """
    <a class="btn" href="/#moduli">Torna ai moduli</a>
    <a class="btn" href="/login">Accedi</a>
    <a class="btn btn-primary" href="/support">Richiedi informazioni</a>
    """
    example_cards = "\n".join(
        f"<div><b>{name}</b><span>{copy}</span></div>"
        for name, copy in examples
    )

    body = f"""
    <section class="futureModule">
      <div class="futureHero">
        <div>
          <div class="futureStatus">In arrivo</div>
          <h1>{title}</h1>
          <p>{description}</p>
          <div class="futureActions">
            <a class="btn btn-primary" href="/#moduli">Torna ai moduli</a>
            <a class="btn" href="/login">Accedi</a>
            <a class="btn" href="/support">Richiedi informazioni</a>
          </div>
        </div>
      </div>

      <section class="futureIntro">
        <div>
          <div class="futureEyebrow">{module_label}</div>
          <h2>{intro_title}</h2>
          <p>{intro_copy}</p>
        </div>
        <span>In arrivo</span>
      </section>

      <section class="futureUses">
        {example_cards}
      </section>

      <section class="futureNote">
        <div>
          <div class="futureEyebrow">Modulo in preparazione</div>
          <h2>Nessuna attivazione pubblica diretta.</h2>
          <p>
            Questo modulo non ha ancora pricing reale, crediti dedicati o un
            onboarding pubblico specifico. Puoi richiedere informazioni per
            valutare il caso d'uso più adatto.
          </p>
        </div>
        <div class="futureActions">
          <a class="btn btn-primary" href="/support">Richiedi informazioni</a>
          <a class="btn" href="/#moduli">Torna ai moduli</a>
        </div>
      </section>

      <style>
        .futureModule {{
          max-width:1180px;
          margin:0 auto;
        }}

        .futureHero {{
          min-height:480px;
          border-radius:30px;
          padding:44px;
          display:flex;
          align-items:flex-end;
          background:linear-gradient(135deg,#0f172a,#0f766e);
          box-shadow:0 28px 90px rgba(2,8,23,.14);
          overflow:hidden;
        }}

        .futureHero h1 {{
          margin:16px 0 0;
          color:white;
          font-size:clamp(44px,7vw,86px);
          line-height:.96;
          letter-spacing:0;
          font-weight:950;
        }}

        .futureHero p {{
          max-width:720px;
          margin-top:18px;
          color:#ecfeff;
          font-size:18px;
          line-height:1.55;
          font-weight:720;
        }}

        .futureStatus,
        .futureEyebrow {{
          display:inline-flex;
          width:max-content;
          padding:8px 13px;
          border-radius:999px;
          background:rgba(255,247,237,.96);
          color:#7c2d12;
          border:1px solid rgba(251,146,60,.20);
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
        }}

        .futureActions {{
          margin-top:24px;
          display:flex;
          gap:12px;
          flex-wrap:wrap;
        }}

        .futureIntro,
        .futureUses div,
        .futureNote {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          background:rgba(255,255,255,.84);
          box-shadow:0 18px 55px rgba(2,8,23,.06);
        }}

        .futureIntro {{
          margin-top:22px;
          padding:26px;
          display:grid;
          grid-template-columns:minmax(0,1fr) auto;
          gap:18px;
          align-items:start;
        }}

        .futureIntro > span {{
          display:inline-flex;
          padding:7px 11px;
          border-radius:999px;
          color:#7c2d12;
          background:rgba(255,247,237,.96);
          border:1px solid rgba(251,146,60,.20);
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
        }}

        .futureIntro h2,
        .futureNote h2 {{
          margin:10px 0 0;
          color:#0f172a;
          font-size:clamp(28px,4vw,46px);
          line-height:1.05;
          letter-spacing:0;
          font-weight:950;
        }}

        .futureIntro p,
        .futureNote p,
        .futureUses span {{
          color:#475569;
          font-weight:730;
          line-height:1.55;
        }}

        .futureUses {{
          margin-top:18px;
          display:grid;
          grid-template-columns:repeat(3,minmax(0,1fr));
          gap:14px;
        }}

        .futureUses div {{
          padding:20px;
        }}

        .futureUses b {{
          display:block;
          color:#0f172a;
          font-size:17px;
          font-weight:950;
        }}

        .futureUses span {{
          display:block;
          margin-top:8px;
          font-size:14px;
        }}

        .futureNote {{
          margin-top:22px;
          padding:28px;
          display:flex;
          justify-content:space-between;
          gap:20px;
          align-items:center;
        }}

        @media(max-width:980px) {{
          .futureIntro,
          .futureUses {{
            grid-template-columns:1fr;
          }}

          .futureNote {{
            flex-direction:column;
            align-items:flex-start;
          }}
        }}

        @media(max-width:560px) {{
          .futureHero,
          .futureIntro,
          .futureNote {{
            padding:24px;
          }}

          .futureActions .btn {{
            width:100%;
          }}
        }}
      </style>
    </section>
    """

    return HTMLResponse(page_public(
        title=title,
        subtitle=subtitle,
        body_html=body,
        actions_html=actions,
    ))


@router.get("/menu", response_class=HTMLResponse)
def menu_home(request: Request):
    return _coming_soon_module_page(
        title="QRFACILE Menu",
        subtitle="Menu",
        description=(
            "Menu digitali aggiornabili per ristoranti, bar, hotel e locali che "
            "vogliono pubblicare carte sempre consultabili da QR."
        ),
        module_label="Modulo Menu Ristorante",
        intro_title="Carte digitali pronte per tavoli, sale e asporto.",
        intro_copy=(
            "QRFACILE Menu sarà pensato per gestire menu, listini, allergeni, "
            "proposte stagionali e contenuti collegati senza ristampare materiali."
        ),
        examples=[
            ("Menu sala", "Carte consultabili al tavolo tramite QR."),
            ("Asporto", "Listini e proposte per clienti fuori sede."),
            ("Carta vini", "Sezioni dedicate a bottiglie, calici e abbinamenti."),
            ("Allergeni", "Informazioni aggiornabili e facili da consultare."),
            ("Menu stagionali", "Proposte temporanee senza ristampe continue."),
            ("Hotel e locali", "Informazioni food, servizi e offerte del giorno."),
        ],
    )


@router.get("/quiz", response_class=HTMLResponse)
def quiz_home(request: Request):
    return _coming_soon_module_page(
        title="QRFACILE Quiz",
        subtitle="Quiz",
        description=(
            "QR per quiz, formazione, raccolta risposte e percorsi guidati da "
            "usare in aula, in azienda, durante eventi o su materiali stampati."
        ),
        module_label="Modulo Quiz/Formazione",
        intro_title="Coinvolgi persone e raccogli risposte da QR.",
        intro_copy=(
            "QRFACILE Quiz sarà pensato per creare esperienze formative e "
            "interattive accessibili con un QR, con contenuti aggiornabili nel tempo."
        ),
        examples=[
            ("Formazione", "Percorsi didattici e materiali di supporto."),
            ("Quiz", "Domande, verifiche rapide e contenuti interattivi."),
            ("Feedback", "Raccolta risposte dopo eventi, corsi o visite."),
            ("Onboarding", "Guide e controlli per nuovi collaboratori."),
            ("Scuole", "Attività e approfondimenti collegati a materiali fisici."),
            ("Campagne", "Esperienze educative o promozionali misurabili."),
        ],
    )


@router.get("/warehouse", response_class=HTMLResponse)
def warehouse_home(request: Request):
    return _coming_soon_module_page(
        title="QRFACILE Magazzino",
        subtitle="Magazzino",
        description=(
            "QR per schede operative, prodotti, scaffali, materiali e inventari "
            "leggeri con informazioni consultabili e aggiornabili."
        ),
        module_label="Modulo QR Magazzino",
        intro_title="Informazioni operative dove servono.",
        intro_copy=(
            "QRFACILE Magazzino sarà pensato per collegare oggetti, aree e "
            "materiali a pagine pratiche, istruzioni, schede e riferimenti rapidi."
        ),
        examples=[
            ("Scaffali", "QR per ubicazioni, categorie e istruzioni di reparto."),
            ("Prodotti", "Schede tecniche e dati consultabili dal personale."),
            ("Materiali", "Documenti, manuali e procedure sempre raggiungibili."),
            ("Inventari", "Supporto leggero per controlli e ricognizioni."),
            ("Manutenzione", "Istruzioni e riferimenti collegati ad attrezzature."),
            ("Logistica", "Informazioni rapide per movimentazione e preparazione."),
        ],
    )


@router.get("/events", response_class=HTMLResponse)
def events_home(request: Request):
    return _coming_soon_module_page(
        title="QRFACILE Eventi",
        subtitle="Eventi",
        description=(
            "QR per eventi, votazioni, raccolta preferenze, programmi, accessi "
            "rapidi e feedback aggiornabili nel tempo."
        ),
        module_label="Modulo Eventi/Votazioni",
        intro_title="Pagine QR per partecipanti, pubblico e staff.",
        intro_copy=(
            "QRFACILE Eventi sarà pensato per gestire contenuti pubblici e "
            "interazioni leggere durante manifestazioni, incontri e iniziative."
        ),
        examples=[
            ("Programmi", "Agenda, orari e informazioni sempre aggiornabili."),
            ("Votazioni", "Raccolta preferenze e scelte dal pubblico."),
            ("Feedback", "Questionari rapidi dopo sessioni o attività."),
            ("Mappe", "Indicazioni, sale, stand e punti di interesse."),
            ("Accessi rapidi", "Link utili per partecipanti e organizzatori."),
            ("Campagne evento", "Contenuti temporanei collegati a materiali stampati."),
        ],
    )


@router.get("/demo/public-label", response_class=HTMLResponse)
def demo_public_label(request: Request):
    html = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo pagina QR · QRFACILE</title>
<meta name="robots" content="noindex,nofollow">
<style>
* { box-sizing:border-box; }
body {
  margin:0;
  font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  background:
    radial-gradient(circle at 0% 0%, rgba(20,184,166,.15), transparent 30%),
    radial-gradient(circle at 100% 0%, rgba(14,165,233,.12), transparent 30%),
    linear-gradient(180deg,#f8fafc,#f3fbf8);
  color:#111827;
}

.demoWatermark {
  position:fixed;
  inset:0;
  z-index:0;
  pointer-events:none;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:clamp(80px,18vw,210px);
  font-weight:950;
  letter-spacing:.08em;
  color:#0f766e;
  opacity:.045;
  transform:rotate(-22deg);
}
.page {
  position:relative;
  z-index:1;
  max-width:1040px;
  margin:0 auto;
  padding:18px;
}

.demoTopbar {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  margin:0 0 18px;
  padding:12px;
  border:1px solid #e5e7eb;
  border-radius:24px;
  background:rgba(255,255,255,.78);
  box-shadow:0 18px 45px rgba(2,8,23,.055);
}

.demoTopActions {
  display:flex;
  gap:10px;
  align-items:center;
  justify-content:flex-end;
  flex-wrap:wrap;
}

.header {
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap:14px;
  margin-bottom:14px;
}
.brandMini {
  display:flex;
  align-items:center;
  gap:10px;
}
.statusBadge {
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding:9px 12px;
  border-radius:999px;
  border:1px solid #e5e7eb;
  background:rgba(255,255,255,.72);
  color:#667085;
  font-size:12px;
  font-weight:900;
}
.statusBadge::before {
  content:"";
  width:9px;
  height:9px;
  border-radius:999px;
  background:#0f766e;
  box-shadow:0 0 0 4px rgba(20,184,166,.13);
}
.hero {
  border:1px solid #e5e7eb;
  border-radius:30px;
  background:
    radial-gradient(circle at 14% 12%, rgba(20,184,166,.17), transparent 30%),
    radial-gradient(circle at 90% 0%, rgba(14,165,233,.14), transparent 34%),
    linear-gradient(135deg, rgba(255,255,255,.98), rgba(255,255,255,.90));
  box-shadow:0 28px 90px rgba(2,8,23,.10);
  padding:28px;
  overflow:hidden;
}

.demoHero {
  position:relative;
}

.demoHero::after {
  content:"";
  position:absolute;
  right:-70px;
  bottom:-110px;
  width:300px;
  height:300px;
  border-radius:999px;
  background:rgba(20,184,166,.08);
}

.demoHeroTop {
  position:relative;
  z-index:1;
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  gap:18px;
  flex-wrap:wrap;
}

.demoTagBox {
  border:1px solid #dbece6;
  background:rgba(255,255,255,.78);
  border-radius:20px;
  padding:14px 16px;
  min-width:210px;
  box-shadow:0 14px 35px rgba(2,8,23,.05);
}

.demoTagBox span {
  display:block;
  color:#0f766e;
  font-size:11px;
  font-weight:950;
  text-transform:uppercase;
  letter-spacing:.08em;
}

.demoTagBox b {
  display:block;
  margin-top:5px;
  color:#0f172a;
  font-size:16px;
  line-height:1.2;
}
.demoWineryLogo {
  max-width:270px;
  width:100%;
  height:auto;
  display:block;
  margin-bottom:16px;
  filter:drop-shadow(0 14px 28px rgba(2,8,23,.08));
}

.demoLabels {
  margin-top:16px;
  border:1px solid #dbece6;
  border-radius:28px;
  background:
    radial-gradient(circle at 0% 0%, rgba(191,245,230,.34), transparent 34%),
    rgba(255,255,255,.90);
  box-shadow:0 24px 70px rgba(2,8,23,.08);
  padding:20px;
}

.demoLabelsHead {
  margin-bottom:14px;
}

.demoLabelsTitle {
  font-size:22px;
  font-weight:950;
  letter-spacing:-.35px;
}

.demoLabelsSub {
  margin-top:5px;
  color:#667085;
  font-size:13px;
  font-weight:760;
  line-height:1.45;
  max-width:760px;
}

.demoLabelsGrid {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:14px;
}

.demoLabelCard {
  border:1px solid #e5e7eb;
  border-radius:24px;
  background:#f9fafb;
  overflow:hidden;
  box-shadow:0 18px 50px rgba(2,8,23,.07);
}

.demoLabelTitle {
  padding:11px 13px;
  color:#667085;
  font-size:11px;
  font-weight:950;
  text-transform:uppercase;
  letter-spacing:.07em;
  border-bottom:1px solid #e5e7eb;
}

.demoLabelCard img {
  width:100%;
  max-height:690px;
  object-fit:contain;
  display:block;
  background:
    linear-gradient(45deg, rgba(15,118,110,.03), rgba(14,165,233,.03)),
    #fff;
  padding:14px;
}
.eyebrow {
  display:inline-flex;
  padding:7px 11px;
  border-radius:999px;
  background:#ecfdf5;
  color:#0f766e;
  border:1px solid rgba(15,118,110,.12);
  font-size:11px;
  font-weight:950;
  letter-spacing:.08em;
  text-transform:uppercase;
}
.title {
  margin:14px 0 0;
  font-size:clamp(31px, 6vw, 54px);
  line-height:.98;
  font-weight:950;
  letter-spacing:-1.8px;
}
.subtitle {
  margin-top:13px;
  color:#667085;
  font-size:15px;
  font-weight:720;
  line-height:1.55;
}
.metaGrid {
  margin-top:18px;
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:10px;
}
.metaItem {
  border:1px solid #e5e7eb;
  background:rgba(255,255,255,.72);
  border-radius:18px;
  padding:12px;
}
.metaItem span {
  display:block;
  color:#667085;
  font-size:11px;
  font-weight:950;
  text-transform:uppercase;
  letter-spacing:.06em;
}
.metaItem b {
  display:block;
  margin-top:5px;
  font-size:15px;
  font-weight:920;
}
.demoValueBox {
  margin-top:16px;
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:14px;
}

.demoValueBox div {
  border:1px solid rgba(20,184,166,.16);
  border-radius:22px;
  background:rgba(236,253,245,.74);
  padding:16px;
}

.demoValueBox span {
  display:block;
  color:#0f766e;
  font-size:11px;
  font-weight:950;
  text-transform:uppercase;
  letter-spacing:.08em;
}

.demoValueBox b {
  display:block;
  margin-top:7px;
  color:#0f172a;
  font-size:14px;
  line-height:1.45;
  font-weight:850;
}

.contentGrid {
  margin-top:16px;
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:14px;
}
.infoCard {
  border:1px solid #e5e7eb;
  border-radius:24px;
  background:rgba(255,255,255,.86);
  box-shadow:0 14px 45px rgba(2,8,23,.055);
  padding:18px;
}
.infoCard.full { grid-column:1 / -1; }
.cardHead {
  display:flex;
  justify-content:space-between;
  gap:10px;
  margin-bottom:13px;
}
.cardTitle {
  font-size:18px;
  font-weight:950;
}
.cardSub {
  margin-top:3px;
  color:#667085;
  font-size:12px;
  font-weight:760;
}
.cardIcon {
  width:38px;
  height:38px;
  border-radius:15px;
  display:flex;
  align-items:center;
  justify-content:center;
  background:linear-gradient(135deg, rgba(20,184,166,.14), rgba(14,165,233,.11));
  border:1px solid #e5e7eb;
  font-size:18px;
}
.textValue {
  color:#334155;
  font-size:15px;
  line-height:1.65;
  font-weight:650;
}
.chips {
  display:flex;
  gap:8px;
  flex-wrap:wrap;
}
.chip {
  display:inline-flex;
  padding:9px 12px;
  border-radius:999px;
  border:1px solid rgba(15,118,110,.13);
  background:#ecfdf5;
  color:#0f766e;
  font-size:13px;
  font-weight:880;
}
.nutritionGrid {
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:10px;
}
.nutritionItem {
  border:1px solid #e5e7eb;
  border-radius:18px;
  background:#f9fafb;
  padding:13px;
}
.nutritionItem span {
  display:block;
  color:#667085;
  font-size:11px;
  font-weight:950;
  text-transform:uppercase;
  letter-spacing:.06em;
}
.nutritionItem b {
  display:block;
  margin-top:6px;
  font-size:14px;
  line-height:1.35;
  font-weight:920;
}
.recycleGrid {
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:10px;
}
.recycleItem {
  border:1px solid #e5e7eb;
  border-radius:20px;
  background:#f9fafb;
  padding:14px;
  position:relative;
  overflow:hidden;
}
.recycleItem::before {
  content:"";
  position:absolute;
  inset:0 auto 0 0;
  width:5px;
  background:#0f766e;
  opacity:.55;
}
.recycleTone-glass { background:linear-gradient(135deg, rgba(236,253,245,.88), rgba(255,255,255,.92)); }
.recycleTone-closure { background:linear-gradient(135deg, rgba(254,243,199,.72), rgba(255,255,255,.92)); }
.recycleTone-capsule { background:linear-gradient(135deg, rgba(239,246,255,.82), rgba(255,255,255,.92)); }
.recycleTone-paper { background:linear-gradient(135deg, rgba(250,250,249,.95), rgba(255,255,255,.92)); }
.recycleTone-box { background:linear-gradient(135deg, rgba(255,247,237,.86), rgba(255,255,255,.92)); }
.recycleTone-other { background:linear-gradient(135deg, rgba(245,243,255,.75), rgba(255,255,255,.92)); }
.recycleTop {
  display:flex;
  justify-content:space-between;
  gap:10px;
  align-items:flex-start;
  flex-wrap:wrap;
  position:relative;
  z-index:1;
}
.recycleNameWrap {
  display:flex;
  align-items:flex-start;
  gap:10px;
}
.recycleIcon {
  width:34px;
  height:34px;
  border-radius:13px;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  background:#ffffff;
  border:1px solid #e5e7eb;
  box-shadow:0 8px 20px rgba(2,8,23,.05);
  font-size:17px;
  flex:0 0 auto;
}
.recycleName { font-size:14px; font-weight:950; }
.recycleHint {
  margin-top:2px;
  color:#667085;
  font-size:11px;
  font-weight:800;
}
.materialCode {
  display:inline-flex;
  padding:7px 10px;
  border-radius:999px;
  background:#ffffff;
  color:#0f766e;
  font-size:12px;
  font-weight:950;
  border:1px solid rgba(15,118,110,.14);
}
.recycleProduct {
  position:relative;
  z-index:1;
  margin-top:10px;
  color:#334155;
  font-size:13px;
  font-weight:760;
}
.footerNote {
  margin-top:14px;
  border:1px solid #e5e7eb;
  border-radius:22px;
  background:rgba(255,255,255,.70);
  padding:14px;
  color:#667085;
  font-size:12px;
  font-weight:720;
  text-align:center;
}
.btn {
  display:inline-flex;
  padding:11px 14px;
  border-radius:14px;
  border:1px solid #e5e7eb;
  background:#fff;
  color:#0f172a;
  text-decoration:none;
  font-size:13px;
  font-weight:900;
}
.btnPrimary {
  background:#0f766e;
  color:#fff;
  border-color:#0f766e;
}
@media(max-width:760px) {
  
.demoTopbar {
    flex-direction:column;
    align-items:flex-start;
  }

  .demoTopActions {
    width:100%;
    justify-content:flex-start;
  }

  .demoTopActions .btn {
    width:100%;
    justify-content:center;
  }

  .page { padding:12px; }
  .hero { border-radius:24px; padding:20px; }
  .metaGrid, .contentGrid, .nutritionGrid, .recycleGrid, .demoLabelsGrid, .demoValueBox { grid-template-columns:1fr; }
  .infoCard.full { grid-column:auto; }
}
</style>
</head>
<body>
<div class="demoWatermark">DEMO</div>
<div class="page">

  <header class="demoTopbar" style="
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:16px;
  margin:0 0 18px;
  padding:14px 18px;
  border:1px solid #e5e7eb;
  border-radius:24px;
  background:rgba(255,255,255,.90);
  box-shadow:0 18px 45px rgba(2,8,23,.06);
">
  <a href="/" style="
    display:flex;
    align-items:center;
    gap:12px;
    text-decoration:none;
    color:#0f172a;
  ">
    <svg width="54" height="54" viewBox="0 0 54 54" xmlns="http://www.w3.org/2000/svg" style="
      width:54px;
      height:54px;
      border-radius:17px;
      display:block;
      flex:0 0 auto;
      box-shadow:0 12px 28px rgba(15,118,110,.12);
    ">
      <rect width="54" height="54" rx="17" fill="#0f766e"/>
      <rect x="11" y="12" width="11" height="11" rx="3" fill="#ffffff"/>
      <rect x="32" y="12" width="11" height="11" rx="3" fill="#ffffff"/>
      <rect x="11" y="32" width="11" height="11" rx="3" fill="#ffffff"/>
      <rect x="28" y="28" width="7" height="7" rx="2" fill="#ffffff"/>
      <rect x="38" y="28" width="5" height="5" rx="2" fill="#ffffff"/>
      <rect x="28" y="38" width="15" height="5" rx="2" fill="#ffffff"/>
      <path d="M27 8C27 8 22 15 22 20C22 24 24 27 27 27C30 27 32 24 32 20C32 15 27 8 27 8Z" fill="#ffffff"/>
      <path d="M24.5 20.5L26.6 22.6L30.8 17.6" stroke="#0f766e" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <div>
      <div style="
        font-size:26px;
        font-weight:950;
        line-height:1;
        letter-spacing:-.6px;
      ">QRFACILE</div>
      <div style="
        margin-top:5px;
        color:#667085;
        font-size:13px;
        font-weight:800;
      ">Demo pagina QR</div>
    </div>
  </a>

  <div style="
    display:flex;
    gap:10px;
    align-items:center;
    justify-content:flex-end;
    flex-wrap:wrap;
  ">
    <a class="btn" href="/">← Torna alla home</a>
    <a class="btn btnPrimary" href="/register-winery">Inizia gratis</a>
  </div>
</header>

  <section class="hero demoHero">
    <div class="heroText">
      <div class="eyebrow">QRFACILE · Etichetta digitale vino</div>

      <h1>Il QR del vino,<br>fatto semplice.<br><span>Lo paghi una volta. Nessun canone annuale.</span></h1>

      <p>
        Acquista crediti soltanto quando ti servono. Ogni QR resta online e modificabile
        per 10 o 25 anni, anche senza rinnovi o nuovi acquisti.
      </p>

      <div class="credit-strip" style="margin-top:18px;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));gap:10px">
        <div style="border:1px solid rgba(2,8,23,.10);background:rgba(255,255,255,.82);border-radius:18px;padding:12px">
          <b style="display:block;font-size:18px">1 credito</b>
          <span style="display:block;margin-top:4px;color:#64748b;font-size:12px;font-weight:850">QR vino 10 anni</span>
        </div>
        <div style="border:1px solid rgba(2,8,23,.10);background:rgba(255,255,255,.82);border-radius:18px;padding:12px">
          <b style="display:block;font-size:18px">2 crediti</b>
          <span style="display:block;margin-top:4px;color:#64748b;font-size:12px;font-weight:850">QR vino 25 anni</span>
        </div>
        <div style="border:1px solid rgba(2,8,23,.10);background:rgba(255,255,255,.82);border-radius:18px;padding:12px">
          <b style="display:block;font-size:18px">+1 credito</b>
          <span style="display:block;margin-top:4px;color:#64748b;font-size:12px;font-weight:850">upgrade 10 → 25 anni su richiesta al supporto</span>
        </div>
      </div>

      <div class="heroActions" style="margin-top:22px">
        <a class="btn btn-primary" href="/register-winery">Sono una Cantina</a>
        <a class="btn" href="/register-studio">Sono uno Studio Grafico</a>
        <a class="btn" href="/pricing">Prezzi</a>
      </div>
    </div>

    <div class="heroMedia">
      <div style="background:linear-gradient(135deg,#dcd6ff,#cfe8ff);border-radius:30px;padding:18px;box-shadow:0 24px 80px rgba(2,8,23,.10)">
        <img src="/static/qr3d.png" alt="QR vino digitale QRFACILE" style="width:100%;display:block;border-radius:24px;background:#fff">
      </div>
      <div class="note" style="margin-top:14px;text-align:center">
        QR professionale · 10 o 25 anni · file pronti per tipografia
      </div>
    </div>
  </section>


  <section class="demoLabels">
    <div class="demoLabelsHead">
      <div>
        <div class="demoLabelsTitle">Etichetta del prodotto</div>
        <div class="demoLabelsSub">
          Il consumatore riconosce subito la bottiglia: fronte e retro vengono mostrati per intero,
          senza tagli e senza effetto catalogo pubblicitario.
        </div>
      </div>
    </div>

    <div class="demoLabelsGrid">
      <div class="demoLabelCard">
        <div class="demoLabelTitle">Fronte etichetta</div>
        <img src="/static/demo/demo_label_front.svg" alt="Etichetta fronte Falanghina del Taburno">
      </div>

      <div class="demoLabelCard">
        <div class="demoLabelTitle">Retro etichetta</div>
        <img src="/static/demo/demo_label_back.svg" alt="Etichetta retro Falanghina del Taburno">
      </div>
    </div>
  </section>

  <section class="demoValueBox">
    <div>
      <span>Perché è utile</span>
      <b>La pagina QR non è solo un obbligo: diventa una scheda digitale ordinata, verificabile e sempre aggiornabile.</b>
    </div>
    <div>
      <span>Per la cantina</span>
      <b>Il QR resta lo stesso, mentre i dati possono essere aggiornati senza ristampare l’etichetta.</b>
    </div>
  </section>

  <main class="contentGrid">
    <section class="infoCard">
      <div class="cardHead">
        <div>
          <div class="cardTitle">Ingredienti</div>
          <div class="cardSub">Elenco ingredienti dichiarati</div>
        </div>
        <div class="cardIcon">🍇</div>
      </div>
      <div class="textValue">
        Uve, mosto d’uva, stabilizzanti, antiossidante: solfiti.
      </div>
    </section>

    <section class="infoCard">
      <div class="cardHead">
        <div>
          <div class="cardTitle">Allergeni</div>
          <div class="cardSub">Sostanze o prodotti dichiarati</div>
        </div>
        <div class="cardIcon">🛡️</div>
      </div>
      <div class="chips">
        <span class="chip">Solfiti</span>
      </div>
    </section>

    <section class="infoCard full">
      <div class="cardHead">
        <div>
          <div class="cardTitle">Valori nutrizionali</div>
          <div class="cardSub">Valori riferiti a 100 ml</div>
        </div>
        <div class="cardIcon">⚖️</div>
      </div>

      <div class="nutritionGrid">
        <div class="nutritionItem"><span>Energia</span><b>310 kJ / 74 kcal</b></div>
        <div class="nutritionItem"><span>Grassi</span><b>0 g<br><small>Saturi 0 g</small></b></div>
        <div class="nutritionItem"><span>Carboidrati</span><b>1.2 g<br><small>Zuccheri 0.8 g</small></b></div>
        <div class="nutritionItem"><span>Proteine / Sale</span><b>0 g / 0 g</b></div>
      </div>
    </section>

    <section class="infoCard full">
      <div class="cardHead">
        <div>
          <div class="cardTitle">Riciclabilità</div>
          <div class="cardSub">Componenti e codici di conferimento</div>
        </div>
        <div class="cardIcon">♻️</div>
      </div>

      <div class="recycleGrid">
        <div class="recycleItem recycleTone-glass">
          <div class="recycleTop">
            <div class="recycleNameWrap"><span class="recycleIcon">🍾</span><div><div class="recycleName">Bottiglia</div><div class="recycleHint">Componente packaging</div></div></div>
            <span class="materialCode">GL71</span>
          </div>
          <div class="recycleProduct">Vetro verde</div>
        </div>

        <div class="recycleItem recycleTone-closure">
          <div class="recycleTop">
            <div class="recycleNameWrap"><span class="recycleIcon">🟤</span><div><div class="recycleName">Tappo</div><div class="recycleHint">Componente separabile</div></div></div>
            <span class="materialCode">FOR51</span>
          </div>
          <div class="recycleProduct">Sughero</div>
        </div>

        <div class="recycleItem recycleTone-capsule">
          <div class="recycleTop">
            <div class="recycleNameWrap"><span class="recycleIcon">🎗️</span><div><div class="recycleName">Capsula</div><div class="recycleHint">Componente separabile</div></div></div>
            <span class="materialCode">C/ALU90</span>
          </div>
          <div class="recycleProduct">Capsula polilaminata</div>
        </div>

        <div class="recycleItem recycleTone-paper">
          <div class="recycleTop">
            <div class="recycleNameWrap"><span class="recycleIcon">🏷️</span><div><div class="recycleName">Etichetta</div><div class="recycleHint">Componente packaging</div></div></div>
            <span class="materialCode">PAP22</span>
          </div>
          <div class="recycleProduct">Carta</div>
        </div>

        <div class="recycleItem recycleTone-box">
          <div class="recycleTop">
            <div class="recycleNameWrap"><span class="recycleIcon">📦</span><div><div class="recycleName">Scatola / imballo</div><div class="recycleHint">Imballo secondario</div></div></div>
            <span class="materialCode">PAP20</span>
          </div>
          <div class="recycleProduct">Cartone ondulato</div>
        </div>

        <div class="recycleItem recycleTone-other">
          <div class="recycleTop">
            <div class="recycleNameWrap"><span class="recycleIcon">♻️</span><div><div class="recycleName">Altro</div><div class="recycleHint">Eventuali componenti aggiuntivi</div></div></div>
            <span class="materialCode">—</span>
          </div>
          <div class="recycleProduct">Non presente in questa confezione</div>
        </div>
      </div>
    </section>
  </main>

  <div class="footerNote">
    Questa è una pagina dimostrativa. Le pagine reali vengono generate dai dati inseriti dalla cantina.
  </div>
</div>
</body>
</html>"""
    return HTMLResponse(html)
