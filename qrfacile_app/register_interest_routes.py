from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

def esc(s: str) -> str:
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

@router.get("/register-interest", response_class=HTMLResponse)
def register_interest(request: Request, type: str = "private"):
    type = (type or "private").strip().lower()
    label = "Privato" if type == "private" else "HoReCa (ristorante/pub/hotel)"

    html = f"""<!doctype html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Richiesta accesso – QRFACILE</title>
<style>
body{{margin:0;background:#f4f6f8;font-family:Arial}}
.wrap{{max-width:820px;margin:18px auto;padding:14px}}
.card{{background:#fff;border-radius:18px;padding:16px;box-shadow:0 8px 20px rgba(0,0,0,.06);margin-top:12px}}
.h2{{margin:0;font-size:18px;font-weight:900}}
.muted{{color:#6b7280;font-size:13px;line-height:1.35}}
.btn{{display:inline-block;background:#065f46;color:#fff;padding:10px 14px;border-radius:12px;font-weight:900;text-decoration:none}}
.btnG{{display:inline-block;border:1px solid #e5e7eb;color:#111827;padding:10px 14px;border-radius:12px;font-weight:900;text-decoration:none}}
</style>
</head><body>
<div class="wrap">
  <div class="card">
    <div class="h2">Richiesta accesso – {esc(label)}</div>
    <div class="muted" style="margin-top:8px">
      Questa modalità è in attivazione. Per ora possiamo abilitarla in beta e raccogliere i requisiti.
    </div>
    <div class="muted" style="margin-top:10px">
      Scrivici cosa ti serve e ti attiviamo l’accesso.
    </div>
    <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap">
      <a class="btn" href="/login">Accedi</a>
      <a class="btnG" href="/">Torna alla home</a>
    </div>
  </div>
</div>
</body></html>
"""
    return HTMLResponse(html)
