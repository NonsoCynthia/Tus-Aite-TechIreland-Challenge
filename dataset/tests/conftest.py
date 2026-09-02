"""Shared fixtures: a database connection and the generated CSVs."""
import os
from pathlib import Path

import pandas as pd
import psycopg
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def conn():
    c = psycopg.connect(
        host=os.environ.get("PGHOST", "db"), port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"])
    yield c
    c.close()


@pytest.fixture(scope="session")
def q(conn):
    def run(sql):
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    return run


@pytest.fixture(scope="session")
def cal():
    return yaml.safe_load((ROOT / "generator" / "calibration" / "vitals_by_category.yml").read_text())


def _load(scope, name):
    p = ROOT / scope / f"{name}.csv"
    if not p.exists():
        pytest.skip(f"{p} not present; run `make generate` first")
    return pd.read_csv(p, dtype=str, keep_default_na=False, na_values=[])


@pytest.fixture(scope="session")
def out():
    return lambda name: _load("out", name)


@pytest.fixture(scope="session")
def sample():
    return lambda name: _load("sample", name)
