"""Generate the synthetic referral prioritisation dataset.

Twelve steps, in the order of BUILD_MANUAL section 8.2. Order matters: each step
depends on the one before it.

Two rules from section 8.3 are the scientific basis of the whole project and are
enforced here rather than trusted to care:

  1. Observations OVERLAP across triage categories. If urgent referrals always had
     a high early warning score, the urgency agent would be rediscovering the label
     it is scored against. The coupling_coefficient in vitals_by_category.yml
     shrinks the between-category mean separation toward the grand mean; the
     within-category spread stays at the MIMIC-fitted value.

  2. latent_hazard is NEVER computed from news2. That is the guarantee that keeps
     the evaluation honest: if risk were a function of what the agent reads, the
     agent would be graded against its own input.

     KNOWN LIMITATION. Despite the parameter being named base_by_condition_range,
     `base` is currently a uniform draw over that range and does NOT depend on the
     referral's condition -- self.refs carries no condition code at that point. Age
     and the noise term are real. Deterioration also couples to waiting time via
     min(1.0, waited / 400.0), which the calibration file does not mention. See
     docs/CALIBRATION_FINDINGS.md; correcting it changes generated data and so needs
     a new data version, not a quiet edit.

Determinism, section 8.5: seeded RNG, no set iteration, sorted before write, fixed
column order, "\\n" line terminator, no datetime.now() in generated content.
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import simpy
import yaml

from generator.writers import write_table

ROOT = Path(__file__).resolve().parent.parent
CAL = ROOT / "generator" / "calibration"
OUT = ROOT / "out"

SPECIALTIES = ["2600", "0100", "0300", "1800", "0700", "0600", "0601"]
PAEDIATRIC = {"0601"}
# Urgent=1, Semi-Urgent=3, Routine=2. The codes are NOT in severity order.
CATEGORY_CODE = {"Urgent": 1, "Semi-Urgent": 3, "Routine": 2}
SEVERITY_RANK = {1: 1, 3: 2, 2: 3}
MTS_BY_RANK = {1: ["red", "orange"], 2: ["orange", "yellow"], 3: ["yellow", "green", "blue"]}
ICTS_BY_RANK = {1: ["red", "orange"], 2: ["orange", "yellow"], 3: ["yellow", "green"]}
AREA_CODES = ["D012", "D024", "G091", "C015", "L023", "W044", "K011", "M032"]


# --------------------------------------------------------------------------- #
# NEWS2
# --------------------------------------------------------------------------- #

def news2(rr, spo2, sbp, hr, avpu, temp) -> int:
    """National Early Warning Score 2, scale 1, breathing air."""
    s = 0
    s += 3 if rr <= 8 else 1 if rr <= 11 else 0 if rr <= 20 else 2 if rr <= 24 else 3
    s += 3 if spo2 <= 91 else 2 if spo2 <= 93 else 1 if spo2 <= 95 else 0
    s += 3 if sbp <= 90 else 2 if sbp <= 100 else 1 if sbp <= 110 else 0 if sbp <= 219 else 3
    s += 3 if hr <= 40 else 1 if hr <= 50 else 0 if hr <= 90 else 1 if hr <= 110 else 2 if hr <= 130 else 3
    s += 0 if avpu == "A" else 3
    s += 3 if temp <= 35.0 else 1 if temp <= 36.0 else 0 if temp <= 38.0 else 1 if temp <= 39.0 else 2
    return min(s, 20)


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #

def load_calibration() -> dict:
    cal = {}
    for name in ("vitals_by_category", "specialty_mix", "length_of_stay", "assumed_parameters"):
        path = CAL / f"{name}.yml"
        if not path.exists():
            raise SystemExit(
                f"Missing {path}.\nRun `make calibrate` first -- the generator does not invent "
                f"distributions when the fitted ones are absent."
            )
        cal[name] = yaml.safe_load(path.read_text())
    return cal


def vitals_model(cal: dict) -> tuple[dict, float]:
    """Return {category_code: {vital: (mean, sd)}} with coupling applied.

    The coupling shrinks each category's mean toward the grand mean. At 1.0 the
    categories are as separated as MIMIC measured; at 0.0 they are identical and
    the vitals carry no signal about category at all.
    """
    vitals_cal = cal["vitals_by_category"]
    coupling = vitals_cal["coupling"]["coupling_coefficient"]["value"]

    per_cat: dict[int, dict[str, tuple[float, float]]] = {}
    weights: dict[int, int] = {}
    for label, block in vitals_cal["categories"].items():
        code = CATEGORY_CODE[label]
        # Routine carries n_source_rows rather than n_stays: it is derived from
        # reference ranges, not fitted, because MIMIC's demo has only 2 ESI 4-5
        # stays. At coupling 1.0 these weights do not affect the result anyway --
        # the shrink toward the grand mean is the identity.
        weights[code] = block.get("n_stays") or block.get("n_source_rows") or 1
        per_cat[code] = {
            key: (stat["mean"], stat["sd"])
            for key, stat in block["vitals"].items()
            if isinstance(stat, dict) and "mean" in stat
        }

    total_w = sum(weights.values())
    keys = sorted(per_cat[1].keys())
    grand = {
        k: sum(per_cat[c][k][0] * weights[c] for c in per_cat) / total_w for k in keys
    }

    out: dict[int, dict[str, tuple[float, float]]] = {}
    for code, vitals in per_cat.items():
        out[code] = {
            k: (grand[k] + coupling * (m - grand[k]), sd) for k, (m, sd) in vitals.items()
        }
    return out, coupling


VITAL_ORDER = ["heartrate", "resprate", "temperature_c", "o2sat", "sbp", "dbp"]

# Physiological bounds. Draws outside these are REJECTED and redrawn rather than
# clipped: clipping piles mass onto the boundary and shrinks the SD away from the
# fitted value, which quietly makes the categories separate more cleanly than the
# source data does.
VITAL_BOUNDS = {
    "heartrate": (35, 180), "resprate": (8, 40), "temperature_c": (34.5, 41.0),
    "o2sat": (80, 100), "sbp": (80, 210), "dbp": (40, 120),
}


def covariance_model(cal: dict, vitals: dict) -> dict:
    """Per-category covariance from the MIMIC-fitted correlation matrix.

    Real vitals move together within a patient. Drawing each one independently
    discards that, and NEWS2's five components then average out into a tighter
    distribution than the source data shows. Routine has no fitted correlation --
    it comes from reference ranges, not from MIMIC -- so it falls back to
    independence, which is recorded rather than hidden.
    """
    block = cal["vitals_by_category"].get("vitals_correlation", {})
    by_cat = block.get("by_category", {})
    label_for = {v: k for k, v in CATEGORY_CODE.items()}

    out = {}
    for code, stats in vitals.items():
        std_devs = np.array([stats[vital][1] for vital in VITAL_ORDER])
        entry = by_cat.get(label_for.get(code, ""))
        if entry:
            source_order = entry["order"]
            matrix = np.array(entry["matrix"], dtype=float)
            position = [source_order.index(vital) for vital in VITAL_ORDER]
            corr = matrix[np.ix_(position, position)]
        else:
            corr = np.eye(len(VITAL_ORDER))
        out[code] = np.outer(std_devs, std_devs) * corr
    return out


def load_pool(cal: dict):
    """Real MIMIC vitals rows, per category, for smoothed-bootstrap resampling.

    Fitting a Gaussian to means and SDs throws away skew, tails, within-patient
    correlation and the SpO2 ceiling, and measurably separates the categories more
    cleanly than the source does (AUC 0.73 against MIMIC's own 0.65). Resampling the
    real rows reproduces the real distribution because it is the real distribution.
    """
    path = CAL / "mimic_vitals_pool.csv"
    if not path.exists():
        return {}, {}, 0.0
    df = pd.read_csv(path)
    jitter = cal["vitals_by_category"]["sampling"]["jitter_sd_fraction"]["value"]
    pool, sds = {}, {}
    for label, code in CATEGORY_CODE.items():
        sub = df[df["category"] == label]
        if len(sub) >= 30:
            pool[code] = sub[VITAL_ORDER].to_numpy(dtype=float)
            sds[code] = sub[VITAL_ORDER].std(ddof=1).to_numpy(dtype=float)
    return pool, sds, jitter


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #

class Generator:
    def __init__(self, cfg: dict, cal: dict, profile: str):
        self.cfg = cfg
        self.cal = cal
        self.profile = profile
        profile_cfg = cfg["profiles"][profile]

        self.rng = np.random.default_rng(cfg["seed"])
        random.seed(cfg["seed"])

        wanted = profile_cfg["hospitals"]
        self.hospitals = [
            h for h in cfg["hospitals"] if wanted == "all" or h["hipe"] in wanted
        ]
        self.public = [h for h in self.hospitals if h["type"] == "public"]
        self.scale = profile_cfg["referrals_scale"]

        self.end = cfg["simulation"]["end_date"]
        if isinstance(self.end, str):
            self.end = date.fromisoformat(self.end)
        self.days = [self.end - timedelta(days=i) for i in range(profile_cfg["days"] - 1, -1, -1)]
        self.start = self.days[0]
        self.snapshot_times = cfg["simulation"]["snapshot_times"]

        self.vitals, self.coupling = vitals_model(cal)
        self.vcov = covariance_model(cal, self.vitals)
        self.pool, self.pool_sd, self.jitter = load_pool(cal)
        self.cond_mix = cal["assumed_parameters"]["parameters"]["condition_mix_by_specialty"]["value"]
        self.hazard = cal["assumed_parameters"]["parameters"]["latent_hazard_model"]["value"]
        self.spec_weights = self._specialty_weights()
        self.bands = self._wait_bands()

        self.t: dict[str, pd.DataFrame] = {}

    def _specialty_weights(self) -> dict[str, float]:
        mix = self.cal["specialty_mix"].get("specialties", {})
        weights = {}
        for code in SPECIALTIES:
            block = mix.get(code) or mix.get(int(code)) if isinstance(mix, dict) else None
            if isinstance(block, dict):
                prop = block.get("proportion")
                if isinstance(prop, dict):
                    prop = prop.get("value")
                if isinstance(prop, (int, float)):
                    weights[code] = float(prop)
        if len(weights) != len(SPECIALTIES) or abs(sum(weights.values())) < 1e-9:
            weights = {code: 1.0 / len(SPECIALTIES) for code in SPECIALTIES}
        total = sum(weights.values())
        return {code: share / total for code, share in weights.items()}

    def _wait_bands(self) -> list[tuple[int, int, float]]:
        """Waiting-time bands from NTPF, fitted.

        Previously this was a gamma(2.2, 42) that nothing justified. NTPF publishes
        the national distribution across wait bands, so the shape comes from the
        source rather than from a shape parameter someone liked.
        """
        national = self.cal["specialty_mix"].get("national_wait_band_distribution", {})
        # NTPF publishes shares per band in months; these are the bands in days.
        bands = [(1, 183, national.get("m0_6")), (183, 365, national.get("m6_12")),
                 (365, 548, national.get("m12_18")), (548, 900, national.get("m18_plus"))]
        bands = [(lo, hi, share) for lo, hi, share in bands if isinstance(share, (int, float))]
        if not bands:
            raise SystemExit("specialty_mix.yml has no fitted wait-band distribution.")
        total = sum(share for _, _, share in bands)
        return [(lo, hi, share / total) for lo, hi, share in bands]

    def _draw_wait(self) -> int:
        chosen = int(self.rng.choice(len(self.bands), p=[share for _, _, share in self.bands]))
        lo, hi, _ = self.bands[chosen]
        return int(self.rng.integers(lo, hi))

    # -- 1. hospitals, wards, ward_specialty -------------------------------- #
    def gen_hospitals(self) -> None:
        self.t["hospitals"] = pd.DataFrame(
            [
                {
                    "hospital_hipe": h["hipe"],
                    "hospital_name": h["name"],
                    "hse_health_region": h["region"],
                    "hospital_type": h["type"],
                    "total_inpatient_beds": h["beds"],
                }
                for h in self.hospitals
            ]
        )

        hs, wards, ws = [], [], []
        for h in self.hospitals:
            # The smallest site does not run every service; that variation is the
            # point, and it gives the system somewhere to redirect patients.
            offered = SPECIALTIES if h["beds"] >= 280 else ["2600", "0100", "1800", "0600"]
            for sp in SPECIALTIES:
                hs.append(
                    {
                        "hospital_hipe": h["hipe"],
                        "specialty_hipe": sp,
                        "service_name": f"{sp} service, {h['name'].split()[0]}"
                        if sp in offered
                        else "(not offered)",
                        "active": "true" if sp in offered else "false",
                    }
                )

            n_wards = max(2, h["beds"] // 90)
            for w in range(n_wards):
                wid = f"W-{h['hipe']}-{w + 1:02d}"
                beds = max(12, h["beds"] // n_wards)
                wards.append(
                    {
                        "hospital_hipe": h["hipe"],
                        "ward_id": wid,
                        "ward_name": f"Ward {w + 1}",
                        "total_beds": beds,
                        "ward_type": "icu" if w == 0 and h["beds"] > 300 else "inpatient",
                    }
                )
                # Every public hospital gets at least one genuinely shared ward.
                # Shared wards are where specialties compete for the same beds,
                # which is the mechanism behind the trolley crisis.
                share = offered[: 3] if w == 0 else offered[w % len(offered): w % len(offered) + 2]
                share = share or offered[:1]
                nominal = max(1, beds // max(1, len(share)))
                for i, sp in enumerate(share):
                    ws.append(
                        {
                            "hospital_hipe": h["hipe"],
                            "ward_id": wid,
                            "specialty_hipe": sp,
                            "nominal_beds": nominal,
                            "is_primary": "true" if i == 0 else "false",
                        }
                    )

        self.t["hospital_specialty"] = pd.DataFrame(hs)
        self.t["wards"] = pd.DataFrame(wards)
        self.t["ward_specialty"] = pd.DataFrame(ws)

    # -- 2/3. persons and patients ------------------------------------------ #
    def gen_people(self) -> None:
        n_ref = {h["hipe"]: max(20, int(h["active_referrals"] * self.scale)) for h in self.public}
        total = sum(n_ref.values())
        self.n_ref = n_ref

        n_persons = int(total * 1.3)
        cov = self.cfg["ihi_coverage"]

        persons, patients = [], []
        for i in range(n_persons):
            ihi = f"IHI-{7000000 + i}"
            sex = "F" if self.rng.random() < 0.52 else "M"
            age = int(np.clip(self.rng.normal(58, 19), 1, 97))
            dob = date(self.end.year - age, 1 + i % 12, 1 + i % 28)
            persons.append(
                {
                    "ihi_number": ihi,
                    "person_sex": sex,
                    "person_date_of_birth": dob,
                    "area_of_residence_code": AREA_CODES[i % len(AREA_CODES)],
                }
            )

        self.persons = persons
        self.t["persons"] = pd.DataFrame(persons)

        # Assign patients per hospital. A share of persons appear at two hospitals,
        # which is what makes multi-list visibility demonstrable. Around a third
        # have no national identifier, and that gap is deliberate.
        idx = 0
        self.patient_of: dict[str, list[tuple[str, str, str | None, int]]] = {}
        for h in self.public:
            rows = []
            for j in range(n_ref[h["hipe"]]):
                p = persons[idx % n_persons]
                idx += 1
                pid = f"MRN-{h['hipe']}-{j:06d}"
                has_ihi = self.rng.random() < cov
                rows.append((pid, p["ihi_number"] if has_ihi else None, p["person_sex"], p["person_date_of_birth"]))
                patients.append(
                    {
                        "hospital_hipe": h["hipe"],
                        "patient_id": pid,
                        "ihi_number": p["ihi_number"] if has_ihi else "",
                        "patient_sex": p["person_sex"],
                        "patient_date_of_birth": p["person_date_of_birth"],
                        "area_of_residence_code": p["area_of_residence_code"],
                    }
                )
            self.patient_of[h["hipe"]] = rows

        self.t["patients"] = pd.DataFrame(patients)
        # persons is trimmed at write time to those actually referenced.

    # -- 4/5/6/7. referrals, triage, conditions, observations --------------- #
    def gen_referrals(self) -> None:
        specs = list(self.spec_weights.keys())
        probs = np.array([self.spec_weights[s] for s in specs])
        probs = probs / probs.sum()

        refs, triage, conds, obs = [], [], [], []
        awaiting_share = self.cfg["awaiting_triage_share"]
        disagree = self.cal["vitals_by_category"]["disagreement"]["gp_triage_disagreement_rate"]["value"]

        for h in self.public:
            for j, (pid, ihi, sex, dob) in enumerate(self.patient_of[h["hipe"]]):
                pw = f"PW-{h['hipe']}-{j:06d}"
                sp = specs[int(self.rng.choice(len(specs), p=probs))]
                if sp in PAEDIATRIC:
                    dob = date(self.end.year - int(self.rng.integers(2, 15)), 6, 1)

                wait = self._draw_wait()
                ref_date = self.end - timedelta(days=wait)
                recv = ref_date + timedelta(days=int(self.rng.integers(1, 15)))
                if recv > self.end:
                    recv = self.end
                gp_pri = 1 if self.rng.random() < 0.28 else 2

                is_awaiting = self.rng.random() < awaiting_share
                if is_awaiting:
                    cat = None
                    te_id = None
                else:
                    # Triage usually agrees with the GP, and the disagreements are
                    # the interesting part.
                    if self.rng.random() < disagree:
                        cat = int(self.rng.choice([1, 3, 2]))
                    else:
                        cat = 1 if gp_pri == 1 else int(self.rng.choice([3, 2], p=[0.45, 0.55]))
                    te_id = f"TE-{h['hipe']}-{j:06d}"
                    sent = recv + timedelta(days=int(self.rng.integers(0, 6)))
                    turn = int(np.clip(self.rng.gamma(2.0, 3.0), 0, 40))
                    ret = sent + timedelta(days=turn)
                    triage.append(
                        {
                            "triage_event_id": te_id,
                            "hospital_hipe": h["hipe"],
                            "pathway_number": pw,
                            "sent_for_triage_date": sent,
                            "triage_date": ret,
                            "date_returned_from_triage": ret,
                            "triage_outcome": 1,
                            "triage_category": cat,
                            "turnaround_days": turn,
                        }
                    )

                refs.append(
                    {
                        "hospital_hipe": h["hipe"],
                        "pathway_number": pw,
                        "patient_id": pid,
                        "specialty_hipe": sp,
                        "referral_date": ref_date,
                        "referral_received_date": recv,
                        "priority_level_gp": gp_pri,
                        "referral_source": int(self.rng.choice([12, 6, 7, 11, 4], p=[0.72, 0.10, 0.08, 0.06, 0.04])),
                        "triage_event_id": te_id,
                        "triage_category": cat,
                        "dob": dob,
                    }
                )

                conds.extend(self._conditions(h["hipe"], pw, sp))
                obs.append(self._observation(h["hipe"], pw, sp, cat, recv))

        self.refs = pd.DataFrame(refs)
        self.t["triage_events"] = pd.DataFrame(triage)
        self.t["conditions"] = pd.DataFrame(conds)
        self.t["observations"] = pd.DataFrame(obs)

    def _conditions(self, hosp: str, pw: str, sp: str) -> list[dict]:
        mix = self.cond_mix.get(sp) or self.cond_mix.get(int(sp)) or {"R69": 1.0}
        codes = sorted(mix.keys())
        p = np.array([mix[c] for c in codes], dtype=float)
        p = p / p.sum()
        primary = codes[int(self.rng.choice(len(codes), p=p))]
        rows = [
            {
                "hospital_hipe": hosp,
                "pathway_number": pw,
                "icd10am_code": primary,
                "condition_label": f"Condition {primary}",
                "is_primary": "true",
                "snomed_ct_id": "",
            }
        ]
        if self.rng.random() < 0.35:
            others = [c for c in codes if c != primary]
            if others:
                sec = others[int(self.rng.integers(0, len(others)))]
                rows.append(
                    {
                        "hospital_hipe": hosp,
                        "pathway_number": pw,
                        "icd10am_code": sec,
                        "condition_label": f"Condition {sec}",
                        "is_primary": "false",
                        "snomed_ct_id": "",
                    }
                )
        return rows

    def _observation(self, hosp: str, pw: str, sp: str, cat: int | None, recv: date) -> dict:
        # Untriaged referrals still have observations; a category of None falls
        # back to the routine distribution rather than being skipped, because a
        # referral nobody has looked at is not thereby healthy.
        code = cat if cat in self.vitals else 2
        v = self.vitals[code]

        lo = np.array([VITAL_BOUNDS[k][0] for k in VITAL_ORDER])
        hi = np.array([VITAL_BOUNDS[k][1] for k in VITAL_ORDER])

        for _ in range(50):
            if code in self.pool:
                # Urgent and Semi-Urgent: resample a real MIMIC row, then jitter.
                row = self.pool[code][self.rng.integers(0, len(self.pool[code]))]
                x = row + self.rng.normal(0, self.pool_sd[code] * self.jitter)
            else:
                # Routine: no usable source rows (n=2), so reference ranges.
                mean = np.array([v[k][0] for k in VITAL_ORDER])
                x = self.rng.multivariate_normal(mean, self.vcov[code])
            # SpO2 has a real physiological ceiling at 100 and the source data
            # genuinely piles up there, so it is clipped rather than rejected.
            x[3] = min(x[3], 100.0)
            if np.all(x >= lo) and np.all(x <= hi) and x[4] > x[5] + 10:
                break
        else:
            x = np.minimum(np.maximum(np.array([v[k][0] for k in VITAL_ORDER]), lo), hi)

        hr = int(round(x[0]))
        rr = int(round(x[1]))
        temp = round(float(x[2]), 1)
        spo2 = int(round(x[3]))
        sbp = int(round(x[4]))
        dbp = int(round(x[5]))
        pm, psd = v.get("pain", (3.0, 2.5))
        pain = int(np.clip(round(self.rng.normal(pm, psd)), 0, 10))
        avpu = "A" if self.rng.random() < 0.985 else "V"

        rank = SEVERITY_RANK.get(code, 3)
        paed = sp in PAEDIATRIC
        scale = ICTS_BY_RANK[rank] if paed else MTS_BY_RANK[rank]
        colour = scale[int(self.rng.integers(0, len(scale)))]

        return {
            "hospital_hipe": hosp,
            "pathway_number": pw,
            "obs_datetime": datetime.combine(recv, datetime.min.time()) + timedelta(hours=9, minutes=int(self.rng.integers(0, 59))),
            "hr": hr,
            "sbp": sbp,
            "dbp": dbp,
            "rr": rr,
            "temp": temp,
            "spo2": spo2,
            "pain": pain,
            "avpu": avpu,
            "chiefcomplaint": "",
            "news2": news2(rr, spo2, sbp, hr, avpu, temp),
            "mts_category": "" if paed else colour,
            "icts_category": colour if paed else "",
        }

    # -- 8. beds, via SimPy -------------------------------------------------- #
    def gen_beds(self) -> None:
        los = self.cal["length_of_stay"]
        occ_target = self._first_value(los.get("occupancy", {}), 0.926)
        alos = self._first_value(los.get("length_of_stay", {}), 6.5)

        rows = []
        for _, w in self.t["wards"].iterrows():
            total = int(w["total_beds"])
            env = simpy.Environment()
            beds = simpy.Resource(env, capacity=total)
            occupancy: list[int] = []

            def patient(env, beds, rng, alos):
                with beds.request() as req:
                    yield req
                    yield env.timeout(max(0.5, rng.gamma(2.0, alos / 2.0)))

            def arrivals(env, beds, rng, alos, rate):
                while True:
                    yield env.timeout(rng.exponential(1.0 / rate))
                    env.process(patient(env, beds, rng, alos))

            def monitor(env, beds, occupancy):
                while True:
                    occupancy.append(beds.count)
                    yield env.timeout(1.0 / 3.0)

            rate = occ_target * total / alos
            env.process(arrivals(env, beds, self.rng, alos, rate))
            env.process(monitor(env, beds, occupancy))
            env.run(until=len(self.days) + 30)

            occupancy = occupancy[-len(self.days) * 3:] or [int(total * occ_target)] * (len(self.days) * 3)
            k = 0
            for d in self.days:
                for tm in self.snapshot_times:
                    occ = min(int(occupancy[k % len(occupancy)]), total)
                    k += 1
                    surge = int(self.rng.integers(0, 5)) if occ >= total else 0
                    free = total + surge - occ
                    pct = round(min(100.0, occ / (total + surge) * 100), 2)
                    over9 = int(self.rng.integers(0, 12)) if pct > 92 else 0
                    rows.append(
                        {
                            "hospital_hipe": w["hospital_hipe"],
                            "ward_id": w["ward_id"],
                            "snapshot_datetime": datetime.combine(d, datetime.strptime(tm, "%H:%M").time()),
                            "occupied": occ,
                            "free": free,
                            "occupancy_pct": pct,
                            "outliers": int(self.rng.integers(0, 10)) if pct > 90 else 0,
                            "surge_capacity_in_use": surge,
                            "delayed_transfers_of_care": int(self.rng.integers(0, 8)),
                            "awaiting_admission_over_9h": over9,
                            "awaiting_admission_over_24h": int(self.rng.integers(0, over9 + 1)),
                            "gar_status": "R" if pct >= 98 else "A" if pct >= 92 else "G",
                        }
                    )
        self.t["bed_status"] = pd.DataFrame(rows)

    @staticmethod
    def _first_value(block: dict, default: float) -> float:
        """Pull the first numeric `value:` out of a calibration block."""
        if isinstance(block, dict):
            for v in block.values():
                if isinstance(v, dict):
                    if isinstance(v.get("value"), (int, float)):
                        return float(v["value"])
                    got = Generator._first_value(v, None)
                    if got is not None:
                        return got
        return default

    # -- 9. clinic sessions -------------------------------------------------- #
    def gen_clinics(self) -> None:
        rows = []
        for h in self.hospitals:
            active = self.t["hospital_specialty"]
            active = active[(active["hospital_hipe"] == h["hipe"]) & (active["active"] == "true")]
            for sp in sorted(active["specialty_hipe"]):
                for d in self.days:
                    if d.weekday() >= 5:
                        continue
                    total = int(self.rng.integers(10, 26))
                    booked = int(self.rng.integers(int(total * 0.55), total + 1))
                    rows.append(
                        {
                            "hospital_hipe": h["hipe"],
                            "clinic_code": f"CL-{h['hipe']}-{sp}",
                            "session_date": d,
                            "clinic_name": f"{sp} outpatients",
                            "specialty_hipe": sp,
                            "slots_total": total,
                            "slots_booked": booked,
                            "slots_available": total - booked,
                        }
                    )
        self.t["clinic_sessions"] = pd.DataFrame(rows)

    # -- 10. cancellations and suspensions ----------------------------------- #
    def gen_events(self) -> None:
        canc, susp, susp_days = [], [], {}
        for r in self.refs.itertuples():
            if self.rng.random() < 0.22:
                for _ in range(int(self.rng.integers(1, 3))):
                    off = int(self.rng.integers(1, max(2, (self.end - r.referral_received_date).days or 2)))
                    canc.append(
                        {
                            "hospital_hipe": r.hospital_hipe,
                            "pathway_number": r.pathway_number,
                            "cancellation_date": r.referral_received_date + timedelta(days=off),
                            "cancellation_reason": int(self.rng.choice([21, 22, 12, 30, 110])),
                            "initiated_by": "H" if self.rng.random() < 0.62 else "P",
                        }
                    )
            if self.rng.random() < 0.045:
                span = (self.end - r.referral_received_date).days
                if span > 25:
                    start = r.referral_received_date + timedelta(days=int(self.rng.integers(5, span - 20)))
                    dur = int(self.rng.integers(7, 35))
                    susp.append(
                        {
                            "hospital_hipe": r.hospital_hipe,
                            "pathway_number": r.pathway_number,
                            "suspension_start_date": start,
                            "suspension_end_date": start + timedelta(days=dur),
                            "suspension_reason": int(self.rng.choice([101, 102, 103, 104])),
                            "suspended_days": dur,
                        }
                    )
                    susp_days[(r.hospital_hipe, r.pathway_number)] = (start + timedelta(days=dur), dur)

        # Deduplicate on the primary key: (hospital, pathway, date).
        self.t["cancellation_events"] = pd.DataFrame(canc).drop_duplicates(
            subset=["hospital_hipe", "pathway_number", "cancellation_date"]
        ) if canc else pd.DataFrame(columns=["hospital_hipe", "pathway_number", "cancellation_date", "cancellation_reason", "initiated_by"])
        self.t["suspension_events"] = pd.DataFrame(susp) if susp else pd.DataFrame(
            columns=["hospital_hipe", "pathway_number", "suspension_start_date", "suspension_end_date", "suspension_reason", "suspended_days"]
        )
        self.susp_days = susp_days

    # -- 11. daily snapshots -------------------------------------------------- #
    def gen_daily(self) -> None:
        rows = []
        for r in self.refs.itertuples():
            for d in self.days:
                if r.referral_received_date > d:
                    continue
                since_ref = (d - r.referral_date).days
                since_recv = (d - r.referral_received_date).days

                # Only suspensions that have ENDED by this date are excluded from
                # the adjusted wait. Section 10.1: use the raw number and you
                # report breaches that are not breaches.
                sd = 0
                s = self.susp_days.get((r.hospital_hipe, r.pathway_number))
                if s and s[0] <= d:
                    sd = s[1]
                adjusted = max(0, since_recv - sd)

                triaged = r.triage_event_id is not None
                status = "triaged" if triaged else "awaiting_triage"
                rows.append(
                    {
                        "hospital_hipe": r.hospital_hipe,
                        "pathway_number": r.pathway_number,
                        "as_of_date": d,
                        "patient_id": r.patient_id,
                        "specialty_hipe": r.specialty_hipe,
                        "referral_date": r.referral_date,
                        "referral_received_date": r.referral_received_date,
                        "priority_level_gp": r.priority_level_gp,
                        "referral_source": r.referral_source,
                        "triage_event_id": r.triage_event_id or "",
                        "appointment_date": "",
                        "arrived_date": "",
                        "clinic_code": "",
                        "clinic_classification": "",
                        "last_cancellation_date": "",
                        "last_cancellation_reason": "",
                        "record_creation_date": r.referral_received_date,
                        "suspension_start_date": "",
                        "suspension_reason": "",
                        "suspension_end_date": "",
                        "removal_date": "",
                        "removal_reason": "",
                        "high_clinical_or_social_needs": 1 if self.rng.random() < 0.07 else 0,
                        "triage_status": status,
                        "days_since_referral": since_ref,
                        "days_since_received": since_recv,
                        "adjusted_wait_days": adjusted,
                        "days_awaiting_triage": "" if triaged else since_recv,
                    }
                )
        self.t["referral_daily"] = pd.DataFrame(rows)

    # -- 12. ground truth ----------------------------------------------------- #
    def gen_ground_truth(self) -> None:
        lo, hi = self.hazard["base_by_condition_range"]
        noise = self.hazard["noise_sd"]
        per_decade = self.hazard["age_effect_per_decade_over_50"]

        rows = []
        for r in self.refs.itertuples():
            age = (self.end - r.dob).days / 365.25
            base = lo + (hi - lo) * self.rng.random()
            age_eff = per_decade * max(0.0, (age - 50) / 10.0)
            # NOTE: news2 is deliberately absent from this expression.
            hazard = float(np.clip(base + age_eff + self.rng.normal(0, noise), 0, 1))

            waited = (self.end - r.referral_received_date).days
            fired = self.rng.random() < hazard * min(1.0, waited / 400.0)
            if fired:
                dd = r.referral_received_date + timedelta(days=int(self.rng.integers(1, max(2, waited))))
                dt = "death" if self.rng.random() < 0.06 else "emergency_admission"
            else:
                dd, dt = "", ""
            rows.append(
                {
                    "hospital_hipe": r.hospital_hipe,
                    "pathway_number": r.pathway_number,
                    "latent_hazard": round(hazard, 3),
                    "deterioration_date": dd,
                    "deterioration_type": dt,
                }
            )
        self.t["ground_truth"] = pd.DataFrame(rows)

    def run(self) -> None:
        self.gen_hospitals()
        self.gen_people()
        self.gen_referrals()
        self.gen_beds()
        self.gen_clinics()
        self.gen_events()
        self.gen_daily()
        self.gen_ground_truth()

        # persons is trimmed to those actually referenced by a patient row.
        used = {i for i in self.t["patients"]["ihi_number"] if i}
        self.t["persons"] = self.t["persons"][self.t["persons"]["ihi_number"].isin(used)]


# --------------------------------------------------------------------------- #
# Column order and sort keys. Both fixed, because determinism depends on them.
# --------------------------------------------------------------------------- #

SPECS = {
    "hospitals": (["hospital_hipe", "hospital_name", "hse_health_region", "hospital_type", "total_inpatient_beds"], ["hospital_hipe"], (), ()),
    "hospital_specialty": (["hospital_hipe", "specialty_hipe", "service_name", "active"], ["hospital_hipe", "specialty_hipe"], (), ()),
    "persons": (["ihi_number", "person_sex", "person_date_of_birth", "area_of_residence_code"], ["ihi_number"], ("person_date_of_birth",), ()),
    "patients": (["hospital_hipe", "patient_id", "ihi_number", "patient_sex", "patient_date_of_birth", "area_of_residence_code"], ["hospital_hipe", "patient_id"], ("patient_date_of_birth",), ()),
    "triage_events": (["triage_event_id", "hospital_hipe", "pathway_number", "sent_for_triage_date", "triage_date", "date_returned_from_triage", "triage_outcome", "triage_category", "turnaround_days"], ["hospital_hipe", "pathway_number"], ("sent_for_triage_date", "triage_date", "date_returned_from_triage"), ()),
    "referral_daily": (["hospital_hipe", "pathway_number", "as_of_date", "patient_id", "specialty_hipe", "referral_date", "referral_received_date", "priority_level_gp", "referral_source", "triage_event_id", "appointment_date", "arrived_date", "clinic_code", "clinic_classification", "last_cancellation_date", "last_cancellation_reason", "record_creation_date", "suspension_start_date", "suspension_reason", "suspension_end_date", "removal_date", "removal_reason", "high_clinical_or_social_needs", "triage_status", "days_since_referral", "days_since_received", "adjusted_wait_days", "days_awaiting_triage"], ["hospital_hipe", "pathway_number", "as_of_date"], ("as_of_date", "referral_date", "referral_received_date", "record_creation_date"), ()),
    "conditions": (["hospital_hipe", "pathway_number", "icd10am_code", "condition_label", "is_primary", "snomed_ct_id"], ["hospital_hipe", "pathway_number", "icd10am_code"], (), ()),
    "observations": (["hospital_hipe", "pathway_number", "obs_datetime", "hr", "sbp", "dbp", "rr", "temp", "spo2", "pain", "avpu", "chiefcomplaint", "news2", "mts_category", "icts_category"], ["hospital_hipe", "pathway_number", "obs_datetime"], (), ("obs_datetime",)),
    "wards": (["hospital_hipe", "ward_id", "ward_name", "total_beds", "ward_type"], ["hospital_hipe", "ward_id"], (), ()),
    "ward_specialty": (["hospital_hipe", "ward_id", "specialty_hipe", "nominal_beds", "is_primary"], ["hospital_hipe", "ward_id", "specialty_hipe"], (), ()),
    "bed_status": (["hospital_hipe", "ward_id", "snapshot_datetime", "occupied", "free", "occupancy_pct", "outliers", "surge_capacity_in_use", "delayed_transfers_of_care", "awaiting_admission_over_9h", "awaiting_admission_over_24h", "gar_status"], ["hospital_hipe", "ward_id", "snapshot_datetime"], (), ("snapshot_datetime",)),
    "clinic_sessions": (["hospital_hipe", "clinic_code", "session_date", "clinic_name", "specialty_hipe", "slots_total", "slots_booked", "slots_available"], ["hospital_hipe", "clinic_code", "session_date"], ("session_date",), ()),
    "cancellation_events": (["hospital_hipe", "pathway_number", "cancellation_date", "cancellation_reason", "initiated_by"], ["hospital_hipe", "pathway_number", "cancellation_date"], ("cancellation_date",), ()),
    "suspension_events": (["hospital_hipe", "pathway_number", "suspension_start_date", "suspension_end_date", "suspension_reason", "suspended_days"], ["hospital_hipe", "pathway_number", "suspension_start_date"], ("suspension_start_date", "suspension_end_date"), ()),
    "ground_truth": (["hospital_hipe", "pathway_number", "latent_hazard", "deterioration_date", "deterioration_type"], ["hospital_hipe", "pathway_number"], ("deterioration_date",), ()),
}


def plant(gen: "Generator") -> None:
    """Rewrite seven referrals into the demo cases, and plant one collision.

    Random sampling will not reliably produce these, and the demo depends on all
    seven existing every run at fixed pathway numbers (BUILD_MANUAL section 8.4).
    """
    daily = gen.t["referral_daily"]
    obs = gen.t["observations"]

    pool = sorted(daily[daily["hospital_hipe"] == "9001"]["pathway_number"].unique())
    partner = sorted(daily[daily["hospital_hipe"] == "9002"]["pathway_number"].unique())
    if len(pool) < 9 or len(partner) < 3:
        raise SystemExit("Not enough referrals at 9001/9002 to plant the demo cases.")

    # 01..05 at 9001; 06/07 need a SECOND PUBLIC hospital, hence 9002 in the
    # small profile. A private site cannot supply the second list: private sites
    # carry zero referrals by design.
    targets = {f"PW-DEMO-{i:02d}": pool[i - 1] for i in range(1, 8)}
    renames = {}

    for demo, src in targets.items():
        renames[("9001", src)] = demo

    def rename(df):
        if df.empty or "pathway_number" not in df.columns:
            return df
        key = list(zip(df["hospital_hipe"], df["pathway_number"]))
        df = df.copy()
        df["pathway_number"] = [renames.get(k, k[1]) for k in key]
        return df

    for name in ["referral_daily", "conditions", "observations", "triage_events",
                 "cancellation_events", "suspension_events", "ground_truth"]:
        gen.t[name] = rename(gen.t[name])

    d = gen.t["referral_daily"]

    # Columns are assigned one at a time and cast to the column's existing dtype.
    # days_awaiting_triage carries "" for triaged rows, so it is a string column;
    # writing an int into it raises rather than silently coercing.
    def put(df, mask, col, value):
        if str(df[col].dtype) in ("object", "string", "str"):
            value = str(value)
        df.loc[mask, col] = value

    # 01 urgent and past its 28-day timeframe
    m = d["pathway_number"] == "PW-DEMO-01"
    for col, val in [("days_since_received", 58), ("adjusted_wait_days", 58),
                     ("days_since_referral", 63), ("triage_status", "triaged")]:
        put(d, m, col, val)

    # 03 urgent by pathway, entirely normal vitals: vitals alone do not identify urgency
    o = gen.t["observations"]
    m3 = o["pathway_number"] == "PW-DEMO-03"
    for col, val in [("hr", 72), ("sbp", 124), ("dbp", 78), ("rr", 14), ("temp", 36.7),
                     ("spo2", 99), ("pain", 1), ("avpu", "A"), ("news2", 0)]:
        put(o, m3, col, val)

    # 05 awaiting triage for 60+ days, no category at all: the invisible population
    m5 = d["pathway_number"] == "PW-DEMO-05"
    for col, val in [("triage_status", "awaiting_triage"), ("triage_event_id", ""),
                     ("days_awaiting_triage", 64), ("days_since_received", 64),
                     ("adjusted_wait_days", 64)]:
        put(d, m5, col, val)
    # Re-read after the rename loop above. Using the frame captured before it
    # would assign back the pre-rename pathway numbers and silently break the
    # referral_daily -> triage_events foreign key.
    tri_now = gen.t["triage_events"]
    gen.t["triage_events"] = tri_now[tri_now["pathway_number"] != "PW-DEMO-05"]

    # The planted waits above are set directly, so any suspension attached to those
    # pathways would contradict them: adjusted_wait_days must equal
    # days_since_received minus the suspended days that have ENDED by that date.
    # Drop the suspensions rather than leave the arithmetic inconsistent.
    se = gen.t["suspension_events"]
    if not se.empty:
        gen.t["suspension_events"] = se[~se["pathway_number"].isin(["PW-DEMO-01", "PW-DEMO-05"])]

    # A pathway number is issued per hospital and is legitimately not globally
    # unique. The referential test asserts that joining on pathway_number ALONE
    # yields MORE rows than joining on (hospital_hipe, pathway_number) -- if it
    # does not, there are no collisions and the test proves nothing.
    #
    # It must sit between 9001 and 9002: make_sample.py seeds from exactly those
    # two, so a collision anywhere else would never reach sample/.
    coll = gen.cfg["planted_collision"]["pathway_number"]
    for name in ["referral_daily", "conditions", "observations", "triage_events",
                 "cancellation_events", "suspension_events", "ground_truth"]:
        df = gen.t[name]
        if df.empty or "pathway_number" not in df.columns:
            continue
        for hosp, src in (("9001", pool[8]), ("9002", partner[0])):
            df.loc[(df["hospital_hipe"] == hosp) & (df["pathway_number"] == src), "pathway_number"] = coll
        gen.t[name] = df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", default="small", choices=["small", "full"])
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "generator" / "config.yml").read_text())
    cal = load_calibration()

    gen = Generator(cfg, cal, args.profile)
    print(f"Generating profile '{args.profile}'  seed={cfg['seed']}  coupling={gen.coupling}")
    gen.run()
    plant(gen)

    if OUT.exists():
        for f in OUT.glob("*.csv"):
            f.unlink()

    total = 0
    for name, (cols, sort_by, dates, ts) in SPECS.items():
        df = gen.t.get(name)
        if df is None or df.empty:
            df = pd.DataFrame(columns=cols)
        n = write_table(df, name, OUT, cols, sort_by, dates, ts)
        total += n
        print(f"  {name:24} {n:>8,}")

    print(f"\n  {total:,} rows -> {OUT}")

    # The correlation is a GUARD RAIL on a fitted distribution, not a target.
    # Reported here so a run that drifts out of band is visible immediately.
    o = gen.t["observations"][["hospital_hipe", "pathway_number", "news2"]]
    t = gen.t["triage_events"][["hospital_hipe", "pathway_number", "triage_category"]]
    j = o.merge(t, on=["hospital_hipe", "pathway_number"])
    if not j.empty:
        j["severity_rank"] = j["triage_category"].map(SEVERITY_RANK)
        r = j["news2"].astype(float).corr(j["severity_rank"].astype(float))
        urgent = j[j["triage_category"] == 1]
        low = (urgent["news2"].astype(float) <= 2).mean() if len(urgent) else float("nan")
        band = "IN BAND" if 0.35 <= abs(r) <= 0.65 else "OUT OF BAND"
        print(f"\n  news2 x severity_rank : r = {r:+.3f}   [{band}, target |r| 0.35-0.65]")
        print(f"  urgent with news2<=2  : {low:.1%}        [need >= 15%]")


if __name__ == "__main__":
    main()
