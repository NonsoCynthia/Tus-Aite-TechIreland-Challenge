"""Publish the dataset to Hugging Face and tag it.

Only after `make test` passes. Private unless the operator says otherwise. No licence
field is declared; that is not this script's decision to make.

The tag is what everyone pins to. Without it there is no versioning, only a moving
target.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "out"
SAMPLE = ROOT / "sample"

CARD = """---
language: [en]
tags: [synthetic, healthcare, ireland, waiting-list, triage, referral-prioritisation]
pretty_name: Synthetic Irish Hospital Referral Prioritisation Dataset
size_categories: [10K<n<100K]
---

# Synthetic Irish Hospital Referral Prioritisation Dataset

> **Every record in this dataset is synthetic. No real patient, clinician, or hospital
> is represented. Hospital names are invented and hospital codes use a reserved range
> that does not correspond to any real facility.**

A synthetic outpatient waiting list that behaves like the Irish one. It exists to
answer a single question: **among patients a clinician has already marked equally
urgent, who should be seen next, and why?**

## Why it exists

The NTPF Outpatient Waiting List Minimum Data Set defines 74 fields, and not one of
them says what is wrong with the patient. No diagnosis, no symptoms, no observations.
So inside a priority category the only ordering signal left is how long someone has
waited. This dataset adds the clinical evidence layer the national record never
captured, and keeps every ranking traceable to the rows it was based on.

## What is here

| Directory | Size | Contents |
|---|---|---|
| `full/` | ~11 MB | The whole dataset, 17 input tables plus the held-out answer key |
| `sample/` | ~1.3 MB | A referentially-closed slice for pipeline checks |

**`sample/` is not the first N rows.** Every child table carries a foreign key to the
referrals table, so a row-truncated sample fails to load. It is built by choosing a set
of referrals and then taking every child row belonging to them and every parent they
require, so every foreign key resolves inside the slice. It contains all seven planted
demo cases.

`ground_truth.csv` is the answer key and is **never loaded into the database** in
normal use. If a ranking agent could read it, it would rank perfectly by looking up the
answer.

## Grounding

| Source | Used for | Granularity |
|---|---|---|
| NTPF Outpatient MDS v2.6 | Field names, code values, rules | specification |
| NTPF open data | Specialty mix, wait-band distribution | aggregate |
| MIMIC-IV-ED Demo (ODbL) | Vitals distributions by triage acuity | row-level, n=207 |
| ESRI RS213 | Bed occupancy, length of stay | aggregate |

No Irish source publishes patient-level waiting list data, so there are no Irish rows
to copy, only Irish shapes to match. Every calibration parameter is labelled `fitted`,
`modelled` or `assumed` in the repository: 90, 16 and 3 respectively.

## Known limitations

- The `latent_hazard` model in `ground_truth` is **unvalidated**. No source says a
  patient with a given condition has any particular chance of deteriorating. Its large
  noise term is deliberate and must not be reduced.
- Condition mix within specialty is **assumed**. The ICD-10-AM codes are real; the
  shares are not.
- Routine-category vitals come from physiological reference ranges, not from data:
  MIMIC's demo subset contains only two ESI 4-5 stays.

## Changelog

### v1.1
Fixes two planted demo referrals whose wait clocks contradicted their own dates.
`PW-DEMO-01` recorded 58 days since receipt against a received date equal to the snapshot
date; `PW-DEMO-05` recorded 64 days of waiting on a letter written 12 days earlier. The
generator now sets the dates and derives the counts from them, and a new schema constraint
makes the combination unloadable.

**Requires schema 008.** Data `v1.0` will not load against schema 008 and `v1.1` will not
load against 007 in a way that is checked. Pin both together.

### v1.0
First release.

## Full specification

See `DATASET_README.md` in the source repository, plus
`docs/HOW_THE_DATA_WAS_MADE.md` for what the calibration measured, including three
assumptions in the original build specification that the data falsified.
"""


def main() -> None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN is not set. Supply it at run time; it is never written to disk.")

    cfg = yaml.safe_load((ROOT / "versions.yml").read_text())
    repo, tag = cfg["hf_repo"], cfg["hf_revision"]

    for d in (FULL, SAMPLE):
        if not d.is_dir() or not list(d.glob("*.csv")):
            sys.exit(f"{d} has no CSVs. Run `make generate PROFILE=full` and "
                     f"`python scripts/make_sample.py` first.")

    api = HfApi(token=token)
    print(f"Creating {repo} (private, dataset)")
    api.create_repo(repo_id=repo, repo_type="dataset", private=True, exist_ok=True)

    (ROOT / "_card.md").write_text(CARD)
    try:
        api.upload_file(path_or_fileobj=str(ROOT / "_card.md"), path_in_repo="README.md",
                        repo_id=repo, repo_type="dataset")
    finally:
        (ROOT / "_card.md").unlink(missing_ok=True)
    print("  uploaded dataset card")

    for src, dest in ((FULL, "full"), (SAMPLE, "sample")):
        n = len(list(src.glob("*.csv")))
        mb = sum(f.stat().st_size for f in src.glob("*.csv")) / 1e6
        api.upload_folder(folder_path=str(src), path_in_repo=dest, repo_id=repo,
                          repo_type="dataset", allow_patterns=["*.csv"])
        print(f"  uploaded {dest}/  {n} files, {mb:.2f} MB")

    try:
        api.create_tag(repo_id=repo, tag=tag, repo_type="dataset")
        print(f"  tagged {tag}")
    except Exception as exc:
        print(f"  tag {tag} not created: {type(exc).__name__} -- {exc}")

    print(f"\n  https://huggingface.co/datasets/{repo}")
    print(f"  pinned in versions.yml as {repo} @ {tag}")


if __name__ == "__main__":
    main()
