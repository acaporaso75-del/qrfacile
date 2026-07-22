from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from qrfacile_app.ui_shell import page_public

router = APIRouter()


def _actions() -> str:
    return """
    <a class="btn" href="/">Home</a>
    <a class="btn" href="/pricing">Prezzi</a>
    <a class="btn" href="/support">Supporto</a>
    <a class="btn" href="/login">Accedi</a>
    <a class="btn btn-primary" href="/register-winery">Inizia gratis</a>
    """


GUIDE_STYLE = """
<style>
.guideWrap {
  max-width:1180px;
  margin:0 auto;
}

.guideHero {
  border:1px solid rgba(2,8,23,.08);
  border-radius:32px;
  overflow:hidden;
  box-shadow:0 28px 95px rgba(2,8,23,.10);
  background:
    radial-gradient(circle at 8% 12%, rgba(191,245,230,.62), transparent 34%),
    radial-gradient(circle at 92% 8%, rgba(207,232,255,.58), transparent 34%),
    linear-gradient(135deg,rgba(255,255,255,.98),rgba(248,252,250,.94));
  padding:38px;
}

.guideEyebrow {
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

.guideTitle {
  margin-top:14px;
  font-size:clamp(34px,5vw,58px);
  line-height:1;
  font-weight:950;
  letter-spacing:-1.8px;
  color:#0f172a;
}

.guideSub {
  max-width:720px;
  margin-top:14px;
  color:#475569;
  font-size:16px;
  font-weight:720;
  line-height:1.55;
}

.guideActions {
  display:flex;
  gap:10px;
  flex-wrap:wrap;
  margin-top:22px;
}

.guideGrid {
  display:grid;
  grid-template-columns:repeat(3,minmax(0,1fr));
  gap:16px;
  margin-top:18px;
}

.guideCard {
  border:1px solid rgba(2,8,23,.08);
  border-radius:24px;
  background:rgba(255,255,255,.88);
  box-shadow:0 14px 45px rgba(2,8,23,.055);
  padding:22px;
}

.guideIcon {
  width:46px;
  height:46px;
  border-radius:18px;
  display:flex;
  align-items:center;
  justify-content:center;
  background:linear-gradient(135deg,rgba(191,245,230,.82),rgba(207,232,255,.78));
  border:1px solid rgba(2,8,23,.07);
  font-size:22px;
}

.guideCard h2 {
  margin:16px 0 8px;
  font-size:22px;
  font-weight:950;
  letter-spacing:-.25px;
  color:#0f172a;
}

.guideCard p,
.guideCard li {
  color:#475569;
  font-size:14px;
  font-weight:720;
  line-height:1.6;
}

.guideCard ul {
  margin:14px 0 0;
  padding-left:20px;
}

.guideCardAction {
  margin-top:18px;
}

@media(max-width:900px) {
  .guideGrid {
    grid-template-columns:1fr;
  }
}

@media(max-width:560px) {
  .guideHero,
  .guideCard {
    padding:22px;
  }

  .guideActions .btn,
  .guideCardAction .btn {
    width:100%;
  }
}
</style>
"""


@router.get("/guide", response_class=HTMLResponse)
def guide(request: Request):
    body = """
    <section class="guideWrap">
      <div class="guideHero">
        <div class="guideEyebrow">QRFACILE · Guide operative</div>
        <div class="guideTitle">Manuali operativi QRFACILE</div>
        <div class="guideSub">
          Guide pratiche per cantine, studi grafici e stampa QR.
        </div>
        <div class="guideActions">
          <a class="btn btn-primary" href="/login">Accedi</a>
          <a class="btn" href="/register-winery">Inizia gratis</a>
          <a class="btn" href="/support">Supporto</a>
        </div>
      </div>

      <div class="guideGrid">
        <div class="guideCard">
          <div class="guideIcon">1</div>
          <h2>Manuale Cantina</h2>
          <p>
            Percorso operativo per creare e gestire le etichette digitali dei vini
            dall’account cantina fino alla pubblicazione del QR.
          </p>
          <ul>
            <li>Registrazione e accesso alla dashboard.</li>
            <li>Creazione lotto vino e dati principali.</li>
            <li>Compilazione dati obbligatori.</li>
            <li>Controllo preview tecnica.</li>
            <li>Pubblicazione controllata.</li>
            <li>Export QR per stampa e archivio.</li>
          </ul>
          <div class="guideCardAction">
            <a class="btn btn-primary" href="/static/manuali/manuale_cantina.pdf" target="_blank">Scarica PDF</a>
          </div>
        </div>

        <div class="guideCard">
          <div class="guideIcon">2</div>
          <h2>Manuale Studio Grafico</h2>
          <p>
            Guida per usare QRFACILE come console partner, collaborare con le cantine
            e preparare materiali pronti per la produzione.
          </p>
          <ul>
            <li>Inviti alle cantine e collegamento cliente.</li>
            <li>Workspace cantina e gestione operativa.</li>
            <li>Permessi di vista, modifica e creazione.</li>
            <li>Preparazione immagini ed etichette.</li>
            <li>Export professionale per QR.</li>
            <li>Supporto cliente durante il workflow.</li>
          </ul>
          <div class="guideCardAction">
            <a class="btn btn-primary" href="/static/manuali/manuale_studio.pdf" target="_blank">Scarica PDF</a>
          </div>
        </div>

        <div class="guideCard">
          <div class="guideIcon">3</div>
          <h2>Guida QR e stampa</h2>
          <p>
            Indicazioni pratiche per usare correttamente i file QR generati da QRFACILE
            in tipografia e sui materiali stampati.
          </p>
          <ul>
            <li>Formati PNG, SVG, PDF e ZIP.</li>
            <li>Dimensione minima consigliata.</li>
            <li>Quiet zone libera intorno al QR.</li>
            <li>Contrasto e leggibilità in stampa.</li>
            <li>Test scansione prima della produzione.</li>
            <li>Uso corretto in tipografia.</li>
          </ul>
          <div class="guideCardAction">
            <a class="btn btn-primary" href="/static/manuali/manuale_qr_stampa.pdf" target="_blank">Scarica PDF</a>
          </div>
        </div>
      </div>

      """ + GUIDE_STYLE + """
    </section>
    """

    return HTMLResponse(page_public(
        title="QRFACILE · Manuali operativi",
        subtitle="Guide",
        body_html=body,
        actions_html=_actions(),
    ))
