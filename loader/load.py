"""Apply migrations, load seeds, and load the dataset into Postgres.

Three modes:
    python -m loader.load --migrate-only    apply db/migrations/*.sql in filename order
    python -m loader.load --seeds-only      load db/seeds/*.csv into the dictionary tables
    python -m loader.load                   load data/<profile>/ into core and eval

Loading technique, per BUILD_MANUAL.md section 9.3: COPY rather than row-by-row
inserts, and the whole load inside ONE transaction. A partial load is worse than
no load, because it looks like it worked.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
import yaml

from loader.load_order import LOAD_ORDER, SEED_TABLES, SCHEMA, DERIVED, csv_name

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "db" / "migrations"
SEEDS = ROOT / "db" / "seeds"
DATA = ROOT / "data"


def connect() -> psycopg.Connection:
    """Connect using the environment the loader container provides."""
    return psycopg.connect(
        host=os.environ.get("PGHOST", "db"),
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def ensure_migration_table(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS public.schema_migrations (
            filename   text PRIMARY KEY,
            applied_at timestamp NOT NULL DEFAULT now()
        )
        """
    )


def apply_migrations(conn: psycopg.Connection) -> None:
    """Apply every unapplied migration, in filename order.

    Never edit an applied migration. To change something, add a new file.
    """
    ensure_migration_table(conn)
    applied = {r[0] for r in conn.execute("SELECT filename FROM public.schema_migrations")}

    files = sorted(MIGRATIONS.glob("*.sql"))
    if not files:
        sys.exit(f"No migrations found in {MIGRATIONS}")

    for path in files:
        if path.name in applied:
            print(f"  skip    {path.name} (already applied)")
            continue
        print(f"  apply   {path.name}")
        conn.execute(path.read_text())
        conn.execute(
            "INSERT INTO public.schema_migrations (filename) VALUES (%s)", (path.name,)
        )
    conn.commit()

    counts = dict(
        conn.execute(
            """
            SELECT table_schema, count(*)
            FROM information_schema.tables
            WHERE table_schema IN ('core','agent','eval')
            GROUP BY 1
            """
        ).fetchall()
    )
    print(
        f"\n  tables: core {counts.get('core', 0)}, "
        f"agent {counts.get('agent', 0)}, eval {counts.get('eval', 0)}"
    )


def copy_csv(conn: psycopg.Connection, table: str, path: Path) -> int:
    """COPY a CSV into a table and return the row count.

    COPY reads the file as text, so leading zeros in code columns such as
    specialty_hipe '0601' survive. Reading via pandas without dtype=str is where
    they get silently turned into 601.
    """
    qualified = f"{SCHEMA[table]}.{table.replace('_stage', '')}" if table.endswith("_stage") else f"{SCHEMA[table]}.{table}"
    if table == "referral_daily_stage":
        qualified = "staging.referral_daily"

    header = path.read_text().splitlines()[0]
    cols = ", ".join(header.split(","))

    with conn.cursor() as cur, path.open("rb") as fh:
        with cur.copy(f"COPY {qualified} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
            while chunk := fh.read(65536):
                cp.write(chunk)
        return cur.rowcount


def load_seeds(conn: psycopg.Connection) -> None:
    """Load the three hand-transcribed dictionary tables."""
    for table in SEED_TABLES:
        path = SEEDS / f"{table}.csv"
        if not path.exists():
            sys.exit(f"Missing seed file: {path}")
        conn.execute(f"TRUNCATE core.{table} CASCADE")
        n = copy_csv(conn, table, path)
        print(f"  {table:24} {n:>8,}")
    conn.commit()


def derive_referrals(conn: psycopg.Connection) -> int:
    """Build core.referrals from the earliest snapshot of each referral.

    referral_daily is keyed per-day, so it cannot itself be the target of the
    foreign keys that conditions, observations and the event tables need.
    """
    conn.execute(
        """
        INSERT INTO core.referrals (
            hospital_hipe, pathway_number, patient_id, specialty_hipe,
            referral_date, referral_received_date, priority_level_gp, referral_source)
        SELECT DISTINCT ON (hospital_hipe, pathway_number)
            hospital_hipe, pathway_number, patient_id, specialty_hipe,
            referral_date, referral_received_date, priority_level_gp, referral_source
        FROM staging.referral_daily
        ORDER BY hospital_hipe, pathway_number, as_of_date
        """
    )
    return conn.execute("SELECT count(*) FROM core.referrals").fetchone()[0]


def load_data(conn: psycopg.Connection, profile: str) -> None:
    """Load data/<profile>/ in dependency order, inside one transaction."""
    src = DATA / profile
    if not src.is_dir():
        sys.exit(
            f"No data at {src}.\n"
            f"Run `make fetch` to pull the pinned revision from Hugging Face first."
        )

    # A load replaces the dataset. Clear the data tables first so re-loading a
    # different profile does not collide with what is already there. The three
    # dictionary tables are loaded separately by --seeds-only and are left alone.
    targets = [f"{SCHEMA[t]}.{t}" for t in LOAD_ORDER if t not in DERIVED]
    targets += ["core.referrals"]
    conn.execute(f"TRUNCATE {', '.join(targets)} CASCADE")

    conn.execute("CREATE SCHEMA IF NOT EXISTS staging")
    conn.execute("DROP TABLE IF EXISTS staging.referral_daily")
    conn.execute(
        "CREATE TABLE staging.referral_daily (LIKE core.referral_daily INCLUDING DEFAULTS)"
    )

    counts: dict[str, int] = {}
    for table in LOAD_ORDER:
        if table == "referrals":
            counts[table] = derive_referrals(conn)
            print(f"  {table:24} {counts[table]:>8,}  (derived)")
            continue

        path = src / csv_name(table)
        if not path.exists():
            if table == "ground_truth":
                print(f"  {table:24} {'-':>8}  (absent; held out builds may omit it)")
                continue
            sys.exit(f"Missing data file: {path}")

        counts[table] = copy_csv(conn, table, path)
        label = "  (staged)" if table in DERIVED else ""
        print(f"  {table:24} {counts[table]:>8,}{label}")

    conn.execute("DROP TABLE staging.referral_daily")
    conn.commit()

    print(f"\n  loaded {sum(counts.values()):,} rows across {len(counts)} tables from '{profile}'")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--migrate-only", action="store_true", help="apply migrations and stop")
    ap.add_argument("--seeds-only", action="store_true", help="load dictionary seeds and stop")
    ap.add_argument("--profile", default=None, help="sample or full; defaults to versions.yml")
    args = ap.parse_args()

    profile = args.profile
    if profile is None:
        cfg = yaml.safe_load((ROOT / "versions.yml").read_text())
        profile = cfg.get("default_profile", "sample")

    with connect() as conn:
        if args.migrate_only:
            print("Applying migrations:")
            apply_migrations(conn)
            return
        if args.seeds_only:
            print("Loading seeds:")
            load_seeds(conn)
            return

        print(f"Loading data (profile: {profile}):")
        load_data(conn, profile)


if __name__ == "__main__":
    main()
