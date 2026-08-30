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

> **Every record here is synthetic.** No real patient, clinician or hospital is
> represented. Hospital names are invented and their codes use a reserved range that
> matches no real facility.

A hospital outpatient waiting list: people waiting for a clinic appointment, what is
wrong with them, how urgent a clinician judged them, and how full the wards and clinics
are. It exists to answer one question: **among patients already marked equally urgent,
who should be seen next, and why?**

## What is in it

Six hospitals. Four public, which have waiting lists; two private, which have beds and
clinics but no queue of their own.

| | |
|---|---|
| **Referral** | One person waiting for one appointment. Identified by `hospital_hipe` + `pathway_number`. Numbers are only unique *within* a hospital. |
| **Triage category** | How urgent a clinician judged it: Urgent, Semi-Urgent or Routine. Assigned once, and nothing in the data reorders across categories. |
| **Timeframe** | How long that category should wait: 28 days if Urgent, 91 if Semi-Urgent. |
| **Wait** | Four different clocks, because they give different answers. `adjusted_wait_days` excludes time when care was bought privately and the clock paused. Use it for breach checks. |
| **Conditions and observations** | What is wrong with the patient, and their vital signs. |
| **Capacity** | Wards, bed occupancy three times a day, and clinic appointment slots. |

**Vitals do not tell you who is urgent.** Roughly two thirds of the urgent referrals here
have entirely unremarkable observations. A suspected melanoma is urgent because of the
referral pathway, not the physiology. That is measured from real triage data, not assumed.

`ground_truth.csv` is the **answer key**: which patients deteriorated while waiting. It is
held out and should never be loaded alongside the rest. Its risk model is synthetic and
unvalidated, and results depending on it must say so.

## The two folders

| | Size | Hospitals | Referrals |
|---|---|---|---|
| `sample/` | 1.3 MB | 2 | 609 |
| `full/` | 11 MB | 6 | 5,200 |

`sample/` is a real slice of `full/`, closed under its foreign keys: every table it
references, it contains. Use it to check a pipeline works; use `full/` for anything you
report.

Pin a **tag**, never a branch. `v1.1` is current.

## More

The repository holds the generator, the schema, the tests and the full specification:
what every column means, where every number came from, and what the real data disproved
along the way.

**[github.com/NonsoCynthia/Tus-Aite-TechIreland-Challenge](https://github.com/NonsoCynthia/Tus-Aite-TechIreland-Challenge)**
Branch `dataset_branch`. The repository is private; ask the team for access.

Start with `README.md` there, then `docs/GETTING_THE_DATA.md` to load it and
`DATASET_README.md` for the column-by-column specification.
"""


def main() -> None:
    # The card describes the data; it changes more often than the data does, and
    # re-uploading 11 MB to fix a sentence is wasteful.
    card_only = "--card-only" in sys.argv

    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN is not set. Supply it at run time; it is never written to disk.")

    cfg = yaml.safe_load((ROOT / "versions.yml").read_text())
    repo, tag = cfg["hf_repo"], cfg["hf_revision"]

    for d in (() if card_only else (FULL, SAMPLE)):
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

    for src, dest in (() if card_only else ((FULL, "full"), (SAMPLE, "sample"))):
        n = len(list(src.glob("*.csv")))
        mb = sum(f.stat().st_size for f in src.glob("*.csv")) / 1e6
        api.upload_folder(folder_path=str(src), path_in_repo=dest, repo_id=repo,
                          repo_type="dataset", allow_patterns=["*.csv"])
        print(f"  uploaded {dest}/  {n} files, {mb:.2f} MB")

    if card_only:
        print(f"\n  card updated on {repo}; data and tags untouched")
        return

    try:
        api.create_tag(repo_id=repo, tag=tag, repo_type="dataset")
        print(f"  tagged {tag}")
    except Exception as exc:
        print(f"  tag {tag} not created: {type(exc).__name__} -- {exc}")

    print(f"\n  https://huggingface.co/datasets/{repo}")
    print(f"  pinned in versions.yml as {repo} @ {tag}")


if __name__ == "__main__":
    main()
