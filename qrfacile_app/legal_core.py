from __future__ import annotations

import json

from fastapi import Request


REQUIRED_LEGAL_DOCUMENTS = {
    "terms": "2026-10-25",
    "privacy": "2026-10-25",
}


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else None


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
