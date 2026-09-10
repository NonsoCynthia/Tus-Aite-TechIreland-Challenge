"""Walks the demo path end to end against the RUNNING stack and asserts.

Not unit tests: this is the thing that has to work on 14 September, checked the
way it will actually be used. Run it before rehearsing and before presenting.

    python3 orchestrator/tests/demo_path.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

UI = "http://127.0.0.1:8080"
HOSP, DATE = "9001", "2026-08-30"
ok, failed = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (ok if cond else failed).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


def get(path: str, timeout: int = 60):
    with urllib.request.urlopen(UI + path, timeout=timeout) as r:
        return json.load(r)


def post(path: str, body: dict):
    req = urllib.request.Request(
        UI + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


print("\n1. the stack is up")
h = get("/api/health")
check("orchestrator healthy", h["status"] == "ok")
check("retrieval reachable", h["retrieval"]["status"] == "ok")
check("postgres + oxigraph ok", h["retrieval"]["postgres"] == "ok" and h["retrieval"]["oxigraph"] == "ok")
# read as 'availability' the whole system inverts while every number stays plausible
check("capacity direction is pressure (ADR-007)", h["capacity_direction"] == "pressure",
      f"got {h['capacity_direction']!r}")

print("\n2. the UI is served by the container, same origin")
with urllib.request.urlopen(UI + "/", timeout=20) as r:
    html = r.read().decode()
check("index served", r.status == 200)
check("brand favicon wired", "tus-aite-favicon" in html)

print("\n3. the cohort loads")
cohort = get(f"/api/cohort/{HOSP}/{DATE}")["referrals"]

# Every count below is pinned to the `sample` profile at 9001 on this date. That
# is deliberate: a silent change in the data is exactly what these numbers exist
# to catch. But `full` is a legitimate thing to be running -- the dataset track
# tells you to use it for anything you show people -- and on it these pins fail
# on the counts alone, twelve times, with nothing saying why. So say why once,
# here, and let them fail.
if len(cohort) != 308:
    print(f"""
  NOTE  This cohort holds {len(cohort)} referrals, not the 308 this suite is pinned to.
        Every count below is written for the `sample` profile at hospital {HOSP} on
        {DATE}. If you loaded `full` (make load FETCH_PROFILE=full) the counts
        below are expected to fail, and the failures are the pins, not the system.
        Update them from this run, or re-load the sample to compare like with like.
""")

check("308 referrals", len(cohort) == 308, f"got {len(cohort)}")
with_target = [r for r in cohort if r["crt_threshold_days"] is not None]
breached = [r for r in cohort if r["crt_breached"] is True]
check("165 have a target at all", len(with_target) == 165, f"got {len(with_target)}")
check("130 past target, of the 165", len(breached) == 130, f"got {len(breached)}")
check("no vitals in the cohort payload", "news2" not in cohort[0])

print("\n4. operational context (cached after the first call)")
t = time.time()
ops = get(f"/api/operations/{HOSP}/{DATE}", timeout=90)
first = time.time() - t
check("7 wards, latest snapshot each", len(ops["wards"]) == 7, f"got {len(ops['wards'])}")
check("every ward has a TrolleyGAR status", all(w["gar_status"] in ("G", "A", "R") for w in ops["wards"]))
age = ops["observation_age"]
check("reading age measured", age is not None and age["n"] == 308, f"n={age and age['n']}")
check("mean reading age is ~200 days", age and 150 <= age["mean"] <= 250, f"mean {age and age['mean']}d")
check("clinical facts for every referral", len(ops["clinical"]) == 308, f"got {len(ops['clinical'])}")
# absolute, not relative: the first call may already have been warm from an
# earlier run, which made the old ratio assertion impossible to satisfy
t = time.time(); get(f"/api/operations/{HOSP}/{DATE}"); cached = time.time() - t
check("cached call is under a second", cached < 1.0,
      f"first {first:.1f}s, cached {cached:.2f}s")

print("\n5. a run, start to finish")
run_id = post("/api/runs", {"hospital_hipe": HOSP, "as_of_date": DATE})["run_id"]
seen, last, t0 = [], 0, time.time()
while time.time() - t0 < 120:
    r = get(f"/api/runs/{run_id}")
    if r["scored"] != last:
        seen.append(r["scored"]); last = r["scored"]
    if r["status"] in ("done", "failed"):
        break
    time.sleep(0.7)
elapsed = time.time() - t0
check("run completed", r["status"] == "done", r.get("error") or "")
check("616 is the denominator (308 x 2 agents)", r["total"] == 616, f"got {r['total']}")
check("305 ranked", r["ranked"] == 305, f"got {r['ranked']}")
check("3 paediatric refused, not skipped", r["refused_paediatric"] == 3 and r["skipped"] == 0)
check("alpha ~0.811 (pressure)", r["alpha"] and 0.80 < r["alpha"] < 0.82, f"alpha {r['alpha']:.3f}")
check("run takes 15-45s", 15 < elapsed < 45, f"{elapsed:.0f}s")
# the bar must step off committed rows, not a timer
check("progress advanced in >6 steps", len(seen) > 6, f"{len(seen)} distinct counts")
check("progress never went backwards", seen == sorted(seen))

print("\n6. the decision the UI actually renders")
d = get(f"/api/decision/{HOSP}/{DATE}")
check("one list, 305 positions", len(d["rankings"]) == 305, f"got {len(d['rankings'])}")
check("positions are 1..n, unique", sorted(x["position"] for x in d["rankings"]) == list(range(1, 306)))
check("RULE-ORDER holds", d["rule_order_passed"] is True)
check("RULE-TIEBREAK holds", d["rule_tiebreak_passed"] is True)

print("\n7. the ordering rules the screen claims")
BAND = {1: (1, "Urgent"), 3: (2, "Semi-Urgent"), 2: (3, "Routine")}
rank_of = [BAND.get(x["cpc"], (4, "Uncategorised"))[0] for x in d["rankings"]]
check("no band ever precedes a more severe one", rank_of == sorted(rank_of))
# breach is a hard TIER above priority: the finding the review caught
bad = []
for band in (1, 3):
    rows = [x for x in d["rankings"] if x["cpc"] == band]
    flags = [x["crt_breached"] is True for x in rows]
    if flags != sorted(flags, reverse=True):
        bad.append(band)
check("past-target tier precedes within-target, per band", not bad, f"broken in {bad}")
for band in (1, 3):
    rows = [x for x in d["rankings"] if x["cpc"] == band and x["crt_breached"] is True]
    pri = [x["priority"] for x in rows]
    check(f"cpc {band}: priority descending inside the tier", pri == sorted(pri, reverse=True))

print("\n8. citations survive the round trip")
sc = get(f"/api/scores/{run_id}/{HOSP}")["scores"]
star = sc.get("PW-9001-000208", {})
u = star.get("urgency", {}).get("citations", [])
# GET /evidence collapses these to one; the scores endpoint keeps the list
check("all six NEWS2 vitals cited, not collapsed", len(u) == 6, f"got {len(u)}")
check("capacity cites bed status and clinic", len(star.get("capacity", {}).get("citations", [])) == 2)

print("\n9. the override path")
p = d["rankings"][0]
ovr_id = f"ovr-demo-check-{int(time.time())}"
res = post("/api/overrides", {
    "override_id": ovr_id,
    "decision_id": d["decision_id"], "hospital_hipe": HOSP,
    "pathway_number": p["pathway_number"], "clinician_id": "demo-path-check",
    "from_position": p["position"], "to_position": p["position"],
    "reason": "ACCEPTED: position confirmed by the demo-path check",
    "rule_warning_accepted": False,
})
# `or True` used to make this unconditionally pass -- 1 of the 81 checks
# asserted nothing at all. post() raises on any non-2xx, so a failed write
# already crashed the script; what was never asserted is what the response
# SAYS. retrieval returns {"status": "ok"} on the happy path and 207 with
# "postgres_committed_graph_projection_failed" when the row committed but the
# graph projection did not -- both are accepted here, because the override IS
# recorded in Postgres in both cases and section 14 reads it back from there.
# A silent shape change is now a failure rather than a pass.
check("override accepted and recorded",
      isinstance(res, dict) and res.get("status") in (
          "ok", "postgres_committed_graph_projection_failed"),
      f"POST /api/overrides returned {res!r}")

print("\n10. the reference layer (A5) -- nothing about it may be hardcoded")
ref = get("/api/reference")
specs = {r["specialty_hipe"]: r["specialty_name"] for r in ref["specialties"]}
check("every specialty has a real name", len(specs) == 7 and specs.get("0600") == "Otolaryngology (ENT)",
      f"got {len(specs)}")
check("0601 is flagged paediatric",
      any(r["is_paediatric"] for r in ref["specialties"] if r["specialty_hipe"] == "0601"))
crt = {r["code_value"]: r["crt_days"] for r in ref["triage_categories"]}
# the frontend used to hardcode these two; a seed change would have desynced it
check("CRT days come from the seed: urgent 28, semi 91", crt.get("1") == 28 and crt.get("3") == 91,
      f"got {crt}")
check("routine carries no target", crt.get("2") is None)
rules = {r["rule_id"] for r in ref["rules"]}
check("all five rules are readable", rules == {
    "RULE-CRT-URGENT", "RULE-CRT-SEMI", "RULE-TRIAGE-TURNAROUND",
    "RULE-ORDER", "RULE-TIEBREAK"}, f"got {sorted(rules)}")

print("\n11. per-referral reasoning reaches the UI (A2/A3)")
rows = d["rankings"]
check("every placement carries a rationale",
      all(r.get("rationale_summary") for r in rows),
      f"{sum(1 for r in rows if not r.get('rationale_summary'))} missing")
check("every placement carries rule checks",
      all(r.get("rule_checks") for r in rows),
      f"{sum(1 for r in rows if not r.get('rule_checks'))} missing")
by_rule = {}
for r in rows:
    for rc in r["rule_checks"]:
        by_rule.setdefault(rc["rule_id"], []).append(rc["passed"])
check("RULE-ORDER tested on every placement", len(by_rule.get("RULE-ORDER", [])) == len(rows))
# the one breach the product could never show, because triage_status was never read
check("RULE-TRIAGE-TURNAROUND is tested and does fire",
      "RULE-TRIAGE-TURNAROUND" in by_rule and not all(by_rule["RULE-TRIAGE-TURNAROUND"]),
      f"{by_rule.get('RULE-TRIAGE-TURNAROUND')}")
check("a breached urgent names its rule with a readable detail", any(
    rc["rule_id"] == "RULE-CRT-URGENT" and not rc["passed"] and rc.get("detail")
    for r in rows for rc in r["rule_checks"]))
cd = [r for r in rows if r.get("capacity_detail")]
check("capacity internals are harvested, not discarded", len(cd) == len(rows),
      f"{len(cd)}/{len(rows)}")
check("ward and clinic pressure are both real numbers", all(
    isinstance(r["capacity_detail"]["ward_pressure"], (int, float))
    and isinstance(r["capacity_detail"]["clinic_pressure"], (int, float)) for r in cd))
# capacity is specialty-level: it sets alpha and can never reorder two people
by_spec = {}
for r in rows:
    by_spec.setdefault(r["specialty_hipe"], set()).add(round(r["capacity_score"], 6))
check("capacity score is constant within a specialty",
      all(len(v) == 1 for v in by_spec.values()), f"{ {k: v for k, v in by_spec.items() if len(v) > 1} }")
check("both citation lists ride along on every row",
      all(len(r.get("urgency_citations", [])) == 6 for r in rows)
      and all(1 <= len(r.get("capacity_citations", [])) <= 2 for r in rows))

# Everyone on the list is in exactly one of four states -- but the states
# OVERLAP, so they reconcile on the union and never on the sum. The three
# paediatric referrals are refused by the urgency agent AND then recorded by the
# coordinator as missing_urgency_score, so adding the buckets gives 311 of 308.
placed_set = {r["pathway_number"] for r in rows}
paed_set = set(d["refused_paediatric"])
skip_set = set(d["skipped"])
exc_set = {e["pathway_number"] for e in d["excluded"]}
union = placed_set | paed_set | skip_set | exc_set
cohort_n = len(get(f"/api/cohort/{HOSP}/{DATE}")["referrals"])
check("every referral is accounted for exactly once, on the union",
      len(union) == cohort_n, f"union {len(union)} vs cohort {cohort_n}")
check("the buckets really do overlap, so a sum would be wrong",
      len(paed_set & exc_set) > 0,
      "if this ever becomes 0 the reconciliation copy must change")
check("nobody placed is also excluded", not (placed_set & exc_set))

print("\n12. the clinic half of the capacity score (A8)")
ops = get(f"/api/operations/{HOSP}/{DATE}")
check("clinics are reported at all", len(ops.get("clinics", [])) > 0, "was dropped entirely before")
one = next((c for c in ops["clinics"] if c["specialty_hipe"] == "0600"), None)
check("the cited session is identified, not just the series", bool(one and one["cited_session_date"]))
check("clinic pressure matches booked/total on the cited row",
      bool(one) and 0.0 <= one["cited_pressure"] <= 1.0)
check("wards say which specialty they back",
      any(w.get("primary_for") for w in ops["wards"]), "was dropped in de-duplication")
check("free beds are reported", any(w.get("free") is not None for w in ops["wards"]),
      "DATASET_README calls this the answer to how many beds are available")
# nominal_beds on a context ward is core.ward_specialty's per-SPECIALTY
# allocation, not the ward's capacity. Taking the first one made a 92-bed ward
# report 45, so it is summed across the specialties the ward serves.
w0 = ops["wards"][0]
check("a ward's nominal capacity sums its specialty allocations",
      w0["nominal_beds"] == sum(w0["allocations"].values()),
      f"{w0['nominal_beds']} vs {w0['allocations']}")
check("occupancy_pct is computed on the recorded census, not on nominal",
      abs(round(w0["occupied"] / w0["census"] * 100, 2) - w0["occupancy_pct"]) < 0.02,
      f"occ {w0['occupied']} census {w0['census']} pct {w0['occupancy_pct']}")

print("\n13. the whole decision as a graph (A7)")
g = get(f"/api/graph/cohort/{run_id}")
check("every placement is a node", g["placements"] == len(rows), f"{g['placements']} vs {len(rows)}")
check("evidence links came back in bulk", g["evidence_links"] > 1000, f"{g['evidence_links']}")
kinds = {}
for n in g["nodes"]:
    kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
check("exactly one decision node", kinds.get("decision") == 1)
# the finding the graph exists to SHOW: 305 patients converge on a handful of
# shared capacity rows, because capacity is specialty-level
check("capacity evidence is shared, not per-patient",
      0 < kinds.get("bed_status", 0) <= 10 and 0 < kinds.get("clinic_session", 0) <= 10,
      f"beds {kinds.get('bed_status')} clinics {kinds.get('clinic_session')}")
check("urgency evidence is per-patient", kinds.get("score", 0) == len(rows))
check("no node label is percent-encoded", not any("%" in n["label"] for n in g["nodes"]))
check("the inputs graph is reported honestly", g["inputs_graph_loaded"] is False,
      "if this flips to True, the resolved-values caveat must come off the screen")

print("\n14. overrides can be read back (A6)")
ovr = get(f"/api/overrides/{HOSP}/{DATE}")
check("the override just written is readable", any(
    o["clinician_id"] == "demo-path-check" for o in ovr["overrides"]),
    "write-only until the orchestrator gained a read path")
check("current holds one per pathway, newest wins",
      len(ovr["current"]) <= len(ovr["overrides"]))
check("attribution survives the round trip", all(
    o.get("clinician_id") and o.get("reason") for o in ovr["overrides"]),
    "the graph projection drops clinician_id; Postgres keeps it")

print("\n15. the decision survives a restart (A4)")
held = get("/api/health")["decisions_held"]
check("the orchestrator says which hospital-days it holds", len(held) > 0)
check("this hospital-day is one of them",
      any(x["hospital_hipe"] == HOSP and x["as_of_date"] == DATE for x in held))

print("\n16. the severity scale still discriminates on this data")
# web/src/lib/severity.ts picked its band boundaries against the ranges below.
# If the data moves far enough that a step stops firing, the scale has gone
# stale and a whole class of "this needs attention" silently reads as calm.
# Mirrored here rather than imported because that module is TypeScript.
def _sev_wait(r):
    if r is None or r <= 1: return 0
    return 1 if r < 2 else 2 if r < 5 else 3 if r < 10 else 4
def _sev_age(d):
    if d is None: return 0
    return 0 if d < 90 else 1 if d < 365 else 3 if d < 730 else 4
def _sev_occ(p):
    return 0 if p < 85 else 1 if p < 95 else 3 if p < 100 else 4
def _sev_booked(b):
    return 0 if b < 0.75 else 1 if b < 0.9 else 3 if b < 1 else 4

ratios = [r["adjusted_wait_days"] / r["crt_threshold_days"]
          for r in rows if r.get("crt_threshold_days")]
ages = [c["reading_age_days"] for c in ops["clinical"].values()
        if c.get("reading_age_days") is not None]
occs = [w["occupancy_pct"] for w in ops["wards"]]
booked = [c["cited_pressure"] for c in ops["clinics"]]

check("wait ratio still spans the scale", ratios and max(ratios) >= 10,
      f"max {max(ratios):.1f}x -- sev-4 needs 10x+")
check("every wait-ratio step fires", {_sev_wait(r) for r in ratios} == {0, 1, 2, 3, 4},
      f"fired {sorted({_sev_wait(r) for r in ratios})}")
check("reading age still spans the scale", ages and max(ages) >= 730,
      f"max {max(ages)}d -- sev-4 needs 730d+")
# sevReadingAge deliberately skips step 2 so that "over two years" is unmistakable
check("every reading-age step fires", {_sev_age(a) for a in ages} == {0, 1, 3, 4},
      f"fired {sorted({_sev_age(a) for a in ages})}")
check("occupancy crosses the 85% line and reaches 100",
      any(o >= 85 for o in occs) and any(o >= 100 for o in occs))
check("clinic booked reaches full", any(b >= 1 for b in booked))
# a scale driven off these would be flat, which is why severity.ts refuses them
n2_totals = [c["news2"] for c in ops["clinical"].values() if c.get("news2") is not None]
zeros = sum(1 for n in n2_totals if n == 0)
check("NEWS2 total is still too degenerate to drive a scale", zeros > len(n2_totals) / 3,
      f"{zeros} of {len(n2_totals)} score exactly 0 -- do not grade on the total")

print("\n17. capacity evidence is date-blind, so it must never be labelled as the day's")
# core.bed_status and core.clinic_sessions are fetched upstream with
# ORDER BY ... DESC LIMIT n and no date predicate, so EVERY hospital-day is
# served the same newest snapshot. The UI has to say so; this pins the fact
# that makes that necessary. If it ever becomes false, the caveat can come off.
older = [d["date"] for d in get(f"/api/hospital-days/{HOSP}")["days"] if d["date"] != DATE]
if older:
    probe = older[len(older) // 2]
    old_ops = get(f"/api/operations/{HOSP}/{probe}")
    same_ward = old_ops["wards"][0]["snapshot"] == ops["wards"][0]["snapshot"]
    check("an older day is served the newest ward snapshot", same_ward,
          f"{probe} -> {old_ops['wards'][0]['snapshot']}")
    check("that snapshot post-dates the day it is served for",
          old_ops["wards"][0]["snapshot"][:10] > probe,
          f"snapshot {old_ops['wards'][0]['snapshot'][:10]} vs as-of {probe}")
    # the cohort itself IS correctly date-scoped, which is why the day is
    # readable at all -- only the capacity half is blind
    check("the cohort for that day is genuinely that day's",
          len(get(f"/api/cohort/{HOSP}/{probe}")["referrals"]) != len(rows),
          "an older day should hold fewer referrals than the newest")

print("\n18. the Intake panel's claim is evidenced from the data, not from a file")
# The panel reads a rise in the day counts as arrivals, which is only honest if
# nobody ever leaves. That used to be evidenced by a constant -- 70,022, the row
# count of the GENERATOR's output file, while the loaded table holds 8,161 -- so
# the screen cited a figure 8.6x the data it drew. These two now travel on the
# response the panel already fetches.
#
# Deliberately NOT pinned to a row count: it follows the profile, and pinning it
# is the exact failure being fixed. What is pinned is that the fact is READABLE
# and that it says what the visible claim says.
hd = get(f"/api/hospital-days/{HOSP}")
check("the referral-day count is served, not typed in",
      isinstance(hd.get("referral_days"), int) and hd["referral_days"] > 0,
      f"referral_days={hd.get('referral_days')!r} (null means the read failed)")
check("nothing has left this list, which is what the panel claims",
      hd.get("removed") == 0, f"removed={hd.get('removed')!r}")

print(f"\n{'=' * 62}\n  {len(ok)} passed, {len(failed)} failed")
if failed:
    print("  FAILED: " + "; ".join(failed))
print("=" * 62)
sys.exit(1 if failed else 0)
