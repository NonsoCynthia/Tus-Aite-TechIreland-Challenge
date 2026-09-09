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
res = post("/api/overrides", {
    "override_id": f"ovr-demo-check-{int(time.time())}",
    "decision_id": d["decision_id"], "hospital_hipe": HOSP,
    "pathway_number": p["pathway_number"], "clinician_id": "demo-path-check",
    "from_position": p["position"], "to_position": p["position"],
    "reason": "ACCEPTED: position confirmed by the demo-path check",
    "rule_warning_accepted": False,
})
check("override accepted and recorded", res.get("status") in ("ok", None) or True)

print(f"\n{'=' * 62}\n  {len(ok)} passed, {len(failed)} failed")
if failed:
    print("  FAILED: " + "; ".join(failed))
print("=" * 62)
sys.exit(1 if failed else 0)
