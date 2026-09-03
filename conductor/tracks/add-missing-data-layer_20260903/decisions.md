# Decisions — Add missing data-layer literal properties

## 1. Move `eat:referredToService` from `eat:Referral` to `eat:ReferralState`

**Decided.** `specialty_hipe` is one of requirements.md R1's material fields — it changes on
redirect, which is exactly what mints a new `eat:ReferralState`. Under decisions.md §1's
Type-2 model, "never-changing fields sit on `eat:Referral`"; a field that can differ between
one state and the next is, by definition, not one of them. Leaving `referredToService` on
`eat:Referral` would make it impossible to state which service a referral was with *during*
an earlier state once a redirect happened — exactly the kind of question a `ReferralState`
range query is supposed to answer.

**Why not keep a copy on both.** decisions.md's whole argument for Type 2 is that a single
shared fragment/property should be trusted, not duplicated across representations that could
drift. A property on both nodes reopens exactly that risk for no benefit — nothing needs the
originally-referred-to service as a value distinct from `eat:Referral`'s other enduring
fields, and nothing in `ontology.md` or `decisions.md` asked for one.

## 2. Extend `eat:atHospital`'s domain to include `eat:Ward`, rather than a new property

**Decided** (user confirmed in scope). `eat:Ward` is hospital-scoped by IRI convention
(`ward/{hospital_hipe}/{ward_id}`) exactly like `eat:Patient`, but had no triple stating which
hospital it belongs to — only the IRI string carried that fact, which namespaces.md and
decisions.md both treat as a citability anti-pattern (structure should be graph structure,
not string parsing). Reusing `eat:atHospital` (already domain `unionOf(Patient, Referral)`,
range `eat:Hospital`) with a wider domain closes the gap without minting a new predicate for
a relationship that means exactly the same thing as the existing one.

## 3. Add `time:hasTime` (OWL-Time, reused) linking `eat:SuspensionEvent` to a `time:Interval`

**Decided** (user confirmed in scope, despite being an object property in a
literal-properties track). decisions.md is explicit that `adjusted_wait_days` is only
derivable if suspended periods are represented as real intervals in the graph
("This is why `eat:SuspensionEvent` must be first-class, with its interval in the graph").
Without a property connecting the event to a `time:Interval`, that requirement is
unsatisfiable regardless of what literal properties exist — `suspension_start_date`/
`suspension_end_date` would otherwise have nowhere to attach. `time:hasTime` is OWL-Time's
own generic "temporal entity of this thing" property, so this is a domain refinement of a
reused term, not a new local predicate — consistent with `ontology.md` §1's reuse-first
principle and with the `sosa:hasMember` / `sosa:observedProperty` refinements from the prior
ontology track.

## 4. `sosa:hasSimpleResult` / `sosa:resultTime` were missing entirely — not scope creep

Not a new decision so much as a correction: `ontology.md` §1 names both terms as reused SOSA
vocabulary, but §3's property table never gave them a domain/range refinement, alongside
`hasMember`/`observedProperty`/`hasFeatureOfInterest`. Without `hasSimpleResult` in
particular, no `sosa:Observation` individual has any way to state the value it measured —
the single most consequential gap this audit found, since it affects every one of the
~12,000 observation rows the dataset documentation describes. Filed under this track because
it is exactly the kind of "column with nowhere to go" the task asked to close, not because it
was requested by name.
