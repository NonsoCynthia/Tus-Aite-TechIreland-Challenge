"""Re-derives the calibration from its sources and checks it still matches.

Reads:  generator/calibration/*.yml (the committed, fitted parameters) and
        re-downloads the MIMIC-IV-ED Demo triage table to compare against.
Writes: nothing. This deliberately does not overwrite the calibration.

Why verify rather than regenerate. The committed calibration determines the
generated data, and the generated data is published on Hugging Face under a tag
that versions.yml pins. Silently re-fitting would change the data while every pin
kept claiming otherwise. So this reports agreement or disagreement and leaves the
files alone; changing them is a deliberate act with a version bump attached.

`make calibrate`.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
CAL = ROOT / "generator" / "calibration"

# How far a re-fitted figure may drift before it is reported. Statistics are
# recomputed from the same rows, so agreement should be exact; the tolerance only
# absorbs floating-point representation, not genuine change.
TOLERANCE = 0.01

MIMIC_URL = "https://physionet.org/files/mimic-iv-ed-demo/2.2/ed/triage.csv.gz"
VITALS = ["heartrate", "resprate", "temperature_c", "o2sat", "sbp", "dbp"]


def news2(resp_rate, oxygen_sat, systolic_bp, heart_rate, consciousness, temp_celsius) -> int:
    """National Early Warning Score 2, scale 1, patient breathing air."""
    score = 0
    score += 3 if resp_rate <= 8 else 1 if resp_rate <= 11 else 0 if resp_rate <= 20 else 2 if resp_rate <= 24 else 3
    score += 3 if oxygen_sat <= 91 else 2 if oxygen_sat <= 93 else 1 if oxygen_sat <= 95 else 0
    score += 3 if systolic_bp <= 90 else 2 if systolic_bp <= 100 else 1 if systolic_bp <= 110 else 0 if systolic_bp <= 219 else 3
    score += 3 if heart_rate <= 40 else 1 if heart_rate <= 50 else 0 if heart_rate <= 90 else 1 if heart_rate <= 110 else 2 if heart_rate <= 130 else 3
    score += 0 if consciousness == "A" else 3
    score += 3 if temp_celsius <= 35.0 else 1 if temp_celsius <= 36.0 else 0 if temp_celsius <= 38.0 else 1 if temp_celsius <= 39.0 else 2
    return min(score, 20)


def area_under_curve(positive, negative) -> float:
    """AUC via the Mann-Whitney U statistic. Average ranks handle ties."""
    positive, negative = np.asarray(positive, float), np.asarray(negative, float)
    ranks = pd.Series(np.concatenate([positive, negative])).rank().values
    n_pos, n_neg = len(positive), len(negative)
    return (ranks[:n_pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def screened_mimic(raw: pd.DataFrame) -> pd.DataFrame:
    """Rows with an acuity, temperature converted to Celsius. No rows dropped.

    Screening happens PER COLUMN in usable_values(), not here, because that is what
    the committed calibration did. vitals_by_category.yml records outliers_dropped
    per vital: 1 for Urgent dbp, 0 for Urgent heartrate. The 879 mmHg diastolic row
    is excluded from the dbp mean and still counted in every other column's.
    Dropping the whole row would silently shrink eleven other means.
    """
    df = raw[raw["acuity"].notna()].copy()
    df["temperature_c"] = (df["temperature"] - 32) * 5 / 9
    return df


def usable_values(df: pd.DataFrame, vital: str) -> pd.Series:
    """One column's values, with nulls and that column's own outliers removed.

    The two documented exclusions, each scoped to the column it affects:
      dbp           -- one row records 879 mmHg against an sbp of 111
      temperature_c -- one row holds a Celsius reading in the Fahrenheit column
    Both are recorded under source_data_quality with the effect of keeping them.
    """
    if vital == "dbp":
        keep = df["dbp"].between(20, 200) & (df["dbp"] <= df["sbp"])
        return df.loc[keep, "dbp"].dropna()
    if vital == "temperature_c":
        return df.loc[df["temperature_c"].between(30, 43), "temperature_c"].dropna()
    return df[vital].dropna()


def main() -> None:
    committed = yaml.safe_load((CAL / "vitals_by_category.yml").read_text())
    provenance = committed["provenance"]

    print(f"Re-downloading {provenance['source']}")
    try:
        payload = urllib.request.urlopen(MIMIC_URL, timeout=60).read()
    except Exception as exc:
        sys.exit(f"Could not reach {MIMIC_URL}\n  {type(exc).__name__}: {exc}")

    digest = hashlib.sha256(payload).hexdigest()
    recorded = provenance.get("sha256_gz")
    print(f"  sha256   {digest[:16]}...  recorded {str(recorded)[:16]}...  "
          f"{'MATCH' if digest == recorded else 'DIFFERS -- the source has changed upstream'}")

    raw = pd.read_csv(io.BytesIO(gzip.decompress(payload)))
    df = screened_mimic(raw)
    df["category"] = np.where(df["acuity"].isin([1, 2]), "Urgent",
                     np.where(df["acuity"] == 3, "Semi-Urgent", "Routine"))

    print("\nComparing re-fitted statistics against the committed calibration:")
    drifted = []
    for label in ["Urgent", "Semi-Urgent"]:
        rows = df[df["category"] == label]
        block = committed["categories"][label]["vitals"]
        for vital in VITALS:
            if vital not in block or "mean" not in block[vital]:
                continue
            column = usable_values(rows, vital)    # pairwise, per-column screening
            refitted = column.mean()
            on_file = block[vital]["mean"]
            gap = abs(refitted - on_file)
            n_on_file = block[vital].get("n")
            n_matches = n_on_file is None or len(column) == n_on_file
            if gap > TOLERANCE or not n_matches:
                drifted.append(f"{label}.{vital}: committed {on_file} (n={n_on_file}), "
                               f"refitted {refitted:.4f} (n={len(column)})")
            print(f"  {label:12} {vital:15} committed {on_file:>9.4f} n={str(n_on_file):>4}  "
                  f"refitted {refitted:>9.4f} n={len(column):>4}  "
                  f"{'ok' if gap <= TOLERANCE and n_matches else 'DRIFT'}")

    # The realism gate's anchor. If this moves, tests/test_plausibility.py is
    # comparing generated data against a threshold that no longer describes the source.
    # NEWS2 needs all five inputs on the same row, so this one IS listwise.
    complete = df.dropna(subset=["resprate", "o2sat", "sbp", "heartrate", "temperature_c"])
    complete = complete[complete["temperature_c"].between(30, 43)]
    urgent = [news2(r.resprate, r.o2sat, r.sbp, r.heartrate, "A", r.temperature_c)
              for r in complete[complete.category == "Urgent"].itertuples()]
    semi = [news2(r.resprate, r.o2sat, r.sbp, r.heartrate, "A", r.temperature_c)
            for r in complete[complete.category == "Semi-Urgent"].itertuples()]
    refitted_auc = area_under_curve(urgent, semi)
    committed_auc = committed["realism_gate"]["auc_mimic"]["value"]
    auc_gap = abs(refitted_auc - committed_auc)
    print(f"\n  realism gate auc_mimic  committed {committed_auc:.4f}  refitted {refitted_auc:.4f}  "
          f"{'ok' if auc_gap <= TOLERANCE else 'DRIFT'}")
    if auc_gap > TOLERANCE:
        drifted.append(f"auc_mimic: committed {committed_auc}, refitted {refitted_auc:.4f}")

    # NTPF and ESRI cannot be re-derived automatically: one is a dated CSV whose URL
    # changes each month, the other a 114-page PDF. Their provenance is printed so a
    # human can check it rather than being silently assumed.
    print("\nNot automatically re-derivable -- verify by hand if you need to:")
    for name in ("specialty_mix", "length_of_stay"):
        prov = yaml.safe_load((CAL / f"{name}.yml").read_text())["provenance"]
        print(f"  {name:16} {prov.get('source', '?')}")
        print(f"  {'':16} {prov.get('url', '?')}")

    print()
    if drifted:
        print(f"  {len(drifted)} figure(s) DRIFTED from the committed calibration:")
        for item in drifted:
            print(f"    - {item}")
        sys.exit("\n  The calibration no longer matches its source. Changing it changes the\n"
                 "  generated data, so it needs a deliberate update and a new data version.")
    print("  Calibration still matches its source. Nothing written.")


if __name__ == "__main__":
    main()
