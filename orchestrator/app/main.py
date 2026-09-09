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

import concurrent.futures as cf
import datetime as _dt
import time

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .runner import CAPACITY_DIRECTION, execute
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
    return {"status": "ok", "retrieval": up, "capacity_direction": CAPACITY_DIRECTION}


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
    out = {
        "hospital_hipe": hospital_hipe,
        "days": days,
        # the newest day holding data: the only one it is honest to rank
        "runnable": days[-1]["date"] if days else None,
        "today": today.isoformat(),
        "today_has_cohort": any(d["date"] == today.isoformat() for d in days),
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
        return {"wards": [], "observation_age": None, "cohort": 0}

    def one(pw: str) -> dict[str, Any] | None:
        try:
            r = _client.get(f"/referrals/{hospital_hipe}/{pw}/context")
            return r.json() if r.status_code == 200 else None
        except httpx.HTTPError:
            return None

    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        contexts = [c for c in ex.map(one, [r["pathway_number"] for r in rows]) if c]

    wards: dict[str, dict[str, Any]] = {}
    ages: list[int] = []
    # Per-referral clinical facts the cohort payload does not carry. Gathered
    # here so the list screen needs one cached call, not 308.
    clinical: dict[str, dict[str, Any]] = {}
    as_of = _dt.date.fromisoformat(as_of_date)
    for ctx in contexts:
        for w in ((ctx.get("capacity") or {}).get("wards") or []):
            bs = w.get("latest_bed_status")
            if bs and w["ward_id"] not in wards:
                wards[w["ward_id"]] = {
                    "ward_id": w["ward_id"], "nominal_beds": w.get("nominal_beds"),
                    "occupancy_pct": float(bs["occupancy_pct"]),
                    "gar_status": bs.get("gar_status"),
                    "over_9h": bs.get("awaiting_admission_over_9h") or 0,
                    "over_24h": bs.get("awaiting_admission_over_24h") or 0,
                    "dtoc": bs.get("delayed_transfers_of_care") or 0,
                    "surge": bs.get("surge_capacity_in_use") or 0,
                    "snapshot": bs.get("snapshot_datetime"),
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
        "observation_age": age,
        "clinical": clinical,
    }
    _ops_cache[key] = out
    return out


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
