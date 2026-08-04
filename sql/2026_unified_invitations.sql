BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin','winery','studio','collaborator'));

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('admin','winery','studio','collaborator'));

ALTER TABLE invites RENAME COLUMN token TO legacy_token;
ALTER TABLE invites ALTER COLUMN legacy_token DROP NOT NULL;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS invite_type TEXT;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS recipient_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS winery_id BIGINT REFERENCES wineries(id) ON DELETE CASCADE;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS wine_id BIGINT;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS studio_id BIGINT;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS token_hash CHAR(64);
ALTER TABLE invites ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS revoked_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS audit_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS send_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS last_sent_at TIMESTAMPTZ;
ALTER TABLE invites ADD COLUMN IF NOT EXISTS supersedes_invite_id BIGINT REFERENCES invites(id) ON DELETE SET NULL;

UPDATE invites SET token_hash=encode(digest(legacy_token,'sha256'),'hex')
WHERE legacy_token IS NOT NULL AND token_hash IS NULL;
UPDATE invites SET invite_type=CASE WHEN label_id IS NOT NULL THEN 'label' ELSE 'collaborator' END
WHERE invite_type IS NULL;
UPDATE invites SET winery_id=wl.winery_id
FROM wine_labels wl WHERE invites.label_id=wl.id AND invites.winery_id IS NULL;

INSERT INTO invites (
  legacy_token, token_hash, invite_type, inviter_user_id, inviter_role,
  invitee_email, target_role, winery_id, wine_id, label_id,
  permissions_json, status, expires_at, accepted_at, accepted_by_user_id,
  created_at, rejected_at, revoked_at, audit_metadata
)
SELECT NULL, encode(digest(si.token,'sha256'),'hex'),
       CASE WHEN si.winery_id IS NULL THEN 'winery'
            WHEN (to_jsonb(si)->>'source_label_id') IS NOT NULL THEN 'label'
            WHEN (to_jsonb(si)->>'source_wine_id') IS NOT NULL THEN 'wine' ELSE 'studio' END,
       si.inviter_user_id, COALESCE(u.role,'winery'), lower(si.studio_email),
       CASE WHEN si.winery_id IS NULL THEN 'winery' ELSE 'studio' END,
       si.winery_id, (to_jsonb(si)->>'source_wine_id')::bigint,
       (to_jsonb(si)->>'source_label_id')::bigint,
       jsonb_build_object('can_view',si.can_view,'can_edit',si.can_edit,
                          'can_create',si.can_create,'can_publish',false),
       CASE WHEN (to_jsonb(si)->>'revoked_at') IS NOT NULL THEN 'revoked'
            WHEN si.used_at IS NOT NULL THEN 'accepted'
            WHEN si.expires_at < extract(epoch from now())::bigint THEN 'expired'
            ELSE 'pending' END,
       to_timestamp(si.expires_at), CASE WHEN si.used_at IS NOT NULL THEN to_timestamp(si.used_at) END,
       si.used_by_user_id, to_timestamp(si.created_at), NULL,
       (to_jsonb(si)->>'revoked_at')::timestamptz,
       jsonb_build_object('legacy_table','studio_invites','legacy_id',si.id)
FROM studio_invites si LEFT JOIN users u ON u.id=si.inviter_user_id
WHERE si.token IS NOT NULL
ON CONFLICT DO NOTHING;

UPDATE invites SET legacy_token=NULL WHERE token_hash IS NOT NULL;

ALTER TABLE invites ALTER COLUMN invite_type SET NOT NULL;
ALTER TABLE invites ALTER COLUMN token_hash SET NOT NULL;
ALTER TABLE invites DROP CONSTRAINT IF EXISTS invites_token_key;
ALTER TABLE invites DROP CONSTRAINT IF EXISTS invites_status_check;
ALTER TABLE invites ADD CONSTRAINT invites_status_check
 CHECK (status IN ('pending','accepted','rejected','expired','revoked'));
ALTER TABLE invites ADD CONSTRAINT invites_type_check
 CHECK (invite_type IN ('studio','winery','collaborator','label','wine'));
ALTER TABLE invites ADD CONSTRAINT invites_scope_check CHECK (
   (invite_type IN ('studio','collaborator') AND winery_id IS NOT NULL)
   OR invite_type='winery'
   OR (invite_type='label' AND winery_id IS NOT NULL AND label_id IS NOT NULL)
   OR (invite_type='wine' AND winery_id IS NOT NULL AND wine_id IS NOT NULL)
);
ALTER TABLE invites ADD CONSTRAINT invites_terminal_dates_check CHECK (
  (status='pending' AND accepted_at IS NULL AND rejected_at IS NULL AND revoked_at IS NULL)
  OR (status='accepted' AND accepted_at IS NOT NULL AND accepted_by_user_id IS NOT NULL)
  OR (status='rejected' AND rejected_at IS NOT NULL)
  OR (status='revoked' AND revoked_at IS NOT NULL)
  OR status='expired'
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_invites_token_hash ON invites(token_hash);
CREATE INDEX IF NOT EXISTS idx_invites_recipient_email ON invites(lower(invitee_email));
CREATE INDEX IF NOT EXISTS idx_invites_status_expiry ON invites(status,expires_at);
CREATE INDEX IF NOT EXISTS idx_invites_sender ON invites(inviter_user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_invites_recipient_user ON invites(recipient_user_id,created_at DESC);

CREATE TABLE IF NOT EXISTS invitation_grants (
 id BIGSERIAL PRIMARY KEY,
 invitation_id BIGINT NOT NULL REFERENCES invites(id) ON DELETE CASCADE,
 user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 scope_type TEXT NOT NULL CHECK (scope_type IN ('winery','wine','label')),
 scope_id BIGINT NOT NULL,
 permissions JSONB NOT NULL,
 active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 revoked_at TIMESTAMPTZ,
 revoked_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
 UNIQUE(invitation_id,scope_type,scope_id)
);
CREATE INDEX IF NOT EXISTS idx_invitation_grants_access
 ON invitation_grants(user_id,scope_type,scope_id) WHERE active;
CREATE UNIQUE INDEX IF NOT EXISTS uq_studio_clients_user_winery
 ON studio_clients(studio_user_id,winery_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_label_collaborators_active
 ON label_collaborators(wine_label_id,collaborator_user_id) WHERE active;
CREATE UNIQUE INDEX IF NOT EXISTS uq_studio_clients_user_winery
 ON studio_clients(studio_user_id,winery_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_label_collaborators_active
 ON label_collaborators(wine_label_id,collaborator_user_id) WHERE active;

-- Legacy rows remain for historical joins, but plaintext secrets are erased.
ALTER TABLE studio_invites ALTER COLUMN token DROP NOT NULL;
UPDATE studio_invites SET token=NULL WHERE token IS NOT NULL;

COMMIT;
