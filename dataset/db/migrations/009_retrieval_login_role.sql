-- Login role for the retrieval service (conductor/tracks/retrieval-service_20260904).
--
-- agent_rw (migration 007) is a NOLOGIN group role -- nothing can connect as it
-- directly. This creates the login role that assumes its privileges via role
-- membership, the same pattern kg_loader uses as a standalone login role for the
-- read-only graph-build side (kg/sql/002_kg_loader_role.sql).
--
-- Password is NOT set here. After running this, set it separately:
--   ALTER ROLE retrieval_rw PASSWORD '<value from retrieval/.env>';
--
-- Re-running after `make reset` will error on CREATE ROLE if the role
-- survived; that error is harmless.

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'retrieval_rw') THEN
        CREATE ROLE retrieval_rw LOGIN;
    END IF;
END $$;

GRANT agent_rw TO retrieval_rw;
