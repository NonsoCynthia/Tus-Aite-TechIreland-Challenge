DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_rw') THEN
        CREATE ROLE agent_rw NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evaluator') THEN
        CREATE ROLE evaluator NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA core TO agent_rw;
GRANT SELECT ON ALL TABLES IN SCHEMA core TO agent_rw;
GRANT USAGE ON SCHEMA agent TO agent_rw;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA agent TO agent_rw;

REVOKE ALL ON SCHEMA eval FROM agent_rw;
REVOKE ALL ON ALL TABLES IN SCHEMA eval FROM agent_rw;

GRANT USAGE ON SCHEMA core, agent, eval TO evaluator;
GRANT SELECT ON ALL TABLES IN SCHEMA core, agent, eval TO evaluator;
