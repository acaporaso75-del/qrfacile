from __future__ import annotations

from datetime import datetime, timezone

from psycopg.rows import dict_row

from qrfacile_app.db import pg

VALID_REVIEW_DECISIONS = {"approved", "rejected"}


def list_pending_ai_reviews(limit: int = 100):
    safe_limit = max(1, min(int(limit), 500))
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, created_at, user_id, use_case, provider, model,
                       model_version, risk_classification,
                       contains_personal_data, human_review_status, metadata
                  FROM ai_usage_log
                 WHERE human_review_status = 'pending'
                 ORDER BY created_at ASC
                 LIMIT %s
                """,
                (safe_limit,),
            )
            return cur.fetchall()


def review_ai_output_record(*, record_id: int, reviewer_user_id: int, decision: str):
    if decision not in VALID_REVIEW_DECISIONS:
        raise ValueError("invalid_review_decision")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE ai_usage_log
                   SET human_review_status = %s,
                       reviewer_user_id = %s,
                       reviewed_at = %s
                 WHERE id = %s
                   AND human_review_status = 'pending'
             RETURNING id, human_review_status
                """,
                (
                    decision,
                    int(reviewer_user_id),
                    datetime.now(timezone.utc),
                    int(record_id),
                ),
            )
            row = cur.fetchone()
        conn.commit()

    return row
