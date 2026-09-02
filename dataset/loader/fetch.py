"""Pull the pinned dataset revision from Hugging Face into data/.

Two profiles:
    sample  a referentially-closed slice, roughly 1.3 MB     (the default)
    full    the whole dataset, roughly 11 MB

`allow_patterns` is what makes the sample cheap: only files under the chosen
profile's directory are transferred. Asking for 'sample' never downloads the
full data at all, which is the point of the split -- a pipeline check should not
wait on eleven megabytes.

The revision is a TAG, never a branch. Nothing here ever fetches "latest".
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml
from huggingface_hub import snapshot_download
from huggingface_hub.errors import GatedRepoError, RepositoryNotFoundError

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--profile",
        default=None,
        choices=["sample", "full"],
        help="which slice to download; defaults to versions.yml default_profile",
    )
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "versions.yml").read_text())
    profile = args.profile or cfg.get("default_profile", "sample")
    repo = cfg["hf_repo"]
    revision = cfg["hf_revision"]

    if revision in {"main", "master", "latest", None, ""}:
        sys.exit(
            f"versions.yml pins hf_revision={revision!r}. That is a moving target.\n"
            f"Pin a tag. Without one there is no versioning, only whatever happens to be there today."
        )

    token = os.environ.get("HF_TOKEN") or None

    print(f"Fetching {repo} @ {revision}  (profile: {profile})")
    print(f"  only files matching {profile}/* are transferred")

    try:
        snapshot_download(
            repo_id=repo,
            revision=revision,
            repo_type="dataset",
            allow_patterns=[f"{profile}/*"],
            local_dir=str(DATA),
            token=token,
        )
    except (GatedRepoError, RepositoryNotFoundError) as exc:
        # Do not fall back to generating locally. Silently diverging data is the
        # exact failure this architecture exists to prevent.
        sys.exit(
            f"\nCould not read {repo} @ {revision}.\n"
            f"  {type(exc).__name__}: {exc}\n\n"
            f"If the dataset is private, set HF_TOKEN in your .env and re-run.\n"
            f"Not falling back to local generation -- data that quietly differs between\n"
            f"team members is worse than no data."
        )

    dest = DATA / profile
    if not dest.is_dir():
        sys.exit(f"Download reported success but {dest} does not exist.")

    files = sorted(dest.glob("*.csv"))
    total = sum(f.stat().st_size for f in files)
    print(f"\n  {len(files)} files, {total / 1e6:.2f} MB into {dest}")
    for f in files:
        print(f"    {f.name:28} {f.stat().st_size / 1e3:>9,.1f} kB")


if __name__ == "__main__":
    main()
