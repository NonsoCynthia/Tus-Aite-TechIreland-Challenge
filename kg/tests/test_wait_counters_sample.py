#!/usr/bin/env python3
"""
Sample validation for kg/queries/wait_counters.rq.

Runs the fragment two ways against the same 35-referral sample and compares both to
core.referral_daily's own stored counters:

  1. A hand-built minimal graph (referral dates, triage status, and suspension/interval
     structure all constructed directly) -- exercises the fragment's logic in isolation.
  2. The SAME referral-level facts, but with suspension/cancellation triples produced by
     the REAL kg/mappings/events.rml.ttl mapping (via a live morph_kgc run), not a
     hand-built approximation of them. This is the scenario that actually proves the
     mapping and the fragment agree with each other, not just with the author's mental
     model of both.

Both scenarios load their triples into the named `…/kg/graph/inputs` graph (matching where
real input-layer data lives per namespaces.md §5) and run wait_counters.rq wrapped in
`GRAPH <…/kg/graph/inputs> { … }`. wait_counters.rq's own patterns have no GRAPH clause by
design -- it is a fragment meant to be spliced into a consuming query, which decides the
graph context. An earlier version of this test loaded everything into Oxigraph's default
(unnamed) graph instead, which the fragment's unwrapped patterns matched by coincidence; once
real graph-tagged mapping output existed, that was found to hide every suspension credit
silently (adjusted_wait_days came back equal to days_since_received, not an error) --
fixed here, not in wait_counters.rq itself. See map-cancellation-events-suspension_20260903's
decisions.md.

No input-layer triples exist in a persistent store yet, so scenario 1 stays hand-built for
the referral-level facts (referralDate/referralReceivedDate/triageStatus) that Track A/B has
not mapped yet. Once A/B exists, replace both scenarios with a query against the real store.

Run from the repo root:
    python kg/tests/test_wait_counters_sample.py
Exits non-zero if either scenario has a mismatch.
"""

import os
import subprocess
import sys

import psycopg
import pyoxigraph as ox
import rdflib

DB_URL = os.environ.get(
    "KG_DB_URL_PSYCOPG",
    "postgresql://kg_loader@localhost:5433/triage",
)
FRAGMENT_PATH = "kg/queries/wait_counters.rq"
EVENTS_MAPPING_PATH = "mappings/events.rml.ttl"  # relative to kg/, matching morph_kgc convention

EAT = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/ns#"
EATD = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/id/"
TIME = "http://www.w3.org/2006/time#"
XSD_DATE = "http://www.w3.org/2001/XMLSchema#date"
INPUTS_GRAPH = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/graph/inputs"

# A fixed sample: 25 unsuspended referrals, the one awaiting_triage referral in the `full`
# profile, and 9 suspended referrals (some closing before the referral_daily window starts,
# some closing partway through it, to exercise the clipping rule).
SAMPLE = [
    ("9002", "PW-9002-001531"), ("9004", "PW-9004-000061"), ("9001", "PW-9001-000399"),
    ("9003", "PW-9003-000144"), ("9002", "PW-9002-000560"), ("9001", "PW-DEMO-05"),
    ("9001", "PW-9001-000332"), ("9001", "PW-9001-001022"), ("9002", "PW-9002-000090"),
    ("9002", "PW-9002-000860"), ("9001", "PW-9001-001306"), ("9003", "PW-9003-000106"),
    ("9002", "PW-9002-001536"), ("9001", "PW-9001-000439"), ("9001", "PW-9001-001263"),
    ("9003", "PW-9003-000101"), ("9002", "PW-9002-000550"), ("9001", "PW-9001-001524"),
    ("9001", "PW-9001-000564"), ("9003", "PW-9003-001036"), ("9001", "PW-9001-001544"),
    ("9003", "PW-9003-001058"), ("9003", "PW-9003-000114"), ("9001", "PW-9001-000274"),
    ("9002", "PW-9002-001118"), ("9001", "PW-9001-001221"), ("9001", "PW-9001-001320"),
    ("9001", "PW-9001-001513"), ("9001", "PW-9001-000188"), ("9001", "PW-9001-001419"),
    ("9001", "PW-9001-001781"), ("9001", "PW-9001-001294"), ("9004", "PW-9004-000215"),
    ("9002", "PW-9002-000046"), ("9001", "PW-9001-000294"),
]


def n(iri):
    return ox.NamedNode(iri)


def lit(value, datatype=None):
    return ox.Literal(str(value), datatype=ox.NamedNode(datatype)) if datatype else ox.Literal(str(value))


def add_referral_facts(store, conn):
    """Referral-level facts (referralDate/referralReceivedDate/triageStatus) have no
    mapping yet (Track A/B doesn't exist) -- hand-built here, into the inputs graph."""
    with conn.cursor() as cur:
        for h, p in SAMPLE:
            cur.execute(
                "SELECT referral_date, referral_received_date FROM core.referrals "
                "WHERE hospital_hipe = %s AND pathway_number = %s",
                (h, p),
            )
            rdate, rrecv = cur.fetchone()

            cur.execute(
                "SELECT DISTINCT triage_status FROM core.referral_daily "
                "WHERE hospital_hipe = %s AND pathway_number = %s",
                (h, p),
            )
            statuses = [r[0] for r in cur.fetchall()]
            assert len(statuses) == 1, f"{h}/{p} changes triage_status mid-window: {statuses}"
            status = statuses[0]

            ref_iri = n(f"{EATD}referral/{h}/{p}")
            g = n(INPUTS_GRAPH)
            store.add(ox.Quad(ref_iri, n(EAT + "referralDate"), lit(rdate, XSD_DATE), g))
            store.add(ox.Quad(ref_iri, n(EAT + "referralReceivedDate"), lit(rrecv, XSD_DATE), g))

            state_iri = n(f"{EATD}referral-state/{h}/{p}/2020-01-01")
            store.add(ox.Quad(state_iri, n(EAT + "stateOf"), ref_iri, g))
            store.add(ox.Quad(state_iri, n(EAT + "validFrom"), lit("2020-01-01", XSD_DATE), g))
            store.add(ox.Quad(state_iri, n(EAT + "triageStatus"), lit(status), g))


def build_store_hand_built(conn):
    """Scenario 1: suspension/interval structure constructed directly, matching the shape
    kg/mappings/events.rml.ttl is supposed to produce."""
    store = ox.Store()
    g = n(INPUTS_GRAPH)
    with conn.cursor() as cur:
        for h, p in SAMPLE:
            cur.execute(
                "SELECT suspension_start_date, suspension_end_date FROM core.suspension_events "
                "WHERE hospital_hipe = %s AND pathway_number = %s",
                (h, p),
            )
            for sstart, send in cur.fetchall():
                ref_iri = n(f"{EATD}referral/{h}/{p}")
                susp_iri = n(f"{EATD}suspension/{h}/{p}/{sstart}")
                store.add(ox.Quad(ref_iri, n(EAT + "hasSuspension"), susp_iri, g))
                interval_iri = n(f"{EATD}suspension/{h}/{p}/{sstart}/interval")
                store.add(ox.Quad(susp_iri, n(TIME + "hasTime"), interval_iri, g))
                begin_iri = n(f"{EATD}suspension/{h}/{p}/{sstart}/begin")
                store.add(ox.Quad(interval_iri, n(TIME + "hasBeginning"), begin_iri, g))
                store.add(ox.Quad(begin_iri, n(TIME + "inXSDDate"), lit(sstart, XSD_DATE), g))
                if send is not None:
                    end_iri = n(f"{EATD}suspension/{h}/{p}/{sstart}/end")
                    store.add(ox.Quad(interval_iri, n(TIME + "hasEnd"), end_iri, g))
                    store.add(ox.Quad(end_iri, n(TIME + "inXSDDate"), lit(send, XSD_DATE), g))
    add_referral_facts(store, conn)
    return store


def run_events_mapping():
    """Materialise kg/mappings/events.rml.ttl for real, via a live morph_kgc run, and
    return the resulting quads as an rdflib.Dataset. Uses a throwaway .ini (git-ignored
    directory, removed afterwards) so this doesn't depend on a developer's local
    mappings/events.ini surviving between runs."""
    kg_dir = "kg"
    ini_path = os.path.join(kg_dir, "mappings", "_test_events.ini")
    out_rel = "out/_test_events.nq"
    env_path = os.path.join(kg_dir, ".env")
    with open(env_path, encoding="utf-8") as f:
        password = next(
            line.split("=", 1)[1].strip()
            for line in f
            if line.startswith("KG_LOADER_PASSWORD=")
        )
    with open(ini_path, "w", encoding="utf-8") as f:
        f.write(
            f"[CONFIGURATION]\n"
            f"output_file: {out_rel}\n"
            f"output_format: N-QUADS\n\n"
            f"[DataSource1]\n"
            f"mappings: {EVENTS_MAPPING_PATH}\n"
            f"db_url: postgresql+psycopg://kg_loader:{password}@localhost:5433/triage\n"
        )
    try:
        subprocess.run(
            [sys.executable, "-m", "morph_kgc", "mappings/_test_events.ini"],
            cwd=kg_dir, check=True, capture_output=True, text=True,
        )
        out_path = os.path.join(kg_dir, out_rel)
        dataset = rdflib.Dataset()
        dataset.parse(out_path, format="nquads")
        os.remove(out_path)
        return dataset
    finally:
        if os.path.exists(ini_path):
            os.remove(ini_path)


def build_store_real_mapping(conn, events_dataset):
    """Scenario 2: copy every quad the real events.rml.ttl mapping produced straight into
    the test store, unmodified."""
    store = ox.Store()
    for s, p, o, g in events_dataset.quads():
        if isinstance(o, rdflib.Literal):
            obj = ox.Literal(str(o), datatype=ox.NamedNode(str(o.datatype))) if o.datatype else ox.Literal(str(o))
        else:
            obj = n(str(o))
        graph = n(str(g)) if str(g) and not str(g).startswith("urn:x-rdflib") else None
        store.add(ox.Quad(n(str(s)), n(str(p)), obj, graph))
    add_referral_facts(store, conn)
    return store


def run_fragment(store, fragment_text, referral_iri, as_of_date):
    """Wrap the fragment in GRAPH <inputs> { … } -- see the module docstring for why."""
    bound = fragment_text.replace(
        "VALUES (?referral ?asOfDate) { }",
        f'VALUES (?referral ?asOfDate) {{ (<{referral_iri}> "{as_of_date}"^^<{XSD_DATE}>) }}',
    )
    where_start = bound.index("WHERE {") + len("WHERE {")
    group_by_start = bound.rindex("GROUP BY")
    where_body = bound[where_start:group_by_start].rstrip()
    assert where_body.endswith("}"), "fragment's WHERE block should end with its own closing brace"
    where_body = where_body[:-1].rstrip()  # drop the original WHERE block's closing brace;
    # GRAPH <inputs> { ... } supplies the replacement, then one more to close WHERE itself.
    wrapped = (
        bound[:where_start]
        + f"\n  GRAPH <{INPUTS_GRAPH}> {{\n"
        + where_body
        + "\n  }\n}\n"
        + bound[group_by_start:]
    )
    return list(store.query(wrapped))


def compare_against_source(conn, store, label):
    total = 0
    mismatches = []
    with conn.cursor() as cur:
        for h, p in SAMPLE:
            cur.execute(
                "SELECT as_of_date, days_since_referral, days_since_received, "
                "days_awaiting_triage, adjusted_wait_days FROM core.referral_daily "
                "WHERE hospital_hipe = %s AND pathway_number = %s ORDER BY as_of_date",
                (h, p),
            )
            referral_iri = f"{EATD}referral/{h}/{p}"
            fragment_text = open(FRAGMENT_PATH, encoding="utf-8").read()
            for as_of, dsr, dsc, dat, awd in cur.fetchall():
                total += 1
                rows = run_fragment(store, fragment_text, referral_iri, as_of)
                if len(rows) != 1:
                    mismatches.append((h, p, str(as_of), f"expected 1 row, got {len(rows)}"))
                    continue
                row = rows[0]

                def val(name):
                    v = row[name]
                    return int(v.value) if v is not None else None

                expected_bound = dat is not None
                got_bound = row["daysAwaitingTriage"] is not None
                if got_bound != expected_bound:
                    mismatches.append((
                        h, p, str(as_of),
                        f"daysAwaitingTriage boundness mismatch: got_bound={got_bound}, "
                        f"expected_bound={expected_bound} (source days_awaiting_triage={dat})",
                    ))
                    continue

                expected = (dsr, dsc, int(dat) if dat is not None else None, awd)
                got = (
                    val("daysSinceReferral"),
                    val("daysSinceReceived"),
                    val("daysAwaitingTriage"),
                    val("adjustedWaitDays"),
                )
                if got != expected:
                    mismatches.append((h, p, str(as_of), f"got {got}, expected {expected}"))

    print(f"[{label}] {total - len(mismatches)}/{total} rows matched core.referral_daily")
    if mismatches:
        print(f"[{label}] FAIL: {len(mismatches)} mismatch(es)\n")
        for m in mismatches:
            print(" ", m)
    return len(mismatches) == 0


def main():
    with psycopg.connect(DB_URL) as conn:
        store1 = build_store_hand_built(conn)
        ok1 = compare_against_source(conn, store1, "hand-built")

        events_dataset = run_events_mapping()
        print(f"events.rml.ttl materialised {len(events_dataset)} triples (all cancellation/suspension events)")
        store2 = build_store_real_mapping(conn, events_dataset)
        ok2 = compare_against_source(conn, store2, "real events.rml.ttl mapping")

    if ok1 and ok2:
        print("PASS: wait_counters.rq matches core.referral_daily on every sampled row, "
              "against both hand-built and real-mapping suspension data")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
