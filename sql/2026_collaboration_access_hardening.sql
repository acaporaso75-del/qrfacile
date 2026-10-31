BEGIN;

-- Gli studi non possono pubblicare etichette: la decisione finale resta a cantina/admin.
UPDATE label_collaborators
SET can_publish=FALSE
WHERE role='studio' AND can_publish=TRUE;

CREATE OR REPLACE FUNCTION enforce_studio_label_permissions()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    general_view BOOLEAN;
    general_edit BOOLEAN;
BEGIN
    IF NEW.role <> 'studio' THEN
        RETURN NEW;
    END IF;

    NEW.can_publish := FALSE;

    SELECT sc.can_view, sc.can_edit
      INTO general_view, general_edit
      FROM studio_clients sc
      JOIN wine_labels wl ON wl.id=NEW.wine_label_id
     WHERE sc.studio_user_id=NEW.collaborator_user_id
       AND sc.winery_id=wl.winery_id
     LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Studio non collegato alla cantina dell etichetta';
    END IF;

    NEW.can_view := COALESCE(NEW.can_view, FALSE) AND COALESCE(general_view, FALSE);
    NEW.can_edit := COALESCE(NEW.can_edit, FALSE) AND NEW.can_view AND COALESCE(general_edit, FALSE);
    NEW.can_media := COALESCE(NEW.can_media, FALSE) AND NEW.can_edit;
    NEW.can_export := COALESCE(NEW.can_export, FALSE) AND NEW.can_view;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_enforce_studio_label_permissions ON label_collaborators;
CREATE TRIGGER trg_enforce_studio_label_permissions
BEFORE INSERT OR UPDATE ON label_collaborators
FOR EACH ROW EXECUTE FUNCTION enforce_studio_label_permissions();

CREATE OR REPLACE FUNCTION sync_label_permissions_from_studio_client()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE label_collaborators lc
           SET active=FALSE,
               can_view=FALSE,
               can_edit=FALSE,
               can_media=FALSE,
               can_export=FALSE,
               can_publish=FALSE,
               updated_at=now()
          FROM wine_labels wl
         WHERE lc.wine_label_id=wl.id
           AND wl.winery_id=OLD.winery_id
           AND lc.collaborator_user_id=OLD.studio_user_id
           AND lc.active=TRUE;
        RETURN OLD;
    END IF;

    UPDATE label_collaborators lc
       SET can_view=lc.can_view AND NEW.can_view,
           can_edit=lc.can_edit AND NEW.can_view AND NEW.can_edit,
           can_media=lc.can_media AND NEW.can_view AND NEW.can_edit,
           can_export=lc.can_export AND NEW.can_view,
           can_publish=FALSE,
           active=CASE WHEN NEW.can_view THEN lc.active ELSE FALSE END,
           updated_at=now()
      FROM wine_labels wl
     WHERE lc.wine_label_id=wl.id
       AND wl.winery_id=NEW.winery_id
       AND lc.collaborator_user_id=NEW.studio_user_id;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_label_permissions_from_studio_client ON studio_clients;
CREATE TRIGGER trg_sync_label_permissions_from_studio_client
AFTER UPDATE OF can_view, can_edit, can_create OR DELETE ON studio_clients
FOR EACH ROW EXECUTE FUNCTION sync_label_permissions_from_studio_client();

-- Gli account studio creati da nuovi flussi non sono considerati verificati automaticamente.
CREATE OR REPLACE FUNCTION protect_new_studio_email_verification()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF lower(COALESCE(NEW.role, ''))='studio' THEN
        NEW.email_verified := 0;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_protect_new_studio_email_verification ON users;
CREATE TRIGGER trg_protect_new_studio_email_verification
BEFORE INSERT ON users
FOR EACH ROW EXECUTE FUNCTION protect_new_studio_email_verification();

CREATE INDEX IF NOT EXISTS idx_label_collaborators_effective_access
    ON label_collaborators (collaborator_user_id, wine_label_id, active, can_view);

COMMIT;
