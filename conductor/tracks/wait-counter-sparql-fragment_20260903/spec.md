# Wait-counter SPARQL fragment — blocked, reporting ontology gap

## Overview
Track 2 of the KG build (`conductor/kg/requirements.md` §5) asks for a shared SPARQL
fragment at `kg/queries/wait_counters.rq` deriving `days_since_referral`,
`days_since_received`, `days_awaiting_triage`, and `adjusted_wait_days`, validated against
`core.referral_daily`. Investigation in Postgres found the fragment **cannot be written**:
the source dates it needs are not carried by any property in `eat.ttl`. This track stops per
the task's own instruction ("if it cannot be cleanly derived, stop and report") and records
the finding instead of writing a workaround.

## Background — what was checked
- `core.referrals` / `core.referral_daily` store `referral_date` and `referral_received_date`
  as enduring, per-referral facts (`referrals_received_after_written` constraint:
  `referral_received_date >= referral_date`).
- `days_since_referral = as_of_date - referral_date`,
  `days_since_received = as_of_date - referral_received_date`
  (enforced by the `rd_counts_match_dates` check constraint on `referral_daily`).
- `adjusted_wait_days` subtracts suspended time from (at least) `days_since_received`, per
  decisions.md §1 and requirements.md R2.
- **The gap**: `conductor/kg/ontology.md` §3's property table — implemented verbatim into
  `eat.ttl` by the prior track (`complete-eat-ttl-owl_20260903`) — has no property carrying
  `referral_date` or `referral_received_date` onto `eat:Referral`. Every other enduring
  field of `eat:Referral` (`atHospital`, `forPatient`, `referredToService`) has a property;
  these two do not.
- **Confirmed empirically** against the loaded `full` profile:
  ```sql
  SELECT
    count(*) FILTER (WHERE first_as_of = referral_received_date) AS eq_received,
    count(*) FILTER (WHERE first_as_of = referral_date) AS eq_referral,
    count(*) AS total
  FROM (
    SELECT hospital_hipe, pathway_number, min(as_of_date) AS first_as_of
    FROM core.referral_daily GROUP BY 1,2
  ) f
  JOIN core.referrals r USING (hospital_hipe, pathway_number);
  -- eq_received=317, eq_referral=0, total=5200
  ```
  `ReferralState.validFrom` cannot substitute for the missing dates: the first `as_of_date`
  for a referral equals `referral_received_date` in only 317 of 5,200 cases, and never
  equals `referral_date`. `validFrom` marks when the extract first captured the referral,
  not when it was made.
- Without `referral_date`/`referral_received_date` reachable from the graph, **none of the
  four counters are derivable in SPARQL** — not just `adjusted_wait_days`. The suspension
  arithmetic for `adjusted_wait_days` was never reached because the base date it adjusts is
  itself unavailable.
- `core.suspension_events` (221 rows on the `full` profile) and the `kg.v_referral_state`
  view are present and usable once this is unblocked — the suspension side of the problem is
  not in question.

## Functional Requirements
1. Do **not** write `kg/queries/wait_counters.rq`.
2. Do **not** add properties to `eat.ttl` or `ontology.md` in this track — that decision
   belongs to the ontology owner (explicit user choice: "stop, report only").
3. Record the finding here, citing the exact evidence above, so whoever amends the ontology
   has the query and numbers already in hand.
4. Track status is `blocked`, not `done`.

## Non-Functional Requirements
- No SQL, ontology, mapping, or shape file is modified by this track.
- The evidence trail (SQL used, row counts) is reproducible from this document alone.

## Acceptance Criteria
- `kg/queries/wait_counters.rq` does not exist after this track.
- The track's spec documents: the two missing properties, the constraint names proving the
  date-arithmetic relationship, and the 317/5,200 measurement disproving the
  `validFrom`-as-substitute idea.
- Track status recorded as `blocked`.

## Out of Scope
- Amending `ontology.md` / `eat.ttl` to add the missing properties.
- Writing the fragment once unblocked (future track, once the ontology gap is resolved).

## Recommendation for whoever unblocks this
Two properties are missing from `ontology.md` §3, analogous in shape to the existing
enduring-field properties on `eat:Referral`:

| Property | Domain | Range | Card. |
|---|---|---|---|
| `eat:referralDate` | `eat:Referral` | `xsd:date` | 1, functional |
| `eat:referralReceivedDate` | `eat:Referral` | `xsd:date` | 1, functional |

Once added to `ontology.md` and `eat.ttl`, and mapped from `core.referrals` (Track A/B), the
fragment becomes: `days_since_referral = ?asOfDate - ?referralDate`,
`days_since_received = ?asOfDate - ?referralReceivedDate`, and `adjusted_wait_days =
days_since_received` minus the sum of overlapping `eat:SuspensionEvent` `time:Interval`
durations up to `?asOfDate`. This is a suggestion for the ontology owner to evaluate, not a
change made by this track.
