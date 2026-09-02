CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS agent;
CREATE SCHEMA IF NOT EXISTS eval;

COMMENT ON SCHEMA core  IS 'Input data. Loaded once, read-only thereafter.';
COMMENT ON SCHEMA agent IS 'Written by the agents at run time. Append only.';
COMMENT ON SCHEMA eval  IS 'Held-out ground truth. Agents must not read this.';
