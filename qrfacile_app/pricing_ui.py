# /opt/qrfacile/qrfacile_app/pricing_ui.py

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from qrfacile_app.checkout_ui import paypal_checkout_form, paypal_checkout_script
from qrfacile_app.ui_shell import page_public, esc
from qrfacile_app.pricing_config import (
    FREE_WINE_CREDITS_ON_REGISTER,
    QR_STANDARD_YEARS,
    QR_EXTENDED_YEARS,
    QR_STANDARD_CREDIT_COST,
    QR_EXTENDED_CREDIT_COST,
    QR_UPGRADE_10_TO_25_CREDIT_COST,
    list_qr_packs,
    list_assisted_services,
    euro,
)

router = APIRouter()


def _pack_badge(highlight: bool) -> str:
    if not highlight:
        return ""
    return """
    <div class="priceBadge">★ Consigliato</div>
    """


def _main_feature(pack: dict) -> str:
    qty = int(pack.get("qty") or 0)

    if qty <= 0:
        return ""

    standard_qr = qty // QR_STANDARD_CREDIT_COST
    extended_qr = qty // QR_EXTENDED_CREDIT_COST

    return f"""
    <div class="priceFeature main">
      <span>✓</span>
      <b>{qty} crediti QR vino</b>
    </div>

    <div class="priceFeature">
      <span>✓</span>
      <div>
        <b>{standard_qr} QR vino da {QR_STANDARD_YEARS} anni</b><br>
        oppure {extended_qr} QR vino da {QR_EXTENDED_YEARS} anni
      </div>
    </div>
    """


def _extra_features(pack: dict) -> str:
    features = pack.get("features") or []

    skip_words = (
        "crediti",
        "QR vino da",
        "10 anni",
        "25 anni",
    )

    cleaned = []
    for item in features:
        text = str(item or "").strip()
        if not text:
            continue
        if any(w.lower() in text.lower() for w in skip_words):
            continue
        cleaned.append(text)

    if not cleaned:
        cleaned = [
            "Nessun abbonamento obbligatorio",
            "Export QR pronto per tipografia",
        ]

    html = ""
    for item in cleaned[:3]:
        html += f"""
        <div class="priceFeature">
          <span>✓</span>
          <div>{esc(item)}</div>
        </div>
        """
    return html


def _qr_pack_card(request: Request, key: str, pack: dict) -> str:
    label = esc(pack.get("label") or key)
    subtitle = esc(pack.get("subtitle") or "")
    amount_cents = int(pack.get("amount_cents") or 0)
    price = euro(amount_cents)
    highlight = bool(pack.get("highlight"))

    cls = "priceCard highlighted" if highlight else "priceCard"

    return f"""
    <article class="{cls}">
      {_pack_badge(highlight)}

      <div class="priceCardTop">
        <div>
          <div class="priceName">{label}</div>
          <div class="priceSubtitle">{subtitle}</div>
        </div>
      </div>

      <div class="priceValue">{price}</div>

      <div class="priceFeatures">
        {_main_feature(pack)}
        {_extra_features(pack)}
      </div>

      {paypal_checkout_form(
          request,
          pack=key,
          button_label="Acquista",
          button_class=f"priceBtn {'primary' if highlight else ''}",
      )}
    </article>
    """


def _assisted_card(key: str, service: dict, icon: str) -> str:
    label = esc(service.get("label") or key)
    subtitle = esc(service.get("subtitle") or "")
    amount_cents = service.get("amount_cents")
    price = euro(amount_cents)

    return f"""
    <article class="assistMiniCard">
      <div class="assistIcon">{icon}</div>
      <div class="assistTitle">{label}</div>
      <div class="assistPrice">{price}</div>
      <div class="assistText">{subtitle}</div>
      <a class="assistBtn" href="/register-winery">Scopri di più</a>
    </article>
    """


@router.get("/pricing", response_class=HTMLResponse)
def pricing_page(request: Request):
    qr_cards = "".join([
        _qr_pack_card(request, key, pack)
        for key, pack in list_qr_packs()
    ])

    assisted_services = list_assisted_services()
    assisted_cards = ""
    icons = ["👤", "👥"]

    for idx, (key, service) in enumerate(assisted_services[:2]):
        assisted_cards += _assisted_card(key, service, icons[idx] if idx < len(icons) else "🎧")

    body = f"""
    <section class="pricingPage">

      <section class="pricingHero">
        <div class="pricingEyebrow">Prezzi QRFACILE</div>
        <h1>Scegli il pacchetto di crediti QR vino più adatto alla tua cantina</h1>
        <p>
          Paghi solo i crediti che usi. Nessun abbonamento obbligatorio.
          QR pronti per la stampa in pochi minuti.
        </p>
      </section>

      <section class="freeBanner">
        <div class="freeIcon">🎁</div>
        <div>
          <b>{FREE_WINE_CREDITS_ON_REGISTER} crediti QR vino gratuiti</b>
          <span>alla registrazione</span>
        </div>
        <a class="freeBtn" href="/register-winery">Inizia gratis</a>
      </section>

      <section class="creditRules">
        <div>
          <b>{QR_STANDARD_CREDIT_COST} credito</b>
          <span>QR vino attivo {QR_STANDARD_YEARS} anni</span>
        </div>
        <div>
          <b>{QR_EXTENDED_CREDIT_COST} crediti</b>
          <span>QR vino attivo {QR_EXTENDED_YEARS} anni</span>
        </div>
        <div>
          <b>+{QR_UPGRADE_10_TO_25_CREDIT_COST} credito</b>
          <span>upgrade da {QR_STANDARD_YEARS} a {QR_EXTENDED_YEARS} anni</span>
        </div>
      </section>

      <section class="priceGrid">
        {qr_cards}
      </section>
      {paypal_checkout_script()}

      <section class="assistSection">
        <div class="assistIntro">
          <div class="assistIcon big">🎧</div>
          <div class="pricingEyebrow">Avvio assistito · opzionale</div>
          <h2>Un supporto dedicato, quando vuoi</h2>
          <p>
            QRFACILE è pensato per essere usato in autonomia.
            L’assistenza è disponibile per chi preferisce delegare il primo caricamento
            o partire con più tranquillità.
          </p>
        </div>

        <div class="assistCards">
          {assisted_cards}
        </div>
      </section>

      <section class="securitySection">
        <h2>Infrastruttura affidabile. Dati al sicuro.</h2>

        <div class="securityGrid">
          <div>
            <span>☁️</span>
            <b>Backup periodici</b>
          </div>
          <div>
            <span>🖥️</span>
            <b>Copie VM</b>
          </div>
          <div>
            <span>☁️</span>
            <b>Copie cloud</b>
          </div>
          <div>
            <span>🖨️</span>
            <b>QR pronti per tipografia</b>
          </div>
        </div>

        <div class="securityNote">
          Sicuro, stabile e pensato per QR destinati a rimanere stampati sulle bottiglie.
        </div>
      </section>

    </section>

    <style>
      .pricingPage {{
        max-width:1180px;
        margin:0 auto;
        padding:20px 0 70px;
      }}

      .pricingHero {{
        text-align:center;
        max-width:860px;
        margin:20px auto 34px;
      }}

      .pricingEyebrow {{
        color:#0f9f8f;
        font-weight:950;
        text-transform:uppercase;
        letter-spacing:.08em;
        font-size:13px;
        margin-bottom:12px;
      }}

      .pricingHero h1 {{
        margin:0;
        font-size:44px;
        line-height:1.05;
        letter-spacing:-1.4px;
        font-weight:950;
        color:#0f1b3d;
      }}

      .pricingHero p {{
        margin:16px auto 0;
        max-width:680px;
        color:#536079;
        font-size:18px;
        line-height:1.55;
        font-weight:700;
      }}

      .freeBanner {{
        max-width:880px;
        margin:0 auto 32px;
        display:grid;
        grid-template-columns:auto 1fr auto;
        gap:18px;
        align-items:center;
        padding:22px 28px;
        border:1px solid rgba(15,23,42,.08);
        border-radius:22px;
        background:linear-gradient(135deg,rgba(255,255,255,.96),rgba(236,253,245,.88));
        box-shadow:0 18px 55px rgba(2,8,23,.06);
      }}

      .freeIcon {{
        width:54px;
        height:54px;
        border-radius:999px;
        display:flex;
        align-items:center;
        justify-content:center;
        background:rgba(20,184,166,.12);
        font-size:26px;
      }}

      .freeBanner b {{
        display:block;
        font-size:19px;
        font-weight:950;
        color:#0f1b3d;
      }}

      .freeBanner span {{
        color:#64748b;
        font-weight:750;
      }}

      .freeBtn {{
        display:inline-flex;
        align-items:center;
        justify-content:center;
        padding:13px 24px;
        border-radius:14px;
        background:linear-gradient(135deg,#0f9f8f,#0f766e);
        color:white;
        font-weight:950;
        text-decoration:none;
        box-shadow:0 16px 34px rgba(15,118,110,.22);
      }}

      .creditRules {{
        margin:0 auto 28px;
        display:grid;
        grid-template-columns:repeat(3,1fr);
        gap:14px;
      }}

      .creditRules div {{
        padding:16px 18px;
        border-radius:20px;
        background:rgba(255,255,255,.88);
        border:1px solid rgba(15,23,42,.08);
        box-shadow:0 12px 35px rgba(2,8,23,.05);
      }}

      .creditRules b {{
        display:block;
        color:#0f766e;
        font-size:19px;
        font-weight:950;
      }}

      .creditRules span {{
        display:block;
        margin-top:4px;
        color:#64748b;
        font-weight:800;
        font-size:13px;
      }}

      .priceGrid {{
        display:grid;
        grid-template-columns:repeat(3,1fr);
        gap:28px;
        align-items:stretch;
        margin-top:18px;
      }}

      .priceCard {{
        position:relative;
        display:flex;
        flex-direction:column;
        padding:28px;
        min-height:500px;
        border-radius:26px;
        background:
          radial-gradient(circle at 100% 0%, rgba(191,245,230,.50), transparent 32%),
          #ffffff;
        border:1px solid rgba(15,23,42,.08);
        box-shadow:0 20px 60px rgba(2,8,23,.07);
      }}

      .priceCard.highlighted {{
        border:2px solid #0f9f8f;
        transform:translateY(-8px);
        box-shadow:0 28px 80px rgba(15,118,110,.14);
      }}

      .priceBadge {{
        position:absolute;
        top:-16px;
        left:50%;
        transform:translateX(-50%);
        padding:8px 18px;
        border-radius:999px;
        background:linear-gradient(135deg,#0f9f8f,#0f766e);
        color:white;
        font-size:13px;
        font-weight:950;
        box-shadow:0 14px 28px rgba(15,118,110,.22);
        white-space:nowrap;
      }}

      .priceName {{
        font-size:24px;
        font-weight:950;
        color:#0f1b3d;
      }}

      .priceSubtitle {{
        margin-top:8px;
        color:#64748b;
        font-size:14px;
        line-height:1.4;
        font-weight:750;
      }}

      .priceValue {{
        margin-top:28px;
        font-size:48px;
        line-height:1;
        font-weight:950;
        color:#0f9f8f;
      }}

      .priceFeatures {{
        margin-top:26px;
        display:grid;
        gap:14px;
      }}

      .priceFeature {{
        display:grid;
        grid-template-columns:24px 1fr;
        gap:12px;
        align-items:flex-start;
        color:#0f1b3d;
        font-weight:800;
        font-size:14px;
        line-height:1.45;
        padding-bottom:14px;
        border-bottom:1px solid rgba(15,23,42,.08);
      }}

      .priceFeature:last-child {{
        border-bottom:0;
      }}

      .priceFeature span {{
        width:22px;
        height:22px;
        border-radius:999px;
        display:flex;
        align-items:center;
        justify-content:center;
        background:#0f9f8f;
        color:white;
        font-size:13px;
        font-weight:950;
      }}

      .priceFeature.main b {{
        font-size:15px;
      }}

      .priceForm {{
        margin-top:auto;
        padding-top:28px;
      }}

      .priceBtn {{
        width:100%;
        border:1px solid #0f9f8f;
        background:white;
        color:#0f766e;
        border-radius:14px;
        padding:15px 18px;
        font-weight:950;
        cursor:pointer;
      }}

      .priceBtn.primary {{
        background:linear-gradient(135deg,#0f9f8f,#0f766e);
        color:white;
        box-shadow:0 16px 34px rgba(15,118,110,.22);
      }}

      .assistSection {{
        margin-top:64px;
        padding:34px;
        border-radius:28px;
        background:linear-gradient(135deg,rgba(236,253,245,.85),rgba(239,246,255,.88));
        border:1px solid rgba(15,23,42,.08);
        display:grid;
        grid-template-columns:1fr 1.35fr;
        gap:28px;
        align-items:center;
        box-shadow:0 20px 60px rgba(2,8,23,.06);
      }}

      .assistIntro h2,
      .securitySection h2 {{
        margin:0;
        font-size:30px;
        line-height:1.1;
        color:#0f1b3d;
        font-weight:950;
      }}

      .assistIntro p {{
        color:#64748b;
        font-weight:750;
        line-height:1.55;
      }}

      .assistIcon {{
        width:48px;
        height:48px;
        border-radius:999px;
        background:rgba(20,184,166,.12);
        display:flex;
        align-items:center;
        justify-content:center;
        font-size:24px;
      }}

      .assistIcon.big {{
        width:64px;
        height:64px;
        margin-bottom:14px;
      }}

      .assistCards {{
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:22px;
      }}

      .assistMiniCard {{
        border-radius:22px;
        background:white;
        border:1px solid rgba(15,23,42,.08);
        padding:24px;
        box-shadow:0 18px 50px rgba(2,8,23,.08);
      }}

      .assistTitle {{
        margin-top:12px;
        font-size:18px;
        font-weight:950;
        color:#0f1b3d;
      }}

      .assistPrice {{
        margin-top:14px;
        color:#0f9f8f;
        font-size:34px;
        font-weight:950;
      }}

      .assistText {{
        margin-top:8px;
        color:#64748b;
        font-weight:750;
        line-height:1.45;
      }}

      .assistBtn {{
        margin-top:18px;
        display:inline-flex;
        padding:11px 16px;
        border-radius:12px;
        border:1px solid #0f9f8f;
        color:#0f766e;
        font-weight:950;
        text-decoration:none;
      }}

      .securitySection {{
        margin-top:54px;
        text-align:center;
      }}

      .securityGrid {{
        margin-top:28px;
        display:grid;
        grid-template-columns:repeat(4,1fr);
        gap:18px;
      }}

      .securityGrid div {{
        padding:18px;
        border-radius:22px;
        background:rgba(255,255,255,.88);
        border:1px solid rgba(15,23,42,.08);
        box-shadow:0 12px 35px rgba(2,8,23,.05);
      }}

      .securityGrid span {{
        display:block;
        font-size:28px;
      }}

      .securityGrid b {{
        display:block;
        margin-top:10px;
        color:#0f1b3d;
        font-size:15px;
        font-weight:950;
      }}

      .securityNote {{
        margin:26px auto 0;
        max-width:760px;
        color:#64748b;
        font-weight:800;
        border-top:1px solid rgba(15,23,42,.08);
        padding-top:20px;
      }}

      @media(max-width:980px) {{
        .priceGrid,
        .creditRules,
        .securityGrid {{
          grid-template-columns:1fr;
        }}

        .priceCard.highlighted {{
          transform:none;
        }}

        .assistSection {{
          grid-template-columns:1fr;
        }}

        .assistCards {{
          grid-template-columns:1fr;
        }}

        .freeBanner {{
          grid-template-columns:1fr;
          text-align:center;
        }}
      }}

      @media(max-width:560px) {{
        .pricingHero h1 {{
          font-size:34px;
        }}

        .pricingHero p {{
          font-size:16px;
        }}

        .priceCard {{
          min-height:auto;
        }}
      }}
    </style>
    """

    return HTMLResponse(page_public(
        title="Prezzi QRFACILE | QR code per etichetta digitale vino",
        subtitle="Prezzi",
        body_html=body
    ))
