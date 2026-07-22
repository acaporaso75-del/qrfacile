# /opt/qrfacile/qrfacile_app/ui_shell.py
import html


def esc(s: str) -> str:
    return html.escape(s or "")


def banner(msg: str = "", err: str = "") -> str:
    out = []

    if msg:
        out.append(f"<div class='note note-ok'><b>OK:</b> {esc(msg)}</div>")

    if err:
        out.append(f"<div class='note note-err'><b>Errore:</b> {esc(err)}</div>")

    return "\n".join(out)


def pill(text: str, kind: str = "") -> str:
    cls = "pill"

    if kind == "green":
        cls += " pill-green"
    elif kind == "warn":
        cls += " pill-warn"
    elif kind == "muted":
        cls += " pill-muted"
    elif kind == "blue":
        cls += " pill-blue"

    return f"<span class='{cls}'>{esc(text)}</span>"


def top_actions(*links: tuple[str, str]) -> str:
    """
    Compatibilità: alcuni moduli importano top_actions.
    Uso: top_actions(('/login','Login'),('/','Home'))
    """
    out = []

    for href, label in links:
        out.append(f"<a class='btn' href='{esc(href)}'>{esc(label)}</a>")

    return " ".join(out)


def _brand_logo_html(size: int = 44) -> str:
    return f"""
      <img src="/static/qrfacile.svg" alt="QRFACILE" style="
        width:{size}px;
        height:{size}px;
        border-radius:16px;
        background:#ffffff;
        padding:6px;
        border:1px solid rgba(2,8,23,.10);
        box-shadow:0 18px 45px rgba(2,8,23,.08);
        display:block;
        object-fit:contain;
      ">
    """.strip()


def _public_topbar(actions_html: str = "") -> str:
    return f"""
    <div class="topbar public-topbar">
      <div class="brand">
        <a href="/" style="display:inline-flex;align-items:center;text-decoration:none">
          <img src="/static/qrfacile-wordmark.svg" alt="QRFACILE" style="
            width:230px;
            max-width:52vw;
            height:auto;
            display:block;
          ">
        </a>
      </div>

      <div class="row topbar-actions">
        {actions_html}
      </div>
    </div>
    """

def _public_hero() -> str:
    return f"""
    <section class="hero">
      <div class="heroGrid">
        <div>
          <div class="h1">Etichetta digitale vino, pronta per la normativa.</div>

          <div class="p" style="margin-top:10px">
            Lotti, ingredienti, allergeni, nutrizione, riciclo. <b>QR pro</b> pronto per tipografia.
            Cantina e studio lavorano insieme con permessi chiari.
          </div>

          <div class="heroPoints">
            <div class="heroPoint">
              <b>Chi siamo</b>
              <span>Piattaforma tecnica per etichetta digitale vino.</span>
            </div>

            <div class="heroPoint">
              <b>Cosa facciamo</b>
              <span>Pagina conforme + export QR professionale PNG/SVG/PDF/ZIP.</span>
            </div>

            <div class="heroPoint">
              <b>Dove andiamo</b>
              <span>Standard europeo, multilingua, analytics e servizi evoluti.</span>
            </div>
          </div>

          <div class="row" style="margin-top:18px">
            <a class="btn btn-primary" href="/register-winery">Registrati come Cantina</a>
            <a class="btn" href="/register-studio">Registrati come Studio Grafico</a>
            <a class="btn" href="/login">Accedi</a>
          </div>
        </div>

        <div class="heroArt">
          <div class="heroArtBox">
            <img src="/static/qr3d.png" alt="QR 3D" style="width:100%;height:auto;display:block">
          </div>

          <div class="note" style="margin-top:12px">
            QR pro · preset stampa · collaborazione cantina/studio.
          </div>
        </div>
      </div>
    </section>
    """


def _public_footer() -> str:
    return """
    <footer class="footer">
      <div style="display:grid;gap:8px;text-align:center">
        <div>
          <b>QRFACILE</b> — piattaforma tecnica per etichetta digitale vino
        </div>

        <div style="font-size:12px;line-height:1.55;color:var(--muted)">
          Servizio gestito da <b>Enolab S.r.l.</b> · P.IVA / C.F. 01413300623 · REA BN118353 · Capitale sociale €90.000,00
          <br>
          Sede legale: Via Campoli-Friuni snc, Campoli del Monte Taburno (BN)
          <br>
          Sede operativa: Via Giovanni Agnelli, 16, Benevento (BN) · PEC: enolab@pcert.it · Email: info@enolab.it
        </div>

        <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;font-size:12px">
          <a href="/legal">Note legali</a>
          <span>·</span>
          <a href="/privacy">Privacy Policy</a>
          <span>·</span>
          <a href="/cookies">Cookie Policy</a>
          <span>·</span>
          <a href="/terms">Termini di servizio</a>
        </div>
      </div>
    </footer>
    """


def _role_label(role: str) -> str:
    role = (role or "").lower().strip()

    if role == "winery":
        return "Cantina"

    if role == "studio":
        return "Studio grafico"

    if role == "admin":
        return "Admin"

    return role or "-"


def _sidebar(role: str, user_email: str, credits: dict | None) -> str:
    role = (role or "").lower().strip()
    credits = credits or {"wine": 0, "generic": 0}

    nav = [
        ("/app/start", "🏠", "Menu", "Area operativa"),
        ("/app/dashboard", "📋", "Dashboard", "Etichette e lotti"),
        ("/app/new-wine-master", "🍷", "Nuova etichetta", "Prodotto"),
        ("/app/new-wine", "🍾", "Nuovo lotto", "Scala 1 wine"),
        ("/app/new-external", "🔗", "QR Link", "3 gratis + generic"),
        ("/app/billing", "💳", "Crediti", "Pacchetti"),
    ]

    if role == "winery":
        nav.append(("/app/winery/logo", "🏷️", "Logo cantina", "Pagina pubblica"))

    if role == "studio":
        nav.append(("/studio", "🎨", "Area Studio", "Inviti e cantine"))
        nav.append(("/studio/settings", "⚙️", "Profilo Studio", "Dati e impostazioni"))
        nav.append(("/studio/commissions", "💶", "Bonus", "Maturazione e payout"))

    if role == "admin":
        nav.append(("/admin", "📊", "Statistiche", "Console admin"))
        nav.append(("/admin/legacy", "🧾", "Legacy", "QR storici"))
        nav.append(("/admin/override-requests", "🔓", "Sblocchi", "Richieste pubblicazione"))
        nav.append(("/admin/payouts", "🛠️", "Payout", "Approve & paid"))

    nav_html = "\n".join([
        f"""
        <a href="{esc(h)}" class="navItem">
          <span class="navIcon">{esc(i)}</span>
          <span class="navText">
            <span class="navTitle">{esc(t)}</span>
            <small>{esc(s)}</small>
          </span>
        </a>
        """
        for (h, i, t, s) in nav
    ])

    footer = f"""
    <div class="sidebarFooter">
      <div class="sidebarCreditBox">
        <div class="sidebarCreditTitle">Crediti</div>

        <div class="sidebarCredits">
          <div class="sidebarCreditItem sidebarCreditWine">
            <span>wine</span>
            <b>{int(credits.get('wine', 0))}</b>
          </div>

          <div class="sidebarCreditItem sidebarCreditGeneric">
            <span>generic</span>
            <b>{int(credits.get('generic', 0))}</b>
          </div>
        </div>
      </div>

      <div class="sidebarUser">
        <div class="sidebarUserEmail">{esc(user_email or "-")}</div>
        <div class="sidebarUserRole">{esc(_role_label(role))}</div>
      </div>

      <div class="sidebarButtons">
        <a class="btn" href="/app/start">Menu</a>
        <a class="btn btn-danger-soft" href="/logout">Logout</a>
      </div>
    </div>
    """

    return f"""
    <aside class="sidebar">
      <div class="sidebarBrand">
        <a href="/app/start" style="display:block;text-decoration:none">
          <img src="/static/qrfacile-wordmark.svg" alt="QRFACILE" style="
            width:100%;
            max-width:220px;
            height:auto;
            display:block;
            border-radius:18px;
            background:#ffffff;
            border:1px solid rgba(2,8,23,.08);
            box-shadow:0 18px 45px rgba(2,8,23,.06);
          ">
        </a>
      </div>

      <nav class="nav">
        {nav_html}
      </nav>

      {footer}
    </aside>
    """


def page(
    title: str,
    subtitle: str,
    body_html: str,
    actions_html: str = "",
    msg: str = "",
    err: str = "",
    user_email: str = "",
    role: str = "",
    credits: dict | None = None,
) -> str:
    if not role:
        return page_public(
            title=title,
            subtitle=subtitle,
            body_html=body_html,
            actions_html=actions_html,
            msg=msg,
            err=err,
        )

    return page_app(
        title=title,
        subtitle=subtitle,
        body_html=body_html,
        actions_html=actions_html,
        msg=msg,
        err=err,
        user_email=user_email,
        role=role,
        credits=credits,
    )


def page_app(
    title: str,
    subtitle: str,
    body_html: str,
    actions_html: str = "",
    msg: str = "",
    err: str = "",
    user_email: str = "",
    role: str = "",
    credits: dict | None = None,
) -> str:
    header = f"""
    <div class="topbar app-topbar">
      <div class="topbar-titleblock">
        <div class="brand-title">{esc(title)}</div>
        <div class="brand-sub">{esc(subtitle)}</div>
      </div>

      <div class="row topbar-actions">
        {actions_html}
      </div>
    </div>
    """

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>
<div class="shell">
  {_sidebar(role=role, user_email=user_email, credits=credits)}

  <main class="content">
    {header}
    {banner(msg, err)}
    {body_html}
  </main>
</div>
</body>
</html>"""


def page_public(
    title: str,
    subtitle: str,
    body_html: str,
    actions_html: str = "",
    msg: str = "",
    err: str = "",
) -> str:
    if not actions_html:
        actions_html = (
            "<a class='btn' href='/login'>Accedi</a> "
            "<a class='btn' href='/register-winery'>Registrati come Cantina</a> "
            "<a class='btn btn-primary' href='/register-studio'>Registrati come Studio Grafico</a>"
        )

    header = _public_topbar(actions_html=actions_html)

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>
<div class="publicWrap">
  {header}

  <main class="publicMain">
    {banner(msg, err)}
    {body_html}
  </main>

  {_public_footer()}
</div>
</body>
</html>"""


def public_hero() -> str:
    return _public_hero()
