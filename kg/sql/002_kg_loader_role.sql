-- Role for the KG loader. Deliberately has no access to schema eval:
-- a mapping that touches ground_truth fails with a permission error
-- rather than succeeding quietly. See DATASET_README.md section 4.
--
-- Password is NOT set here. After running this, set it separately:
--   ALTER ROLE kg_loader PASSWORD '<value from kg/.env>';
--
-- Re-running after `make reset` will error on CREATE ROLE if the role
-- survived; that error is harmless.

CREATE ROLE kg_loader LOGIN;

GRANT USAGE ON SCHEMA core, agent TO kg_loader;
GRANT SELECT ON ALL TABLES IN SCHEMA core, agent TO kg_loader;

GRANT USAGE ON SCHEMA kg TO kg_loader;
GRANT SELECT ON kg.v_referral_state TO kg_loader;

-- Tables created later must also be readable, or a mapping fails confusingly.
ALTER DEFAULT PRIVILEGES IN SCHEMA core, agent
  GRANT SELECT ON TABLES TO kg_loader;
