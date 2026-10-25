from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response


router = APIRouter(tags=["seo"])

PUBLIC_BASE_URL = "https://www.qrfacile.it"
PUBLIC_PAGES = (
    ("/", "1.0"),
    ("/wine", "0.9"),
    ("/pricing", "0.9"),
    ("/legal", "0.4"),
    ("/privacy", "0.4"),
    ("/cookies", "0.3"),
    ("/terms", "0.4"),
    ("/trust", "0.6"),
    ("/support", "0.6"),
    ("/ai-policy", "0.5"),
)

PRIVATE_PATHS = (
    "/admin/",
    "/api/",
    "/app/",
    "/e/",
    "/internal/",
    "/paypal/",
    "/preview/",
    "/studio/",
    "/uploads/",
    "/verify-email/",
)


def _robots_group(user_agent: str) -> str:
    lines = [f"User-agent: {user_agent}", "Allow: /"]
    lines.extend(f"Disallow: {path}" for path in PRIVATE_PATHS)
    return "\n".join(lines)


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots_txt():
    groups = [
        _robots_group("*"),
        _robots_group("OAI-SearchBot"),
        _robots_group("GPTBot"),
    ]
    return PlainTextResponse(
        "\n\n".join(groups)
        + f"\n\nSitemap: {PUBLIC_BASE_URL}/sitemap.xml\n",
        media_type="text/plain; charset=utf-8",
    )


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml():
    urls = "\n".join(
        "  <url>"
        f"<loc>{PUBLIC_BASE_URL}{path}</loc>"
        "<lastmod>2026-10-25</lastmod>"
        f"<priority>{priority}</priority>"
        "</url>"
        for path, priority in PUBLIC_PAGES
    )
    payload = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    return Response(payload, media_type="application/xml; charset=utf-8")


@router.get("/llms.txt", response_class=PlainTextResponse, include_in_schema=False)
def llms_txt():
    return PlainTextResponse(
        """# QRFACILE

QRFACILE is a B2B service operated by Enolab S.r.l. for wineries and graphic studios.
Its active Wine module creates digital wine labels, manages mandatory product data and exports QR files for print.

## Primary pages
- Product: https://www.qrfacile.it/wine
- Pricing: https://www.qrfacile.it/pricing
- Demo: https://www.qrfacile.it/demo/public-label
- Legal: https://www.qrfacile.it/legal
- Privacy: https://www.qrfacile.it/privacy
- AI policy: https://www.qrfacile.it/ai-policy
- Support: https://www.qrfacile.it/support

## Important limitations
- QRFACILE is a technical support tool and does not replace legal or regulatory advice.
- Compliance suggestions and AI-assisted functions require human review before publication.
- Public mandatory e-label pages are separated from sales and marketing content and do not track visitors.
""",
        media_type="text/plain; charset=utf-8",
    )
