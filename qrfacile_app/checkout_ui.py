from __future__ import annotations

from fastapi import Request

from qrfacile_app.csrf_core import csrf_input
from qrfacile_app.ui_shell import esc
from qrfacile_app.pricing_config import get_purchase_pack, euro


def paypal_checkout_form(
    request: Request,
    *,
    pack: str,
    button_label: str = "Acquista ora",
    button_class: str = "btn btn-primary",
    billing_winery_id: int = 0,
    disabled: bool = False,
    disabled_label: str = "Non acquistabile online",
    style: str = "",
) -> str:
    winery_input = (
        f'<input type="hidden" name="billing_winery_id" value="{int(billing_winery_id)}">'
        if billing_winery_id else ""
    )
    disabled_attr = " disabled aria-disabled=\"true\"" if disabled else ""
    label = disabled_label if disabled else button_label
    style_attr = f' style="{esc(style)}"' if style else ""
    fiscal_html = ''
    product = get_purchase_pack(pack) or {}
    if product.get('annual'):
        net = int(product['amount_cents'])
        tax = (net * 22 + 50) // 100
        fiscal_html = f'''<p>Imponibile {euro(net)} + IVA ordinaria italiana 22% {euro(tax)}.
        Totale da pagare: <strong>{euro(net + tax)}</strong>. I crediti sono utilizzabili entro 12 mesi;
        non è un abbonamento e non prevede rinnovo automatico.</p>
        <label><input type="checkbox" name="fiscal_confirmation" value="IT_ORDINARY" required>
        Confermo acquisto professionale con sede fiscale in Italia, regime IVA ordinario
        e accetto il totale e le <a href="/terms">condizioni di acquisto</a>:
        unità non utilizzate in scadenza a 12 mesi, senza riporto; i QR creati restano attivi per la durata scelta.
        Per estero o regimi speciali: <a href="/support">richiedi preventivo</a>.</label>'''
    return f"""
    <form method="post" action="/paypal/start" data-paypal-checkout{style_attr}>
      {csrf_input(request)}
      <input type="hidden" name="pack" value="{esc(pack)}">
      {winery_input}
      {fiscal_html}
      <button class="{esc(button_class)}" type="submit" data-paypal-submit{disabled_attr}>
        {esc(label)}
      </button>
      <div class="checkoutStatus" data-paypal-status role="status" aria-live="polite" hidden></div>
    </form>
    """


def paypal_checkout_script() -> str:
    return """
    <script>
    document.addEventListener('submit', function (event) {
      const form = event.target.closest('form[data-paypal-checkout]');
      if (!form) return;
      if (form.dataset.submitting === 'true') {
        event.preventDefault();
        return;
      }
      form.dataset.submitting = 'true';
      const button = form.querySelector('[data-paypal-submit]');
      const status = form.querySelector('[data-paypal-status]');
      if (button) {
        button.disabled = true;
        button.setAttribute('aria-busy', 'true');
        button.textContent = 'Connessione a PayPal...';
      }
      if (status) {
        status.hidden = false;
        status.textContent = 'Connessione sicura a PayPal in corso.';
      }
    });
    </script>
    """
