"""Tus Aite orchestrator.

Serves the built UI and proxies the retrieval service same-origin, because
retrieval has no CORS middleware and a browser on another origin is blocked at
preflight on every call. The bearer token is held here and never reaches the
browser.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import concurrent.futures as cf
import datetime as _dt
import time

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .runner import CAPACITY_DIRECTION, execute
from .sources import query, sources_status, sparql
from .state import Run, store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RETRIEVAL = os.environ.get("RETRIEVAL_BASE_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ.get("RETRIEVAL_BEARER_TOKENS", "").split(",")[0].strip()
DIST = Path(os.environ.get("UI_DIST", Path(__file__).resolve().parents[2] / "web" / "dist"))

app = FastAPI(title="Tus Aite orchestrator", version="0.1.0")
# retrieval runs one uvicorn worker and every handler makes a blocking psycopg
# call, so it is easy to swamp: the operations fetch alone opens 16 connections
# and a run is looping the cohort at the same time. Cap our side rather than
# discover the ceiling as a 502 mid-demo.
_client = httpx.Client(
    base_url=RETRIEVAL,
    timeout=httpx.Timeout(30.0, connect=5.0),
    limits=httpx.Limits(max_connections=24, max_keepalive_connections=12),
    headers={"Authorization": f"Bearer {TOKEN}"} if TOKEN else {},
)


def _get(path: str, *, attempts: int = 3) -> Any:
    """GETs are idempotent, so a transient pool or timeout failure is retried
    rather than surfaced. The error names the RETRIEVAL path, not /api, so
    whoever reads it knows which service actually failed."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            r = _client.get(path)
        except httpx.HTTPError as exc:
            last = exc
            time.sleep(0.15 * (i + 1))
            continue
        if r.status_code >= 500 and i < attempts - 1:
            time.sleep(0.15 * (i + 1))
            continue
        if r.status_code >= 400:
            raise HTTPException(r.status_code, f"retrieval GET {path} -> {r.status_code}")
        return r.json()
    raise HTTPException(502, f"retrieval unreachable after {attempts} attempts: GET {path}") from last


# ---------------------------------------------------------------- reads

@app.get("/api/health")
def health() -> dict[str, Any]:
    try:
        up = _client.get("/health").json()
    except Exception as exc:                                    # noqa: BLE001
        up = {"status": "unreachable", "detail": str(exc)}
    # decisions_held makes the snapshot restore observable. A silent restore is
    # indistinguishable from "nobody has run yet", which is exactly the state it
    # exists to prevent someone misreading before a demo.
    return {"status": "ok", "retrieval": up, "capacity_direction": CAPACITY_DIRECTION,
            "sources": sources_status(), "decisions_held": store.decisions_held()}


@app.get("/api/cohort/{hospital_hipe}/{as_of_date}")
def cohort(hospital_hipe: str, as_of_date: str) -> dict[str, Any]:
    return _get(f"/hospitals/{hospital_hipe}/cohort/{as_of_date}")


@app.get("/api/context/{hospital_hipe}/{pathway_number}")
def context(hospital_hipe: str, pathway_number: str) -> dict[str, Any]:
    return _get(f"/referrals/{hospital_hipe}/{pathway_number}/context")


@app.get("/api/scores/{run_id}/{hospital_hipe}")
def scores(run_id: str, hospital_hipe: str) -> dict[str, Any]:
    """Citations come from here, not GET /evidence: reads.py's _resolve_iri
    collapses repeated predicates into one dict key, so a score citing six
    observations reads back as one. This path returns them as proper lists."""
    return _get(f"/runs/{run_id}/hospitals/{hospital_hipe}/scores")


@app.get("/api/decision/{hospital_hipe}/{as_of_date}")
def decision(hospital_hipe: str, as_of_date: str) -> dict[str, Any]:
    d = store.get_decision(hospital_hipe, as_of_date)
    if d is None:
        raise HTTPException(404, "no decision held for that hospital-day; run the agents")
    return d


_ops_cache: dict[tuple[str, str], dict[str, Any]] = {}
_days_cache: dict[str, dict[str, Any]] = {}


@app.get("/api/hospital-days/{hospital_hipe}")
def hospital_days(hospital_hipe: str, window: int = 60) -> dict[str, Any]:
    """Which hospital-days actually hold a cohort, discovered rather than assumed.

    The UI used to carry a hardcoded fortnight, which meant a day appearing in
    the data -- a new batch loaded today, say -- would be invisible until
    someone edited the frontend. This probes the window instead, so the selector
    follows the data.

    RUNNABLE vs READABLE is a real distinction, not a nicety. Evidence is
    date-blind: GET /referrals/{h}/{pw}/context takes no date and returns the
    most recent observation whichever day you ask about, so scoring an earlier
    day would cite readings taken later. Every day with a cohort can be READ;
    only the latest can honestly be RANKED.
    """
    cached = _days_cache.get(hospital_hipe)
    if cached:
        return cached

    today = _dt.date.today()
    candidates = [(today - _dt.timedelta(days=i)).isoformat() for i in range(window)]

    def probe(d: str) -> tuple[str, int]:
        try:
            r = _client.get(f"/hospitals/{hospital_hipe}/cohort/{d}")
            if r.status_code != 200:
                return d, 0
            return d, len(r.json().get("referrals", []))
        except httpx.HTTPError:
            return d, 0

    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        found = [(d, n) for d, n in ex.map(probe, candidates) if n > 0]

    found.sort(key=lambda x: x[0])
    days = [{"date": d, "referrals": n} for d, n in found]

    # The Intake panel reads a rise in these counts as arrivals, which is only
    # honest if nobody ever leaves. It used to evidence that with a constant --
    # the row count of dataset/out/referral_daily.csv, 70,022 -- which is the
    # GENERATOR's output file and not what gets loaded: the sample profile puts
    # 8,161 rows in this table, 4,063 of them this hospital's. The screen was
    # citing a figure 8.6x the data it was drawing. So the fact is read from the
    # table the panel is already showing, and travels on this response because
    # the panel already asks for it.
    #
    # NULL, never 0, when the read fails: query() returns [] rather than raising
    # (sources.py), and "0 referral-days recorded, none removed" would read as
    # evidence when it is actually a dead connection. The UI drops the line.
    counted = query(
        "SELECT count(*) AS referral_days, "
        "       count(*) FILTER (WHERE removal_date IS NOT NULL) AS removed "
        "  FROM core.referral_daily WHERE hospital_hipe = %s",
        (hospital_hipe,))
    intake = counted[0] if counted else {}

    out = {
        "hospital_hipe": hospital_hipe,
        "days": days,
        # the newest day holding data: the only one it is honest to rank
        "runnable": days[-1]["date"] if days else None,
        "today": today.isoformat(),
        "today_has_cohort": any(d["date"] == today.isoformat() for d in days),
        "referral_days": intake.get("referral_days"),
        "removed": intake.get("removed"),
    }
    _days_cache[hospital_hipe] = out
    return out


@app.post("/api/hospital-days/{hospital_hipe}/refresh")
def refresh_days(hospital_hipe: str) -> dict[str, Any]:
    """Forget what we discovered and look again -- for when a batch is loaded
    while the service is up, which is exactly the case this has to survive."""
    _days_cache.pop(hospital_hipe, None)
    for key in [k for k in _ops_cache if k[0] == hospital_hipe]:
        _ops_cache.pop(key, None)
    return hospital_days(hospital_hipe)


@app.get("/api/operations/{hospital_hipe}/{as_of_date}")
def operations(hospital_hipe: str, as_of_date: str) -> dict[str, Any]:
    """Hospital-level operational context for the overview.

    Every ward's latest bed-status arrives inside ANY referral's context call, so
    the ward panel costs one request. Observation age needs one call per referral,
    which is ~3.3s at 16-way concurrency, so the whole thing is cached per
    hospital-day.

    Only the LATEST snapshot is reported, deliberately. The capacity agent reads
    the primary ward's latest bed-status and the most recent clinic session --
    14 rows of 364 -- so drawing the fortnight beside alpha would imply a causal
    link the code does not contain.
    """
    key = (hospital_hipe, as_of_date)
    if key in _ops_cache:
        return _ops_cache[key]

    rows = _get(f"/hospitals/{hospital_hipe}/cohort/{as_of_date}")["referrals"]
    if not rows:
        return {"hospital_hipe": hospital_hipe, "as_of_date": as_of_date, "cohort": 0,
                "wards": [], "clinics": [], "observation_age": None, "clinical": {}}

    def one(pw: str) -> dict[str, Any] | None:
        try:
            r = _client.get(f"/referrals/{hospital_hipe}/{pw}/context")
            return r.json() if r.status_code == 200 else None
        except httpx.HTTPError:
            return None

    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        contexts = [c for c in ex.map(one, [r["pathway_number"] for r in rows]) if c]

    wards: dict[str, dict[str, Any]] = {}
    # The clinic half of the capacity score. The agent's clinic_pressure is
    # slots_booked/slots_total on the specialty's most recent session, and
    # DATASET_README calls this "where the real constraint usually sits" -- yet
    # de-duplicating wards used to drop the whole clinic_sessions array, so 30%
    # of the capacity score had no operational display anywhere.
    clinics: dict[str, dict[str, Any]] = {}
    ages: list[int] = []
    # Per-referral clinical facts the cohort payload does not carry. Gathered
    # here so the list screen needs one cached call, not 308.
    clinical: dict[str, dict[str, Any]] = {}
    as_of = _dt.date.fromisoformat(as_of_date)
    for ctx in contexts:
        cap = ctx.get("capacity") or {}
        spec = cap.get("specialty_hipe")
        for w in (cap.get("wards") or []):
            bs = w.get("latest_bed_status")
            if not bs:
                continue
            row = wards.setdefault(w["ward_id"], {
                "ward_id": w["ward_id"],
                # nominal_beds on a context ward is core.ward_specialty's figure:
                # beds this ward allocates to THAT ONE specialty, not the ward's
                # capacity. Taking the first one made a 92-bed ward report 45.
                # Accumulated per specialty below and summed.
                "allocations": {}, "nominal_beds": None,
                "occupancy_pct": float(bs["occupancy_pct"]),
                "occupied": bs.get("occupied"),
                # DATASET_README: "the answer to how many beds are available",
                # and it was never fetched.
                "free": bs.get("free"),
                "outliers": bs.get("outliers") or 0,
                "gar_status": bs.get("gar_status"),
                "over_9h": bs.get("awaiting_admission_over_9h") or 0,
                "over_24h": bs.get("awaiting_admission_over_24h") or 0,
                "dtoc": bs.get("delayed_transfers_of_care") or 0,
                "surge": bs.get("surge_capacity_in_use") or 0,
                "snapshot": bs.get("snapshot_datetime"),
                # Which specialties this ward backs, and whether it is their
                # primary. Dropped during de-duplication before, which left the
                # ward panel unjoinable to any referral's capacity score.
                "specialties": [], "primary_for": [],
            })
            if spec and spec not in row["specialties"]:
                row["specialties"].append(spec)
            if spec and w.get("nominal_beds") is not None:
                row["allocations"][spec] = w["nominal_beds"]
            if spec and w.get("is_primary") and spec not in row["primary_for"]:
                row["primary_for"].append(spec)

        sessions = cap.get("clinic_sessions") or []
        if spec and sessions and spec not in clinics:
            booked = sum(x["slots_booked"] for x in sessions)
            total = sum(x["slots_total"] for x in sessions)
            # The agent reads sessions[0] only. Marking it means the series can
            # be drawn as context with the ONE row that was cited called out,
            # rather than implying the agent read the fortnight.
            clinics[spec] = {
                "specialty_hipe": spec,
                "clinic_code": sessions[0].get("clinic_code"),
                "clinic_name": sessions[0].get("clinic_name"),
                "cited_session_date": sessions[0].get("session_date"),
                "cited_pressure": (round(sessions[0]["slots_booked"] / sessions[0]["slots_total"], 3)
                                   if sessions[0].get("slots_total") else 1.0),
                "slots_booked": booked, "slots_total": total,
                "slots_available": total - booked,
                "sessions": [
                    {"session_date": x["session_date"], "slots_total": x["slots_total"],
                     "slots_booked": x["slots_booked"], "slots_available": x["slots_available"]}
                    for x in sorted(sessions, key=lambda x: x["session_date"])
                ],
            }
        ref = ctx.get("referral") or {}
        pw = ref.get("pathway_number")
        obs = ctx.get("observations") or []
        newest_obs = max(obs, key=lambda o: o["obs_datetime"]) if obs else None
        age_days = None
        if newest_obs:
            taken = _dt.datetime.fromisoformat(newest_obs["obs_datetime"]).date()
            age_days = (as_of - taken).days
            ages.append(age_days)
        if pw:
            primary = next((c for c in (ctx.get("conditions") or []) if c.get("is_primary")), None)
            tri = (ctx.get("triage_events") or [{}])[0]
            clinical[pw] = {
                # news2 is NOT in the cohort payload; it only exists here.
                "news2": newest_obs.get("news2") if newest_obs else None,
                "obs_datetime": newest_obs.get("obs_datetime") if newest_obs else None,
                # The age is the point: a normal reading 871 days old is an
                # absence of information, not reassurance.
                "reading_age_days": age_days,
                "pain": newest_obs.get("pain") if newest_obs else None,
                "mts_category": newest_obs.get("mts_category") if newest_obs else None,
                # A weighted random draw over the specialty's mix, independent of
                # acuity. A record field, never evidence.
                "icd10am_code": primary.get("icd10am_code") if primary else None,
                "referral_date": ref.get("referral_date"),
                "referral_received_date": ref.get("referral_received_date"),
                "sent_for_triage_date": tri.get("sent_for_triage_date"),
                "triage_date": tri.get("triage_date"),
                "turnaround_days": tri.get("turnaround_days"),
            }

    # the ward's nominal capacity is the sum of what it allocates to each
    # specialty; occupied + free is the census actually recorded against it
    for row in wards.values():
        allocs = row.pop("allocations", {})
        row["allocations"] = allocs
        row["nominal_beds"] = sum(allocs.values()) if allocs else None
        occ, free = row.get("occupied"), row.get("free")
        row["census"] = (occ + free) if isinstance(occ, int) and isinstance(free, int) else None

    ages.sort()
    age = None
    if ages:
        age = {
            "n": len(ages), "median": ages[len(ages) // 2],
            "mean": round(sum(ages) / len(ages)),
            "max": ages[-1],
            "over_1y": sum(1 for a in ages if a > 365),
            "over_2y": sum(1 for a in ages if a > 730),
        }

    out = {
        "hospital_hipe": hospital_hipe, "as_of_date": as_of_date,
        "cohort": len(rows),
        # Every ward, latest snapshot only. The 85% line is the safe-operating
        # threshold from Bagust, Place & Posnett, BMJ 1999;319:155-8.
        "wards": sorted(wards.values(), key=lambda w: w["ward_id"]),
        "clinics": sorted(clinics.values(), key=lambda c: c["specialty_hipe"]),
        "observation_age": age,
        "clinical": clinical,
    }
    _ops_cache[key] = out
    return out


# ------------------------------------------------- reference layer (A5)

_ref_cache: dict[str, Any] = {}


@app.get("/api/reference")
def reference() -> dict[str, Any]:
    """The reference layer, so the UI stops hardcoding it.

    Three tables retrieval exposes no endpoint for, and which the frontend was
    substituting for:

    - `core.ref_specialty` -- every screen said "specialty 0600" because the
      names were never fetched. 0600 is Otolaryngology (ENT).
    - `core.ref_codes` where code_table='triage_category' -- carries the
      authoritative severity_rank AND crt_days, which the frontend hardcoded as
      28 and 91. A change to the seed would have silently desynced.
    - `core.ref_rules` -- the five rule IDs and their statements, none of which
      has ever appeared on a screen.

    Read once and cached: this is seed data that does not move while the service
    is up.
    """
    if _ref_cache:
        return _ref_cache
    out = {
        "specialties": query(
            "SELECT specialty_hipe, specialty_name, is_paediatric "
            "FROM core.ref_specialty ORDER BY specialty_hipe"),
        "triage_categories": query(
            "SELECT code_value, description, severity_rank, crt_days "
            "FROM core.ref_codes WHERE code_table = 'triage_category' "
            "ORDER BY severity_rank NULLS LAST, code_value"),
        "rules": query(
            "SELECT rule_id, statement, applies_to, threshold_days "
            "FROM core.ref_rules ORDER BY rule_id"),
        "codes": query(
            "SELECT code_table, code_value, description FROM core.ref_codes "
            "WHERE code_table <> 'triage_category' ORDER BY code_table, code_value"),
    }
    if out["specialties"]:
        _ref_cache.update(out)
    return out


# ------------------------------------------------- the hospital roster

_hosp_cache: dict[str, Any] = {}


@app.get("/api/hospitals")
def hospitals() -> dict[str, Any]:
    """Which hospitals exist, and what they are called.

    `core.hospitals` has held both since the seed, and no endpoint served it, so
    App.tsx carried the HIPE ids AND the display names as a literal -- two lines
    above a comment reading "Hospital-days are DISCOVERED, never hardcoded",
    which was true of the days and never true of the hospitals above them. A
    third hospital in the seed was invisible to the UI and a renamed one would
    have shown its old name for as long as nobody edited the frontend.

    Seed data, so it is read once and cached for the life of the process, the
    same as /api/reference.

    An EMPTY list is not the same claim as "no hospitals exist", and this
    handler cannot tell the two apart: sources.query() returns [] when the read
    fails rather than raising. So an empty read is NOT cached -- a retry costs
    one SELECT and might succeed -- and the caller is told in api.ts to read []
    as "the roster could not be read".
    """
    if _hosp_cache:
        return _hosp_cache
    rows = query(
        "SELECT hospital_hipe, hospital_name, hse_health_region, hospital_type, "
        "       total_inpatient_beds "
        "  FROM core.hospitals ORDER BY hospital_hipe")
    for r in rows:
        # char(4) in 003_core.sql. The UI compares this against the selector's
        # string value, so it is carried as a stripped string from here rather
        # than left to whatever the driver and JSON make of a padded char.
        r["hospital_hipe"] = str(r["hospital_hipe"]).strip()
    out = {"hospitals": rows}
    if rows:
        _hosp_cache.update(out)
    return out


# ------------------------------------------------- overrides, read back (A6)

@app.get("/api/overrides/{hospital_hipe}/{as_of_date}")
def overrides(hospital_hipe: str, as_of_date: str) -> dict[str, Any]:
    """What a clinician actually did, read back.

    Overrides were write-only: retrieval has no GET, the graph projection keeps
    only three triples and drops clinician_id, from_position, to_position and
    rule_warning_accepted, and the UI showed a flash message that died on the
    next navigation. So pressing the button left no trace anywhere a clinician
    could see.

    Joined through agent.decisions on (hospital, as_of_date) because an override
    references a decision_id, not a date. Newest first, and the newest per
    pathway is the one that stands -- earlier ones are history, not competing
    claims.
    """
    rows = query(
        """
        SELECT o.override_id, o.decision_id, o.pathway_number, o.clinician_id,
               o.from_position, o.to_position, o.reason,
               o.rule_warning_accepted, o.created_at
          FROM agent.overrides o
          JOIN agent.decisions d ON d.decision_id = o.decision_id
         WHERE o.hospital_hipe = %s AND d.as_of_date = %s
         ORDER BY o.created_at DESC
        """,
        (hospital_hipe, as_of_date),
    )
    for r in rows:
        if r.get("created_at") is not None:
            r["created_at"] = r["created_at"].isoformat()
    latest: dict[str, dict[str, Any]] = {}
    for r in rows:
        latest.setdefault(r["pathway_number"], r)
    return {"hospital_hipe": hospital_hipe, "as_of_date": as_of_date,
            "overrides": rows, "current": latest}


# ------------------------------------------------- the cohort graph (A7)

_GRAPH_BASE = "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/"
_EAT = _GRAPH_BASE + "ns#"

_COHORT_QUERY = """
PREFIX eat: <{eat}>
SELECT ?placement ?position ?referral ?role ?evidence
WHERE {{
  GRAPH <{graph}> {{
    ?decision a eat:Decision ; eat:hasPlacement ?placement .
    ?placement eat:position ?position ; eat:ranks ?referral .
    OPTIONAL {{
      ?placement ?roleProp ?evidence .
      VALUES (?roleProp ?role) {{
        (eat:citesUrgencyEvidence   "urgency")
        (eat:citesCapacityEvidence  "capacity")
        (eat:citesTimeframeEvidence "timeframe")
        (eat:citesMultiListEvidence "multi_list")
      }}
    }}
  }}
}}
ORDER BY ?position
"""


def _leaf(iri: str) -> str:
    return iri.rstrip("/").rsplit("/", 1)[-1]


def _label(iri: str, kind: str) -> str:
    """A readable name for a cited node.

    The last path segment is the wrong choice for half of these: a bed status
    ends in a percent-encoded timestamp and a clinic session in a bare date, so
    both would read as noise. The segment that identifies the thing is the one
    before it -- the ward, the clinic -- which is also the part a clinician
    recognises.
    """
    parts = [unquote(x) for x in iri.rstrip("/").split("/")]
    if kind in ("bed_status", "clinic_session") and len(parts) >= 2:
        return f"{parts[-2]} \u00b7 {parts[-1][:10]}"
    if kind == "score" and len(parts) >= 2:
        return f"{parts[-1]} {parts[-2]}"
    if kind == "referral_state" and len(parts) >= 2:
        return parts[-2]
    return parts[-1]


def _kind(iri: str) -> str:
    """What an evidence IRI is, read from its path segment.

    The inputs graph is not loaded on this machine, so these IRIs resolve to
    nothing -- a cited node has an identity and a type but no property values.
    That is stated on the surface rather than papered over.
    """
    for seg in ("bed-status", "clinic-session", "referral-state", "obs", "condition",
                "triage-event", "score", "rule"):
        if f"/{seg}/" in iri:
            return seg.replace("-", "_")
    return "evidence"


@app.get("/api/graph/cohort/{run_id}")
def cohort_graph(run_id: str, limit: int = 0) -> dict[str, Any]:
    """The WHOLE decision as a graph, in one SPARQL query.

    Every graph the product has drawn so far was rebuilt from Postgres, four
    levels deep, for one patient at a time. Meanwhile the run graph holds one
    Decision, 305 RankedPlacements, 613 Scores, 2,446 cites and 776 RuleChecks,
    and nothing in the application had ever issued a SPARQL query.

    `limit` caps placements for a smaller draw; 0 means the whole cohort.
    """
    graph = f"{_GRAPH_BASE}graph/run/{run_id}"
    rows = sparql(_COHORT_QUERY.format(eat=_EAT, graph=graph))
    if not rows:
        raise HTTPException(404, f"no triples in the run graph for {run_id}")

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def node(nid: str, label: str, kind: str, **extra: Any) -> str:
        n = nodes.setdefault(nid, {"id": nid, "label": label, "kind": kind, "cites": 0})
        n.update(extra)
        return nid

    node("decision", "decision", "decision")
    keep: set[str] = set()
    for r in rows:
        pos = int(r["position"])
        if limit and pos > limit:
            continue
        pid = r["placement"]
        keep.add(pid)
        node(pid, str(pos), "placement", position=pos, pathway=_leaf(r["referral"]))
        edges.append({"source": "decision", "target": pid, "label": "hasPlacement"})

    # one placement produces one row per citation, so hasPlacement repeats
    seen_edge: set[tuple[str, str, str]] = set()
    deduped = []
    for e in edges:
        key = (e["source"], e["target"], e["label"])
        if key not in seen_edge:
            seen_edge.add(key)
            deduped.append(e)
    edges = deduped

    for r in rows:
        ev, pid = r.get("evidence"), r["placement"]
        if not ev or pid not in keep:
            continue
        kind = _kind(ev)
        node(ev, _label(ev, kind), kind)
        nodes[pid]["cites"] += 1
        key = (pid, ev, r["role"])
        if key in seen_edge:
            continue
        seen_edge.add(key)
        edges.append({"source": pid, "target": ev, "label": r["role"]})

    placements = sum(1 for n in nodes.values() if n["kind"] == "placement")
    return {
        "run_id": run_id, "graph": graph,
        "nodes": list(nodes.values()), "edges": edges,
        "placements": placements,
        # NOT a citation count. A placement's six cited vitals arrive as ONE
        # role-tagged edge to its urgency score node, and the timeframe role
        # covers rule and referral-state links which are not evidence at all.
        # The recorded citation count behind 305 placements is 2,440; this is
        # 1,386 lines. Named for what it is.
        "evidence_links": sum(1 for e in edges if e["label"] != "hasPlacement"),
        # Honest about what this graph can and cannot say.
        "inputs_graph_loaded": bool(sparql(
            f"SELECT ?s WHERE {{ GRAPH <{_GRAPH_BASE}graph/inputs> {{ ?s ?p ?o }} }} LIMIT 1")),
    }


# ---------------------------------------------------------------- runs

class RunIn(BaseModel):
    hospital_hipe: str = Field(min_length=4, max_length=4)
    as_of_date: str


@app.post("/api/runs", status_code=202)
def start_run(payload: RunIn) -> dict[str, Any]:
    """Plain def, not async: the agents use synchronous httpx and loop the cohort
    sequentially. Work happens on a worker thread so the event loop stays free to
    answer the 1s progress poll this run depends on."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run = Run(run_id=f"run-{stamp}-{uuid.uuid4().hex[:4]}",
              hospital_hipe=payload.hospital_hipe, as_of_date=payload.as_of_date)
    store.create_run(run)
    threading.Thread(target=execute, args=(run, store),
                     kwargs={"base_url": RETRIEVAL, "token": TOKEN},
                     daemon=True, name=f"run-{run.run_id}").start()
    return {"run_id": run.run_id, "status": run.status}


@app.get("/api/runs/{run_id}")
def run_status(run_id: str) -> dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(404, "unknown run_id")
    return run.as_dict()


@app.post("/api/overrides")
def override(body: dict[str, Any]) -> JSONResponse:
    try:
        r = _client.post("/overrides", json=body)
    except httpx.HTTPError as exc:
        raise HTTPException(502, "retrieval unreachable: POST /overrides") from exc
    return JSONResponse(status_code=r.status_code, content=r.json() if r.content else {})


# ---------------------------------------------------------------- the UI

if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        candidate = DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
else:
    @app.get("/")
    def not_built() -> dict[str, str]:
        return {"status": "ui not built", "hint": "npm run build in web/", "dist": str(DIST)}
