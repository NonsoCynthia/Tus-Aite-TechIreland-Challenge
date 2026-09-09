"""Two read-only sources the orchestrator did not previously have.

Everything the UI showed came through retrieval's eleven endpoints, which is a
narrow window: there is no endpoint for the reference tables, none for reading
an override back, and the one SPARQL read path collapses repeated predicates so
a score citing six observations returns one. Meanwhile Postgres holds the
reference layer and the override log, and Oxigraph holds 11,839 triples per run
that nothing has ever queried.

Both are on the same compose network and both are opened READ ONLY here. No
write ever leaves this module, and the connection asserts that at the session
level rather than trusting the SQL below to stay well behaved.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DB_URL = os.environ.get("RETRIEVAL_DB_URL", "")
OXIGRAPH_QUERY_URL = os.environ.get("OXIGRAPH_QUERY_URL", "")

# retrieval runs one uvicorn worker over the same database and every handler
# makes a blocking call, so this side stays deliberately small. The volume here
# is trivial -- the reference layer is read once and cached, overrides are a
# handful of rows -- so a plain short-lived connection is used rather than
# adding psycopg_pool to the image for no measurable gain.
_lock = threading.Lock()


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """One read, READ ONLY at the session level.

    Returns [] rather than raising: a missing table, an unset URL or a
    permission the role does not hold degrades one panel, never the page. The
    UI must still start and serve every pre-existing surface with this
    connection unavailable.
    """
    if not DB_URL:
        return []
    try:
        import psycopg

        with _lock, psycopg.connect(DB_URL, connect_timeout=5, autocommit=True) as conn:
            # asserted at the session level rather than trusting the SQL below
            # to stay well behaved as this file grows
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [d.name for d in (cur.description or [])]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:                                            # noqa: BLE001
        logger.exception("read failed: %s", sql.strip().split("\n")[0][:80])
        return []


# ---------------------------------------------------------------- oxigraph

_sparql = httpx.Client(timeout=httpx.Timeout(20.0, connect=5.0))


def sparql(q: str) -> list[dict[str, Any]]:
    """SPARQL SELECT against the graph store, flattened to plain dicts.

    Returns the `bindings` list with each binding reduced to its `value`, so a
    caller reads `row["position"]` rather than `row["position"]["value"]`.
    Unbound OPTIONAL variables are simply absent from the row.
    """
    if not OXIGRAPH_QUERY_URL:
        return []
    try:
        r = _sparql.post(
            OXIGRAPH_QUERY_URL,
            content=q.encode("utf-8"),
            headers={"Content-Type": "application/sparql-query",
                     "Accept": "application/sparql-results+json"},
        )
        if r.status_code != 200:
            logger.warning("sparql -> %s %s", r.status_code, r.text[:200])
            return []
        return [{k: v["value"] for k, v in b.items()}
                for b in r.json().get("results", {}).get("bindings", [])]
    except httpx.HTTPError:
        logger.exception("oxigraph unreachable")
        return []


def sources_status() -> dict[str, str]:
    """What /api/health reports. Named honestly: 'off' means the URL was never
    set, which is a configuration state, not an outage."""
    if not DB_URL:
        db = "off"
    else:
        db = "ok" if query("SELECT 1 AS ok") else "unreachable"
    if not OXIGRAPH_QUERY_URL:
        graph = "off"
    else:
        # ASK against the DEFAULT graph is the trap retrieval's own health probe
        # fell into: every triple here lives in a NAMED graph, so the default
        # graph is empty and the probe would report empty-but-reachable forever.
        rows = sparql("SELECT (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } }")
        graph = "ok" if rows and int(rows[0].get("n", 0)) > 0 else "unreachable"
    return {"postgres": db, "oxigraph": graph}
