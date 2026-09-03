#!/usr/bin/env python3
"""
Sample validation for kg/queries/wait_counters.rq.

No input-layer triples exist in any store yet (only kg/out/referral_state.nt, which carries
no referral dates, suspensions, or triage events). So this script materialises a MINIMAL
in-memory graph for a fixed sample of real referrals — dates, suspension intervals and
triage status pulled straight from Postgres — runs the fragment against it, and compares the
result to core.referral_daily's own stored counters for every (referral, as_of_date) row in
the extract window. It reports the actual match count; it does not assert one.

Once the A/B/E mappings exist and produce a real materialised graph, replace the in-memory
store here with a connection to that graph and drop the manual triple construction — the
comparison logic (against core.referral_daily) stays the same.

Run from the repo root:
    python kg/tests/test_wait_counters_sample.py
Exits non-zero if any comparison fails.
"""

import os
import sys

import psycopg
import pyoxigraph as ox

DB_URL = os.environ.get(
    "KG_DB_URL_PSYCOPG",
    "postgresql://kg_loader@localhost:5433/triage",
)
FRAGMENT_PATH = "kg/queries/wait_counters.rq"

EAT = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/ns#"
EATD = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/id/"
TIME = "http://www.w3.org/2006/time#"
XSD_DATE = "http://www.w3.org/2001/XMLSchema#date"

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


def build_store(conn):
    """Materialise the minimal graph the fragment needs, from live Postgres, for SAMPLE."""
    store = ox.Store()
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

            cur.execute(
                "SELECT suspension_start_date, suspension_end_date FROM core.suspension_events "
                "WHERE hospital_hipe = %s AND pathway_number = %s",
                (h, p),
            )
            suspensions = cur.fetchall()

            ref_iri = n(f"{EATD}referral/{h}/{p}")
            store.add(ox.Quad(ref_iri, n(EAT + "referralDate"), lit(rdate, XSD_DATE)))
            store.add(ox.Quad(ref_iri, n(EAT + "referralReceivedDate"), lit(rrecv, XSD_DATE)))

            state_iri = n(f"{EATD}referral-state/{h}/{p}/2020-01-01")
            store.add(ox.Quad(state_iri, n(EAT + "stateOf"), ref_iri))
            store.add(ox.Quad(state_iri, n(EAT + "validFrom"), lit("2020-01-01", XSD_DATE)))
            store.add(ox.Quad(state_iri, n(EAT + "triageStatus"), lit(status)))

            for sstart, send in suspensions:
                susp_iri = n(f"{EATD}suspension/{h}/{p}/{sstart}")
                store.add(ox.Quad(ref_iri, n(EAT + "hasSuspension"), susp_iri))
                interval_iri = n(f"{EATD}suspension/{h}/{p}/{sstart}/interval")
                store.add(ox.Quad(susp_iri, n(TIME + "hasTime"), interval_iri))
                begin_iri = n(f"{EATD}suspension/{h}/{p}/{sstart}/begin")
                store.add(ox.Quad(interval_iri, n(TIME + "hasBeginning"), begin_iri))
                store.add(ox.Quad(begin_iri, n(TIME + "inXSDDate"), lit(sstart, XSD_DATE)))
                if send is not None:
                    end_iri = n(f"{EATD}suspension/{h}/{p}/{sstart}/end")
                    store.add(ox.Quad(interval_iri, n(TIME + "hasEnd"), end_iri))
                    store.add(ox.Quad(end_iri, n(TIME + "inXSDDate"), lit(send, XSD_DATE)))
    return store


def run_fragment(store, fragment_text, referral_iri, as_of_date):
    q = fragment_text.replace(
        "VALUES (?referral ?asOfDate) { }",
        f'VALUES (?referral ?asOfDate) {{ (<{referral_iri}> "{as_of_date}"^^<{XSD_DATE}>) }}',
    )
    return list(store.query(q))


def main():
    fragment_text = open(FRAGMENT_PATH, encoding="utf-8").read()

    with psycopg.connect(DB_URL) as conn:
        store = build_store(conn)
        print(f"Materialised {len(store)} triples for {len(SAMPLE)} referrals")

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

                    expected = (dsr, dsc, int(dat) if dat is not None else None, awd)
                    got = (
                        val("daysSinceReferral"),
                        val("daysSinceReceived"),
                        val("daysAwaitingTriage"),
                        val("adjustedWaitDays"),
                    )
                    if got != expected:
                        mismatches.append((h, p, str(as_of), f"got {got}, expected {expected}"))

    print(f"{total - len(mismatches)}/{total} rows matched core.referral_daily")
    if mismatches:
        print(f"\nFAIL: {len(mismatches)} mismatch(es)\n")
        for m in mismatches:
            print(" ", m)
        return 1

    print("PASS: wait_counters.rq matches core.referral_daily on every sampled row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
