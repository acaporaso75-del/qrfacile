from __future__ import annotations

import html
from typing import Iterable


def esc(s: str | None) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def pill(href: str, text: str) -> str:
    return f"<a class='pill' href='{esc(href)}'>{esc(text)}</a>"


def btn(href: str, text: str, cls: str = "btn") -> str:
    return f"<a class='{esc(cls)}' href='{esc(href)}'>{esc(text)}</a>"


def note(text: str, tone: str = "ok") -> str:
    tone = (tone or "ok").strip().lower()
    cls = "note"
    if tone in ("warn", "warning"):
        cls += " note-warn"
    elif tone in ("err", "error", "danger"):
        cls += " note-err"
    return f"<div class='{cls}'>{esc(text)}</div>"


def layout(title: str, body: str, *, subtitle: str = "", top_actions: str = "") -> str:
    """
    Layout premium base (SaaS modern) con CSS globale in /static/app.css
    """
    subtitle_html = f"<div class='brand-sub'>{esc(subtitle)}</div>" if subtitle else "<div class='brand-sub'> </div>"
    actions_html = f"<div style='display:flex;gap:10px;flex-wrap:wrap'>{top_actions}</div>" if top_actions else ""
    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>
<div class="container">

  <div class="topbar">
    <div class="brand">
      <div class="brand-dot"></div>
      <div>
        <div class="brand-title">QRFACILE</div>
        {subtitle_html}
      </div>
    </div>
    {actions_html}
  </div>

  {body}

</div>
</body>
</html>
"""


# -----------------------------
# Badge + Label Card (riusabile ovunque)
# -----------------------------
def badge_html(text: str, tone: str = "muted") -> str:
    tone = (tone or "muted").strip().lower()
    return f"<span class='badge badge-{esc(tone)}'>{esc(text)}</span>"


def label_card(*,
               title: str,
               subtitle: str,
               thumb_url: str,
               href: str,
               badges: list[tuple[str, str]] | None = None,
               actions: list[tuple[str, str]] | None = None) -> str:
    """
    Card standard SaaS (miniatura + testo + badge + azioni).
    badges: [(text, tone)] tone: success|warn|danger|info|muted
    actions: [(label, href)]
    """
    badges = badges or []
    actions = actions or []

    badges_html = "".join(badge_html(t, tone) for (t, tone) in badges)

    actions_html = ""
    if actions:
        actions_html = "<div class='cardActions'>" + "".join(
            f"<a class='btn btn-soft' href='{esc(h)}'>{esc(lbl)}</a>"
            for (lbl, h) in actions
        ) + "</div>"

    return f"""
    <a class="labelCard" href="{esc(href)}">
      <div class="thumbWrap">
        <img class="thumbImg" src="{esc(thumb_url)}" loading="lazy" alt="Etichetta">
        <div class="thumbBadges">{badges_html}</div>
      </div>

      <div class="labelMeta">
        <div>
          <div class="labelTitle">{esc(title)}</div>
          <div class="labelSub">{esc(subtitle)}</div>
        </div>
        {actions_html}
      </div>
    </a>
    """


def placeholder_thumb() -> str:
    # usiamo un placeholder SVG statico: /static/img/placeholder_label.svg
    return "/static/img/placeholder_label.svg"
