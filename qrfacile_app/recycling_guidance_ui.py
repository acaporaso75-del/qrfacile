from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from qrfacile_app.wine_compliance_ui import compliance_get as legacy_compliance_get

router = APIRouter(tags=["recycling-guidance"])

CATALOG_VERSION = "2026.07.1"

RECYCLING_CATALOG = [
    {"family": "Plastica", "material": "PET - Polietilene tereftalato", "code": "PET 1", "collection": "Raccolta plastica"},
    {"family": "Plastica", "material": "HDPE - Polietilene alta densità", "code": "HDPE 2", "collection": "Raccolta plastica"},
    {"family": "Plastica", "material": "PVC - Polivinilcloruro", "code": "PVC 3", "collection": "Verifica disposizioni comunali"},
    {"family": "Plastica", "material": "LDPE - Polietilene bassa densità", "code": "LDPE 4", "collection": "Raccolta plastica"},
    {"family": "Plastica", "material": "PP - Polipropilene", "code": "PP 5", "collection": "Raccolta plastica"},
    {"family": "Plastica", "material": "PS - Polistirene", "code": "PS 6", "collection": "Raccolta plastica"},
    {"family": "Plastica", "material": "Altre plastiche", "code": "OTHER 7", "collection": "Verifica disposizioni comunali"},
    {"family": "Carta", "material": "Cartone ondulato", "code": "PAP 20", "collection": "Raccolta carta"},
    {"family": "Carta", "material": "Cartone non ondulato", "code": "PAP 21", "collection": "Raccolta carta"},
    {"family": "Carta", "material": "Carta", "code": "PAP 22", "collection": "Raccolta carta"},
    {"family": "Metallo", "material": "Acciaio / banda stagnata", "code": "FE 40", "collection": "Raccolta metalli"},
    {"family": "Metallo", "material": "Alluminio", "code": "ALU 41", "collection": "Raccolta metalli"},
    {"family": "Legno", "material": "Legno", "code": "FOR 50", "collection": "Raccolta legno"},
    {"family": "Legno", "material": "Sughero", "code": "FOR 51", "collection": "Raccolta dedicata o organico secondo Comune"},
    {"family": "Tessile", "material": "Cotone", "code": "COT 60", "collection": "Raccolta tessili"},
    {"family": "Tessile", "material": "Iuta", "code": "TEX 61", "collection": "Raccolta tessili"},
    {"family": "Vetro", "material": "Vetro incolore", "code": "GL 70", "collection": "Raccolta vetro"},
    {"family": "Vetro", "material": "Vetro verde", "code": "GL 71", "collection": "Raccolta vetro"},
    {"family": "Vetro", "material": "Vetro marrone", "code": "GL 72", "collection": "Raccolta vetro"},
    {"family": "Composto", "material": "Carta/cartone + plastica", "code": "C/PAP 81", "collection": "Verifica materiale prevalente e disposizioni comunali"},
    {"family": "Composto", "material": "Carta/cartone + alluminio", "code": "C/PAP 82", "collection": "Verifica materiale prevalente e disposizioni comunali"},
    {"family": "Composto", "material": "Carta/cartone + plastica + alluminio", "code": "C/PAP 84", "collection": "Verifica materiale prevalente e disposizioni comunali"},
    {"family": "Composto", "material": "Plastica + alluminio", "code": "C/OTHER 90", "collection": "Verifica polimero prevalente e disposizioni comunali"},
    {"family": "Personalizzato", "material": "Altro materiale / codice personalizzato", "code": "", "collection": "Verificare con il fornitore e il Comune"},
]


def _guidance_markup() -> str:
    catalog_json = json.dumps(RECYCLING_CATALOG, ensure_ascii=False)
    return f"""
    <datalist id="qrf-recycling-materials">
      {''.join(f'<option value="{item["material"]}">{item["family"]} · {item["code"]}</option>' for item in RECYCLING_CATALOG)}
    </datalist>
    <datalist id="qrf-recycling-codes">
      {''.join(f'<option value="{item["code"]}">{item["material"]}</option>' for item in RECYCLING_CATALOG if item["code"])}
    </datalist>
    <script>
    (() => {{
      const catalog = {catalog_json};
      const byMaterial = new Map(catalog.map(item => [item.material.toLowerCase(), item]));
      const byCode = new Map(catalog.filter(item => item.code).map(item => [item.code.toLowerCase(), item]));

      document.querySelectorAll('input[name^="rec_"][name$="_product"]').forEach(product => {{
        const prefix = product.name.slice(0, -8);
        const code = document.querySelector(`input[name="${{prefix}}_code"]`);
        const note = document.querySelector(`input[name="${{prefix}}_note"]`);
        if (!code) return;

        product.setAttribute('list', 'qrf-recycling-materials');
        product.setAttribute('autocomplete', 'off');
        code.setAttribute('list', 'qrf-recycling-codes');
        code.setAttribute('autocomplete', 'off');

        const applyFromMaterial = () => {{
          const item = byMaterial.get(product.value.trim().toLowerCase());
          if (!item) {{
            product.dataset.catalogStatus = 'custom';
            return;
          }}
          product.dataset.catalogStatus = 'known';
          if (!code.value.trim() && item.code) code.value = item.code;
          if (note && !note.value.trim() && item.collection) note.value = item.collection;
        }};

        const applyFromCode = () => {{
          const item = byCode.get(code.value.trim().toLowerCase());
          if (!item) {{
            code.dataset.catalogStatus = 'custom';
            return;
          }}
          code.dataset.catalogStatus = 'known';
          if (!product.value.trim()) product.value = item.material;
          if (note && !note.value.trim() && item.collection) note.value = item.collection;
        }};

        product.addEventListener('change', applyFromMaterial);
        product.addEventListener('input', applyFromMaterial);
        code.addEventListener('change', applyFromCode);
        code.addEventListener('input', applyFromCode);
      }});
    }})();
    </script>
    <div class="note" style="margin-top:14px">
      Catalogo riciclabilità {CATALOG_VERSION}: scegli un valore suggerito oppure inserisci liberamente un materiale o codice non presente. I valori personalizzati devono essere verificati con il fornitore dell’imballaggio.
    </div>
    """


@router.get("/app/wine/{wine_id}/compliance", response_class=HTMLResponse)
def guided_compliance_get(request: Request, wine_id: int, msg: str = ""):
    response = legacy_compliance_get(request, wine_id, msg)
    body = response.body.decode("utf-8")
    marker = "</body>"
    if marker in body:
        body = body.replace(marker, _guidance_markup() + marker, 1)
    return HTMLResponse(body, status_code=response.status_code, headers=dict(response.headers))
