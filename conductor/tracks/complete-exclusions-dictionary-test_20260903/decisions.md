# Decisions — Complete the EXCLUSIONS dictionary

## 1. Two undocumented name divergences found, not fixed here

While tracing all 50 misses, two property/column divergences turned up that are not yet in
`requirements.md` §4's divergence table: `eat:referredToService` / `specialty_hipe` (moved to
`eat:ReferralState` by `add-missing-data-layer_20260903`) and `sosa:resultTime` /
`obs_datetime`. Both are recorded here as EXCLUSIONS reasons, which is sufficient for this
test to pass, but `requirements.md` §4's table itself is not amended — that edit is outside
this track's scope (test file only). Suggested follow-up: add both rows to the table the next
time `requirements.md` is touched.

## 2. No genuine gap found

All 50 misses were legitimate under one of the task's five categories. No property was added
to `eat.ttl` or `ontology.md`, consistent with the task's instruction not to touch either
file.
