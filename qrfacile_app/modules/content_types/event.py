"""Evento: date, place and description, with an 'add to calendar' file."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.responses import Response

from qrfacile_app.modules.content_types.base import ContentError
from qrfacile_app.modules.content_types.link import valid_url
from qrfacile_app.modules.content_types.page import field, public_page, text
from qrfacile_app.ui_shell import esc

FORMAT = "%Y-%m-%dT%H:%M"


def _when(form, key: str, *, required: bool) -> str:
    value = str(form.get(key) or "").strip()
    if not value:
        if required:
            raise ContentError("Indica data e ora di inizio.")
        return ""
    try:
        return datetime.strptime(value, FORMAT).strftime(FORMAT)
    except ValueError as exc:
        raise ContentError("Data e ora non valide.") from exc


def _ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_time(value: str) -> str:
    return datetime.strptime(value, FORMAT).strftime("%Y%m%dT%H%M%S")


def _label(value: str) -> str:
    return datetime.strptime(value, FORMAT).strftime("%d/%m/%Y %H:%M")


class EventType:
    key = "event"
    label = "Evento"

    def parse(self, form, files, previous, *, qr_item_id):
        title = text(form, "event_title", 100)
        if not title:
            raise ContentError("Inserisci il nome dell'evento.")
        start = _when(form, "event_start", required=True)
        end = _when(form, "event_end", required=False)
        if end and end <= start:
            raise ContentError("La fine dell'evento deve essere dopo l'inizio.")
        link = text(form, "event_link", 2000)
        if link and not valid_url(link):
            raise ContentError("Link non valido: usa un indirizzo che inizia con https://")
        return {
            "title": title, "start": start, "end": end, "place": text(form, "event_place", 160),
            "text": str(form.get("event_text") or "").strip()[:1000], "link": link,
        }

    def is_complete(self, content: dict) -> bool:
        return bool(content.get("title") and content.get("start"))

    def asset_response(self, content: dict, name: str):
        if name != "evento.ics":
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        lines = [
            "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//QRFacile//Link//IT", "BEGIN:VEVENT",
            f"UID:{stamp}-{abs(hash(content['title'] + content['start']))}@qrfacile.it", f"DTSTAMP:{stamp}",
            f"DTSTART;TZID=Europe/Rome:{_ics_time(content['start'])}",
        ]
        if content.get("end"):
            lines.append(f"DTEND;TZID=Europe/Rome:{_ics_time(content['end'])}")
        lines.append(f"SUMMARY:{_ics_escape(content['title'])}")
        if content.get("place"):
            lines.append(f"LOCATION:{_ics_escape(content['place'])}")
        if content.get("text"):
            lines.append(f"DESCRIPTION:{_ics_escape(content['text'])}")
        if content.get("link"):
            lines.append(f"URL:{content['link']}")
        lines += ["END:VEVENT", "END:VCALENDAR"]
        return Response("\r\n".join(lines) + "\r\n", media_type="text/calendar", headers={
            "Content-Disposition": 'attachment; filename="evento.ics"', "Cache-Control": "no-store",
        })

    def public_response(self, content: dict, *, slug: str):
        when = _label(content["start"]) + (f" – {_label(content['end'])}" if content.get("end") else "")
        place = f"<p><b>Dove:</b> {esc(content['place'])}</p>" if content.get("place") else ""
        description = f'<p class="text">{esc(content["text"])}</p>' if content.get("text") else ""
        link = f'<a class="button" href="{esc(content["link"])}" rel="noopener">Maggiori informazioni</a>' if content.get("link") else ""
        inner = (
            f"<h1>{esc(content['title'])}</h1><p><b>Quando:</b> {esc(when)}</p>{place}{description}"
            f'<a class="button" href="/d/{esc(slug)}/a/evento.ics">Aggiungi al calendario</a>{link}'
        )
        return public_page(content["title"], inner, slug=slug)

    def editor_html(self, content: dict | None) -> str:
        content = content or {}
        return (
            field("event_title", "Nome dell'evento (obbligatorio)", content.get("title", ""), maxlength=100, prefix="ev")
            + field("event_start", "Inizio (obbligatorio)", content.get("start", ""), type_="datetime-local", prefix="ev")
            + field("event_end", "Fine (facoltativo)", content.get("end", ""), type_="datetime-local", prefix="ev")
            + field("event_place", "Luogo", content.get("place", ""), maxlength=160, prefix="ev")
            + '<div><label for="ev-text">Descrizione</label>'
            + f'<textarea id="ev-text" class="input" name="event_text" maxlength="1000" rows="4">{esc(content.get("text", ""))}</textarea></div>'
            + field("event_link", "Link per iscrizioni o biglietti (facoltativo)", content.get("link", ""), maxlength=2000, prefix="ev")
        )
