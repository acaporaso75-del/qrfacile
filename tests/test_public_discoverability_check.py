from scripts import check_public_discoverability


def _page(path: str) -> str:
    canonical = f"https://www.qrfacile.it{path}"
    return f"""<!doctype html><html><head>
    <meta name="robots" content="index,follow">
    <meta name="description" content="QRFACILE Wine B2B">
    <link rel="canonical" href="{canonical}">
    <meta property="og:url" content="{canonical}">
    <script type="application/ld+json">{{"@type":"WebPage"}}</script>
    </head><body></body></html>"""


def test_public_page_requires_canonical_metadata_and_indexability():
    assert check_public_discoverability.verify_public_page("/wine", _page("/wine"), {}) == []
    errors = check_public_discoverability.verify_public_page(
        "/wine",
        _page("/pricing"),
        {"x-robots-tag": "noindex"},
    )
    assert "page_canonical_mismatch:/wine" in errors
    assert "page_noindex:/wine" in errors


def test_robots_sitemap_and_llms_contracts_use_canonical_source():
    from qrfacile_app import seo_ui

    assert check_public_discoverability.verify_robots(seo_ui.robots_txt().body.decode()) == []
    assert check_public_discoverability.verify_sitemap(seo_ui.sitemap_xml().body.decode()) == []
    assert check_public_discoverability.verify_llms(seo_ui.llms_txt().body.decode()) == []


def test_main_reports_only_origin_and_count(monkeypatch, capsys):
    from qrfacile_app import seo_ui

    payloads = {
        "/robots.txt": seo_ui.robots_txt().body.decode(),
        "/sitemap.xml": seo_ui.sitemap_xml().body.decode(),
        "/llms.txt": seo_ui.llms_txt().body.decode(),
        **{path: _page(path) for path, _priority in seo_ui.PUBLIC_PAGES},
    }
    monkeypatch.setattr(
        check_public_discoverability,
        "fetch",
        lambda _base, path, **_kwargs: (payloads[path], {}),
    )
    assert check_public_discoverability.main(["--base-url", "https://staging.qrfacile.it"]) == 0
    output = capsys.readouterr()
    assert "PUBLIC_DISCOVERABILITY_OK origin=https://staging.qrfacile.it" in output.out
    assert "<html" not in output.out + output.err
