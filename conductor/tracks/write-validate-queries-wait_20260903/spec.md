# Write and validate kg/queries/wait_counters.rq

## Overview
`wait-counter-sparql-fragment_20260903` stopped because `eat:Referral` had no
`referralDate`/`referralReceivedDate` and `eat:SuspensionEvent` had no interval link.
`add-missing-data-layer_20260903` added both. This track writes and validates
`kg/queries/wait_counters.rq`, deriving all four requirements.md R2 wait counters, and marks
the earlier blocked track superseded (status only — its record of the original blocker is
left intact, not rewritten).

**No input-layer triples exist in any store yet** — only `kg/out/referral_state.nt` (49,888
`stateOf`/`validFrom`/`validTo` triples only; no referral dates, suspensions, or triage
events, since the A/B/E mappings haven't run). Validating against real materialised data is
therefore not possible. A minimal test graph was materialised in-memory instead — real
values pulled straight from Postgres for a sample of 35 referrals, spanning unsuspended,
awaiting-triage, and suspended (both closed-before-window and closing-during-window) cases —
and the fragment's output was compared row-by-row against `core.referral_daily`'s stored
counters. **This was actually run; the match rate below is measured, not asserted.**

## What was found while building this
1. **The day-count derivation (requirements.md §6's "one real risk") is tractable.**
   Oxigraph normalises `xsd:date - xsd:date` to a duration always expressed in whole days
   (`"P13D"`, `"PT0S"`, or `"-P7D"` — verified empirically, never month/year components for a
   date-date subtraction). A `REPLACE`-based digit extraction converts that to an integer.
   This resolves the risk requirements.md flagged — it does not need the R2 fallback
   ("store `adjusted_wait_days` as a literal").
2. **`adjusted_wait_days`'s real rule, reverse-engineered from `core.referral_daily`:** a
   suspension subtracts its full length only once *closed* as of `as_of_date`
   (`time:hasEnd`'s date `<= ?asOfDate`) — an open suspension contributes **nothing** until
   it closes, then contributes its whole span at once (never prorated while still open). This
   is measured behaviour (traced day-by-day against real rows), not an assumption.
3. **"No triage event exists" is not a reliable stand-in for awaiting-triage — found and
   confirmed mid-build.** 13,117 of 70,012 `triaged` rows (18.7%) in the `full` profile have
   no `triage_events` row at all (predates retained history), yet their
   `days_awaiting_triage` is correctly `NULL`. The actual rule the data follows is
   `eat:triageStatus = "awaiting_triage"` (a `ReferralState` property), confirmed to match
   every one of 473 sampled rows. The user confirmed using `eat:triageStatus` instead of the
   literal "no triage event" wording.
4. **An Oxigraph engine quirk, worked around, not routed around silently:** referencing an
   outer `BIND`-derived variable inside a later `OPTIONAL`'s `BIND`, combined with
   `GROUP BY`, silently fails to bind in pyoxigraph 0.3.22 (reproduced in isolation). Fixed
   with the standard SPARQL idiom for conditional unbinding — `IF(condition, value, 1/0)`.

## Validation result
35 referrals × up to 14 `as_of_date` rows = **473 comparisons, 0 mismatches** across all four
counters, covering: 25 unsuspended referrals, 1 awaiting-triage referral (all its available
days), and 9 suspended referrals (5 closed well before the window, 4 closing partway through
it). No case of an open/never-closing suspension exists in the `full` profile to test the
"still open" branch against real data; the logic for it is implemented and matches finding
#2's reverse-engineered rule, but is **untested by data**, same caveat pattern as
`eat:validTo`'s removal branch from the ontology track.

## Functional Requirements
1. Write `kg/queries/wait_counters.rq`.
2. Write a reusable validation script, `kg/tests/test_wait_counters_sample.py`.
3. Mark `wait-counter-sparql-fragment_20260903`'s `metadata.json` status `"superseded"` and
   add a one-line "Superseded by" pointer to its `index.md`. Its `spec.md`/`decisions.md`
   content is left untouched.
4. Do not touch mappings, shapes, SQL, `eat.ttl`, or `ontology.md`.

## Acceptance Criteria
- `kg/queries/wait_counters.rq` exists, matches the validated design.
- `python kg/tests/test_wait_counters_sample.py` exits 0 and prints 473/473 matched.
- `wait-counter-sparql-fragment_20260903`'s metadata status is `superseded`; its
  spec/decisions content is unchanged.
- No file outside `kg/queries/`, `kg/tests/`, both tracks' directories is touched.

## Out of Scope
- Running this against a real materialised graph (A/B/E mappings don't exist yet).
- SHACL shapes, mappings, SQL, the ontology files.
