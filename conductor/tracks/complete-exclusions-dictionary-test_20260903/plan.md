# Implementation Plan — Complete the EXCLUSIONS dictionary

### Phase 1 — Add the EXCLUSIONS entries
- [x] Task: Add the 50 entries to `EXCLUSIONS`, grouped by table, each with its specific
      reason.
- [x] Task: Run `python kg/tests/test_column_coverage.py` against the live database; confirm
      it prints PASS and exits 0.
- [x] Task: Conductor - User Manual Verification 'EXCLUSIONS complete' (Protocol in
      workflow.md) — confirmed the diff touches only the test file, and every entry has a
      specific, checkable reason.
