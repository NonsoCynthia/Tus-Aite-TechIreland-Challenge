# Decisions — Write and validate kg/queries/wait_counters.rq

## 1. Validate against a materialised in-memory sample, not the real store

**Decided.** No input-layer triples exist anywhere yet — `kg/out/referral_state.nt` carries
only `stateOf`/`validFrom`/`validTo`. Per the task's explicit instruction, rather than report
an unvalidated fragment, a minimal graph was built in-memory (pyoxigraph) from real Postgres
values for 35 referrals, and the fragment was actually run and compared against
`core.referral_daily`. The 473/473 match rate reported is measured, not asserted. The
validation script is committed (`kg/tests/test_wait_counters_sample.py`), not a throwaway,
so it is reproducible and re-runnable once real mappings exist.

## 2. `eat:triageStatus`, not "no `eat:hasTriageEvent`", drives `days_awaiting_triage`

**Decided**, confirmed with the user mid-build. Measurement showed 13,117 of 70,012
`triaged` rows in the `full` profile (18.7%) have no linked `triage_events` row at all,
yet their `days_awaiting_triage` is correctly `NULL` — so absence of a triage event is not a
safe proxy for "awaiting triage". `eat:triageStatus = "awaiting_triage"` was measured to
match every sampled row exactly. This is a correction to the task's literal wording, made
because the wording didn't match the actual data, not a stylistic preference.

## 3. Suspensions only subtract once closed — reverse-engineered, not assumed

**Decided**, based on tracing `core.referral_daily` day-by-day for suspensions that close
partway through the extract window (e.g. `PW-9001-001022`: subtraction is 0 while the
suspension is still open, then jumps to the full `suspended_days` on the day it closes and
stays there). The fragment implements exactly this: a suspension contributes only once its
interval's `time:hasEnd` date is `<= ?asOfDate`; an open suspension (no `time:hasEnd` yet)
contributes nothing, matching the pattern actually observed.

## 4. Superseding the earlier track: status only, content untouched

**Decided**, per the task's explicit instruction not to edit the earlier track. Only
`wait-counter-sparql-fragment_20260903/metadata.json`'s `status` field and a one-line
"Superseded by" pointer in its `index.md` were changed — its `spec.md`/`decisions.md`, which
record the original blocker and the evidence for it, are left exactly as they were.
