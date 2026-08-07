from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.recycling_catalog import (
    CATALOG_SOURCE,
    CATALOG_VERSION,
    RECYCLING_CATALOG,
    get_recycling_suggestions,
)
from qrfacile_app.wine_compliance_ui import compliance_get as legacy_compliance_get

router = APIRouter(tags=["recycling-guidance"])


COMPONENT_LABELS = {
    "bottle": "Bottiglia",
    "closure": "Tappo",
    "capsule": "Capsula",
    "label": "Etichetta",
    "box": "Scatola",
    "other": "Altro",
}


def _guidance_markup() -> str:
    catalog_json = json.dumps(RECYCLING_CATALOG, ensure_ascii=False)
    suggestions = {
        component: get_recycling_suggestions(component)
        for component in COMPONENT_LABELS
    }
    suggestions_json = json.dumps(suggestions, ensure_ascii=False)
    component_labels_json = json.dumps(COMPONENT_LABELS, ensure_ascii=False)
    datalists = "".join(
        f'''<datalist id="qrf-recycling-materials-{component}">
          {''.join(f'<option value="{item["material"]}">{item["family"]} · {item["code"] or "codice da inserire"}</option>' for item in items)}
        </datalist>
        <datalist id="qrf-recycling-codes-{component}">
          {''.join(f'<option value="{item["code"]}">{item["material"]}</option>' for item in items if item["code"])}
        </datalist>'''
        for component, items in suggestions.items()
    )
    return f"""
    <style>
      .qrfRecycleStatus{{display:block;margin-top:7px;font-size:12px;font-weight:850;color:#64748b}}
      .qrfRecycleStatus.known{{color:#166534}}.qrfRecycleStatus.custom{{color:#92400e}}.qrfRecycleStatus.invalid{{color:#b91c1c}}
      .qrfRecycleTools{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px}}
      .qrfRecycleReset{{border:1px solid rgba(15,23,42,.16);background:#fff;border-radius:10px;padding:6px 9px;font-size:12px;font-weight:800;cursor:pointer}}
      .qrfRecycleReset:hover{{background:#f8fafc}}
      .qrfRecycleAccept{{border:0;background:#0f766e;color:#fff;border-radius:10px;padding:7px 10px;font-size:12px;font-weight:850;cursor:pointer}}
      .qrfRecycleCollection{{display:block;margin-top:7px;font-size:12px;color:#475569}}
      .qrfRecycleHelp{{margin-top:14px;padding:14px;border:1px solid rgba(2,8,23,.08);border-radius:16px;background:rgba(248,250,252,.86)}}
      .qrfRecycleHelp b{{display:block;margin-bottom:4px}}
      .qrfRecycleAlert{{display:none;margin:14px 0;padding:13px 14px;border-radius:14px;border:1px solid #fecaca;background:#fff1f2;color:#991b1b;font-weight:750}}
      .qrfRecycleAlert.show{{display:block}}
      .qrfRecycleAlert ul{{margin:7px 0 0 18px;padding:0}}
    </style>
    {datalists}
    <div id="qrf-recycling-alert" class="qrfRecycleAlert" role="alert" aria-live="assertive"></div>
    <script>
    (() => {{
      const catalog = {catalog_json};
      const suggestions = {suggestions_json};
      const componentLabels = {component_labels_json};
      const normalize = value => String(value || '').trim().toLowerCase().replace(/\\s+/g, ' ');
      const byMaterial = new Map(catalog.map(item => [normalize(item.material), item]));
      const byCode = new Map(catalog.filter(item => item.code).map(item => [normalize(item.code), item]));
      const tracked = [];

      document.querySelectorAll('input[name^="rec_"][name$="_product"]').forEach(product => {{
        const prefix = product.name.slice(0, -8);
        const component = prefix.replace(/^rec_/, '');
        const code = document.querySelector(`input[name="${{prefix}}_code"]`);
        const note = document.querySelector(`input[name="${{prefix}}_note"]`);
        if (!code) return;

        product.setAttribute('list', `qrf-recycling-materials-${{component}}`);
        product.setAttribute('autocomplete', 'off');
        code.setAttribute('list', `qrf-recycling-codes-${{component}}`);
        code.setAttribute('autocomplete', 'off');

        const status = document.createElement('span');
        status.className = 'qrfRecycleStatus';
        status.setAttribute('aria-live', 'polite');
        code.insertAdjacentElement('afterend', status);

        const tools = document.createElement('div');
        tools.className = 'qrfRecycleTools';
        const reset = document.createElement('button');
        reset.type = 'button';
        reset.className = 'qrfRecycleReset';
        reset.textContent = 'Ripristina suggerimento';
        tools.appendChild(reset);
        const accept = document.createElement('button');
        accept.type = 'button'; accept.className = 'qrfRecycleAccept'; accept.textContent = 'Usa codice suggerito'; accept.hidden = true;
        tools.appendChild(accept);
        status.insertAdjacentElement('afterend', tools);
        const collection = document.createElement('span'); collection.className='qrfRecycleCollection';
        tools.insertAdjacentElement('afterend', collection);

        const preferred = suggestions[component] || [];
        const recommended = preferred.find(item => !item.custom) || null;

        const evaluate = () => {{
          const materialItem = byMaterial.get(normalize(product.value));
          const codeItem = byCode.get(normalize(code.value));
          const item = codeItem || materialItem || null;
          const hasValue = product.value.trim() || code.value.trim();
          accept.hidden = true;
          collection.textContent = item && item.collection ? `Indicazione di raccolta: ${{item.collection}}` : '';

          if (!hasValue) {{
            status.className = 'qrfRecycleStatus';
            status.textContent = '';
            return {{state: 'empty', item: null}};
          }}
          if (!code.value.trim() || code.value.trim() === '-') {{
            status.className = 'qrfRecycleStatus invalid';
            status.textContent = 'Inserire il codice del materiale prima del salvataggio.';
            return {{state: 'missing-code', item}};
          }}
          if (!item || item.custom) {{
            status.className = 'qrfRecycleStatus custom';
            status.textContent = 'Valore personalizzato: conservarlo, ma verificarlo con il fornitore dell’imballaggio.';
            return {{state: 'custom', item}};
          }}
          if (materialItem && codeItem && materialItem.code !== codeItem.code) {{
            status.className = 'qrfRecycleStatus invalid';
            status.textContent = `Materiale e codice non coincidono: ${{materialItem.code}} atteso per il materiale selezionato.`;
            accept.hidden = false;
            return {{state: 'mismatch', item: codeItem}};
          }}
          if (!(item.components || []).includes(component)) {{
            status.className = 'qrfRecycleStatus invalid';
            status.textContent = `Codice presente nel catalogo, ma non consigliato per ${{componentLabels[component] || component}}.`;
            return {{state: 'wrong-component', item}};
          }}
          status.className = 'qrfRecycleStatus known';
          status.textContent = `Valido · ${{item.material}} · ${{item.collection}}`;
          return {{state: 'known', item}};
        }};

        const apply = item => {{
          if (!item) return evaluate();
          product.value = item.material || product.value;
          if (item.code) code.value = item.code;
          if (note && item.collection) note.value = item.collection;
          return evaluate();
        }};

        const applyFromMaterial = () => {{
          const item = byMaterial.get(normalize(product.value));
          if (item && item.code) code.value = item.code;
          if (item && note && !note.value.trim() && item.collection) note.value = item.collection;
          evaluate();
        }};
        const applyFromCode = () => {{
          const item = byCode.get(normalize(code.value));
          if (item && !product.value.trim()) product.value = item.material;
          if (item && note && !note.value.trim() && item.collection) note.value = item.collection;
          evaluate();
        }};

        product.addEventListener('change', applyFromMaterial);
        product.addEventListener('input', evaluate);
        product.addEventListener('blur', applyFromMaterial);
        code.addEventListener('change', applyFromCode);
        code.addEventListener('input', evaluate);
        code.addEventListener('blur', applyFromCode);
        reset.addEventListener('click', () => apply(recommended));
        accept.addEventListener('click', () => applyFromMaterial());

        product.placeholder = preferred.length
          ? 'es. ' + preferred.slice(0, 3).map(item => item.material.split(' - ')[0]).join(', ')
          : product.placeholder;

        tracked.push({{component, product, code, evaluate}});
        evaluate();
      }});

      const form = tracked.length ? tracked[0].product.closest('form') : null;
      const alertBox = document.getElementById('qrf-recycling-alert');
      if (form && alertBox) {{
        form.addEventListener('submit', event => {{
          const problems = [];
          tracked.forEach(entry => {{
            const result = entry.evaluate();
            if (['missing-code', 'mismatch', 'wrong-component'].includes(result.state)) {{
              problems.push(`${{componentLabels[entry.component] || entry.component}}: controllare materiale e codice.`);
            }}
          }});
          if (!problems.length) {{
            alertBox.className = 'qrfRecycleAlert';
            alertBox.innerHTML = '';
            return;
          }}
          event.preventDefault();
          alertBox.className = 'qrfRecycleAlert show';
          alertBox.innerHTML = '<b>Correggere prima del salvataggio:</b><ul>' + problems.map(item => `<li>${{item}}</li>`).join('') + '</ul>';
          alertBox.scrollIntoView({{behavior: 'smooth', block: 'center'}});
        }});
      }}
    }})();
    </script>
    <div class="qrfRecycleHelp">
      <b>Catalogo riciclabilità {CATALOG_VERSION}</b>
      Fonte di classificazione: {CATALOG_SOURCE}. Il sistema propone materiali coerenti con ciascun componente, compila il codice e l’indicazione di raccolta e segnala le incongruenze prima del salvataggio. I valori personalizzati restano ammessi, ma richiedono verifica con il fornitore dell’imballaggio. Le indicazioni di raccolta devono sempre essere confrontate con le disposizioni del Comune.
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
        "suggestions": {
            component: get_recycling_suggestions(component)
            for component in COMPONENT_LABELS
        },
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
