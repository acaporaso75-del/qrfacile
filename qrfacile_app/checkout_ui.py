from __future__ import annotations

from fastapi import Request

from qrfacile_app.csrf_core import csrf_input
from qrfacile_app.ui_shell import esc


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
    return f"""
    <form method="post" action="/paypal/start" data-paypal-checkout{style_attr}>
      {csrf_input(request)}
      <input type="hidden" name="pack" value="{esc(pack)}">
      {winery_input}
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
