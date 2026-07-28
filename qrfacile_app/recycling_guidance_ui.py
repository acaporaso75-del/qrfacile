from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.recycling_catalog import (
    CATALOG_SOURCE,
    CATALOG_VERSION,
    RECYCLING_CATALOG,
)
from qrfacile_app.wine_compliance_ui import compliance_get as legacy_compliance_get

router = APIRouter(tags=["recycling-guidance"])


def _guidance_markup() -> str:
    catalog_json = json.dumps(RECYCLING_CATALOG, ensure_ascii=False)
    return f"""
    <style>
      .qrfRecycleStatus{{display:block;margin-top:7px;font-size:12px;font-weight:850;color:#64748b}}
      .qrfRecycleStatus.known{{color:#166534}}.qrfRecycleStatus.custom{{color:#92400e}}
      .qrfRecycleHelp{{margin-top:14px;padding:14px;border:1px solid rgba(2,8,23,.08);border-radius:16px;background:rgba(248,250,252,.86)}}
      .qrfRecycleHelp b{{display:block;margin-bottom:4px}}
    </style>
    <datalist id="qrf-recycling-materials">
      {''.join(f'<option value="{item["material"]}">{item["family"]} · {item["code"] or "codice da inserire"}</option>' for item in RECYCLING_CATALOG)}
    </datalist>
    <datalist id="qrf-recycling-codes">
      {''.join(f'<option value="{item["code"]}">{item["material"]}</option>' for item in RECYCLING_CATALOG if item["code"])}
    </datalist>
    <script>
    (() => {{
      const catalog = {catalog_json};
      const normalize = value => String(value || '').trim().toLowerCase().replace(/\\s+/g, ' ');
      const byMaterial = new Map(catalog.map(item => [normalize(item.material), item]));
      const byCode = new Map(catalog.filter(item => item.code).map(item => [normalize(item.code), item]));

      document.querySelectorAll('input[name^="rec_"][name$="_product"]').forEach(product => {{
        const prefix = product.name.slice(0, -8);
        const component = prefix.replace(/^rec_/, '');
        const code = document.querySelector(`input[name="${{prefix}}_code"]`);
        const note = document.querySelector(`input[name="${{prefix}}_note"]`);
        if (!code) return;

        product.setAttribute('list', 'qrf-recycling-materials');
        product.setAttribute('autocomplete', 'off');
        code.setAttribute('list', 'qrf-recycling-codes');
        code.setAttribute('autocomplete', 'off');

        const status = document.createElement('span');
        status.className = 'qrfRecycleStatus';
        status.setAttribute('aria-live', 'polite');
        code.insertAdjacentElement('afterend', status);

        const setStatus = item => {{
          if (item && !item.custom) {{
            status.className = 'qrfRecycleStatus known';
            status.textContent = `Codice presente nel catalogo ${{{json.dumps(CATALOG_VERSION)}}}.`;
          }} else if (product.value.trim() || code.value.trim()) {{
            status.className = 'qrfRecycleStatus custom';
            status.textContent = 'Valore personalizzato: conservarlo, ma verificarlo con il fornitore dell’imballaggio.';
          }} else {{
            status.className = 'qrfRecycleStatus';
            status.textContent = '';
          }}
        }};

        const apply = item => {{
          if (!item) {{ setStatus(null); return; }}
          if (!product.value.trim()) product.value = item.material;
          if (!code.value.trim() && item.code) code.value = item.code;
          if (note && !note.value.trim() && item.collection) note.value = item.collection;
          setStatus(item);
        }};

        const applyFromMaterial = () => apply(byMaterial.get(normalize(product.value)));
        const applyFromCode = () => apply(byCode.get(normalize(code.value)));

        product.addEventListener('change', applyFromMaterial);
        product.addEventListener('input', applyFromMaterial);
        code.addEventListener('change', applyFromCode);
        code.addEventListener('input', applyFromCode);

        const preferred = catalog.filter(item => (item.components || []).includes(component) && !item.custom);
        product.placeholder = preferred.length
          ? 'es. ' + preferred.slice(0, 3).map(item => item.material.split(' - ')[0]).join(', ')
          : product.placeholder;

        applyFromCode();
        if (!code.value.trim()) applyFromMaterial();
      }});
    }})();
    </script>
    <div class="qrfRecycleHelp">
      <b>Catalogo riciclabilità {CATALOG_VERSION}</b>
      Fonte di classificazione: {CATALOG_SOURCE}. Seleziona un suggerimento oppure inserisci liberamente un materiale o codice non presente. I valori personalizzati non vengono eliminati né bloccati, ma richiedono verifica con il fornitore dell’imballaggio. Le indicazioni di raccolta devono sempre essere confrontate con le disposizioni del Comune.
    </div>
    """


@router.get("/api/compliance/recycling-catalog", response_class=JSONResponse)
def recycling_catalog_api(request: Request):
    require_any_role(request, ("admin", "studio", "winery"))
    return JSONResponse({
        "catalog_version": CATALOG_VERSION,
        "source": CATALOG_SOURCE,
        "count": len(RECYCLING_CATALOG),
        "items": RECYCLING_CATALOG,
    })


@router.get("/app/wine/{wine_id}/compliance", response_class=HTMLResponse)
def guided_compliance_get(request: Request, wine_id: int, msg: str = ""):
    response = legacy_compliance_get(request, wine_id, msg)
    body = response.body.decode("utf-8")
    marker = "</body>"
    if marker in body:
        body = body.replace(marker, _guidance_markup() + marker, 1)
    headers = dict(response.headers)
    headers.pop("content-length", None)
    return HTMLResponse(body, status_code=response.status_code, headers=headers)
