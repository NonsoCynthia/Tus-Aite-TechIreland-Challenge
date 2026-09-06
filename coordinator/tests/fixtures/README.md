# Fixtures

## `cohort_9004_2026-08-30.json`

Captured live from `GET /hospitals/9004/cohort/2026-08-30` (task 1.3,
`conductor/tracks/coordinating-agent_20260906/plan.md`). Authenticated with
a bearer token read from `RETRIEVAL_BEARER_TOKENS` in the repo-root `.env`
at capture time; the token is not, and must never be, present in this file.

Contents, as captured:

- **500 referrals**, one hospital-day cohort for hospital 9004,
  `as_of_date` 2026-08-30.
- **`cpc`**: `int` or `None` — 95 of 500 referrals in this cohort (19%)
  have `cpc: null` (uncategorised). Categorised counts: `1` (Urgent) x131,
  `2` (Routine) x141, `3` (Semi-Urgent) x133. No `4` (Excluded) referrals
  appear in this cohort — Excluded is defined in `core.ref_codes` but does
  not occur anywhere in data v1.1: `SELECT triage_category, count(*) FROM
  core.triage_events` returns only categories 1 (1,248), 2 (1,586) and 3
  (1,378) across 4,212 rows. Hand-built fixtures in `test_bands.py` still
  carry the Excluded case, since the coordinator must not break on the
  first real one.
- **The null-CPC group is not a small edge case.** Across the dataset
  there are 4,212 triage events against 5,200 referrals, so roughly a
  fifth of referrals either have no `triage_event_id` at all or were
  triaged without a category being recorded — consistent with the 19%
  seen in this cohort. Consequence for the coordinator: `RULE-TRIAGE-
  TURNAROUND` (21 days, `awaiting_triage`) will fire on a large share of
  this uncategorised tail, and the clinician UI must present that group
  as **unknown priority, not low priority** (ADR-006).
- **`crt_breached`**: three-valued (`True` / `False` / `None`), taken as
  given from the retrieval service, never re-derived (spec.md FR5).
- **`adjusted_wait_days`**: ranges 0-893 in this cohort; the upper end is
  the "heavily breached waits" case the plan calls out.

Recapture by re-running the `curl` in this track's history against a live
`retrieval` instance with a valid bearer token, then re-run
`test_bands.py::test_real_cohort_fixture_bands_resolve_cleanly` (and later
Phase 3-5 tests) against the new file.
