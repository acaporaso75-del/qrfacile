from __future__ import annotations

import json

from fastapi import Request


REQUIRED_LEGAL_DOCUMENTS = {
    "terms": "2026-10-29",
    "privacy": "2026-10-25",
}

# QRFacile Link addendum (customer content + aggregated scan statistics).
# Draft text: docs/legal/2026-11-22-link-terms-privacy-draft.md. Accepted at
# the first use of /app/link; activated together with the "link" switch.
LINK_LEGAL_DOCUMENTS = {
    "terms": "2026-12-link",
    "privacy": "2026-12-link",
}
LINK_TERMS_SUMMARY = (
    "Sei responsabile dei contenuti collegati ai tuoi QR (link, PDF, mini-pagine): "
    "devono essere leciti, tuoi o usati con permesso, senza truffe, malware, contenuti "
    "che violano diritti di terzi o la legge. QRFacile può sospendere un QR segnalato o "
    "contrario a queste regole. Se attivi le statistiche, contiamo le scansioni solo in "
    "forma aggregata (giorno, ora, tipo di dispositivo, lingua), senza indirizzi IP, "
    "cookie o altri dati personali di chi scansiona."
)


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    client = getattr(request, "client", None)
    return client.host if client else None


def record_registration_acceptances(cur, *, user_id: int, request: Request) -> None:
    """Record the exact legal versions accepted during account registration.

    This intentionally runs in the same database transaction as account creation:
    registration must fail closed if the legal document catalogue is missing or stale.
    """
    for document_key, document_version in REQUIRED_LEGAL_DOCUMENTS.items():
        cur.execute(
            """
            SELECT title
            FROM legal_documents
            WHERE document_key=%s AND version=%s
              AND effective_at <= now()
              AND (retired_at IS NULL OR retired_at > now())
            LIMIT 1
            """,
            (document_key, document_version),
        )
        document = cur.fetchone()
        if not document:
            raise RuntimeError(
                f"Documento legale obbligatorio non attivo: {document_key}:{document_version}"
            )

        evidence = {
            "method": "registration_form",
            "explicit_action": True,
            "checkbox_name": (
                "terms_accepted"
                if document_key == "terms"
                else "privacy_acknowledged"
            ),
            "document_title": document["title"],
        }
        cur.execute(
            """
            INSERT INTO legal_acceptances (
                user_id, document_key, document_version,
                ip_address, user_agent, evidence
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (user_id, document_key, document_version) DO NOTHING
            """,
            (
                int(user_id),
                document_key,
                document_version,
                client_ip(request),
                request.headers.get("user-agent"),
                json.dumps(evidence, ensure_ascii=False),
            ),
        )


def has_link_acceptance(cur, user_id: int) -> bool:
    cur.execute(
        """
        SELECT COUNT(DISTINCT document_key) AS n FROM legal_acceptances
        WHERE user_id=%s AND (document_key, document_version) IN ((%s, %s), (%s, %s))
        """,
        (
            int(user_id),
            "terms", LINK_LEGAL_DOCUMENTS["terms"],
            "privacy", LINK_LEGAL_DOCUMENTS["privacy"],
        ),
    )
    row = cur.fetchone()
    count = row["n"] if isinstance(row, dict) else (row[0] if row else 0)
    return int(count or 0) == len(LINK_LEGAL_DOCUMENTS)


def record_link_acceptance(cur, *, user_id: int, request: Request) -> None:
    for document_key, document_version in LINK_LEGAL_DOCUMENTS.items():
        evidence = {"method": "link_first_use", "explicit_action": True, "checkbox_name": "accept"}
        cur.execute(
            """
            INSERT INTO legal_acceptances (user_id, document_key, document_version, ip_address, user_agent, evidence)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (user_id, document_key, document_version) DO NOTHING
            """,
            (
                int(user_id), document_key, document_version,
                client_ip(request), request.headers.get("user-agent"),
                json.dumps(evidence, ensure_ascii=False),
            ),
        )
