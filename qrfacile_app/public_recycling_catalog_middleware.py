from __future__ import annotations

import json
import re
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from qrfacile_app.services.recycling_catalog import CATALOG_SOURCE, CATALOG_VERSION, RECYCLING_CATALOG

PUBLIC_LABEL_PATH = re.compile(r"^/(?:e|preview)/[^/]+/?$")


class PublicRecyclingCatalogMiddleware(BaseHTTPMiddleware):
    """Enrich public e-label recycling cards using the central packaging catalog."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        content_type = response.headers.get("content-type", "").lower()
        if (
            request.method != "GET"
            or not PUBLIC_LABEL_PATH.match(request.url.path)
            or response.status_code != 200
            or "text/html" not in content_type
        ):
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            html = body.decode("utf-8")
        except UnicodeDecodeError:
            return Response(content=body, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)

        widget = _public_recycling_widget()
        marker = "</body>"
        html = html.replace(marker, f"{widget}{marker}", 1) if marker in html else html + widget
        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(content=html, status_code=response.status_code, headers=headers, media_type="text/html")


def _public_recycling_widget() -> str:
    catalog_json = json.dumps(RECYCLING_CATALOG, ensure_ascii=False)
    return f"""
<style>
.qrfPublicRecycleMeta{{margin-top:12px;padding:12px 14px;border:1px solid rgba(2,8,23,.08);border-radius:16px;background:rgba(248,250,252,.9);font-size:12px;line-height:1.5;color:#475569}}
.qrfPublicRecycleMeta b{{color:#0f172a}}
.qrfPublicRecycleBadge{{display:inline-flex;align-items:center;margin-top:8px;padding:5px 8px;border-radius:999px;font-size:11px;font-weight:900;border:1px solid rgba(2,8,23,.08)}}
.qrfPublicRecycleBadge.known{{background:#ecfdf5;color:#166534}}.qrfPublicRecycleBadge.custom{{background:#fff7ed;color:#9a3412}}
.qrfPublicRecycleCollection{{margin-top:7px;font-size:12px;font-weight:760;color:#475569}}
</style>
<script>
(function(){{
  const catalog={catalog_json};
  const normalize=value=>String(value||'').trim().toLowerCase().replace(/\\s+/g,' ');
  const byCode=new Map(catalog.filter(item=>item.code).map(item=>[normalize(item.code),item]));
  const cards=document.querySelectorAll('.recycleItem');
  cards.forEach(card=>{{
    const codeNode=card.querySelector('.materialCode');
    const productNode=card.querySelector('.recycleProduct');
    const rawCode=codeNode ? String(codeNode.textContent||'').split(',')[0].trim() : '';
    const item=byCode.get(normalize(rawCode));
    const badge=document.createElement('span');
    badge.className='qrfPublicRecycleBadge '+(item?'known':'custom');
    badge.textContent=item?'Codice verificato nel catalogo':'Codice personalizzato da verificare';
    card.appendChild(badge);
    if(item && item.collection){{
      const collection=document.createElement('div');
      collection.className='qrfPublicRecycleCollection';
      collection.textContent=item.collection;
      card.appendChild(collection);
      if(productNode && !String(productNode.textContent||'').trim()) productNode.textContent=item.material;
    }}
  }});
  const grid=document.querySelector('.recycleGrid');
  if(grid && !document.getElementById('qrf-public-recycle-meta')){{
    const meta=document.createElement('div');
    meta.id='qrf-public-recycle-meta';
    meta.className='qrfPublicRecycleMeta';
    meta.innerHTML='<b>Informazioni ambientali</b><br>Catalogo {CATALOG_VERSION} · {CATALOG_SOURCE}. Le modalità di raccolta vanno verificate secondo le disposizioni del Comune.';
    grid.insertAdjacentElement('afterend',meta);
  }}
}})();
</script>
"""
