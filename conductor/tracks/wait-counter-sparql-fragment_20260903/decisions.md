# Decisions — Wait-counter SPARQL fragment

## 1. Stop and report, rather than add the missing properties in this track

**Decided.** Investigation found `eat.ttl` has no property carrying `referral_date` or
`referral_received_date` onto `eat:Referral`, which blocks all four wait counters (not just
`adjusted_wait_days`). Two paths were offered to the user:

1. Stop, report only — leave the ontology untouched and record the finding for the ontology
   owner to act on.
2. Add the two missing properties to `ontology.md` and `eat.ttl` in this same track, then
   proceed to write and validate the fragment.

**Chosen: (1), stop and report only.** The user's own task instructions singled out exactly
this scenario ("if adjusted_wait_days cannot be cleanly derived in SPARQL, stop and report
that rather than working around it"), and the prior ontology track was explicit that
`ontology.md` is normative and nothing should be invented outside it. Amending the ontology
is a decision for whoever owns `ontology.md`/`decisions.md`, not something to fold silently
into a query-writing track.

**Why not (2).** Even though the fix is small and the shape is obvious (mirrors
`atHospital`/`forPatient`), making it unilaterally here would mean a query-writing track
quietly expanding the normative ontology spec — the same failure mode the instructions were
guarding against.
