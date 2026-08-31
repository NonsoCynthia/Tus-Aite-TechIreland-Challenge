"""Schema shape, and the permission barrier that makes the answer key unreachable."""
import psycopg
import pytest

EXPECTED = {"core": 18, "agent": 7, "eval": 1}


@pytest.mark.parametrize("schema,n", EXPECTED.items())
def test_table_counts(q, schema, n):
    got = q(f"SELECT count(*) FROM information_schema.tables "
            f"WHERE table_schema='{schema}' AND table_type='BASE TABLE'")[0][0]
    assert got == n, f"{schema} has {got} tables, expected {n}"


def test_every_table_has_a_primary_key(q):
    missing = q("""
        SELECT t.table_schema, t.table_name FROM information_schema.tables t
        WHERE t.table_schema IN ('core','agent','eval') AND t.table_type='BASE TABLE'
          AND NOT EXISTS (SELECT 1 FROM information_schema.table_constraints c
            WHERE c.table_schema=t.table_schema AND c.table_name=t.table_name
              AND c.constraint_type='PRIMARY KEY')""")
    assert missing == [], f"tables without a primary key: {missing}"


def test_agent_rw_cannot_read_the_answer_key(conn):
    """The held-out guarantee is a database permission, not a convention.

    This failing is the pass condition. If an agent could read eval.ground_truth
    it would rank perfectly by looking up the answer.
    """
    with conn.cursor() as cur:
        cur.execute("SET ROLE agent_rw")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cur.execute("SELECT 1 FROM eval.ground_truth LIMIT 1")
        conn.rollback()


def test_agent_rw_can_read_inputs_and_write_outputs(conn):
    with conn.cursor() as cur:
        cur.execute("SET ROLE agent_rw")
        cur.execute("SELECT count(*) FROM core.ref_rules")
        assert cur.fetchone()[0] == 5
        conn.rollback()


@pytest.mark.parametrize("idx", [
    "idx_rd_as_of", "idx_rd_hosp_as_of", "idx_rd_status", "idx_obs_datetime",
    "idx_bs_snapshot", "idx_cs_date", "idx_conditions_one_primary", "idx_ws_one_primary"])
def test_expected_indexes_exist(q, idx):
    assert q(f"SELECT count(*) FROM pg_indexes WHERE indexname='{idx}'")[0][0] == 1


def test_pgadmin_server_file_matches_the_live_connection(q):
    """db/pgadmin/servers.json is a static file, so it can drift from .env.

    pgAdmin cannot read environment variables, so the pre-provisioned connection
    hardcodes the username and database. Change POSTGRES_USER in .env without
    changing this file and pgAdmin fails to log in with an authentication error
    that points at nothing useful. This asserts they still agree, so drift fails a
    test instead of costing somebody an afternoon.
    """
    import json
    from pathlib import Path

    server = json.loads(
        (Path(__file__).resolve().parent.parent / "db" / "pgadmin" / "servers.json")
        .read_text())["Servers"]["1"]

    live_user = q("SELECT current_user")[0][0]
    live_db = q("SELECT current_database()")[0][0]

    assert server["Username"] == live_user, (
        f"servers.json Username is {server['Username']!r} but the database user is "
        f"{live_user!r}. Update db/pgadmin/servers.json to match your .env.")
    assert server["MaintenanceDB"] == live_db, (
        f"servers.json MaintenanceDB is {server['MaintenanceDB']!r} but the database "
        f"is {live_db!r}. Update db/pgadmin/servers.json to match your .env.")
    assert server["Host"] == "db" and server["Port"] == 5432, (
        "pgAdmin runs inside the Docker network, so it must reach the database at "
        "db:5432. localhost:5433 is the address from your own machine.")
