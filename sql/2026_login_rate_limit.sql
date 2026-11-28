BEGIN;

CREATE TABLE IF NOT EXISTS login_failures (
    id BIGSERIAL PRIMARY KEY,
    identity_hash CHAR(64) NOT NULL,
    client_ip VARCHAR(80) NOT NULL DEFAULT '',
    created_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_login_failures_identity_time
    ON login_failures (identity_hash, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_login_failures_ip_time
    ON login_failures (client_ip, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_login_failures_created_at
    ON login_failures (created_at);

COMMIT;
