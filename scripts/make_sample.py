"""Derive sample/ from out/ by referential closure.

Why this is not a `head -n`.

Every child table -- conditions, observations, triage_events, cancellation_events,
suspension_events -- carries a foreign key to core.referrals. Take the first N rows
of each CSV and those foreign keys point at referrals that are not in the slice, so
`make load` dies on constraint violations. It dies AFTER the download, with an error
that points at Postgres rather than at the sampler.

So the sample is closed under the foreign-key graph: choose a set of referrals, then
take every child row belonging to exactly those referrals and every parent row they
require.

Read with dtype=str throughout. specialty_hipe '0601' is Paediatric ENT; letting
pandas infer the type turns it into 601 and the foreign key stops resolving.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "out"
DST = ROOT / "sample"

# How many ordinary referrals to take from each seeded hospital, on top of the
# planted cases. Sorted by pathway_number so the sample is reproducible.
N_PER_HOSPITAL = 300

# make_sample seeds from these two hospitals. Both are PUBLIC: PW-DEMO-06 and
# PW-DEMO-07 are the multi-list-across-two-hospitals cases, and the planted
# pathway-number collision lives between these two as well. A collision planted
# anywhere else would never reach sample/, and the referential test would pass
# while proving nothing on the profile everyone actually runs.
SEED_HOSPITALS = ["9001", "9002"]

KEY = ["hospital_hipe", "pathway_number"]

# Tables keyed by (hospital_hipe, pathway_number) -- filtered to the seed set.
CHILD_TABLES = [
    "referral_daily",
    "triage_events",
    "conditions",
    "observations",
    "cancellation_events",
    "suspension_events",
    "ground_truth",
]

# Tables keyed by hospital -- filtered to the hospitals present in the seed set.
CAPACITY_TABLES = [
    "hospitals",
    "hospital_specialty",
    "wards",
    "ward_specialty",
    "bed_status",
    "clinic_sessions",
]

# Dictionaries: taken whole. About 130 rows between them; slicing them would only
# punch foreign-key holes for no saving.
DICTIONARY_TABLES = ["ref_specialty", "ref_codes", "ref_rules"]


def read(name: str) -> pd.DataFrame | None:
    path = SRC / f"{name}.csv"
    if not path.exists():
        return None
    # dtype=str is load-bearing, not a default. specialty_hipe '0601' is Paediatric
    # ENT; let pandas infer and it becomes the integer 601, the foreign key stops
    # resolving, and the sample fails to load. keep_default_na=False stops an empty
    # ihi_number becoming the string "nan".
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[])


def write(df: pd.DataFrame, name: str) -> int:
    DST.mkdir(parents=True, exist_ok=True)
    df.to_csv(DST / f"{name}.csv", index=False, lineterminator="\n")
    return len(df)


def main() -> None:
    if not SRC.is_dir():
        sys.exit(f"No generated data at {SRC}. Run `make generate PROFILE=full` first.")

    daily = read("referral_daily")
    if daily is None:
        sys.exit(f"Missing {SRC}/referral_daily.csv -- nothing to sample from.")

    # 1. Seed set -----------------------------------------------------------
    referrals = daily[KEY].drop_duplicates().sort_values(KEY).reset_index(drop=True)

    planted = referrals[referrals["pathway_number"].str.startswith(("PW-DEMO-", "PW-COLLIDE-"))]

    ordinary = []
    for hosp in SEED_HOSPITALS:
        rows = referrals[
            (referrals["hospital_hipe"] == hosp)
            & ~referrals["pathway_number"].str.startswith(("PW-DEMO-", "PW-COLLIDE-"))
        ].sort_values("pathway_number").head(N_PER_HOSPITAL)
        ordinary.append(rows)

    seed = pd.concat([planted, *ordinary]).drop_duplicates().sort_values(KEY)
    seed_pairs = set(map(tuple, seed[KEY].values))
    hospitals_present = sorted(seed["hospital_hipe"].unique())

    print(f"Seed set: {len(seed):,} referrals across hospitals {hospitals_present}")
    print(f"  planted cases : {len(planted):,}")
    print(f"  ordinary      : {len(seed) - len(planted):,}")

    missing_demo = {f"PW-DEMO-{i:02d}" for i in range(1, 8)} - set(planted["pathway_number"])
    if missing_demo:
        sys.exit(
            f"\nDemo cases missing from the generated data: {sorted(missing_demo)}\n"
            f"The sample cannot carry what the generator never produced."
        )

    def in_seed(df: pd.DataFrame) -> pd.DataFrame:
        pairs = list(zip(df["hospital_hipe"], df["pathway_number"]))
        return df[[p in seed_pairs for p in pairs]]

    counts: dict[str, int] = {}

    # 2. Children -----------------------------------------------------------
    for name in CHILD_TABLES:
        df = read(name)
        if df is None:
            print(f"  {name:24} {'—':>8}  (absent)")
            continue
        counts[name] = write(in_seed(df), name)

    # 3. Parents ------------------------------------------------------------
    daily_seeded = in_seed(daily)
    patient_pairs = set(zip(daily_seeded["hospital_hipe"], daily_seeded["patient_id"]))

    patients = read("patients")
    if patients is None:
        sys.exit("Missing patients.csv")
    keep = [
        (h, p) in patient_pairs
        for h, p in zip(patients["hospital_hipe"], patients["patient_id"])
    ]
    patients = patients[keep]
    counts["patients"] = write(patients, "patients")

    ihis = {i for i in patients["ihi_number"] if i}
    persons = read("persons")
    if persons is not None:
        counts["persons"] = write(persons[persons["ihi_number"].isin(ihis)], "persons")

    # 4. Capacity, for the hospitals present --------------------------------
    for name in CAPACITY_TABLES:
        df = read(name)
        if df is None:
            print(f"  {name:24} {'—':>8}  (absent)")
            continue
        counts[name] = write(df[df["hospital_hipe"].isin(hospitals_present)], name)

    # 5. Dictionaries, whole ------------------------------------------------
    for name in DICTIONARY_TABLES:
        df = read(name)
        if df is not None:
            counts[name] = write(df, name)

    print()
    for name, n in counts.items():
        print(f"  {name:24} {n:>8,}")

    src_bytes = sum(f.stat().st_size for f in SRC.glob("*.csv"))
    dst_bytes = sum(f.stat().st_size for f in DST.glob("*.csv"))
    print(
        f"\n  sample: {dst_bytes / 1e6:.2f} MB from {src_bytes / 1e6:.2f} MB "
        f"({dst_bytes / src_bytes * 100:.1f}%)"
    )


if __name__ == "__main__":
    main()
