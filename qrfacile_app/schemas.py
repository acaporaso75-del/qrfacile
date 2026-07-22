from qrfacile_app.db import pg

def ensure_tables():
    # NON distruttivo: crea solo ciò che può mancare per crediti/last_mode
    with pg() as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_mode TEXT;")
            cur.execute("""
              CREATE TABLE IF NOT EXISTS credit_ledger (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                credit_type TEXT NOT NULL,
                delta INTEGER NOT NULL,
                reason TEXT,
                ref_table TEXT,
                ref_id BIGINT,
                created_at BIGINT NOT NULL
              );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_credit_ledger_user ON credit_ledger(user_id, created_at DESC);")
            cur.execute("""
              CREATE OR REPLACE VIEW credit_balance AS
              SELECT user_id, credit_type, COALESCE(SUM(delta),0) AS balance
              FROM credit_ledger
              GROUP BY user_id, credit_type;
            """)
        conn.commit()
