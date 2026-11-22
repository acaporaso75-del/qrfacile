"""Six more QRFacile Link content types: vCard, Wi-Fi, review, WhatsApp, gallery, event."""
from __future__ import annotations

import io

import pytest
from PIL import Image

from qrfacile_app.modules.content_types import CONTENT_TYPES, ContentError, get_type
from tests.test_link_app_area import area  # noqa: F401 - fixture


def _upload(name, data):
    from types import SimpleNamespace

    return SimpleNamespace(filename=name, file=io.BytesIO(data))


def _png(size=(40, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "red").save(buffer, format="PNG")
    return buffer.getvalue()


def test_all_types_are_registered_in_order():
    assert list(CONTENT_TYPES) == ["link", "pdf", "minipage", "vcard", "wifi", "review", "whatsapp", "gallery", "event"]
    for ctype in CONTENT_TYPES.values():
        assert ctype.label and callable(ctype.is_complete)


def test_vcard_downloads_a_contact():
    vcard = get_type("vcard")
    content = vcard.parse({"vcard_name": "Mario Rossi", "vcard_org": "Bar Sport; Benevento",
                           "vcard_phone": "+39 0824 123456", "vcard_email": "info@example.test",
                           "vcard_website": "https://example.test", "vcard_address": "Via Roma 1, Benevento"},
                          {}, None, qr_item_id=1)
    response = vcard.public_response(content, slug="AAA")
    body = response.body.decode()
    assert response.media_type == "text/vcard"
    assert body.startswith("BEGIN:VCARD\r\nVERSION:3.0\r\n") and body.endswith("END:VCARD\r\n")
    assert "FN:Mario Rossi\r\n" in body and "ORG:Bar Sport\\; Benevento\r\n" in body
    assert "TEL;TYPE=CELL:+390824123456\r\n" in body and "EMAIL:info@example.test\r\n" in body
    assert 'filename="mario-rossi.vcf"' in response.headers["content-disposition"]
    for bad in ({"vcard_name": ""}, {"vcard_name": "X\r\nEND:VCARD"}, {"vcard_name": "X", "vcard_website": "javascript:x"}):
        with pytest.raises(ContentError):
            vcard.parse(bad, {}, None, qr_item_id=1)


def test_wifi_page_and_direct_payload():
    wifi = get_type("wifi")
    content = wifi.parse({"wifi_ssid": "Bar<Sport>", "wifi_password": "pa;ss:1234", "wifi_security": "WPA"},  # pragma: allowlist secret
                         {}, None, qr_item_id=1)
    html = wifi.public_response(content, slug="AAA").body.decode()
    assert "Bar&lt;Sport&gt;" in html and "pa;ss:1234" in html and "<script" not in html
    from qrfacile_app.modules.content_types.wifi import wifi_qr_payload

    assert wifi_qr_payload(content) == "WIFI:T:WPA;S:Bar<Sport>;P:pa\\;ss\\:1234;;"
    open_net = wifi.parse({"wifi_ssid": "Ospiti", "wifi_password": "", "wifi_security": "nopass"}, {}, None, qr_item_id=1)
    assert wifi_qr_payload(open_net) == "WIFI:T:nopass;S:Ospiti;;"
    with pytest.raises(ContentError):
        wifi.parse({"wifi_ssid": "X", "wifi_password": "", "wifi_security": "WPA"}, {}, None, qr_item_id=1)


def test_review_redirects_to_google_review_page():
    review = get_type("review")
    by_place = review.parse({"review_place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4", "review_url": ""}, {}, None, qr_item_id=1)
    response = review.public_response(by_place, slug="AAA")
    assert response.status_code == 302
    assert response.headers["location"] == "https://search.google.com/local/writereview?placeid=ChIJN1t_tDeuEmsRUsoyG83frY4"
    by_url = review.parse({"review_place_id": "", "review_url": "https://g.page/r/abc/review"}, {}, None, qr_item_id=1)
    assert review.public_response(by_url, slug="AAA").headers["location"] == "https://g.page/r/abc/review"
    for bad in ({"review_place_id": "", "review_url": ""}, {"review_place_id": "x y", "review_url": ""},
                {"review_place_id": "", "review_url": "javascript:alert(1)"}):
        with pytest.raises(ContentError):
            review.parse(bad, {}, None, qr_item_id=1)


def test_whatsapp_opens_chat_with_message():
    whatsapp = get_type("whatsapp")
    content = whatsapp.parse({"whatsapp_number": "+39 333 123 4567", "whatsapp_message": "Ciao, vorrei prenotare & info"},
                             {}, None, qr_item_id=1)
    location = whatsapp.public_response(content, slug="AAA").headers["location"]
    assert location == "https://wa.me/393331234567?text=Ciao%2C%20vorrei%20prenotare%20%26%20info"
    with pytest.raises(ContentError):
        whatsapp.parse({"whatsapp_number": "123", "whatsapp_message": ""}, {}, None, qr_item_id=1)


def test_gallery_images_videos_and_assets(tmp_path, monkeypatch):
    from qrfacile_app.modules.content_types import gallery as module

    monkeypatch.setattr(module, "get_uploads_dir", lambda: str(tmp_path))
    gallery = get_type("gallery")
    with pytest.raises(ContentError):
        gallery.parse({"gallery_title": "T", "gallery_video_1": "javascript:x"}, {}, None, qr_item_id=4)
    with pytest.raises(ContentError):
        gallery.parse({"gallery_title": "T"}, {"gallery_image_1": _upload("b.jpg", b"not an image")}, None, qr_item_id=4)
    content = gallery.parse({"gallery_title": "Le nostre torte", "gallery_video_1": "https://www.youtube.com/watch?v=abc"},
                            {"gallery_image_1": _upload("a.png", _png())}, None, qr_item_id=4)
    assert len(content["images"]) == 1 and content["images"][0].startswith("modules/link/4/img-")
    assert content["videos"] == ["https://www.youtube.com/watch?v=abc"]
    # A second save without new files keeps the images; removing one deletes it from the content.
    kept = gallery.parse({"gallery_title": "Torte"}, {"gallery_image_1": _upload("c.png", _png((10, 10)))}, content, qr_item_id=4)
    assert len(kept["images"]) == 2
    removed = gallery.parse({"gallery_title": "Torte", "gallery_remove_1": "on"}, {}, kept, qr_item_id=4)
    assert removed["images"] == kept["images"][1:]
    assert gallery.files(kept) == set(kept["images"])
    html = gallery.public_response(content, slug="AAA").body.decode()
    assert 'src="/d/AAA/a/img-1"' in html and "/uploads/" not in html and "<script" not in html
    asset = gallery.asset_response(content, "img-1")
    assert asset.status_code == 200 and asset.media_type == "image/png"
    assert gallery.asset_response(content, "img-9") is None and gallery.asset_response(content, "../x") is None
    with pytest.raises(ContentError):
        many = {f"gallery_image_{i}": _upload(f"{i}.png", _png((5 + i, 5))) for i in range(1, 14)}
        gallery.parse({"gallery_title": "T"}, many, None, qr_item_id=4)


def test_event_page_and_calendar_file():
    event = get_type("event")
    content = event.parse({"event_title": "Degustazione; vini", "event_start": "2026-12-20T18:30",
                           "event_end": "2026-12-20T21:00", "event_place": "Cantina, Benevento",
                           "event_text": "Prenota <b>ora</b>", "event_link": "https://example.test/prenota"},
                          {}, None, qr_item_id=1)
    html = event.public_response(content, slug="EVT").body.decode()
    assert "Degustazione; vini" in html and "&lt;b&gt;ora&lt;/b&gt;" in html and "20/12/2026 18:30" in html
    assert 'href="/d/EVT/a/evento.ics"' in html
    ics = event.asset_response(content, "evento.ics")
    body = ics.body.decode()
    assert ics.media_type == "text/calendar"
    assert "DTSTART;TZID=Europe/Rome:20261220T183000\r\n" in body and "DTEND;TZID=Europe/Rome:20261220T210000\r\n" in body
    assert "SUMMARY:Degustazione\\; vini\r\n" in body and "LOCATION:Cantina\\, Benevento\r\n" in body
    for bad in ({"event_title": "", "event_start": "2026-12-20T18:30"},
                {"event_title": "X", "event_start": "ieri"},
                {"event_title": "X", "event_start": "2026-12-20T18:30", "event_end": "2026-12-20T17:00"}):
        with pytest.raises(ContentError):
            event.parse(bad, {}, None, qr_item_id=1)


@pytest.mark.parametrize("key", ["vcard", "wifi", "review", "whatsapp", "gallery", "event"])
def test_editors_are_labelled(key):
    import re

    html = get_type(key).editor_html(None)
    labels = set(re.findall(r'<label for="([^"]+)"', html))
    for control in re.findall(r'<(?:input|select|textarea)[^>]*\bid="([^"]+)"', html):
        assert control in labels, control


def test_resolver_serves_assets_only_for_active_codes(monkeypatch):
    from qrfacile_app.modules import public as resolver
    from tests.test_module_public_resolver import REQUEST, _install

    content = {"title": "Cena", "start": "2026-12-20T20:00", "end": "", "place": "", "text": "", "link": ""}
    rows = {"EVT": {"id": 9, "status": "attiva", "module": "link", "stats_level": "none",
                    "payload": {"type": "event", "content": {"event": content}}}}
    _install(monkeypatch, rows)
    assert resolver.resolve_module_qr(REQUEST, "EVT").status_code == 200
    assert resolver.module_asset(REQUEST, "EVT", "evento.ics").media_type == "text/calendar"
    assert resolver.module_asset(REQUEST, "EVT", "nope").status_code == 404
    rows["EVT"]["status"] = "bozza"
    assert resolver.module_asset(REQUEST, "EVT", "evento.ics").status_code == 404
    rows["EVT"]["status"] = "attiva"
    rows["EVT"]["payload"]["content"]["event"] = {"title": "", "start": ""}
    assert resolver.resolve_module_qr(REQUEST, "EVT").status_code == 404


@pytest.mark.integration
def test_wifi_direct_qr_download(area, monkeypatch):
    import asyncio

    from qrfacile_app import export_qr_ui
    from tests.test_link_app_area import _create, _request

    _create(area, kind="wifi")
    asyncio.run(area.ui.link_content_post(_request({"type": "wifi", "wifi_ssid": "Ospiti", "wifi_password": "",
                                                    "wifi_security": "nopass"}), 1))
    seen = []
    monkeypatch.setattr(export_qr_ui, "_qr_png", lambda url, *a: seen.append(url) or b"png")
    response = area.ui.link_wifi_qr(_request(), 1)
    assert response.media_type == "image/png" and seen == ["WIFI:T:nopass;S:Ospiti;;"]
    html = area.ui.link_detail(_request(), 1).body.decode()
    assert "/app/link/1/wifi-qr.png" in html


@pytest.mark.integration
def test_new_type_choice_lists_all_types(area):
    from tests.test_link_app_area import _request

    html = area.ui.link_new_get(_request()).body.decode()
    for key in ("vcard", "wifi", "review", "whatsapp", "gallery", "event"):
        assert f'value="{key}"' in html
