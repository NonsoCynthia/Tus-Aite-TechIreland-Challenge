"""Deterministic CSV writing.

Determinism is non-negotiable: same seed, byte-identical output. Every downstream
guarantee -- the published tag meaning one specific dataset, the sample being
reproducible, a ranking being replayable -- rests on it.

The rules, from BUILD_MANUAL section 8.5, enforced here rather than remembered:
  - sort every frame before writing
  - fixed column order
  - lineterminator="\\n", never the platform default
  - dates as YYYY-MM-DD, timestamps as YYYY-MM-DD HH:MM:SS
  - no datetime.now() anywhere in generated content
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATE_FMT = "%Y-%m-%d"
TS_FMT = "%Y-%m-%d %H:%M:%S"


def fmt_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.strftime(DATE_FMT).fillna("")


def fmt_ts(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.strftime(TS_FMT).fillna("")


def write_table(
    df: pd.DataFrame,
    name: str,
    out_dir: Path,
    columns: list[str],
    sort_by: list[str],
    date_cols: tuple[str, ...] = (),
    ts_cols: tuple[str, ...] = (),
) -> int:
    """Write one table deterministically and return the row count.

    `columns` fixes the column order. `sort_by` fixes the row order. Both are
    required rather than optional, because the failure they prevent -- a hash
    that differs between two runs of the same seed -- is silent until the
    determinism check catches it, and confusing when it does.
    """
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")

    out = df.copy()
    for c in date_cols:
        if c in out.columns:
            out[c] = fmt_date(out[c])
    for c in ts_cols:
        if c in out.columns:
            out[c] = fmt_ts(out[c])

    out = out[columns].sort_values(sort_by, kind="mergesort").reset_index(drop=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / f"{name}.csv", index=False, lineterminator="\n")
    return len(out)
