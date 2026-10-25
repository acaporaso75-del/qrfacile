BEGIN;

SET LOCAL lock_timeout = '10s';

-- This table contains only short-lived failed-login counters. Rolling back the
-- feature does not alter users, credentials, sessions or successful logins.
DROP TABLE IF EXISTS login_failures;

COMMIT;
