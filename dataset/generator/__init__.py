"""Generates the synthetic dataset.

Reads:  generator/config.yml (hospitals, profiles, planted cases) and
        generator/calibration/*.yml (distributions fitted from real sources).
Writes: out/*.csv, one file per table.

`python -m generator.generate --profile small|full`, or `make generate PROFILE=...`.
"""
