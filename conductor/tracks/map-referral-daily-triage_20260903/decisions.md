# Decisions — Map referral_daily, triage_events, patients and persons to RDF

## 1. `clinic_code`/`clinic_classification`/`removal_reason`: joined back to `referral_daily`, not added to the view

`kg.v_referral_state` deliberately excludes any column that isn't an R1 material field —
that's the whole point of the change-detection view. `clinic_code`, `clinic_classification`,
and `removal_reason` are not material fields, so they were never going to be in the view,
yet `eat:ReferralState` needs values for all three (per `add-missing-data-layer_20260903`).
**Decided:** join back to `core.referral_daily` inside each property's own `rr:sqlQuery`,
picking the row for the day each property actually applies to — `valid_from` for
`clinic_code`/`clinic_classification` (they track `appointment_date`, itself material, so
fixed for the whole state once set), `valid_to` for `removal_reason` (the day the referral
was actually removed). This is a data lookup keyed on the state's own dates, not a
change-detection decision — requirements.md §4's rule that mapping logic never lives outside
the view is about *when a new state is cut*, not about *reading a non-material column for an
already-determined state*.

**Why not extend the view instead.** Adding these three columns to `kg.v_referral_state`
would work too, but it would blur the view's one job (material-field change detection) with
an unrelated one (passthrough of non-material columns), and every future non-material column
someone wants exposed would then also go through the view. Keeping the join in the mapping
keeps the view exactly as focused as decisions.md §1 designed it.

## 2. `record_creation_date`: a correlated `MIN()` subquery, not a second table in the FROM clause

`core.referrals` has no `record_creation_date` column; only `referral_daily` does.
`add-missing-data-layer_20260903` verified it constant per referral in Postgres (0 referrals
with more than one distinct value), so `SELECT r.*, (SELECT MIN(rd.record_creation_date) …)
FROM core.referrals r` is exact — not "the earliest observed value," which would imply some
referrals disagree across days.

## 3. `eat:areaOfResidenceCode` included on `eat:Patient`/`eat:Person`, beyond the task's literal property list

The task named `eat:sex` and `eat:dateOfBirth` specifically for both classes.
`eat:areaOfResidenceCode` is a real, non-null column on both `core.patients` and
`core.persons`, and an already-declared property from `add-missing-data-layer_20260903`
with no open question attached to it (unlike, say, `eat:isRecordOf`'s null-handling, which
*is* explicitly addressed). Added it because leaving it out would mean "completing the input
layer" silently left a real, unambiguous column unmapped for no stated reason — not because
the task's list was read as exhaustive.

## 4. The named-graph fix touches only the two pre-existing maps' subject/graph maps

`ReferralStateMap` and `ReferralStateClosedMap` keep their original `rr:sqlQuery`,
`rr:template`, and predicate/object maps untouched — only a `rr:graphMap` was added to each
`rr:subjectMap`, plus the four new predicateObjectMaps for the newly-added NOT-NULL
`ReferralState` columns landed on `ReferralStateMap` itself rather than as separate maps,
since they don't need their own `IS NOT NULL` filter (verified: `triage_status`,
`high_clinical_or_social_needs`, and `specialty_hipe` all inherit NOT NULL from
`referral_daily`'s own schema).
