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
