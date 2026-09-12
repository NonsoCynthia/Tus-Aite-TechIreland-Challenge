# Tús Áite — clinician ranked list: design pack

**For Claude Design.** This document specifies structure, hierarchy, density, states, data
bindings, interaction and final copy. It deliberately specifies **no brand colours and no
typefaces** — those are yours. Where it names a semantic requirement ("clinical state is
never encoded by colour alone") that is a safety constraint, not a style preference.

Built for the TechIreland National AI Challenge 2026. Presenting 14 September 2026.
Every figure here was verified against running containers and merged code; nothing is
assumed. Where something could not be verified it says so.

---

## 1. What this product is

A clinician has already triaged these patients into categories. This screen answers a
narrower question: **among patients marked equally urgent, who should be seen next, and
why.** It never changes a clinical category and it never triages anyone.

### The claim the interface must support, and its limit

> NEWS2 reads six vital signs and nothing else. On this hospital-day **268 of 308 referrals
> (87.0%) score 2 or less**, and **20 of the 84 a clinician marked Urgent (23.8%) score 0**.
> A physiology-only score cannot separate these patients. Waiting time does the
> discriminating, and the interface has to show that plainly rather than dressing it up as
> clinical reasoning.

The urgency agent says the same of itself: *"one auditable component of urgency. It is not
a triage judgement, and no ranked list built on it alone should be described as clinically
prioritised."*

### Three things that look like evidence and are not

| Field | Why it is not evidence |
|---|---|
| ICD-10-AM condition | A weighted random draw over the specialty's condition mix (`generate.py:472`), independent of vitals, acuity and triage category. The stored label is the placeholder string `"Condition C43.9"`. Show it as a record field with its provenance stated. |
| `mts_category` | Measured in ADR-004: within a band the colour is a coin flip, and 0 of 609 observations carry a chief complaint. It is the CPC band relabelled. Give it no privileged colour channel. |
| `rationale_summary` | All 308 strings say *"urgency weighted more heavily than waiting time"*, contradicting any honest contribution display. Never render verbatim. |

### Capacity, stated correctly

Capacity sets α, the exchange rate between urgency and waiting time, at **one value for the
whole hospital-day**. Moving α inside its documented [0.5, 0.9] range flips real pairs, so
capacity **does** affect ordering. It cannot move anyone across a category boundary and it
does not enter any individual's score.

---

## 2. Non-negotiables

### Safety invariants

These must remain true however the design evolves.

1. No urgency score is ever displayed without its contributing evidence reachable in ONE
   interaction, and this holds in the loading, empty, refused, unresolved and error states,
   not only the happy path.
2. Nothing on the screen claims to know how sick a patient is. The urgency component reads
   six vital signs and nothing else; the interface says so permanently in the scope line,
   again in the column header, and never attaches a clinical adjective to a NEWS2 score.
   This is the thesis (C1): 268 of 308 score 2 or less, so a physiology-only score cannot
   separate these patients, and waiting time must - and every row says which.
3. A missing score is missing information, not low urgency (ADR-008). No absent value is
   ever defaulted to zero, rendered as zero, or rendered as a blank that could be read as
   zero. Pre-run, absence is structural - the column is not rendered - rather than a
   placeholder repeated 308 times.
4. A referral that was refused a score is never rendered in a way that could read as a rank,
   a low position or a low priority. It sits in a named tail region whose own heading says
   'Not scored, not placed. This is not a low position.', and its clinician-recorded facts -
   category, waiting time, target - render at full normal weight, because refusing to score
   someone does not unrecord what a clinician wrote.
5. 'We deliberately do not cover paediatrics' (a coverage statement) and 'some rows are
   broken' (a data-quality incident) must never be renderable in the same element, with the
   same words, or in the same count. The coordinator's single 'missing_urgency_score' string
   makes this an active defence, not a passive one.
6. cpc null is UNKNOWN priority, not low priority, and cpc 4 Excluded is a different thing
   again. The two tails are never merged, and the zero-row Excluded header renders anyway
   because it is the cheapest visible proof the system keeps the distinction (ADR-006).
7. No score, no weight, no capacity value and no interaction can move a referral across a
   CPC band boundary. The only thing that can place a referral outside its band is a
   clinician recording a reason, and that action always names the rule it crosses BEFORE the
   attestation.
8. The ordering is presented as PROVISIONAL, never final, for as long as ADR-011 is open.
   The breach-tier divider and its sentence are permanent structure, and no surface may
   describe the ranking as clinically prioritised or signed off.
9. Capacity's real effect on the ordering is stated with its two limits alongside: it sets
   ONE exchange rate for the whole hospital-day, it never enters an individual's score, and
   it can never move anyone across a band or across the waiting-target tier - but it DOES
   change who is above whom inside a tier, for 272 of 305 referrals across its documented
   range. A capacity-conditioned list must never be presented as a purely clinical one, and
   the codebase's own docstring denying this must never be repeated in copy.
10. Every number on screen is traceable to a stored field, a committed constant, or an
   arithmetic operation the interface names as its own. There is no UI-side gloss, no
   invented label, no plain-English diagnosis and no fabricated uncertainty.
11. The interface never displays a confidence, certainty, probability or reliability figure
   of any kind, because nothing in agent.agent_scores carries one and a fabricated one would
   be read as calibrated.
12. The whole interruption budget is exactly ONE modal, spent on the band- or tier-crossing
   override. Interrupting modals are accepted at 38.67% against 61.57% for non-interrupting
   alternatives across 39 studies, so anything else that interrupts delivers the band-
   crossing warning to an already-desensitised clinician.
13. Accepting never requires a reason and overriding always does - but overriding is never
   harder to REACH than accepting: Move is ungated wherever a position exists, while Accept
   requires one expansion. If overriding is harder than accepting, the human-in-the-loop
   claim is cosmetic.
14. An acceptance is a first-class RECORDED act (POST /overrides with from_position ===
   to_position), or the interface says in visible text that it is not recorded. An audit-
   framed product must never imply a click was filed when it was not, and a row must never
   look accepted after a failed write.
15. No ranking is ever rendered from partially written scores. Position numerals, the ranked
   order and the contrastive column are withheld until both agents have finished AND a
   clinician has explicitly applied the result. Two counters with their two true
   denominators, never one bar and never a percentage.
16. A partial list is never rendered without saying, in the same viewport and before the
   first row, that it is partial and against what denominator. A quiet partial list looks
   exactly like a complete one and is the most dangerous failure this UI can have.
17. The clinician-recorded layer renders first, fast and completely from one cohort call; the
   computed layer arrives visibly second and on top of it. There is therefore never any
   pressure to display a ranking in order to have a useful screen - which is why the pre-run
   state is the deliverable and not a fallback.
18. Rows never move under the cursor and never reorder on a background poll, because a row
   that moves under the cursor is a mis-click on an override control. Numerals and meter
   widths never tween, because a tweening wait figure displays day counts that were never
   true of any patient.
19. The synthetic-data label and the decision-support statement are present on every ranking
   surface, in every export, in every screenshot and in the demo, with no dismiss control
   and no close control.
20. Nothing that was not part of the computation is ever rendered as if it were - no post-hoc
   narrative, no second explanation, no picture that tells a different story from the list
   it is drawn from. The provenance graph, if ever built, may only be a second rendering of
   the expander's own evidence list.
21. clinician_id is attribution, not authentication, and the interface says so at the point
   of entry. No field, control or layout may imply an access-control guarantee this build
   does not have.
22. The interface presents SUPPORTIVE INFORMATION, never command-type advice (EU AI Act Art.
   14(4)(b); automation bias RR 1.26, 95% CI 1.11-1.44, with display prominence a measured
   mediator). Nothing is styled as a recommendation to act, and the most prominent element
   on a row is the clinician-recorded waiting time rather than the agent's score.

### Forbidden

- NEVER render the ICD-10-AM condition as evidence, on a row, in a chip, in a filter, or
  with an invented English label. REASON (C3): generate.py:472 draws the code by rng.choice
  over the specialty's condition mix, independent of vitals, acuity and triage category;
  HOW_THE_DATA_WAS_MADE.md 5.3 confirms latent_hazard never reads the diagnosis; mean NEWS2
  by condition is flat at 0.73-1.03; and the stored label is the literal placeholder
  'Condition C43.9' with snomed_ct_id null on all 408 rows. A diagnosis on a row would dress
  a random draw as clinical context and would be the only uncited string on a screen whose
  whole claim is traceability.
- NEVER tell the story as 'a melanoma was missed'. REASON (C1): PW-9001-000208 is not a
  planted case, the code is drawn independently of physiology, and the claim is falsifiable
  in ten seconds by a judge who reads the generator. The true and stronger thesis is about
  the INSTRUMENT.
- NEVER give mts_category a colour channel, a badge, a legend, a filter or a place in any
  list of signals. REASON (C3): within a band it takes two values and is close to a coin
  flip (44 orange / 40 red within CPC 1 on this hospital-day; 77 red / 75 orange with 3
  unrecorded, of 155, across both), 0 of 609 observations carry a chief complaint, and
  ADR-004 makes it the CPC band relabelled. The five MTS hues are also a national standard
  with fixed target times and must never be reused for another axis.
- NEVER render rationale_summary verbatim on a row, in a tooltip, in the dock, or as this
  patient's reasoning. REASON (C3): _alpha_weight_phrase picks one of exactly two strings on
  a single midpoint test against alpha, so all 308 strings carry the same clause and
  describe a hospital-day parameter, not a patient - and it would contradict the honest
  contribution arithmetic printed two inches away.
- NEVER read the ranking back from GET /decisions/{h}/{date}. REASON (C10): a second POST
  APPENDS its placements rather than replacing them because the graph node is keyed only on
  (hospital_hipe, as_of_date), so it can return two interleaved rankings; it resolves every
  placement's citations through roughly 1,500 sequential SPARQL round trips; and it returns
  no urgency_score, no rationale_summary, no band, no wait_normalised, no priority and no
  alpha.
- NEVER probe GET /decisions across the 28 selector cells to build ranked markers. REASON:
  same N+1 - probing is fast only while every cell is empty and degrades exactly as the demo
  gets better.
- NEVER infer run state from GET /runs/{run_id}/hospitals/{h}/scores alone. REASON (verified
  against a fabricated id): it returns HTTP 200 with an empty object for any unknown run_id,
  so a stale run_id is indistinguishable from a run that just started and would sit at 0 of
  305 forever.
- NEVER call the retrieval service from the browser. REASON: retrieval has no CORS
  middleware and the bearer token must never reach the browser. Same-origin through the
  orchestrator is mandatory, not a preference.
- NEVER add column sorting, a 'sorted' state, aria-sort, a sort control, or a click listener
  on any <th> (R4). REASON: SEVERITY_RANK maps cpc 1->1, 3->2, 2->3, so an ascending numeric
  sort on cpc silently places Routine above Semi-Urgent - the DATASET_README calls it
  'wrong, and it is wrong silently' - and any sortable column must defend against that
  forever. Deleting it removes the trap permanently and saves an hour.
- NEVER render a fused 'priority score', 'AI score', 'triage score' or 'risk score' column.
  REASON: a single number implies a measured quantity with real variance when 148 of 308 of
  its urgency inputs are exactly 0.000, and it is not comparable across bands or breach
  tiers because both sit above priority in the sort key.
- NEVER display alpha as a bare coefficient on a row or in the dock's identity headers, and
  NEVER provide a slider or any control that changes it. REASON: alpha is set by capacity
  data across a documented [0.5, 0.9] range, not by a drag gesture, and a runtime slider
  would put the single most consequential parameter in the least accountable surface.
- NEVER hardcode the alpha-sensitivity figures (272, 2,026, 20.9%, 51) or the named foil.
  REASON: they are cohort-dependent - 9002 differs - and the pack's own worked pair holds at
  alpha 0.7 and at no other tested value, so a hardcoded foil is wrong at 0.5 and 0.9.
- NEVER describe PW-9001-000208 as position 1. REASON: reproducing the committed sort key
  puts it at 10 / 15 / 34 across alpha 0.5 / 0.7 / 0.9, because 12 breached Urgent referrals
  score NEWS2 4 or more. Position 1 at every alpha in range is PW-9001-000191 (NEWS2 7, 152
  days) - the one case where physiology genuinely separates a patient, which is a better
  beat than a planted one.
- NEVER draw a bar, meter, gauge, ring, sparkline or colour ramp for urgency. REASON: 148 of
  308 rows would render an empty bar that reads as missing data for half the list, and a bar
  7.5% full beside one 0% full asserts 'slightly more urgent' when the true statement is
  that NEWS2 cannot distinguish them.
- NEVER display a confidence, certainty, probability or reliability figure anywhere. REASON:
  nothing in agent.agent_scores carries an uncertainty, so any such figure would be
  fabricated - and uncertainty displays are read as calibrated, which makes a fabricated one
  the most dangerous single element that could be placed on this screen.
- NEVER render a NEWS2 of 0, or a normalised 0.000, as blank, as an em dash, as zero-width,
  or with any clinical adjective - not 'low urgency', 'not urgent', 'low risk', 'stable',
  'normal' or 'no concern'. REASON: 0.000 is a computed value on a documented polarity, and
  the words assert a clinical judgement the instrument cannot support.
- NEVER render 0.08 for a NEWS2-1 urgency score, and never round a stored score on screen.
  REASON: the calibration anchors are exact and the column is numeric(4,3), so 0.075 is the
  stored value and 0.08 is a different number. The over-precision concern is answered by
  DEMOTING the figure and naming the eight reachable values, not by rounding.
- NEVER render a passed rule check, a within-target state, or a resolved evidence list as a
  tick, a green state or an 'OK'. REASON: a rule that did not fire says only that the rule
  did not fire, and a within-CRT referral is not a well patient. There is no success level
  in the authority taxonomy at all.
- NEVER style the breach-tier divider as an error, a warning or a defect. REASON: it is a
  structural fact about the sort key and an open clinical question (ADR-011); styling an
  unresolved question as a bug is its own misrepresentation.
- NEVER draw the breach-tier divider pre-run. REASON: pre-run order is referral_date (R5),
  so breached and within-target rows interleave and no single transition exists - a divider
  drawn anywhere would be a fiction. The band header carries the split as a count instead.
- NEVER place a refused referral among ranked rows. REASON (C8): a row among ranked rows
  implies a rank it does not have, and the three 0601 rows are verified NON-CONTIGUOUS in
  cohort order (indices 57, 193, 220; cpc 2, 2 and null; 330, 101 and 70 days), so in-place
  rendering would scatter them through Routine and No-category with no warning to a scanning
  clinician.
- NEVER sum two or more not-ranked buckets into a single 'excluded' figure, and NEVER print
  a bucket count as 0 when its source did not report. REASON (ADR-007): the urgency agent
  raises different exception types precisely so a coverage statement and a data-quality
  incident never look alike; the coordinator's single 'missing_urgency_score' string is
  exactly the collapse the UI must not reproduce.
- NEVER let colour, a 1px dash/dot/hatch pattern, a 6px strip, an 11px tick or a 3-decimal
  numeral be the sole carrier of any primary meaning. REASON (C7): at 1280x720 on a
  projector a 6px strip subtends about 12.7 arcmin and a 1px pattern about 2.1 arcmin, and
  that arithmetic models neither projector contrast, keystone nor compression.
- NEVER shrink type below 12px to make a cell fit. REASON (R2): the correct response to
  overflow is to CUT A LINE - which is why '6 vitals cited' left the urgency cell and the
  meter shares a line box with the days numeral - because a row that fits only at 10px is a
  row nobody in the room can read.
- NEVER reorder rows on a background poll, animate a numeral or a meter width, or stagger a
  transition. REASON: a row that moves under the cursor is a mis-click on an override
  control; a tweening wait figure displays day counts that were never true of any patient;
  and staggering harms multi-object tracking.
- NEVER interrupt for anything except the band- or tier-crossing override - not the run, not
  a breach, not a rule check, not an empty state, not the stop-run confirm, not the re-run
  guard, not a filter change. REASON: interrupting modals are accepted at 38.67% against
  61.57% across 39 studies, so a second modal spends the budget the band-crossing warning
  needs.
- NEVER build a bulk accept, an accept-all, a select-all or any multi-row action. REASON:
  the human-in-the-loop claim rests on a per-patient act of attention, and a bulk control
  makes 305 acceptances one click.
- NEVER pre-tick the attestation, place it before the disclosure, or offer a 'do not show
  this again'. REASON: attestation before disclosure is a signature on an unread document,
  and a suppression control converts a one-off safety step into a permanently disabled one.
- NEVER frame an override as disagreement - never 'override the AI recommendation', never
  'why do you disagree', never an 'are you sure' shaped like an error, never a destructive
  red confirm. REASON: recording your own clinical order is a normal, expected, attributed
  act, and framing it as deviation discourages exactly the behaviour the design exists to
  enable.
- NEVER show a generic error, an apology, a mascot, an illustration or a meaning-carrying
  icon in any empty or error state. REASON: a clinician debugging a demo needs the endpoint
  and the status code, and 'something went wrong' hides which of four different absences the
  system is actually in.
- NEVER render a skeleton table. REASON: the cohort measures 50ms for 111KB, so a skeleton
  that flashes for 50ms is noise. Below 400ms nothing renders; past 400ms one line of text
  in the ledger; every unknown count is an em dash and never a 0, because a zero is a claim
  about the cohort.
- NEVER render a totals row, a 'worst day', a trend line, or any cross-hospital or cross-day
  comparison. REASON: ranking hospitals or days is an objective nobody asked for, and a
  clean list whose real objective is not its stated one is precisely the Obermeyer failure
  shape. The 28 hospital-days are a selector, not a dataset.
- NEVER add a login screen, a permissions tier or a role selector. REASON: clinician_id is
  attribution, not authentication, in the API's own words, and a login-shaped field would
  imply an access-control guarantee this build does not have.
- NEVER show patient name, date of birth, MRN or IHI anywhere. REASON: GET
  /referrals/{h}/{pw}/context returns none of them, so any such field would be invented, and
  an interface that implies it holds identifiers it does not hold is lying about its own
  scope.
- NEVER build the provenance graph as a second narrative. REASON (C6): it is deferred, it
  renders empty against today's data, and if ever built it may only be a second rendering of
  the expander's own evidence list with the same entries and the same strings. A graph that
  told a prettier story than the list is post-hoc explanation that is not the actual
  computation.
- NEVER print a statistic without its denominator and its scope. REASON: two populations
  exist and they disagree - 20 of 84 Urgent referrals score NEWS2 0 on this hospital-day
  (23.8%) against 48 of 155 (31.0%) across both hospitals - and printing 31% next to a
  cohort where a judge can count 24% destroys the credibility of every other number on the
  screen.
- NEVER count NEWS2 by observation row. REASON: the display rule is observations[-1] per
  referral, so NEWS2 1 is 85 referrals and never 86. Row-counting is the one arithmetic slip
  that would put a wrong number in the headline sentence of the whole pitch.
- NEVER use a single '305' denominator for both run counters. REASON: only the urgency agent
  refuses 0601; the capacity agent iterates the whole cohort, so capacity is n of 308 and a
  shared denominator would put '308 of 305' on stage.

---

## 3. Geometry

Target viewport is **1280×720** (the projector), widening gracefully to 1440+. Conference
projectors are commonly 1280×800 and macOS mirroring scales to the projector, not the
laptop panel, so 1280 is the design target and 1920 is not.

### The grid

```
ONE GRID. Both prior grids are deleted. Viewport 1280x720, page gutters 16px left and right, content
width exactly 1248px. Six column tracks, fixed, table-layout:fixed, horizontal overflow lives in the
table's own overflow-x container and document.body never scrolls sideways.

  1  Rail (position + pathway), sticky left      192
  2  Category and timeframe                      176
  3  Waiting time and target                     256
  4  Urgency (NEWS2)                             184
  5  Why this position                           192
  6  Actions, sticky right                       248
  ARITHMETIC: 192+176 = 368; +256 = 624; +184 = 808; +192 = 1000; +248 = 1248. 1248 + 16 + 16 = 1280
exactly.

INTERNAL ARITHMETIC, every track proved against its worst-case string (13px tabular ~7.8px/glyph,
13px prose ~6.9px, 12px prose ~6.4px, 15px/600 ~8.3px, 20px/600 ~11.5px):
  Rail 192 = 8 pad + 16 A/B marker + 4 + 34 position numeral (right-aligned) + 10 + 112 pathway + 8
pad. "PW-9001-000208" measures ~109px at 13px tabular, inside 116. NEVER truncate the pathway; if
the chosen face is wider, drop the pathway to 12px rather than clip - it is the join key and the
string a clinician reads aloud.
  Category 176 = 8 + 160 + 8. Worst chip "No category recorded" = 20ch at 13px/600 = 138 + 16 chip
padding = 154, inside 160.
  Waiting 256 = 8 + 240 + 8, and 240 = meter 140 + 8 gap + days numeral 92 (right-aligned). Exact.
  Urgency 184 = 8 + 168 + 8. Worst line 1 "NEWS2 17 of 17" = 116. Worst line 2 "Evidence did not
resolve" = 154.
  Why this position 192 = 8 + 176 + 8. Worst line 1 "Ahead on waiting time" = 145. Worst line 2 "vs
PW-9001-000026" = 109.
  Actions 248 = 8 + 232 + 8, and 232 >= Compare 64 + Accept 72 + Move 46 + disclosure 24 = 206, plus
three 8px gaps = 230. 2px slack.

ABOVE 1440px CSS WIDTH: content width = viewport - 32. The entire surplus goes to column 5 only. At
1440: content 1408, surplus 160, "why this position" becomes 352; all five other tracks are
unchanged. There are NO extra columns at any width. The "specialty" and "flags" columns of both
prior specs are DELETED - flags was never defined by any field, and specialty now lives on rail line
2 and in the expander.

PRE-RUN uses the SAME SIX TRACKS (R1 is not conditional). Per R5 three things are absent, and
absence is expressed structurally rather than by placeholder glyphs:
  - the rail's 34px position sub-column is not rendered; the pathway sub-column expands to 156px and
the A/B marker stays;
  - columns 4 and 5 render EMPTY cells, and their two header cells are replaced by ONE header cell
spanning both tracks (376px), captioned "Not ranked yet" / "No agent has scored this hospital-day".
  No em dash, no zero, no "Not yet scored" repeated 308 times. The reason is stated once in the
header and once in the ordering-strip banner.
```

### Sticky chrome budget

```
STICKY CHROME - ONE BUDGET TABLE. Both prior 148px stacks are deleted; neither held. Measured from
the copy at the final type sizes. Every strip is one fixed height in EVERY state, so no state change
moves the list.

DESK (--row-h 48). Order top to bottom; all position:sticky.
| # | element | height | lines | worst-case string (measured) | running total |
| 1 | Context bar | 40 | 1 @14px | "St Brendan's / Sunday 30 August 2026 / 308 referrals" 51ch =
377px, + [Change hospital-day] 168 + clinician field 220 + [Run the agents for this hospital-day]
248 + 3x16 gaps = 1061 of 1248 | 40 |
| 2 | Scope line | 24 | 1 @12px | four clauses, 127ch = 813px of 1248 | 64 |
| 3 | Reconciliation ledger | 28 | 1 @12px | six terms joined by middots, 164ch = 1050px of 1248;
the "counts unavailable" variant is 185ch = 1184px, still one line | 92 |
| 4 | Ordering strip | 40 | 2 @12px | line 2 = ADR011_SHORT, 161ch = 1030px of 1248 | 132 |
| 5 | Column header | 40 | 2 @12px/600 | urgency header "Urgency" / "NEWS2 only / 6 vital signs"
25ch = 160px inside a 168px track | 172 |
TOTAL DESK CHROME = 172px. scroll-padding-block-start: 172px. Sticky band group headers: top: 172px.

PRESENT (--row-h 56, type +1 step): 44 + 28 + 32 + 48 + 44 = 196px. scroll-padding-block-start:
196px; group headers top: 196px.

WHAT WAS TAKEN OUT OF THE STACK TO MAKE IT HOLD (R3):
 - The urgency caveat is NOT a 56px header block. It is 0px in the sticky stack: the header carries
only "Urgency / NEWS2 only / 6 vital signs", and this cohort's measured figures (268 of 308 score 2
or less; 20 of the 84 marked Urgent score 0) live in the scope line's third-clause disclosure, which
opens BELOW the strip, pushes the list, and is not sticky.
 - The 2x14 hospital-day grid is NOT permanently in the bar. The bar carries the selected day in
words plus a "Change hospital-day" disclosure; the grid opens below the bar at full 24x24 cell size,
pushing the list. This is what makes both the 40px bar and WCAG 2.2 SC 2.5.8 true at once.
 - The full ADR-011 sentence (261ch, unavoidably two lines in a 1248px measure) is NOT in the strip.
The strip carries ADR011_SHORT on one line with a "[Why this matters]" text control appended;
ADR011_FULL opens as a non-sticky disclosure.
 - Every disclosure in the chrome (scope clauses, selector, ADR-011, tier "Why?") expands BELOW the
sticky stack and pushes content. None of them changes the 172px.

CONSEQUENCE FOR SC 2.4.11: scroll-padding-block-start equals the full 172px (196px present), tested
by keyboard traversal of all 308 rows, Home/End, PageUp/PageDown and the [ / ] boundary jumps - not
by inspection.
```

### Row metrics

```
ROW HEIGHT IS DERIVED FROM CONTENT (R2). 36px is deleted.

--row-h = 48px DESK (1280x720 and 1440x900) / 56px PRESENT (one token flip, the single lever named
in the open questions).
DERIVATION at 48: 4px top pad + line box A 24px + line box B 16px + 4px bottom pad = 48. Exactly TWO
lines per cell, never three.
DERIVATION at 56: 4 + 28 + 20 + 4 = 56, with type up one step (primary 15->17, secondary 12->13,
days numeral 20->22).

THE THIRD LINE EVERY PRIOR SPEC CARRIED IS CUT, not shrunk (R2's instruction: cut a line rather than
go below 12px):
 - Urgency cell loses "6 vitals cited". The citation count already exists in expander section 7's
role heading.
 - Waiting cell does not stack numeral / statement / meter. The 10px meter shares line box A with
the 20px days numeral (meter 140px left, numeral 92px right-aligned, both vertically centred in the
24px box); the target statement is line box B. Nothing in the row is below 12px.

DEPENDENT FIGURES, RE-DERIVED AT BOTH VIEWPORTS.
Element heights: band group header 40 desk / 44 present. Breach tier divider 32 / 36. Outside-the-
ranking heading block 80 / 88, opened by a 24px gap and a 3px rule. Row expander max-height 520 /
560. Pairwise dock 208 / 240. Inline reason strip 72 / 80.

1280x720 DESK, browser fullscreen (viewport height 720):
 - list viewport = 720 - 172 = 548px
 - first fold = Urgent group header (40) + rows 1-10 fully visible, row 11 clipped. (548 - 40) / 48
= 10.58.
 - dock open (208): list viewport 340 -> group header + 6 rows. (340 - 40) / 48 = 6.25. Both sides
of any adjacent pair plus four rows of context.
 - expander open (max 520): pushes the list, never overlays. The row plus its expander is 568px, so
an open expander fills the fold; sections 1-3 (359px, the safety core) sit above the expander's own
internal scroll fold.
 - total scroll height = 308x48 + 5x40 + 2x32 + 107 (24 gap + 3 rule + 80 tail heading) = 15,155px.
 - boundary jumps for [ and ]: SIX pre-run (5 group headers + tail heading), EIGHT once ranked (+2
tier dividers). Pre-run there is no tier divider, because pre-run order is referral_date and
breached rows are interleaved - see BreachTierDivider.

1280x720 PRESENT (--row-h 56):
 - list viewport = 720 - 196 = 524px
 - first fold = group header (44) + rows 1-8 fully, row 9 clipped. (524 - 44) / 56 = 8.57.
 - dock open (240): list viewport 284 -> group header + 4 rows. (284 - 44) / 56 = 4.28.
 - total scroll height = 308x56 + 5x44 + 2x36 + 115 = 17,655px.

1440x900 DESK: chrome unchanged at 172. list viewport 728 -> group header + 14 rows. (728 - 40) / 48
= 14.33. Dock open: 520 -> header + 10 rows. Content width 1408; the 160px surplus goes to "why this
position" only.

THE NUMBER THE DEMO NARRATIVE MUST NOW USE: ten rows above the fold at 1280x720, not fourteen. Ten
is still the right first impression, because 75 of the 84 Urgent referrals are past their 28-day
target, so the whole first fold is inside the past-target tier.
```

---

## 4. Screens

### S1 - Ranked list, the only route (/h/:hospital/d/:date)

**MUST** — Show every referral in one hospital-day in five band groups plus the named tail region, so a
clinician can see who is where, why, and what the instrument could not see - with or without
a run having happened.

**Regions**

```
Vertical stack. Sticky chrome 172px in five parts: context bar 40, scope line 24, reconciliation
ledger 28, ordering strip 40, column header 40. Below it the list, plain memoised DOM: 308 rows at
48px, 5 group headers at 40px, 2 tier dividers at 32px (ranked only), and the Outside-the-ranking
region opened by a 24px gap, a 3px rule and an 80px heading block. Total scroll height 15,155px. Six
column tracks at 1248px. Bottom dock 0 or 208px. The expander is an in-flow full-width row that
pushes the list. There is no page-level navigation anywhere in the product.
```

**Above the fold at 1280×720**

```
720 - 172 = 548px of list. Urgent group header (40) plus rows 1-10 fully visible, row 11 clipped:
(548-40)/48 = 10.58. That whole first fold sits inside the past-target tier, which is the right
first impression, because 75 of the 84 Urgent referrals are past their 28-day target. With the dock
open (208px): the group header plus 6 rows. At 1440x900: the group header plus 14 rows.
```

**States**

- PRE-RUN - today's only real state, verified: GET /decisions/9001/2026-08-30 returns 404
  and every hospital-day probed does the same. All 308 rows render grouped with every
  clinician-recorded fact, in referral_date order. Position, urgency and 'why this position'
  are ABSENT, not blank and not zero. No tier dividers (referral_date order interleaves
  breached and within-target rows). Six boundary jumps.
- RUNNING - identical geometry; the list does not reorder, gains no positions, and no row
  moves under the cursor. Urgency cells fill in place.
- RANKED - positions applied, groups re-sorted, tier dividers drawn, eight boundary jumps.
  Reached only by an explicit Show ranking click, never automatically.
- FILTERED - rows hidden, never reordered, never renumbered; the ledger and every affected
  group header state the count and that positions are unchanged.
- OVERRIDDEN / ACCEPTED - residue on rail line 2 at the same visual weight as any other row.
  Never an error state, never red.
- EMPTY - verified real: 2026-08-16 and 2026-08-31 return 200 with referrals: [].
- ERROR - the endpoint and status code in the ledger; the selector stays live.

**Interactions**

- Keyboard first: role=grid, aria-rowcount, aria-rowindex, roving tabindex on the ROW so the
  whole list is one tab stop.
- Up/Down or j/k; Home/End; PageUp/PageDown. [ and ] traverse the structure - six keypresses
  pre-run, eight once ranked, showing the entire list without narration. That is the
  projector navigation model.
- Enter/Right expand, Esc/Left collapse. c compare, a accept, m move, e evidence, r run, h
  hospital - all inert while a text field has focus.
- Alt+Left/Right move between the four action-rail controls inside the focused row.
- Ctrl+F / Cmd+F find-in-page works on all 308 rows because there is no virtualisation. A
  clinician types a pathway number and lands on it - a real clinical affordance, and worth
  saying in the demo.
- NO column sorting anywhere.

### S2 - Row expander, the evidence in place

**MUST** — Let a clinician independently review the basis for a position in plain language without
leaving the list, and see what the instrument could not see.

**Regions**

```
Full-width in-flow row beneath the expanded row, pushing the list. 16px inset, two 592px columns
with a 32px gutter (16+592+32+592+16 = 1248), max-height 520px desk / 560px present, overflow-y:auto
on the body only, 24px pinned identity header. Eight sections in a fixed reading order: left column
1-5 (593px), right column 6-8 (436px).
```

**Above the fold at 1280×720**

```
An open expander plus its own row is 568px against 548px of list viewport, so it fills the fold -
which is correct, because at that moment the expander is the content. Inside it, sections 1-3 total
359px and are guaranteed above the expander's own internal scroll fold: position and what decided
it, the waiting-target rule, and the six NEWS2 components with their total. That is the safety core,
visible without any scrolling of any kind.
```

**States**

- PRE-RUN - sections 2, 3, 4, 5 and 6 render FULLY from cohort plus one context call with no
  run at all. Sections 1 and 7 are present with their own explanatory sentence, never
  removed. This is most of the safety argument, available before any agent executes.
- LOADED - all eight sections.
- REFUSED - section 3 is replaced by the refusal statement, and section 4 still renders the
  six vital values with no sub-scores and no total, because PW-9001-000098 carries a
  recorded NEWS2 of 4 and hiding that would be less honest than the refusal.
- EVIDENCE-EMPTY WITH A DECISION HELD - defect authority, 3px left border.
- EVIDENCE-UNRESOLVED - the entry stays at full weight with its complete IRI printed.
- ERROR - sections 2, 4, 5 and 8 still render; section 3 names the failing endpoint with a
  retry.

**Interactions**

- Enter, Right or e opens; Esc or Left closes; focus returns to the row.
- Expanding permanently arms that row's Accept control for the session.
- Foot actions: accept, move inside the category, move across a boundary, compare with the
  row below, compare with the row above.
- Section 8 is a closed <details>; nothing inside it is ever surfaced on a row.

### S3 - Pairwise dock

**MUST** — Answer the question a clinician actually asks - among patients already marked equally
urgent, why is this one above that one - by decomposing the gap in the exact order the sort
key applies its terms.

**Regions**

```
208px bottom dock (240 present) spanning the full 1248px width: 28px identity band (A and B in two
612px halves with a 24px gutter), 118px steps band (three 400px columns with 24px gaps), 18px
computed closing sentence, 32px tie-warning and alpha-sensitivity band, 12px padding. Steps stack to
one column below 1000px.
```

**Above the fold at 1280×720**

```
The dock occupies the bottom 208px of the 548px list viewport, leaving the group header plus 6 rows
above it - both sides of any adjacent pair plus four rows of context. At present density: header
plus 4 rows. At 1440x900: header plus 10 rows.
```

**States**

- CATEGORIES DIFFER - step 1 decides; steps 2 and 3 render greyed and read 'Not reached'
  rather than being hidden.
- CATEGORIES TIE, TARGET STATE DIFFERS - step 2 decides and the ADR-011 open flag is
  repeated.
- BOTH TIE - step 3 renders the three-row arithmetic and the computed closing sentence.
- TIE WARNING - the common case, not the edge case: 87 of the 299 adjacent same-band same-
  tier pairs are two NEWS2-0 referrals.
- ALPHA SENSITIVITY - always shown once step 3 is reached, in one of two forms.
- PRE-RUN - steps 1 and 2 work in full; step 3 says no scores exist.
- EMPTY - 44px, one line explaining how to pin.

**Interactions**

- c compares the focused row with the row IMMEDIATELY BELOW - the adjacent pair is the
  question actually being asked.
- Shift+c pins A; Shift+Up/Down then walks B up and down the list with the arithmetic
  updating live. That is the demo move.
- A and B are marked by a letter in the rail's reserved 16px slot plus the row's accessible
  name - never a background.
- Esc closes. The dock never traps focus and never steals it from the list.

### S4 - Override, the one modal in the product

**MUST** — Let a clinician record their own order as a normal, expected, attributed act, while making a
move that breaks a named rule impossible to perform without reading the rule first.

**Regions**

```
Two weights, chosen by geometry and never by the clinician. In-band, in-tier: a 72px inline reason
strip beneath the row. Across a band or the breach tier: a native <dialog> at 620x520, reading order
heading -> disclosure (rule with real numbers, then both patients as a two-column table with
identical field order) -> attestation -> coded reason plus free text -> actions.
```

**Above the fold at 1280×720**

```
520px of dialog inside a 720px viewport leaves 100px of margin above and below. The whole reading
order - heading, rule, both patients, attestation, reason, actions - fits without scrolling, which
is what makes 'disclosure precedes attestation' true in practice and not just in DOM order.
```

**States**

- in-band-move - inline strip, no attestation, still writes POST /overrides.
- cross-band-move - RULE-ORDER named with both parties.
- cross-tier-move - the ADR-011 open-question framing, not a hard-rule framing.
- unranked-referral - from_position null, to_position set, table reads 'Not currently
  placed'.
- attestation-unchecked - the reason select is disabled.
- pre-run - Move is disabled with its own visible reason.
- post-failed - the row reverts, the endpoint and status are named, the typed text is
  preserved.
- recorded - residue on rail line 2, full reason in the expander.

**Interactions**

- m or o opens the appropriate flow. Shift+Up/Down reorders and opens the modal the moment a
  move crosses a boundary; it never silently commits.
- Focus trapped, returned to the moved row on close, Esc cancels without writing, a dirty
  form raises an inline confirm inside the same dialog.
- Exactly one showModal() call site in the bundle. The re-run guard, the stop-run confirm
  and every empty state are inline.

### S5 - Hospital-day selector

**MUST** — Move between the 28 hospital-days in one click and make coverage visible at a glance,
without spending permanent chrome on a control used once a minute.

**Regions**

```
A 'Change hospital-day' disclosure in the 40px context bar, opening a 2x14 grid BELOW the bar that
pushes the list. Cells 24x24 (SC 2.5.8), a real 20px day-number header row, two row labels, a 20px
legend line. Footprint about 486x88.
```

**Above the fold at 1280×720**

```
Collapsed, the selector costs 0px beyond the 40px bar it shares with the run control and the
clinician field. Open, it costs 88px and pushes the list down to 460px - the group header plus 8
rows still visible, so the reader never loses their place while switching.
```

**States**

- collapsed - the default
- expanded - the grid open below the bar
- all-outline - no hospital-day ranked in this session, and the state after an orchestrator
  restart
- out-of-range - 2026-08-16 and 2026-08-31 are reachable by URL edit and fall through to the
  empty-cohort state
- switching-with-run-in-flight - the poll aborts, the run continues server-side, and the
  copy says so rather than claiming a cancellation

**Interactions**

- Click a cell to switch; arrow keys inside the grid; h toggles hospital; [ and ] step the
  day only when focus is inside the grid.
- Switching aborts polls, clears list state, closes any open expansion, comparison or
  override, and refetches. A half-typed override reason is confirmed once before discarding.
- At most one request on mount and none per cell. Probing GET /decisions across the 28 cells
  is forbidden.

### S6 - Run and Show ranking

**MUST** — Start a scoring run and keep the clinician truthfully informed about what has and has not
been computed, without ever letting a partially-scored list read as a ranking.

**Regions**

```
One button plus a two-counter status line inside the 40px context bar; one inline band in the 40px
ordering strip on completion carrying Show ranking; a 44px delta sub-column borrowed from column 5
for exactly one refresh after the transition. No modal, no overlay, no spinner, no percentage.
```

**Above the fold at 1280×720**

```
Zero additional height at every run state - the counters live in the context bar and the completion
band lives in the ordering strip, both already in the 172px budget. The list keeps all 548px and all
ten rows throughout the run, which is the point: an 'about 30 seconds' wait never costs a useful
screen.
```

**States**

- idle / starting / running / stalled / one-agent-complete / scores-but-no-ranking / ready /
  decision / cancelled / failed / restarted
- re-run guard - an inline, non-modal confirm naming the true consequence: a second POST
  appends its placements to the graph alongside the first and the two cannot be told apart
  there

**Interactions**

- Click or r starts; Esc or the button stops polling.
- Show ranking is the ONLY way positions ever appear: one unstaggered 220ms FLIP over
  viewport rows only, transform and opacity only, keyed by pathway_number, pinning the
  reader's anchor row.
- Under prefers-reduced-motion the animation is disabled entirely and the delta column is
  the whole treatment.
- Numerals and meter widths never tween.

### S7 - State family

**MUST** — Make every state the product can actually be in say what is true, what is missing and what
to do next - in the same place, in the same voice, without a spinner standing in for an
explanation.

**Regions**

```
No separate screen. A banner in the ordering strip (no ranking yet), a 280px panel replacing the
list body only (empty cohort), a line in the reconciliation ledger (loading past 400ms, errors,
partial), and per-entry treatments inside the expander (unresolved evidence).
```

**Above the fold at 1280×720**

```
The pre-run state costs 0px of extra height: it is a banner on line 1 of a strip that is 40px in
every state, so all 308 rows and all ten above-fold rows survive. That is the whole reason it is a
banner and not a panel - a 200px panel announcing a normal state would cost four rows of the fold.
```

**States**

- no-ranking-yet - normal, today's state, the table fully rendered beneath
- empty-cohort - a real 200 with referrals: []
- network-or-http-error - endpoint and status code, verbatim
- unresolved-evidence - full weight, IRI printed
- partial - both numbers stated before any row is drawn

**Interactions**

- Every error state leaves the selector operable so another day can be tried without a
  reload.
- Nothing is dismissible; nothing auto-retries silently. Focus moves to the heading on state
  change with a polite announcement.

### S8 - Orchestrator service surface

**MUST** — Not a screen, but the surface every screen depends on: serve the built SPA same-origin,
launch and own runs, hold the decision it built, and know the difference between 'this run
has not started' and 'this run_id is wrong'.

**Regions**

```
One FastAPI container on :8080. StaticFiles mount serving web/dist at / with an index.html fallback.
Endpoints: GET /ui/cohort/{h}/{date}, GET /ui/decision/{h}/{date}, GET /ui/runs/{run_id}, GET
/ui/context/{h}/{pw}, POST /ui/runs, POST /ui/overrides, GET /ui/health. One module-level dict keyed
by run_id and one keyed by (hospital, date).
```

**Above the fold at 1280×720**

```
Not applicable. Its budget contribution is the 6-8 hours taken out of the 35 before the UI's ~27 are
counted.
```

**States**

- no run for this hospital-day - the normal state on a fresh container
- run in flight / run finished with the ranking held / agents finished but coordinator
  failed
- container restarted - all held state is gone; the UI falls back to pre-run and SAYS SO
  rather than pretending. In-memory is the right call at 35 hours; say out loud that it is
  in-memory

**Interactions**

- ONE process, ONE cohort fetch, ONE score fetch. Shell the coordinator CLI once to mint and
  POST 'dec-{uuid4()}' (the only way decision_id becomes reachable), then in the same
  request re-derive band, severity_rank, wait_normalised, priority and alpha by importing
  rank_cohort on the same referral dicts with the SAME capacity-direction value read from
  one shared constant. Assert the imported ordering equals the CLI's and refuse to serve the
  decision if it does not - --capacity-direction is required with no default, so two
  independent computations can silently diverge and let a clinician record an override
  against a position that is not the stored one.
- Import urgency_agent.run.run_for_cohort rather than shelling that agent, and read
  CohortRunResult's four bucket dicts directly; they are keyed by pathway_number, so per-row
  attribution comes free. Treat exit code 1 with a non-empty skipped dict as success-with-
  exclusions.
- Prefetch all 308 contexts once per hospital-day at first cohort request (~15ms each, about
  4.6s serially, inside container start) and serve news2 alongside the cohort. This is the
  single cheapest change in the whole plan: the full NEWS2 column, the distribution figures,
  the dock's tie warning and the expander's six sub-scores then all work with zero agents
  running, and the demo survives the run path never being built.
- The re-run guard lives here too: 409 with an explicit body unless confirm_duplicate=true.
  Every proxied error passes through with its upstream status code and endpoint so the UI
  can print the true string.

### S9 - Export, filters and ranked markers

**SHOULD** — Absorb surviving hours in the order that adds the most demo value per hour, with none of
them load-bearing.

**Regions**

```
An export control in the context bar, filter chips beyond the ledger's six terms, markers on the
selector grid.
```

**Above the fold at 1280×720**

```
Zero. All three are absent by default and nothing else changes shape when they are missing.
```

**States**

- absent-by-default

**Interactions**

- Filters hide rows and never reorder or renumber. No filter survives a hospital-day switch.

### S10 - Provenance graph route

**COULD** — Deferred and recorded, not built. The flat citation list answers the same question at a
fraction of the cost and renders correctly against today's empty evidence arrays.

**Regions**

```
If ever built: a second route assembled client-side from payloads already held, rendering exactly
the entries and strings of expander section 7.
```

**Above the fold at 1280×720**

```
Not applicable - not built.
```

**States**

- not-built

**Interactions**

- None. The entry point is a 12px note in the expander, not a disabled button.

---

## 5. Components

**25 MUST**, 3 SHOULD, 1 COULD. MUST totals **24h** against 26h available for one developer.

`strings` lists the canonical string ids the component renders. Every id resolves in
section 6; there are no dangling references and no orphans.

### MUST

#### OrchestratorService — 3h

The fifth compose service. One FastAPI app on :8080 serving web/dist same-origin at / and
proxying /api/* to retrieval on :8000 with the bearer token held server-side. Composes
urgency_agent.run.run_for_cohort, capacity_agent.run.run_for_cohort and the coordinator's
rank_cohort/build_ranking/build_decision in-process — no CLIs, no subprocesses, no exit
codes. Holds the decision, the score map, the run history and the override log in memory,
keyed on (hospital_hipe, as_of_date). Mints run_id and its own decision_id 'dec-{uuid4}'.
Multi-stage Dockerfile: node build of web/, then the Python image with dist/ copied in.

**Data**

- GET /api/cohort/{h}/{date} → proxies GET /hospitals/{h}/cohort/{date} (308 rows, 14
  fields, 111,331 bytes, measured 50ms) and JOINS news2 onto every row from the context
  prefetch. news2 is NOT in the cohort payload — verified.
- GET /api/context/{h}/{pw} → proxies GET /referrals/{h}/{pw}/context (~15ms). Prefetched
  once per hospital-day at ~4.6s serially, which is what makes the whole thesis visible pre-
  run.
- POST /api/runs {hospital_hipe, as_of_date} → {run_id, decision_id, started_at}. A PLAIN
  def, not async: both agents use synchronous httpx and an async handler starves the 1s
  poll. Progress denominator 616 = two agents × 308.
- GET /api/runs/{run_id} → {urgency_done, capacity_done, denominator 616, buckets,
  elapsed_s}. Reads CohortRunResult.scored / refused_paediatric / skipped /
  graph_projection_failed directly; all four are keyed by pathway_number.
- GET /api/decision/{h}/{date} → the held view model: position, band, severity_rank,
  crt_breached, urgency_score, news2, wait_normalised, priority, alpha, rule_checks,
  citations, excluded[]. NEVER retrieval's GET /decisions — with a decision present that
  call resolves every placement through ~1,500 sequential SPARQL round trips.
- POST /api/overrides → POST /overrides carrying the held decision_id. The graph IRI
  'decision/9001/2026-08-30' that GET /decisions returns is a different identifier and is
  rejected with 400.
- Empty-cohort guard re-implemented here: verified it exists only in coordinator/app/cli.py
  main(), which is never called. 2026-08-16 and 2026-08-31 return 200 with referrals: [].
- Runs restricted to 2026-08-30: get_referral_context takes no date and retrieval does ORDER
  BY as_of_date DESC LIMIT 1, so the evidence horizon is date-blind.

**States**

- cold — bundle served, no cohort fetched
- prefetching-contexts — 308 context calls, ~4.6s, inside container start
- idle — cohort and news2 held, no decision
- running — both agents in flight, counters advancing to 616
- held — decision, score map and override log in memory for (hospital, as_of_date)
- restarted — memory empty; reports no held run rather than pretending
- upstream-401 / upstream-5xx — surfaces the retrieval status and path verbatim

**Strings**

`RUN_STATUS`, `RUN_ERROR`, `RESTARTED`, `AUTH_ERROR`, `HTTP_ERROR`, `ORCH_UNREACHABLE`,
`EMPTY_COHORT`, `CTX_RUN_DISABLED_DATE`, `RUN_DATE_LOCK_BODY`, `RUN_EXIT_NOTE`

**Safety rule.** The bearer token never leaves this process and the browser never calls :8000, which has no
CORS middleware. The fixture score path is unreachable — fixture_scores uses built-in hash()
and is non-deterministic across processes; the orchestrator never passes
score_source=fixture, so PYTHONHASHSEED is not needed and is deleted. Refusals, skips and
graph-projection failures are carried through as four separate buckets and are never summed.

#### AppScaffoldAndDataLayer — 0.75h

Vite + React + TS in web/. One route /h/:hospital/d/:date plus a redirect from /. No router
beyond that, no <nav> in the DOM at any state. Two design tokens only: --row-h (48 desk / 56
present) and --type-step (0 / 1); plus --exp-gap (16px), the expander's inter-section gap,
published explicitly. One formatting module owns every number rendered anywhere.

**Data**

- All browser calls same-origin to /api/*. Endpoint names fixed here once and used verbatim
  by every component.
- Formatting rules: leading zero always; normalised urgency 3dp; signed contributions 3dp
  with an explicit + or −; wait days 0dp; row multiplier FLOORED to an integer; expander
  multiplier 1dp; units always attached; font-variant-numeric: tabular-nums on every numeric
  cell; numerics right-aligned, identifiers and prose left-aligned, nothing centred.

**States**

- boot — chrome renders immediately from the URL, no request returned
- cohort-resolved — the four clinician-recorded columns are live
- decision-held — columns 4 and 5 appear, the rail gains its position sub-column
- density-present — one token flip, no second stylesheet, no root-font-size toggle

**Strings**

`UNKNOWN_COUNT`

**Safety rule.** Every number passes through one module, so there is exactly one place a decimal count or
rounding rule can be wrong. The multiplier floors, never rounds: a row must never claim a
larger overshoot than it has.

#### RankedTableShell — 2.5h

One <table> with table-layout:fixed inside a single overflow-x:auto container. Six fixed
tracks 192/176/256/184/192/248 = 1248 inside 16px page gutters at 1280. Above 1440 the whole
surplus goes to track 5 only. Sticky left rail and sticky right action column carry a 1px
hairline plus an 8px inset shadow that appears only once scrollLeft > 0; the focus ring is
composited as per-cell inset box-shadow so it reads as one continuous 2px ring across both
frozen boundaries. Sticky chrome exactly 172px desk / 196px present; band group headers
position:sticky at that same top; scroll-padding-block-start and every row's scroll-margin-
block-start take the same figure. No zebra striping.

**Data**

- Pre-run rows: GET /api/cohort/{h}/{date} → referrals[]. Verified 9001/2026-08-30: 308
  rows; cpc 1=84, 3=81, 2=88, null=55, 4=0; crt_breached cpc1 {true 75, false 9}, cpc3 {true
  55, false 26}, null for cpc 2 and null; adjusted_wait_days 0..871, 213 distinct, 11 zeros;
  143 rows with crt_threshold_days null; 307 triaged / 1 awaiting_triage;
  currently_suspended false on all 308.
- Ranked rows: GET /api/decision/{h}/{date}. React key is pathway_number, never array index.
- All 308 rows in the DOM at all times. No virtualisation, no windowing, no overscan.

**States**

- pre-run — four content columns; tracks 4 and 5 empty under one merged 376px header cell;
  rail has no position sub-column; rows in referral_date order
- running — identical geometry plus track 4 filling in place; no positions, no reorder
- ranked — all six columns; positions applied only after Show ranking
- filtered — rows hidden, never reordered, never renumbered; aria-rowcount reflects the
  filtered count
- row-focused — 2px ring at ≥3:1 on the row, composited across both frozen edges
- row-expanded — a full-width expander row directly beneath, pushing subsequent rows down
- empty / error — the table body is replaced inside its own scroll container; chrome stays
  mounted

**Strings**

`COLH_RAIL`, `COLH_RAIL_PRERUN`, `COLH_CATEGORY`, `COLH_WAIT`, `COLH_URGENCY`, `COLH_WHY`,
`COLH_ACTIONS`, `COLH_PRERUN_MERGED`, `FIND_HINT`, `KEYBOARD_HINT`

**Safety rule.** No column sorting anywhere: no sort control, no aria-sort, no role/tabindex/click listener
on any <th>. Rows never reorder on a background poll and never move under the cursor — a row
that moves under the cursor is a mis-click on an override control. The only reordering is
Show ranking or a clinician's own recorded move.

#### BandGroupHeader — 0.75h

A 12px gap, a 2px full-bleed rule, then a 40px sticky header row (44 present) at the chrome
height. Line 1 at 15px/600: band name in words + CPC code + referral count + ranked count +
not-ranked count where non-zero + target in days. Line 2 at 12px: the breach split, and pre-
run the display-order sentence. Three redundant non-colour separators at once — gap, rule,
header text.

**Data**

- referrals[].cpc. Verified 9001: 84/81/88/55/0. Verified 9002 differs: 71/94/90/46/0.
  Nothing hardcoded.
- crt_threshold_days verified constant within band: 28 for all 84 cpc-1, 91 for all 81
  cpc-3, null for all 88 cpc-2 and all 55 cpc-null. Only two target values exist in the
  dataset.
- The ranked/not-ranked split is mandatory: the three paediatric refusals carry cpc 2, 2 and
  null, so Routine must read 86 ranked / 2 outside and No-category 54 ranked / 1 outside.
- triage_status: 307 triaged, 1 awaiting_triage (PW-DEMO-05, days_awaiting_triage 64 against
  RULE-TRIAGE-TURNAROUND's 21).

**States**

- urgent / semi-urgent / routine / no-category / excluded (0 rows, header RENDERS anyway)
- pre-run — line 2 carries DISPLAY_ORDER, the breach count and PRE_RUN_TIER_NOTE
- collapsed — the header states the count it is hiding
- filtered — LEDGER_FILTERED appended
- loading — counts render as an em dash, never 0

**Strings**

`GROUP_URGENT_L1`, `GROUP_URGENT_L2`, `GROUP_SEMI_L1`, `GROUP_SEMI_L2`, `GROUP_ROUTINE_L1`,
`GROUP_ROUTINE_L2`, `GROUP_NOCAT_L1`, `GROUP_NOCAT_L2`, `GROUP_EXCLUDED_L1`,
`GROUP_EXCLUDED_L2`, `GROUP_PRERUN_L2`, `GROUP_COLLAPSED`, `SEVERITY_NOTE`,
`UNKNOWN_NOT_LOW`, `PRE_RUN_TIER_NOTE`, `TRIAGE_RULE_FULL`, `LEDGER_FILTERED`,
`UNKNOWN_COUNT`

**Safety rule.** ADR-006: cpc null is UNKNOWN priority, not low priority, and cpc 4 Excluded is a different
thing again. Two tails, never merged. The zero-row Excluded header is the cheapest visible
proof the system keeps the distinction. Band identity must survive with every colour token
forced to one grey.

#### BreachTierDivider — 0.5h

A 32px full-width row (36 present) on the table grid: a 1px rule spanning tracks 2-5 only —
deliberately not crossing the frozen rails, so it reads as a property of the ordering rather
than a break in the patient list — with a 12px caption inset 8px from track 2's left edge
and a 13px 'Why?' control at a 24×24 target opening a 3-line inline disclosure (+60px).

**Data**

- Computed in the UI from the crt_breached transition within a band in ranked order.
  Verified for 9001/2026-08-30 by reproducing the committed sort key: CPC 1 after row 75 of
  84, CPC 3 after row 55 of 81.
- CRT_BREACHED_RANK {True:2, False:1, None:0} sits above priority in
  coordinator/app/ranking.py's sort_key.
- ADR-011, status OPEN.

**States**

- present-ranked — the only state it is drawn in; exactly two instances today
- ABSENT PRE-RUN — pre-run order is referral_date, so breached and within-target rows
  interleave and no single transition exists
- absent-all-outside / absent-all-within — the band header already says so
- not-applicable — CPC 2, no-category and Excluded, where crt_breached is null on every row
- expanded — the disclosure is open

**Strings**

`TIER_CAPTION`, `TIER_WHY`, `TIER_WHY_BODY`, `ADR011_FULL`, `PRE_RUN_TIER_NOTE`

**Safety rule.** Styled as a structural fact, never as an error, warning or defect token. Styling an
unresolved clinical question as a bug is its own misrepresentation — and ADR-011 is the
reason the ordering may not be described as final.

#### ReferralRailCell — 0.25h

192px sticky left, two lines. Line 1 ranked: 8 pad + 16px pin slot (13px/700 letter, empty
when unpinned, always reserved) + 4 + 34px position numeral right-aligned 15px tabular muted
+ 10 + 112px pathway_number left 13px tabular, never truncated + 8 pad = 192. Line 1 pre-
run: 8 + 16 pin + 4 + 156 pathway + 8 = 192, with the position sub-column not rendered. Line
2: specialty code then name, 12px muted. No patient name, date of birth, MRN or IHI anywhere
— GET /referrals/{h}/{pw}/context returns none and the interface must not imply it has them.

**Data**

- referrals[].pathway_number and referrals[].specialty_hipe. Verified mix 9001/2026-08-30:
  1800 n=98, 0300 n=64, 0600 n=54, 0100 n=44, 2600 n=29, 0700 n=16, 0601 n=3.
- position from the held decision only. A flat unique integer 1..305 across the whole
  decision, never restarted per group.
- Specialty names from core.ref_codes: 1800 Orthopaedics, 0300 Dermatology, 0600
  Otolaryngology (ENT), 0100 Cardiology, 2600 General Surgery, 0700 Gastro-Enterology, 0601
  Paediatric ENT.

**States**

- default — position, pathway, specialty
- pre-run — no position sub-column; pathway expands to 156px; the pin slot stays because the
  dock's steps 1 and 2 work pre-run
- outside-the-ranking — no position sub-column; visually-hidden NO_POSITION_ARIA. A dash in
  a right-aligned numeric column destroys the vertical scan and reads as a rank
- pinned-A / pinned-B — the letter renders and the row's accessible name gains it. That is
  the whole treatment: no background
- accepted — line 2 replaced by ACCEPTED_RESIDUE
- overridden — line 2 replaced by OVERRIDE_RESIDUE
- loading — a 108px and a 64px neutral block, no digits

**Strings**

`RAIL_SPECIALTY`, `NO_POSITION_ARIA`, `RAIL_PIN_A`, `RAIL_PIN_B`, `PIN_ARIA`,
`ACCEPTED_RESIDUE`, `OVERRIDE_RESIDUE`

**Safety rule.** Every string here is a stored field or a core.ref_codes label. No UI-side gloss, no invented
plain-English diagnosis, no ICD-10-AM dictionary anywhere in the bundle. The pathway number
is never truncated — it is the join key and the string a clinician reads aloud.

#### CategoryTimeframeChip — 0.5h

176px, two lines. Line 1 the chip: 24px tall, 8px horizontal padding, adjective in sentence
case at 13px/600 with the code appended. THREE form levels only: filled ground for Urgent,
outline for Semi-urgent, plain text for Routine / No category recorded / Excluded. Meaning
is carried by the words, printed in full in every case. Line 2: target status, plain text,
no ground, 12px.

**Data**

- referrals[].cpc, crt_threshold_days, crt_breached, triage_status, days_awaiting_triage —
  all from the one cohort call, no run needed.
- Verified counts: urgent-past 75, urgent-within 9, semi-past 55, semi-within 26, routine
  88, no-category 55, excluded 0. Exactly one awaiting_triage row, PW-DEMO-05 at day 64.

**States**

- urgent-past (75) / urgent-within (9)
- semi-past (55) / semi-within (26)
- routine (88) — line 2 'No target for this category'. Never a tick, never OK, never a
  success colour
- no-category (55) — no code appended, since there is no code to print. Never 'Low', never
  'Unassigned', never greyed out
- awaiting-triage (1) — a modifier on no-category; line 2 reads TRIAGE_LATE
- excluded (0 rows) — built, not rendered today

**Strings**

`CHIP_URGENT`, `CHIP_SEMI`, `CHIP_ROUTINE`, `CHIP_NOCAT`, `CHIP_EXCLUDED`, `TARGET_PAST`,
`TARGET_WITHIN`, `TARGET_AT`, `TARGET_NONE`, `TRIAGE_LATE`, `UNKNOWN_NOT_LOW`

**Safety rule.** Say which rule fired, by name: 'Past the 28-day target' beats 'overdue'. The within-target
state renders as neutral text and never as a success signal, because a passing CRT check
means only that RULE-CRT-URGENT did not fire and says nothing about the patient.

#### WaitTargetCell — 0.75h

256px, two lines, NO GRAPHIC. The square-root meter is deleted. LINE BOX A (24px): the days
count right-aligned in 92px at 20px/600 tabular — the largest numeral on the row — with the
remaining 140px of the 240px content track left empty so the numeral holds the same optical
position on every row. LINE BOX B (16px): the target statement at 12px. This cell gets the
visual dominance because 213 distinct adjusted_wait_days across 308 rows is the variable
that actually discriminates, against a NEWS2 column where 148 tie at exactly 0.

**Data**

- referrals[].adjusted_wait_days — verified 0 nulls, range 0..871, 213 distinct, 11 rows at
  exactly 0. Equals days_since_received, not days_since_referral.
- referrals[].crt_threshold_days — verified 28 | 91 | null only; 143 of 308 null.
- PW-9001-000208 at 871 against 28 = 31.107×, the cohort maximum. Floored to '31×'.
- AT-TARGET IS REAL: PW-9001-000020 has adjusted_wait_days 91 against crt_threshold_days 91
  with crt_breached false — the comparison is strictly greater-than. Verified as the only
  row at exactly 1.00×.
- 28 breached rows sit at or above 1.00× and below 2.00× (9 CPC-1, 19 CPC-3). PW-9001-000137
  at 30/28 = 1.07× renders days-over.
- currently_suspended verified false on all 308; the state is still built.

**States**

- past-target, 2.00× or above — line 2 gives the FLOORED integer multiplier. 2.9× renders
  '2×'
- past-target, 1.00× to under 2.00× (28 rows) — line 2 gives days over, because '1× the
  target' reads as compliant
- AT-TARGET, exactly 1.00× — line 2 reads TARGET_AT; never 'Within', never '1×', never a
  tick
- within-target (35 rows) — a state word, never a tick, never a success colour
- no-target (143 rows) — line 2 reads TARGET_NONE; line 1 still prints the days, because
  adjusted_wait_days is never null
- zero-wait (11 rows) — the literal '0 days' plus WAIT_ZERO_NOTE
- suspended (0 rows here) — line 2 reads 'Clock suspended', as a word, never an icon
- loading — one neutral block

**Strings**

`WAIT_DAYS`, `WAIT_MULTIPLE`, `WAIT_DAYS_OVER`, `WAIT_WITHIN_DAYS`, `TARGET_AT`,
`TARGET_NONE`, `WAIT_ZERO`, `WAIT_ZERO_NOTE`, `WAIT_SUSPENDED`, `WAIT_ARIA`

**Safety rule.** With the meter gone the words carry everything, which is what F17 always required. The
multiplier is FLOORED, never rounded: a row must never claim a larger overshoot than it has.
Nothing in this cell is below 12px.

#### UrgencyNews2Cell — 0.5h

184px, exactly two lines. LINE 1 is primary and hand-checkable: 'NEWS2 1 of 17' at 15px/600
tabular — the denominator is always printed because NEWS2_MAX is 17 (temperature's top band
is 2, every other component's is 3). LINE 2 demotes the computed value: 'normalised 0.075'
at 12px muted, always 3dp. NO bar, meter, gauge, ring, sparkline, colour ramp or confidence
indicator, at any state.

**Data**

- news2 joined onto the cohort row by the orchestrator from the context prefetch. Not in the
  cohort payload — verified 14 fields, no vitals.
- Distribution measured first-hand from all 308 contexts: 0→148, 1→85, 2→35, 3→26, 4→8, 5→3,
  6→2, 7→1. 268 of 308 (87.0%) score 2 or less. Of the 84 clinician-marked Urgent, 20 score
  0 (23.8%) and 58 score 2 or less. Exactly one observation per referral for this hospital-
  day.
- urgency_score is the calibration of news2, anchors (0,0.000) (4,0.300) (6,0.600)
  (7,1.000), linear between, saturating above 7. NEWS2 1 maps to exactly 0.075. Only eight
  values are reachable on this data. 0.08 is a different number and appears nowhere.

**States**

- scored
- scored-zero (148 rows) — structurally IDENTICAL to any other scored value. Never blank,
  never an em dash, never labelled low urgency, not urgent, low risk, stable, normal or no
  concern
- awaiting (mid-run) — AWAITING_AGENT at 13px, line 2 absent. Not a zero and not an empty
  cell
- refused (3 rows) — NOT_SCORED / REASON_PAEDIATRIC
- skipped (0 rows here, built) — NOT_SCORED / REASON_NO_OBSERVATION
- evidence-unresolved — the score renders normally on line 1; line 2 becomes
  REASON_UNRESOLVED
- PRE-RUN — the whole column is absent, not blank and not filled with 308 placeholders

**Strings**

`NEWS2_LINE`, `NORMALISED_LINE`, `NEWS2_ZERO_ARIA`, `NOT_SCORED`, `REASON_PAEDIATRIC`,
`REASON_NO_OBSERVATION`, `REASON_UNRESOLVED`, `AWAITING_AGENT`, `COLH_URGENCY`

**Safety rule.** FDA CDS Criterion 4: 'NEWS2 1 of 17' is hand-checkable against six printed sub-scores; a
normalised 0.075 never can be, which is why the integer is primary and the normalised value
is demoted. This cell is deliberately NOT the largest thing on the row — the waiting-time
numeral is.

#### WhyThisPositionCell — 0.75h

192px (352px at 1440), two lines, no graphic. LINE 1 at 13px is the verdict in words. LINE 2
at 12px muted names the foil. Signed arithmetic appears ONLY in the dock and the expander,
never on a collapsed row.

**Data**

- The foil is the adjacent row in the ordered array the orchestrator holds — same band, same
  breach tier. Read at render time, never hardcoded: verified the star case's foil is
  PW-9001-000026 at alpha 0.7, PW-9001-000009 at 0.5 and PW-9001-000138 at 0.9.
- The verdict is decided by the sign and magnitude of alpha·(u_this − u_foil) against
  (1−alpha)·(w_this − w_foil); the numbers themselves are not printed here.
- Verified frequency: of the 299 adjacent same-band same-tier pairs, 87 have both referrals
  at NEWS2 0 and therefore urgency 0.000, so 'Ahead on waiting time' with a zero urgency
  term is the commonest verdict on this cohort.

**States**

- ahead-on-wait / ahead-on-news2 / ahead-on-both
- tier-boundary — VERDICT_TIER / VERDICT_NO_SCORES
- band-boundary — VERDICT_BAND / VERDICT_NO_SCORES
- last-in-tier — compared against the row ABOVE, and line 2 says so
- outside-the-ranking — the cell is empty; there is no position, so no comparison exists
- PRE-RUN — the whole column is absent

**Strings**

`VERDICT_WAIT`, `VERDICT_NEWS2`, `VERDICT_BOTH`, `VERDICT_TIER`, `VERDICT_BAND`,
`VERDICT_NO_SCORES`, `FOIL_LINE`, `FOIL_ABOVE`

**Safety rule.** rationale_summary is never rendered here or anywhere on a row. All 308 strings end with the
same clause about capacity weighting, generated by a single midpoint test on alpha, so it
describes a hospital-day parameter and not this patient — and it would contradict the honest
contribution arithmetic printed two inches away in the dock.

#### ContributionDisplay — 0.5h

A three-row four-column table at 15px tabular, fixed 3dp, right-aligned, with an explicit +
or − on every figure. Rows in fixed order: urgency contributed, waiting contributed,
composite priority. Columns A, B, difference. Header row 18px, body rows 18px each — 72px
total. Below it one computed closing sentence at 13px. Rendered inline in the dock's step 3,
and behind the EXP_S1_ARITHMETIC disclosure in expander section 1, so the two surfaces can
never disagree. Contribution to a DIFFERENCE, never a share of a total, never alpha as a
bare coefficient.

**Data**

- alpha, urgency_score and wait_normalised from the held decision. priority =
  alpha·urgency_score + (1−alpha)·wait_normalised. wait_normalised is percentile rank WITHIN
  BAND with ties sharing the rank, (count_less + count_equal/2)/n, per ADR-010.
- Worked pair reproduced first-hand at alpha 0.7 against live data: PW-9001-000208 (NEWS2 1,
  u 0.075, 871 days, w 0.9940, p 0.3507) sits directly above PW-9001-000026 (NEWS2 3, u
  0.225, 205 days, w 0.6250, p 0.3450). Waiting contributes +0.111, NEWS2 contributes
  −0.105, net +0.006.
- ADR-010 promises wait_normalised is never displayed as a bare number. Honoured: it appears
  only as a signed contribution and as PERCENTILE_SENTENCE — the correct wording, because
  ties share the percentile so the longest wait in an 84-row band scores 0.994, not 1.000.

**States**

- computed — both terms shown with their signs, including the negative one, never suppressed
- refused — the pair is separated by a band or a tier: the table is NOT rendered and
  CONTRIB_REFUSED replaces it
- pre-run — no scores exist; the table is absent and says so

**Strings**

`CONTRIB_ROW_U`, `CONTRIB_ROW_W`, `CONTRIB_ROW_P`, `CONTRIB_COLS`, `CONTRIB_CLOSING`,
`HAND_CHECK`, `CONTRIB_REFUSED`, `CONTRIB_PRERUN`, `PERCENTILE_SENTENCE`

**Safety rule.** There is NO fused priority score, AI score, triage score or risk score column anywhere in
the product. A single number implies a measured quantity with real variance when 148 of 308
of its urgency inputs are exactly 0.000, and it is not comparable across bands or breach
tiers because both sit above priority in the sort key.

#### ActionRail — 0.75h

248px sticky right, 232px content, two line boxes. LINE BOX A (24px): four controls left to
right at 13px with 8px horizontal padding, each 24px tall — Compare 64 / Accept 72 / Move 46
/ disclosure 24, separated by 8px gaps = 230 of 232. Accept is sized at 72 so 'Accepted'
fits without reflow. The disclosure is a 24×24 chevron whose accessible name is 'Show
evidence' and whose state is carried by aria-expanded. LINE BOX B (16px): the disabled-
reason line at 12px, rendered only when a control is disabled, empty otherwise, never
collapsing the row.

**Data**

- Enabled/disabled derives from: whether a decision is held (Move), whether this row's
  evidence has been rendered at least once this session (Accept), and whether the row is in
  the Outside-the-ranking region (Accept).
- Disabled reasons measured against the 232px track: ACCEPT_DISABLED_UNEXPANDED 211px,
  MOVE_DISABLED_PRERUN 230px, ACCEPT_DISABLED_UNRANKED 179px. All fit on one line at 12px.

**States**

- default-ranked — all four enabled
- pre-run — Move disabled with MOVE_DISABLED_PRERUN, Accept disabled with
  ACCEPT_DISABLED_UNEXPANDED; Compare and disclosure enabled, because the dock's steps 1 and
  2 work with no run
- unexpanded — Accept disabled; one expansion arms it permanently for that row; Move is
  NEVER gated
- outside-the-ranking — Accept disabled with ACCEPT_DISABLED_UNRANKED; Move ENABLED, because
  from_position and to_position are both optional in OverrideIn and a clinician may still
  record a reason
- accepted — Accept becomes a disabled label reading 'Accepted'; the timestamp goes to rail
  line 2
- submitting — an inline 12px progress label; no spinner, no overlay

**Strings**

`ACT_COMPARE`, `ACT_ACCEPT`, `ACT_ACCEPTED`, `ACT_MOVE`, `ACT_DISCLOSURE_ARIA`,
`ACCEPT_DISABLED_UNEXPANDED`, `ACCEPT_DISABLED_UNRANKED`, `MOVE_DISABLED_PRERUN`,
`SUBMITTING`

**Safety rule.** Overriding is never harder to reach than accepting. Move is ungated at every state where a
position exists, while Accept requires one expansion. If overriding is harder than
accepting, the human-in-the-loop claim is cosmetic.

#### AcceptAction — 0.25h

No surface of its own. It is the Accept control's behaviour plus the residue it leaves on
rail line 2. No dialog, no confirm, no reason field — friction on accept trains people to
click past the friction that matters.

**Data**

- POST /api/overrides → POST /overrides with from_position == to_position (the row's current
  position), reason exactly ACCEPT_WIRE, rule_warning_accepted false, plus override_id (UI-
  generated), decision_id (held by the orchestrator), hospital_hipe, pathway_number,
  clinician_id. The live OverrideIn schema permits this: from_position and to_position are
  optional and nullable, reason has minLength 1 and is non-blank here.
- The orchestrator keeps the override log in memory keyed by (hospital, date, pathway) and
  serves it with the decision, so the UI renders residue without re-reading anything.
- There is no accept endpoint in the 11-path API; POST /overrides is the only write path
  that exists.

**States**

- armed — the row's evidence has been rendered at least once this session
- recorded — the control becomes the disabled label 'Accepted' and rail line 2 reads
  ACCEPTED_RESIDUE
- survives a hospital/date switch and a re-render, because the UI refetches the override log
  on every route change
- DOES NOT survive an orchestrator restart — the log is in memory, and the ledger says so in
  words rather than silently showing an unaccepted list
- failed — no residue, the control returns to 'Accept', and the failure names the endpoint
  and status code

**Strings**

`ACCEPT_WIRE`, `ACCEPTED_RESIDUE`, `ACT_ACCEPTED`, `RESTARTED`, `OVERRIDE_FAILED`,
`CTX_ATTRIBUTION_NOTE`

**Safety rule.** Accepting never requires a reason and never opens a dialog. The whole interruption budget is
spent once, on the band- or tier-crossing override. A row that looks accepted after a failed
write is a lie about what is recorded.

#### RowEvidenceExpander — 2.75h

A full-width row inserted directly beneath the expanded row, PUSHING the list down, never
overlaying. Opening it scrolls its row to the top of the list viewport (scroll-margin-block-
start 172px desk / 196px present). 16px inset each side, SINGLE column 1216px, text measure
capped at 68ch. max-height 520px desk / 560px present, overflow-y:auto on the body only; a
24px pinned header restates the pathway number. EIGHT sections in a FIXED order, none
renameable, none droppable, at 74 / 140 / 202 / 150 / 230 / 92 / 256 / 24 with a 16px inter-
section gap published as --exp-gap. Sections 1-3 = 448px inside the 496px body, so the
safety core clears the internal fold.

**Data**

- Section 3 recomputes all six sub-scores client-side from the committed rubric and MUST
  equal the stored news2. Verified for PW-9001-000208: rr 17→0, spo2 99→0, sbp 140→0, hr
  108→1, avpu A→0, temp 36.4→0, total 1. Rubric traps: sbp is NOT a descending ladder (≥220
  scores 3, same as ≤90); avpu is binary (A→0, V/P/U→3); temp's top band is 2, which is why
  NEWS2_MAX is 17; temp arrives as a JSON string and must be parsed.
- Section 4 binds observations[-1].pain, .dbp, .mts_category and conditions[] primary —
  verified 10, 94, orange and C43.9 on the star case. All four are in the record and outside
  the six NEWS2 inputs.
- Section 5 lists EVERY condition (verified 408 rows across 308 referrals: 208 have one, 100
  have two), condition_label always the code written out and snomed_ct_id null on all 408,
  plus mts_category with its measured split and chiefcomplaint null on all 308 observations.
- Section 6 binds alpha and recomputes both endpoint orderings client-side: 272 of 305 move
  between 0.500 and 0.900, largest single move 51 places, star at 10 / 15 / 34. Two
  multiplications, no endpoint, never hardcoded.
- Section 7 uses the held decision's citations first and GET /api/evidence only as a
  fallback. The coordinator emits exactly ONE urgency citation (the score node), not six;
  multi_list is never emitted at all, so its group is structurally zero forever and is
  labelled as such. The three ward bed_status nodes are the capacity citations, verified for
  specialty 0300: W-9001-03 79.12% G, W-9001-01 89.01% G, W-9001-02 98.91% R with 7 outliers
  and 3 awaiting admission over 24h. occupancy_pct arrives as a STRING and is
  occupied/(occupied+free) — W-9001-02 has nominal 45 against occupied 91.
- Section 8 binds rationale_summary and rule_checks. Do NOT bind GET
  /referrals/{h}/{pw}/wait-counters: re-verified today it returns 404 for a referral that IS
  in that date's cohort.

**States**

- collapsed — the default for every row
- loading — sections 2, 4, 5 and 8 render immediately from data already held; section 3
  shows six neutral rows; section 7 shows CITATION_RESOLVING
- loaded — all eight sections
- PRE-RUN — sections 2, 3, 4 and 5 render FULLY from cohort plus news2 with no run at all.
  Sections 1, 6 and 7 are present with their own explanatory sentence, never removed — the
  fixed order IS the safety argument
- refused — section 3 is replaced by EXP_S3_REFUSED, but section 4 STILL RENDERS the six
  vital values with no sub-scores and no total
- recompute-disagreement — EXP_S3_DISAGREE; neither number is shown as the answer
- evidence-empty-with-decision-held — defect authority, 3px left border
- evidence-unresolved — the entry stays at full weight with its complete IRI as visible text
- error — sections 2, 4, 5 and 8 still render; section 3 names the failing endpoint with a
  retry

**Strings**

`EXP_PINNED_HEADER`, `EXP_H1`, `EXP_H2`, `EXP_H3`, `EXP_H4`, `EXP_H5`, `EXP_H6`, `EXP_H7`,
`EXP_H8`, `EXP_S1_POSITION`, `EXP_S1_VERDICT`, `EXP_S1_ARITHMETIC`, `EXP_S1_PRERUN`,
`EXP_S2_RULE`, `EXP_S2_FIRED`, `EXP_S2_NOT_FIRED`, `EXP_S2_NO_RULE`, `EXP_S2_TIER`,
`RULE_NOT_FIRED`, `EXP_S3_TOTAL`, `EXP_S3_VITAL_ROW`, `EXP_S3_VITAL_LABELS`,
`EXP_S3_DISAGREE`, `EXP_S3_NORMALISE_CONTROL`, `CALIBRATION_NOTE`, `EXP_S3_REFUSED`,
`EXP_S3_LOADING`, `EXP_S3_ERROR`, `EXP_S4_SENTENCE_LOW`, `EXP_S4_SENTENCE_HIGH`,
`EXP_S4_PAIN`, `EXP_S4_DBP`, `EXP_S4_MTS`, `EXP_S4_CONDITION`, `EXP_S4_ABSENT`,
`EXP_S5_CONDITION_ROW`, `CONDITION_PROVENANCE`, `EXP_S5_MTS_ROW`, `MTS_PROVENANCE`,
`EXP_S5_ICTS`, `CAPACITY_LIMIT_AND_EFFECT`, `CAPACITY_PRERUN`, `EXP_S7_ROLE_URGENCY`,
`EXP_S7_ROLE_TIMEFRAME`, `EXP_S7_ROLE_CAPACITY`, `EXP_S7_URGENCY_ONE_NOTE`,
`MULTILIST_ZERO`, `GRAPH_DEFERRED`, `EXP_S8_SUMMARY`, `EXP_S8_RULE_CHECKS`, `EXP_S8_IDS`,
`RATIONALE_DEFECT`, `ADR011_FULL`, `TAIL_NEWS2_NOTE`, `PERCENTILE_SENTENCE`

**Safety rule.** Section 4 is the point of the product: what the instrument could not see. It is never
collapsed by default, never behind a disclosure and never reordered. All six NEWS2 sub-
scores are always shown, including the ones scoring 0, because a normal vital is evidence of
normality and not an absence of evidence. If the recomputed total ever disagrees with the
stored value the screen says so rather than silently showing either number.

#### CitationChip — 0.25h

A 32px two-line entry inside a role group: line 1 the resolved fact at 13px, line 2 the IRI
at 12px monospace, middle-ellipsised at 420px with the full string revealed on focus and
always selectable. Role groups appear in the fixed order Urgency, Timeframe, Capacity,
Multi-list, each with a count in its heading.

**Data**

- Held decision citations[] = {role, iri, type, properties}, roles urgency | capacity |
  timeframe | multi_list.
- GET /runs/{run_id}/.../scores citations are a DIFFERENT, unresolved shape ({evidence_type,
  evidence_key}) with no properties — render as CITATION_RESOLVING and never fabricate a
  fact from a key.
- GET /evidence/{h}/{date}/{pw} accepts a role query parameter; section 7 uses ONE unscoped
  call. Verified today it returns 200 with an empty evidence array, because no decision
  exists yet.

**States**

- resolved — fact plus IRI
- unresolved — type null and empty properties: the entry stays at full weight with the
  complete IRI printed as visible DOM text. Never dropped, never blank, never counted out of
  the role's total
- structurally-empty — the multi_list group, zero on every row forever, labelled as such
- resolving — the unresolved shape from the scores endpoint
- empty-array-no-decision — CITATION_EMPTY_NO_DECISION
- empty-array-decision-held — CITATION_EMPTY_DEFECT, defect authority with a 3px left border

**Strings**

`CITATION_FACT`, `CITATION_UNRESOLVED`, `CITATION_RESOLVING`, `CITATION_EMPTY_DEFECT`,
`CITATION_EMPTY_NO_DECISION`, `MULTILIST_ZERO`

**Safety rule.** Retrieval deliberately refuses to drop an unresolvable citation; the UI mirrors that refusal
exactly. An audit trail with a silently missing entry is worse than one that says it is
broken. The empty array is AMBIGUOUS between 'no decision' and 'audit trail broken' and is
disambiguated from the orchestrator's own knowledge of whether it holds a decision — never
guessed.

#### OutsideRankingRegion — 0.5h

Below the Excluded band header, opened by a 24px gap and a 3px full-bleed rule — double a
band separator, because it is a different KIND of boundary. An 80px heading block (88
present): line 1 at 17px/600 states the region and the count, line 2 at 13px states the two
negatives, lines 3-4 at 12px carry the coverage paragraph. Then rows on the SAME six tracks
at the same row height. No dashed borders, no hatched insets, no border-style coding: the
region has a name, and a name at 17px beats a 1px dash pattern at projector distance. Never
collapsible.

**Data**

- specialty_hipe == '0601'. Verified exactly 3 rows in 9001/2026-08-30: PW-9001-000098 (cpc
  2, 330 days, NEWS2 4), PW-9001-000146 (cpc 2, 101 days, NEWS2 0), PW-9001-000024 (cpc
  null, 70 days, NEWS2 0). All three carry crt_threshold_days null and mts_category null,
  and carry icts_category instead (green, green, yellow). 9002 has 6 such rows — never
  hardcode 3.
- The three rows are verified NON-CONTIGUOUS in cohort order (indices 57, 193, 220), which
  is precisely why in-place rendering would scatter them through Routine and No-category
  with no warning to a scanning clinician.
- Membership comes from the urgency agent's refused_paediatric bucket when a run exists, and
  from specialty_hipe pre-run. Both give the same 3 rows here; the heading says which source
  it used.
- CRITICAL: the coordinator stamps exclusion_reason 'missing_urgency_score' on EVERY
  exclusion regardless of cause, so paediatric refusal, no-observation and graph-projection
  failure all arrive with the same string. Attribution must come from specialty_hipe plus
  the agent's four-bucket report; anything the orchestrator cannot attribute renders under
  its own sub-heading.

**States**

- paediatric-refusal — the three verified rows with the coverage statement
- unexplained-absence — its own sub-heading and count, NEVER merged into the paediatric
  count
- no-observation — its own sub-heading, its own words and its own action. 0 rows here; built
- pre-run — the region STILL RENDERS, because the refusal is a property of the specialty,
  not of the run
- empty — the region is absent entirely and the ledger's fourth term reads 0
- loading — the heading renders with an em-dash count, never 0

**Strings**

`TAIL_HEADING`, `TAIL_SUBLINE`, `TAIL_BODY`, `TAIL_SOURCE_RUN`, `TAIL_SOURCE_PRERUN`,
`TAIL_NEWS2_NOTE`, `TAIL_SUB_NO_OBS`, `TAIL_SUB_UNEXPLAINED`, `TAIL_UNEXPLAINED_BODY`,
`NO_POSITION_ARIA`, `UNKNOWN_COUNT`

**Safety rule.** A refused referral must never sort to the bottom as if it were low priority, and the
region's own copy has to say that out loud, because a tail position is exactly what a reader
will misread it as. Their category chip and wait figures render fully and at normal weight,
because those are clinician-recorded facts and refusing to score someone does not unrecord
them. PW-9001-000098's NEWS2 of 4 is stated, not hidden.

#### ReconciliationLedger — 0.5h

ONE 28px line (32 present) pinned under the ordering strip, all figures tabular, six terms
in fixed order separated by a middot and 12px of space, never by colour, each a filter
toggle at a 24×24 target (12px text with 6px vertical padding). The six-term ranked string
measures 164 characters = 1050px of the 1248px track; the counts-unavailable variant is 185
characters = 1184px. Both hold on one line in every state.

**Data**

- Term 1 cohort length. Term 2 pathways carrying an 'urgency' key in the orchestrator's held
  score map. Term 3 placements in the held decision. Terms 4-6 from the urgency agent's own
  four-bucket CohortRunResult, captured in-process by the orchestrator.
- 'skipped' and 'graph_projection_failed' are NOT separable from any retrieval endpoint — an
  absent pathway in GET /runs/.../scores is just absent. Without the agent's report those
  two counts render 'unavailable', never 0.
- Verified 9001/2026-08-30: 308 in cohort, 3 with specialty_hipe 0601, so 305 scored and 305
  placed.

**States**

- pre-run — only terms 1, 4 and the not-reported terms are honest; LEDGER_PRERUN asserts
  nothing no source reported
- running — LEDGER_RUNNING
- ranked — all six terms, and the arithmetic adds up on screen
- filtered — a second 11px line states the fraction; the strip says positions are unchanged
- mismatch — defect authority, 3px left border, both numbers named
- loading — every count renders as an em dash, never 0
- error — the line reads that the counts are unknown and names the failing upstream endpoint

**Strings**

`LEDGER_1`, `LEDGER_2`, `LEDGER_3`, `LEDGER_4`, `LEDGER_5`, `LEDGER_6`, `LEDGER_PRERUN`,
`LEDGER_RUNNING`, `LEDGER_UNAVAILABLE`, `LEDGER_MISMATCH`, `LEDGER_FILTERED`,
`LEDGER_ERROR`, `LOADING`, `PARTIAL`, `UNKNOWN_COUNT`, `RUN_EXIT_NOTE`

**Safety rule.** The six terms are verbatim and fixed in EVERY state. The four not-ranked categories get
separate labels, separate counts and separate destinations and are never summed into one
'excluded' figure — ADR-007 raises different exception types precisely so that 'we
deliberately do not cover paediatrics' and 'some rows are broken' never look alike. A 0 that
no source reported is a false claim about the cohort.

#### OrderingStripAndPreRunBanner — 0.75h

Exactly TWO lines at 12px in a fixed 40px strip (48 present), in EVERY state, so no state
change moves the list. Line 1 says what the current order is and where it came from; ranked,
it carries the content the deleted decision header used to hold. Line 2 carries the standing
caveat about the ordering rule, with a [Why this matters] control appending ADR011_FULL as a
non-sticky disclosure below the stack. Never a badge, never an icon, never amber, never
role=alert.

**Data**

- rule_checks from the held decision. RULE-TIEBREAK's real promise per ADR-013 is earlier
  referral date first among referrals ALSO tied on category, target breach and score —
  verified in the committed sort key (band_order, severity_rank, −crt_rank, −priority,
  referral_date, pathway_number).
- ADR-011 verbatim from conductor/tracks/coordinating-agent_20260906/decisions.md line 332,
  status OPEN.
- There is no 'checked 14:02' timestamp field anywhere in the data contract; no timestamp is
  fabricated.
- Alpha is NOT printed here. It appears only in expander section 6, with both endpoints of
  its documented range and the outcome each produces.

**States**

- pre-run — line 1 = PRE_RUN (the banner, not a panel: the 308-row cohort stays fully
  rendered beneath it), line 2 = DISPLAY_ORDER
- running — line 1 = RUN_STATUS, line 2 = DISPLAY_ORDER, because the list is still in
  referral-date order
- ready — line 1 gains SHOW_RANKING inline plus SHOW_RANKING_READY
- ranked — line 1 = ORDER_RANKED, line 2 = ADR011_SHORT with the [Why this matters] control
- rule-fired — the strip names the rule and marks the PAIR of rows involved, drawing a
  connector between them
- re-run confirm — the inline, non-modal confirm appears here
- error — the endpoint and the status code, verbatim

**Strings**

`PRE_RUN`, `DISPLAY_ORDER`, `ORDER_RANKED`, `RULE_LINE`, `ADR011_SHORT`, `ADR011_WHY`,
`ADR011_FULL`, `SHOW_RANKING`, `SHOW_RANKING_READY`, `RERUN_CONFIRM`, `RERUN_YES`,
`RERUN_NO`, `RUN_ERROR`, `SELECTOR_SWITCH_MIDRUN`

**Safety rule.** The ordering is presented as provisional, not final, for as long as ADR-011 is open. No
surface may describe the ranking as clinically prioritised or signed off. The pre-run state
is a BANNER, not a panel — a 200px panel that pushes 308 valid rows down to announce a
normal state is exactly the wrong emphasis.

#### ScopeLine — 0.5h

A 24px strip (28 present), four clauses at 12px separated by middots, each a keyboard-
reachable text control at a 24px minimum target. Activating a clause expands a 13px/20px
disclosure BELOW the strip, in place, pushing the list — never a modal, never a navigation,
never sticky, and it does not change the 172px. No dismiss control, no close control, ever.
Baked into every export and screenshot.

**Data**

- Two populations, each with its own denominator, never merged: THIS hospital-day (268 of
  308 score NEWS2 2 or less; 20 of the 84 marked Urgent score 0, 23.8%) and BOTH hospitals
  on 30 August (48 of 155 Urgent score 0, 31.0%). Both re-measured first-hand.
- Paediatric: 3 rows of 308 here, 6 of 301 on 9002, specialty 0601, ADR-007.
- The urgency agent's dataset-wide calibration figures use a different denominator (609
  observations in data v1.1) and are deliberately kept out of these strings.

**States**

- default — four clauses collapsed
- expanded — one clause open below the strip, adding 72-120px and pushing the list; only one
  open at a time
- export — baked into rendered output, not dismissible, not collapsible
- loading / empty / error — unchanged. The strip's claims do not depend on any request
  succeeding, which is the point of putting them in chrome

**Strings**

`SCOPE_LINE`, `SCOPE_C1`, `SCOPE_C1_BODY`, `SCOPE_C2`, `SCOPE_C2_BODY`, `SCOPE_C3`,
`SCOPE_C3_BODY`, `SCOPE_C4`, `SCOPE_C4_BODY`, `EXPORT_FOOTER`

**Safety rule.** EU AI Act Art. 14(4)(b) requires the interface keep the person exercising oversight aware of
the tendency to over-rely on the output; a plain, permanent statement of what the system
does not do is the cheapest way to satisfy that at the point of use. For the pitch and not
the UI: Annex III 5(d) names emergency healthcare triage and this system orders an elective
outpatient waiting list, so asserting 5(d) is an overclaim — the defensible posture is
designed-to Art. 13 and Art. 14 without asserting a classification.

#### ContextBarAndHospitalDaySelector — 0.75h

A 40px bar (44 present), one line at 14px: the selected hospital-day in full words, then a
'Change hospital-day' disclosure control, then the clinician-id text input, then the run
control. Worst case measures 1061px of 1248. The SELECTOR ITSELF is the disclosure: a 2×14
grid opening BELOW the bar, pushing the list, 24×24px cells (SC 2.5.8), day numbers 17-30 as
a real 20px header row, two row labels — about 486×88 plus a 20px legend line. Cell state is
carried by border weight plus a glyph, never fill alone: 1px outline = cohort only; outline
plus a filled 8px square = ranked in this session; 2px ring = selected.

**Data**

- GET /api/cohort/{h}/{date} for the selected cell only. Do NOT prefetch 28 cohorts on load.
- Ranked markers come EXCLUSIVELY from the orchestrator's own in-session run history. HARD
  PROHIBITION: never probe GET /decisions across the 28 cells — when a decision exists that
  call resolves every placement's citations through roughly 1,500 sequential SPARQL round
  trips, so probing is fast only while every cell is empty and degrades exactly as the demo
  gets better.
- Only two hospitals (9001 St Brendan's University Hospital, 9002 Kilbrannan Regional
  Hospital) and 14 dates, 2026-08-17 (a Monday) to 2026-08-30 (a Sunday). Cohort shapes
  differ materially: 9001 has 308 rows at 84/81/88/55/0; 9002 has 301 at 71/94/90/46/0 with
  6 paediatric rows. No count may be hardcoded.
- 2026-08-16 and 2026-08-31 return 200 with referrals: [] — reachable by URL edit, falling
  through to the empty-cohort state.
- Only 2026-08-30 is runnable, because the evidence horizon is date-blind. Every other cell
  opens for reading.

**States**

- collapsed — the default; the bar is one 40px line
- expanded — the grid is open below the bar
- default selection 9001 / 2026-08-30, the largest cohort and the demo hospital-day
- all-outline — no hospital-day ranked in this session yet, and the state after an
  orchestrator restart
- not-runnable — the 27 cells that are not 2026-08-30; readable, with the run control
  disabled and its reason visible
- switching-with-run-in-flight — the poll is aborted and the run keeps running server-side;
  the strip says so rather than claiming it was cancelled

**Strings**

`CTX_HOSPITAL_DAY`, `CTX_CHANGE_DAY`, `CTX_CLINICIAN_LABEL`, `CTX_ATTRIBUTION_NOTE`,
`SELECTOR_HEADING`, `SELECTOR_ROW_9001`, `SELECTOR_ROW_9002`, `SELECTOR_LEGEND`,
`SELECTOR_SCOPE`, `SELECTOR_SWITCH_MIDRUN`, `CTX_RUN_DISABLED_DATE`, `RUN_DATE_LOCK_BODY`

**Safety rule.** The grid must never rank or compare hospitals or days against each other — no totals row, no
worst day, no trend line. Ranking hospital-days is an objective nobody asked for and is the
Obermeyer failure shape: a clean list whose real objective is not its stated one. The 28
days are a selector, not a dataset.

#### RunProgressPanel — 1.25h

One button plus a two-counter status line inside the 40px context bar, and one inline band
in the ordering strip on completion. Never a modal, never a spinner, never an overlay, never
a percentage, never one aggregate bar. Counters are 13px tabular; the only animation during
a run is the digits changing. The delta column ('up 12' / 'down 3' / em dash) is a 44px sub-
column borrowed from track 5 for exactly one refresh after Show ranking — it is the whole
prefers-reduced-motion treatment and an accessibility fallback cannot be a COULD.

**Data**

- POST /api/runs {hospital_hipe, as_of_date} → {run_id, decision_id, started_at}. A plain
  def, not async. The orchestrator mints run_id and owns run history; there is no HTTP run
  trigger anywhere in the repo.
- TWO counters, SAME denominator: urgency n of 308 and capacity n of 308, total 616.
  Verified on origin/urgency_agent that urgency_agent.run.run_for_cohort iterates every
  entry of cohort['referrals'] and refuses 0601 inside the loop;
  capacity_agent.run.run_for_cohort does the same with no refusal of any kind.
- Composed in-process, so exit codes are gone: the orchestrator reads CohortRunResult's four
  dicts directly. The buckets are keyed by pathway_number, so per-row attribution comes
  free. 3 paediatric refusals alone are success-with-exclusions, never failure.
- Timing: both agents loop the full cohort serially at ~15ms per context read plus a
  Postgres write and a graph projection per referral. Say about 20 to 30 seconds and set the
  stall threshold from the first real measurement.
- GET /runs/{unknown}/hospitals/{h}/scores returns HTTP 200 with an empty object, so a stale
  run_id is indistinguishable from a run that just started. The UI asks the orchestrator,
  which knows.

**States**

- idle / pre-run — the state of all 28 hospital-days today
- not-runnable — every hospital-day except 2026-08-30
- starting — accepted, no scores yet
- running — the list does not reorder and gains no positions; urgency cells fill in place
- stalled — counters have not advanced past the measured threshold. Never auto-fail, never
  auto-retry silently
- one-agent-complete — the ranking still does not render
- scores-but-no-ranking — show the scores, refuse to invent positions
- ready — a decision exists and has not been applied; the count of rows that will move is
  stated
- re-run guard — an INLINE, non-modal confirm stating the true consequence, plus a 409 from
  the orchestrator unless confirm_duplicate is passed
- cancelled — polling stops; the copy does not claim to have killed anything it did not kill
- failed — the exception type and the pathway it was raised on, verbatim
- restarted — the orchestrator has no held run: the UI falls back to pre-run and says so

**Strings**

`CTX_RUN_BUTTON`, `CTX_RUN_DISABLED_DATE`, `RUN_DATE_LOCK_BODY`, `RUN_STATUS`,
`RUN_DENOM_NOTE`, `RUN_WITHHOLD`, `RUN_EXPECTED`, `RUN_STARTING`, `RUN_ONE_DONE`,
`RUN_STALLED`, `STALL_KEEP`, `STALL_STOP`, `RUN_STOP_NOTE`, `RUN_SCORES_NO_RANKING`,
`RUN_FAILED`, `RUN_EXIT_NOTE`, `RESTARTED`, `RUN_ERROR`, `SHOW_RANKING`,
`SHOW_RANKING_READY`, `DELTA_UP`, `DELTA_DOWN`, `DELTA_SAME`, `RERUN_CONFIRM`

**Safety rule.** Two counters, never one bar and never a percentage. A bar at 70% with no statement of what
is missing invites a clinician to read a half-scored list as a whole one, and the scores
endpoint's own contract guarantees half-scored rows exist mid-run. No position numeral
renders until both agents have finished and a clinician has explicitly applied the result.

#### PairwiseCompareDock — 1.75h

A 208px bottom dock spanning the full 1248px list width (240px present). Not a modal and not
a side panel — a side panel would squeeze the columns and break the grid. (1) a 28px
identity band, A left and B right in two 612px halves with a 24px gutter, each carrying
pathway_number, category, day count against target, waiting days and NEWS2 n of 17; (2) a
118px steps band, three 400px columns with 24px gaps, STEP 1 CATEGORY / STEP 2 WAITING
TARGET / STEP 3 SCORE INSIDE THE TIER, each 16px heading + 20px verdict chip + its sentence,
with step 3's sentence replaced by the 72px ContributionDisplay when reached; (3) an 18px
computed closing sentence full width; (4) a 32px two-line band for the tie warning and the
alpha-sensitivity sentence. 28+118+18+32+12 padding = 208. Steps stack to one column below
1000px. NEWS2 sub-scores do NOT appear here — hand-checking is the expander's job.

**Data**

- Steps 1 and 2 come entirely from the cohort payload and work with NO run.
- Step 3 comes from the held decision. Full sort key reproduced first-hand from
  coordinator/app/ranking.py: (band_order, severity_rank, −crt_rank, −priority,
  referral_date, pathway_number). alpha = 0.5 + 0.4·scarcity, computed ONCE per decision
  from the mean of the DISTINCT specialty capacity scores (7 distinct specialties here).
  ALPHA_MIN 0.5 and ALPHA_MAX 0.9 are verified constants.
- The alpha-sensitivity line recomputes both priorities at 0.5 and 0.9 client-side and NEVER
  hardcodes a figure. Reproduced first-hand: 272 of 305 sit at a different position between
  the two ends, largest single move 51 places, and PW-9001-000208 sits at 10 / 15 / 34 at
  alpha 0.5 / 0.7 / 0.9.
- THE STAR CASE IS NOT POSITION 1 AND THE COPY MUST NOT SAY IT IS. Position 1 at every alpha
  in the documented range is PW-9001-000191 (CPC 1, NEWS2 7, 152 days) — the one case where
  physiology genuinely separates a patient, which is a better demo beat than a planted one.
- TIE FREQUENCY, verified: of the 299 adjacent same-band same-tier pairs, 87 (29.1%) have
  both referrals at NEWS2 0 and therefore urgency 0.000. The tie warning is the common case.

**States**

- categories-differ — step 1 decides; steps 2 and 3 render greyed and READ 'Not reached'
- categories-tie-target-differs — step 2 decides, and the ADR-011 open flag is repeated here
- both-tie — step 3 renders the arithmetic and the computed closing sentence
- tie-warning — fires when the composite difference is below 0.001 or the two urgency scores
  are identical
- alpha-sensitivity — always shown once step 3 is reached, in one of two forms depending on
  whether the pair actually flips inside [0.5, 0.9]
- one-not-scored — one side is an Outside-the-ranking referral: its column carries the
  refusal statement and no contribution is computed
- pre-run — steps 1 and 2 work and are stated in full; step 3 says no scores exist
- empty — nothing pinned: the dock is 44px with one line explaining how to pin

**Strings**

`DOCK_EMPTY`, `DOCK_IDENTITY`, `STEP1_HEADING`, `STEP2_HEADING`, `STEP3_HEADING`,
`VERDICT_DECIDES`, `VERDICT_TIED`, `VERDICT_NOT_REACHED`, `STEP1_TIE`, `STEP1_DECIDES`,
`STEP2_TIE`, `STEP2_DECIDES`, `STEP3_PRERUN`, `TIE_WARNING`, `IDENTICAL_URGENCY`,
`ALPHA_FLIP`, `ALPHA_STABLE`, `DOCK_ONE_UNRANKED`, `DOCK_CLOSE`, `CONTRIB_ROW_U`,
`CONTRIB_ROW_W`, `CONTRIB_ROW_P`, `CONTRIB_COLS`, `CONTRIB_CLOSING`, `HAND_CHECK`,
`ADR011_SHORT`

**Safety rule.** The dock refuses to compute contributions when the pair is separated by a band or a tier,
and says which boundary decided it instead. Printing numbers that did not decide the
ordering is a fabricated explanation. Alpha is never printed as a bare coefficient on a row
or in the identity headers; it appears only as the two endpoints of its documented range
next to the outcome each produces, so it reads as a mechanism rather than as a clinical fact
about either patient.

#### OverrideDialogAndInlineReasonStrip — 2.5h

TWO deliberately different weights, and the clinician never chooses which — the geometry
does. (A) INSIDE A CATEGORY AND TIER: non-modal. The row lands and a 72px inline reason
strip opens directly beneath it (80 present): a required coded select, an optional free-text
input, and Record / Cancel. Nothing is written until Record. (B) ACROSS A BAND OR ACROSS THE
BREACH TIER: THE ONE MODAL IN THE PRODUCT, a native <dialog> at 620×520, fitting inside 720
with room to spare. READING ORDER IS FIXED AND LOAD-BEARING: (1) a specific 18px/600
heading, no icon; (2) THE DISCLOSURE — the named rule in plain English with the actual
numbers, then both patients as a fixed two-column table with identical field order in both
columns so the eye compares vertically, never prose; (3) THEN THE ATTESTATION, a 24×24
checkbox in a 44px hit row, unchecked, never pre-ticked, which ALONE enables step 4; (4) the
required coded reason select (40px) plus an optional 3-row textarea; (5) actions at 40px —
primary NOT destructive-styled, plus a shortcut that performs the common correction without
abandoning the dialog. There is no 'do not show this again'.

**Data**

- POST /api/overrides → POST /overrides. Verified against the live OverrideIn schema:
  required are override_id, decision_id, hospital_hipe, pathway_number, clinician_id, reason
  (minLength 1, non-blank). Optional and nullable: from_position, to_position. Boolean with
  default: rule_warning_accepted.
- decision_id is a HARD INTEGRATION GAP the orchestrator closes: it is the Postgres key
  'dec-{uuid4}' assigned inside coordinator/app/cli.py and NO GET endpoint returns it. GET
  /decisions returns the graph IRI 'decision/9001/2026-08-30', a DIFFERENT identifier that
  POST /overrides rejects with 400. Composing the coordinator in-process is what makes the
  whole override loop reachable.
- THE API CARRIES ONE REASON STRING, so the coded value is prefixed into it. When the free-
  text field is empty the wire string is '{CODE}: no further detail given' — deterministic,
  satisfies minLength 1, never ends on a bare colon.
- Boundary detection is client-side from the held decision plus the cohort: a move crosses a
  boundary if the target row's band differs, or its crt_breached differs within the same
  band.
- An override IS representable on an Outside-the-ranking row: from_position null,
  to_position set.

**States**

- in-band-move — the inline strip only, no attestation, rule_warning_accepted false. It DOES
  write POST /overrides, because reason has minLength 1 and there is no other write path
- cross-band-move — the modal, with RULE-ORDER named and both parties identified
- cross-tier-move — the modal, with the ADR-011 open-question framing rather than a hard-
  rule framing
- unranked-referral — the move table reads 'Not currently placed' and the heading adapts
- attestation-unchecked — the reason select is disabled. The attestation FOLLOWS the
  disclosure and can never precede it
- reason-empty — Record disabled, the field marked required in text and not by an asterisk
  alone, never a silent no-op
- pre-run — the Move control is disabled with its own visible reason, because POST
  /overrides would be rejected against a decision_id that does not exist
- submitting — an inline 12px progress label on the primary; the dialog stays open, no
  spinner overlay
- post-failed — the row REVERTS to its prior position, the failure names the endpoint and
  status code, and the typed text is preserved
- error-no-decision — the 400 case, said plainly rather than failing opaquely
- recorded — the dialog closes, focus returns to the originating row, and rail line 2
  carries OVERRIDE_RESIDUE with the full reason in the expander

**Strings**

`INLINE_HEADING`, `INLINE_MOVE_STATEMENT`, `REASON_LABEL`, `REASON_PLACEHOLDER`,
`REASON_FREETEXT_LABEL`, `INLINE_RECORD`, `INLINE_CANCEL`, `REASON_EMPTY_ERROR`,
`MODAL_HEADING_BAND`, `MODAL_HEADING_TIER`, `MODAL_HEADING_UNRANKED`,
`MODAL_DISCLOSURE_BAND`, `MODAL_DISCLOSURE_TIER`, `MODAL_TABLE_HEADINGS`,
`MODAL_TABLE_FIELDS`, `MODAL_UNPLACED`, `ATTESTATION`, `REASON_OPT_CLINICAL`,
`REASON_OPT_NEWINFO`, `REASON_OPT_PATIENT`, `REASON_OPT_CAPACITY`, `REASON_OPT_DATA`,
`REASON_OPT_OTHER`, `MODAL_PRIMARY`, `MODAL_SECONDARY`, `MODAL_SHORTCUT`, `REASON_WIRE`,
`REASON_WIRE_EMPTY`, `OVERRIDE_RECORDED`, `OVERRIDE_FAILED`, `OVERRIDE_NO_DECISION`,
`OVERRIDE_RESIDUE`, `MOVE_DISABLED_PRERUN`, `ADR011_FULL`, `CTX_ATTRIBUTION_NOTE`

**Safety rule.** The copy never frames the act as disagreement: never 'override the AI recommendation', never
'why do you disagree', never an 'are you sure' shaped like an error, never a destructive red
confirm. Interrupting modals are accepted at 38.67% against 61.57% for non-interrupting
alternatives across 39 studies, so the re-run guard, the stop-run confirm, filters and every
empty state are inline and non-modal — spending the budget anywhere else would deliver the
band-crossing warning to an already-desensitised clinician. A row that stays moved after a
failed write is a lie about what is recorded.

#### EmptyErrorStateFamily — 0.5h

Not a separate screen. TWO in-place treatments owned here, both inside the table's own
scroll container so the page never scrolls sideways and the chrome stays visible. (1) EMPTY
COHORT: a 280px panel replacing the list body only, chrome and selector intact, one 40px
primary action. (2) NETWORK / HTTP / AUTH ERROR: a line in the reconciliation ledger naming
the upstream endpoint and status code, with the selector still live. Both state their
denominator. Defect variants carry a 3px left border. No illustration, no mascot, no icon
carrying meaning. The other two absences of the original four still render, from the
components that already own them: 'no ranking yet' is the OrderingStrip banner and
'unresolved evidence' is CitationChip's unresolved state.

**Data**

- Verified today: GET /decisions/9001/2026-08-30 returns 404 'no decision for that
  hospital/date'. Every hospital-day probed does the same. Pre-run is not an edge case to
  bolt on — it is the current and only state.
- Verified: GET /hospitals/9001/cohort/2026-08-31 returns 200 with referrals: [], an empty
  cohort and not an error. Same for 2026-08-16.
- Verified: a missing or malformed Authorization header returns 401 'Missing or malformed
  Authorization header'. That token lives only in the orchestrator, so this can only ever be
  a server-side misconfiguration.

**States**

- empty-cohort — panel, chrome intact, selector live
- network-or-http-error — endpoint and status code, verbatim, always. Never a generic
  apology
- partial — a partial list is NEVER rendered without the ledger saying it is partial, with
  both numbers

**Strings**

`EMPTY_COHORT`, `EMPTY_COHORT_ACTION`, `HTTP_ERROR`, `AUTH_ERROR`, `ORCH_UNREACHABLE`,
`PARTIAL`, `UNKNOWN_COUNT`

**Safety rule.** Never render a partial list without saying, in the same viewport, that it is partial and
against what denominator. A quiet partial list is the single most dangerous failure this UI
can have, because it looks exactly like a complete one. Collapsing the four absences into
one friendly empty state would hide a genuine failure behind a calm panel — the cut here is
one of OWNERSHIP, not of states: all four still render and still look different from one
another.

#### LoadingRule — 0.25h

Below 400ms nothing renders at all — the cohort measures 50ms for 111KB and a skeleton that
flashes for 50ms is noise. Past 400ms, ONE line of text in the reconciliation ledger. THERE
IS NO SKELETON TABLE anywhere in the product. Wherever any count would render during loading
it renders as an em dash, never as 0. The per-cell neutral blocks are the only skeletons and
they exist solely for the lazy per-row context call inside an open expander, where the wait
is real and per-row.

**Data**

- Cohort measured live at 50ms for 111,331 bytes. Context measured ~15ms per row.
- aria-busy is set on the grid only while a request that would change row count is in
  flight.

**States**

- under-400ms — nothing renders, no text, no block
- over-400ms — one line in the ledger
- expander-context-in-flight — six 20px neutral rows in section 3 only; sections 2, 4, 5 and
  8 render immediately from data already held

**Strings**

`LOADING`, `UNKNOWN_COUNT`, `EXP_S3_LOADING`

**Safety rule.** Every count is an em dash while unknown. A 0 that no source reported is a false claim about
the cohort, and it is exactly the failure the reconciliation ledger exists to prevent.

### SHOULD

#### WaitMeterGraphic — 1h

The deferred per-band square-root meter, recorded so the cut is traceable rather than
forgotten: a 140×10px track with a 1px outline sharing line box A with the days numeral,
plus a separate 2px-wide 18px-tall 1× tick overshooting the track 4px above and below, so
'the fill has crossed the tick' is a topological judgement that survives greyscale and ten
feet.

**Data**

- Per-band domains over the observed maximum, so nothing is ever clipped: CPC 1 domain
  0-31.107×, CPC 3 domain 0-9.099×. Square root only because it is monotonic — it can
  compress magnitude but can never reverse two patients.
- no-target rows would render as an empty outline with no fill and no tick; zero-wait rows
  need a 2px origin stub, because a 0px fill is pixel-identical to a missing bar.

**States**

- absent-by-default — WaitTargetCell's two text lines already carry the days, the target and
  the breach state in words

**Strings**

`WAIT_DAYS`, `WAIT_MULTIPLE`, `WAIT_DAYS_OVER`, `TARGET_AT`

**Safety rule.** If it is ever built it is redundant reinforcement only, and must be droppable with
display:none without changing a single meaning on the row. It may never be the only channel
carrying the breach state.

#### PinnedRowTreatment — 1h

The deferred half of the A/B markers: row-level pinned styling in the table, matching
markers in the dock's steps band, and pin persistence across a route change. What survives
in the MUST build is the reserved 16px slot and its letter.

**Data**

- Pin state is client-only and is never written to any endpoint.

**States**

- absent-by-default — the letter in the rail plus the dock's own identity band already
  identify A and B

**Strings**

`RAIL_PIN_A`, `RAIL_PIN_B`, `PIN_ARIA`

**Safety rule.** Any pinned treatment must not spend the background channel, which gap, rule, tier divider
and focus ring have already spent. Nothing about pinning may alter how sick a row looks.

#### ExportAndFilters — 2h

Three independent, individually droppable additions: filter chips beyond the ledger's own
six terms; an export control producing the CURRENT view with the synthetic-data and
decision-support labels burned in; ranked/not-ranked markers on the selector grid.

**Data**

- Filters read only fields already loaded. Export needs no endpoint. Markers need the
  orchestrator's in-session run history and must never probe GET /decisions.

**States**

- absent-by-default — nothing else changes shape when they are missing

**Strings**

`EXPORT_FOOTER`, `LEDGER_FILTERED`, `SELECTOR_LEGEND`

**Safety rule.** A filter must never produce a view that looks like a complete ranked list but is not. Every
filtered state prints the count and 'positions unchanged' in the ledger AND in each affected
group header.

### COULD

#### ProvenanceGraph — 7h

DEFERRED, recorded so the decision is traceable rather than forgotten. If ever built:
assembled CLIENT-SIDE from the REST payloads already held, rendering exactly the same
evidence entries as expander section 7 with the same strings. Roles distinguished by an edge
LABEL first; nothing primary may depend on a dashed, dotted or hatched distinction at
1280×720.

**Data**

- GET /evidence/{h}/{date}/{pw}. Verified today it returns an empty evidence array for every
  pathway, because no decision exists anywhere.

**States**

- not-built — the default, and the state on 14 September

**Strings**

`GRAPH_DEFERRED`

**Safety rule.** If it is ever built it may only be a second rendering of the expander's own evidence list. A
graph that told a prettier story than the list it is drawn from is post-hoc explanation that
is not the actual computation — the exact failure this build exists to avoid.

---

## 6. Canonical strings

All 278 user-facing strings, final wording. Nothing is a
placeholder. Every number inside a string was verified first-hand against the live API or
the source. Use these verbatim; if a string needs to change, change it here first so the
components that share it stay consistent.

| id | text | used by |
|---|---|---|
| `CTX_HOSPITAL_DAY` | St Brendan's · Sunday 30 August 2026 · 308 referrals | ContextBarAndHospitalDaySelector, bar line 1 (52ch/333px) |
| `CTX_CHANGE_DAY` | Change hospital-day | ContextBar, disclosure control |
| `CTX_CLINICIAN_LABEL` | Clinician ID — attribution only, not authentication | ContextBar, text input label |
| `CTX_ATTRIBUTION_NOTE` | Recorded as clinician-01. Attribution, not authentication: this record says who typed it, it does not verify them. | ContextBar; OverrideDialog footer |
| `CTX_RUN_BUTTON` | Run the agents for this hospital-day | RunProgressPanel, idle control |
| `CTX_RUN_DISABLED_DATE` | Runs are available on 30 August 2026 only | RunProgressPanel, disabled reason on the other 27 cells |
| `RUN_DATE_LOCK_BODY` | The evidence call carries no date. GET /referrals/{h}/{pw}/context returns the most recent observation on record whichever day you are looking at, so scoring 21 August would cite observations taken on 30 August. You can read all 28 hospital-days; the agents run on the latest day with data. | RunProgressPanel + Selector disclosure |
| `SELECTOR_HEADING` | Choose a hospital-day | Selector grid heading |
| `SELECTOR_ROW_9001` | 9001 St Brendan's University Hospital | Selector row label 1 |
| `SELECTOR_ROW_9002` | 9002 Kilbrannan Regional Hospital | Selector row label 2 |
| `SELECTOR_LEGEND` | Outline: cohort available · Filled square: ranked in this session · Ring: selected | Selector 20px legend line |
| `SELECTOR_SCOPE` | Two hospitals, 17–30 August 2026. These 28 cells are a selector, not a comparison: no hospital and no day is ranked against another. | Selector footer |
| `SELECTOR_SWITCH_MIDRUN` | You switched hospital-day while a run was in flight. Polling stopped here. The run is still going on the server; nothing was cancelled. | OrderingStrip, switching-with-run-in-flight |
| `SCOPE_LINE` | Synthetic data · Decision support, not a decision · Urgency is NEWS2 only — six vital signs · Paediatric referrals are not scored | ScopeLine, 24px strip (129ch/826px of 1248) |
| `SCOPE_C1` | Synthetic data | ScopeLine clause 1 control |
| `SCOPE_C1_BODY` | Every patient, referral, observation and ward figure here is generated. No real person is on this list. The hospital codes, specialty codes and NTPF prioritisation categories are real; the people are not. | ScopeLine clause 1 disclosure |
| `SCOPE_C2` | Decision support, not a decision | ScopeLine clause 2 control |
| `SCOPE_C2_BODY` | This screen proposes an order and shows its working. It does not book, defer, discharge or clinically prioritise anyone. A clinician's own order, recorded here, is the output that counts — and the ordering rule itself is an open question (ADR-011), so nothing here is signed off. | ScopeLine clause 2 disclosure |
| `SCOPE_C3` | Urgency is NEWS2 only — six vital signs | ScopeLine clause 3 control |
| `SCOPE_C3_BODY` | NEWS2 reads respiratory rate, oxygen saturation, systolic blood pressure, heart rate, level of consciousness and temperature. It does not read the diagnosis, pain, diastolic pressure, the MTS category, the referral source or the pathway. On this hospital-day 268 of 308 referrals score 2 or less, and 20 of the 84 the clinician marked Urgent score 0. Across both hospitals on 30 August, 48 of 155 Urgent referrals score 0. The instrument cannot separate most of these patients. | ScopeLine clause 3 disclosure (the urgency caveat; 0px in the sticky stack) |
| `SCOPE_C4` | Paediatric referrals are not scored | ScopeLine clause 4 control |
| `SCOPE_C4_BODY` | NEWS2 is validated in adults. The urgency agent refuses specialty 0601, Paediatric ENT, rather than scoring a child on an adult scale (ADR-007). On this hospital-day that is 3 referrals of 308; on 9002 it is 6 of 301. They are shown in full, below the ranking, in a named region. | ScopeLine clause 4 disclosure |
| `LEDGER_1` | 308 in cohort | ReconciliationLedger term 1, fixed in every state |
| `LEDGER_2` | 305 scored | ReconciliationLedger term 2 |
| `LEDGER_3` | 305 placed | ReconciliationLedger term 3 |
| `LEDGER_4` | 3 outside the ranking — paediatric (specialty 0601) | ReconciliationLedger term 4 |
| `LEDGER_5` | 0 not scored — no observation to cite | ReconciliationLedger term 5 |
| `LEDGER_6` | 0 absent, no reason recorded | ReconciliationLedger term 6. Joined string = 164ch = 1050px of 1248, one line |
| `LEDGER_PRERUN` | 308 in cohort · not yet scored · 3 are specialty 0601 and will not be scored · 2 further counts unavailable until a run reports them. Not the same as zero. | ReconciliationLedger pre-run (155ch/992px) |
| `LEDGER_RUNNING` | 308 in cohort · 142 scored so far · reconciliation available when the run finishes | ReconciliationLedger running |
| `LEDGER_UNAVAILABLE` | 2 counts unavailable — the urgency agent's run report was not returned. Not the same as zero. | ReconciliationLedger, terms 5 and 6 with no agent report |
| `LEDGER_MISMATCH` | Ledger does not reconcile: 304 scored plus 3 outside the ranking against 308 in cohort. 1 referral is unaccounted for. | ReconciliationLedger mismatch, defect authority 3px left border |
| `LEDGER_FILTERED` | Showing 64 of 308 · positions unchanged | ReconciliationLedger filtered + every affected BandGroupHeader |
| `LEDGER_ERROR` | Counts unknown. GET /hospitals/9001/cohort/2026-08-30 returned 502. | ReconciliationLedger error; names the upstream retrieval path, never /api |
| `UNKNOWN_COUNT` | — | Every unknown count everywhere. Never 0 |
| `COLH_RAIL` | Position / and pathway | Column header 1, two lines 12px/600 |
| `COLH_RAIL_PRERUN` | Pathway / referral date order | Column header 1, pre-run |
| `COLH_CATEGORY` | Category / clinician-assigned | Column header 2 |
| `COLH_WAIT` | Waiting time / against target | Column header 3 |
| `COLH_URGENCY` | Urgency / NEWS2 only, 6 vital signs | Column header 4 (line 2 = 25ch = 160px inside the 168px track) |
| `COLH_WHY` | Why this position / versus the row below | Column header 5 |
| `COLH_ACTIONS` | Actions / compare · accept · move | Column header 6 |
| `COLH_PRERUN_MERGED` | Not ranked yet / No agent has scored this hospital-day | The one merged header cell spanning tracks 4 and 5 (376px) pre-run |
| `PRE_RUN` | Nothing has been ranked for this hospital-day. Everything below is what a clinician recorded, not what an agent computed. | OrderingStrip line 1 pre-run (the banner); EmptyErrorStateFamily; EXPORT_FOOTER |
| `DISPLAY_ORDER` | Referral date order — a display order, not a ranking. | OrderingStrip line 2 pre-run and running; every BandGroupHeader line 2 pre-run |
| `ORDER_RANKED` | 305 placed · category, then target breach, then urgency and waiting time at one exchange rate for the whole hospital-day · RULE-ORDER and RULE-TIEBREAK hold | OrderingStrip line 1 ranked. Absorbs the deleted decision header. Alpha is NOT printed here |
| `RULE_LINE` | RULE-ORDER holds · RULE-TIEBREAK holds — earlier referral date first among referrals also tied on category, target breach and score | OrderingStrip rule-check disclosure |
| `ADR011_SHORT` | Inside a category, every referral past its waiting target is ordered above every one inside it, at any score — an open clinical question (ADR-011), not signed off. | OrderingStrip line 2 ranked (163ch = 1043px of 1248, one line) |
| `ADR011_WHY` | Why this matters | OrderingStrip line 2 disclosure control |
| `ADR011_FULL` | Inside a category, every referral past its waiting target is ordered above every referral inside it, at any score. On this hospital-day that puts 75 of the 84 Urgent referrals in the upper tier, so the 9 still inside the 28-day target sit beneath them whatever their NEWS2. That tiering is an open clinical question in this project (ADR-011) and is not signed off. No decision made under it should be presented as final. | OrderingStrip disclosure; BreachTierDivider Why?; MODAL_DISCLOSURE_TIER |
| `SHOW_RANKING` | Show ranking | OrderingStrip ready state, inline control |
| `SHOW_RANKING_READY` | Both agents finished. {n} of 305 referrals will change place when you apply this. | RunProgressPanel ready. {n} computed by diffing the two orders, never hardcoded |
| `RERUN_CONFIRM` | This hospital-day was already ranked in this session. Running again writes a second set of placements to the graph alongside the first, and the two cannot be told apart there. | OrderingStrip inline non-modal re-run guard |
| `RERUN_YES` | Run it again | Re-run guard, primary |
| `RERUN_NO` | Keep the ranking I have | Re-run guard, secondary |
| `RUN_STATUS` | Scoring · urgency {n} of 308 · capacity {n} of 308 · {t} s | RunProgressPanel. Total denominator 616 = two agents × 308 |
| `RUN_DENOM_NOTE` | Both agents read all 308. The urgency agent refuses 3 of them; a refusal is an outcome, not a skipped row. | RunProgressPanel, beside the counters |
| `RUN_WITHHOLD` | No positions are shown until both agents finish and you apply the result. 616 scores to write. | RunProgressPanel running |
| `RUN_EXPECTED` | About 20 to 30 seconds. | RunProgressPanel starting/running |
| `RUN_STARTING` | Run accepted. No scores yet. | RunProgressPanel starting |
| `RUN_ONE_DONE` | urgency 308 of 308 · capacity 211 of 308 — the ranking is not shown until both finish | RunProgressPanel one-agent-complete |
| `RUN_STALLED` | No new scores for {n} seconds. The run may have stopped. | RunProgressPanel stalled. Never auto-fail, never auto-retry |
| `STALL_KEEP` | Keep watching | RunProgressPanel stalled |
| `STALL_STOP` | Stop polling | RunProgressPanel stalled |
| `RUN_STOP_NOTE` | Polling stopped. The run is still going on the server; nothing was cancelled. | RunProgressPanel cancelled |
| `RUN_SCORES_NO_RANKING` | Both agents finished. The coordinator did not produce a ranking. The scores are shown; no positions are invented. | RunProgressPanel scores-but-no-ranking |
| `RUN_FAILED` | The {agent} agent raised {exception} on {pathway}. Nothing was ranked. {n} scores were already written and are still in the database. | RunProgressPanel failed. In-process, so an exception replaces the old CLI exit code |
| `RUN_EXIT_NOTE` | 3 paediatric refusals alone do not make a run a failure: this run reports 305 scored, 3 refused, 0 skipped, 0 graph projection failures. | RunProgressPanel completion; ReconciliationLedger source note |
| `RESTARTED` | That run is not known to this orchestrator. It was probably restarted. Nothing is lost in the database; there is no held ranking to show. | RunProgressPanel restarted; AcceptAction residue loss |
| `RUN_ERROR` | POST /api/runs returned 500. No run started and nothing was written. | RunProgressPanel; the one place the /api path is named, because it is the failing call |
| `DELTA_UP` | up {n} | RunProgressPanel delta column, one refresh after Show ranking |
| `DELTA_DOWN` | down {n} | RunProgressPanel delta column |
| `DELTA_SAME` | — | RunProgressPanel delta column, no move |
| `GROUP_URGENT_L1` | Urgent · CPC 1 · 84 referrals · 84 ranked · target 28 days | BandGroupHeader line 1, 15px/600 |
| `GROUP_URGENT_L2` | 75 past the 28-day target, 9 within | BandGroupHeader line 2 |
| `GROUP_SEMI_L1` | Semi-urgent · CPC 3 · 81 referrals · 81 ranked · target 91 days | BandGroupHeader line 1 |
| `GROUP_SEMI_L2` | 55 past the 91-day target, 26 within · ranks above Routine: order is by clinical severity, not by code number | BandGroupHeader line 2, the only place CPC 3 > CPC 2 is stated |
| `GROUP_ROUTINE_L1` | Routine · CPC 2 · 88 referrals · 86 ranked · 2 outside the ranking | BandGroupHeader line 1. The ranked/not-ranked split is mandatory here |
| `GROUP_ROUTINE_L2` | No waiting target applies to this category | BandGroupHeader line 2, never blank, never a tick |
| `GROUP_NOCAT_L1` | No category recorded · 55 referrals · 54 ranked · 1 outside the ranking | BandGroupHeader line 1 |
| `GROUP_NOCAT_L2` | Unknown priority, not low priority. No waiting target applies. 1 of the 55 is still awaiting triage. | BandGroupHeader line 2 |
| `GROUP_EXCLUDED_L1` | Excluded · CPC 4 · 0 referrals | BandGroupHeader line 1. RENDERS at zero rows |
| `GROUP_EXCLUDED_L2` | This category exists and is empty today. It is kept separate from 'no category recorded' — the two are different things (ADR-006). | BandGroupHeader line 2 |
| `GROUP_PRERUN_L2` | Referral date order — a display order, not a ranking. 75 of 84 are past the 28-day target. The tier line is drawn once a ranking exists. | BandGroupHeader line 2 pre-run |
| `GROUP_COLLAPSED` | {Band} collapsed — hiding {n} referrals | BandGroupHeader collapsed |
| `SEVERITY_NOTE` | Ranks above Routine: order is by clinical severity, not by code number. | BandGroupHeader semi-urgent; expander section 2 |
| `UNKNOWN_NOT_LOW` | Unknown priority, not low priority. | BandGroupHeader no-category; CategoryTimeframeChip aria |
| `TIER_CAPTION` | Below this line: within the 28-day target. | BreachTierDivider, 12px caption inset 8px from track 2 |
| `TIER_WHY` | Why? | BreachTierDivider, 13px control at a 24×24 target |
| `TIER_WHY_BODY` | Waiting-target breach sits above the score in the sort key, so inside this category every referral past its target is ordered above every referral inside it, whatever their NEWS2. Above this line, 75. Below it, 9. That is ADR-011, and it is open: nobody has signed it off. | BreachTierDivider, 3-line inline disclosure (+60px) |
| `PRE_RUN_TIER_NOTE` | 75 of 84 are past the 28-day target. The tier line is drawn once a ranking exists. | BandGroupHeader pre-run, because no single crt_breached transition exists in referral_date order |
| `RAIL_SPECIALTY` | 0300 Dermatology | ReferralRailCell line 2, 12px muted. Labels from core.ref_codes: 1800 Orthopaedics, 0300 Dermatology, 0600 Otolaryngology (ENT), 0100 Cardiology, 2600 General Surgery, 0700 Gastro-Enterology, 0601 Paediatric ENT |
| `NO_POSITION_ARIA` | No position. This referral is outside the ranking. | ReferralRailCell outside-the-ranking, visually hidden. No dash in the numeric sub-column |
| `RAIL_PIN_A` | A | ReferralRailCell 16px pin slot, 13px/700 |
| `RAIL_PIN_B` | B | ReferralRailCell 16px pin slot |
| `PIN_ARIA` | pinned as A for comparison | ReferralRailCell, appended to the row's accessible name |
| `ACCEPTED_RESIDUE` | Accepted 14:07 | ReferralRailCell line 2 replaces specialty after AcceptAction |
| `OVERRIDE_RESIDUE` | Order recorded by you · CLINICAL-CONCERN · 14:07 | ReferralRailCell line 2 after an override |
| `CHIP_URGENT` | Urgent · CPC 1 | CategoryTimeframeChip, filled ground |
| `CHIP_SEMI` | Semi-urgent · CPC 3 | CategoryTimeframeChip, outline |
| `CHIP_ROUTINE` | Routine · CPC 2 | CategoryTimeframeChip, plain text |
| `CHIP_NOCAT` | No category recorded | CategoryTimeframeChip, plain text, no code appended (20ch = 138px + 16 padding inside 160) |
| `CHIP_EXCLUDED` | Excluded · CPC 4 | CategoryTimeframeChip, built, 0 rows today |
| `TARGET_PAST` | Past the 28-day target | CategoryTimeframeChip line 2. Names the rule that fired, never 'overdue' |
| `TARGET_WITHIN` | Within the 28-day target | CategoryTimeframeChip line 2. Neutral text, never a success colour, never a tick |
| `TARGET_AT` | At the 91-day target | CategoryTimeframeChip and WaitTargetCell for PW-9001-000020, the only row at exactly 1.00×. Never 'Within', never '1×' |
| `TARGET_NONE` | No target for this category | CategoryTimeframeChip / WaitTargetCell, 143 rows |
| `TRIAGE_LATE` | Triage day 64 of 21 | CategoryTimeframeChip awaiting-triage modifier, PW-DEMO-05 |
| `TRIAGE_RULE_FULL` | RULE-TRIAGE-TURNAROUND: 21 days from sent-for-triage to returned. This referral is on day 64 and has not been triaged, so it carries no category. | BandGroupHeader no-category; expander section 2 |
| `WAIT_DAYS` | 871 days | WaitTargetCell line box A, 20px/600 tabular right-aligned in 92px. The largest numeral on the row |
| `WAIT_MULTIPLE` | 31× the 28-day target | WaitTargetCell line B at 2.00× and above. Integer, FLOORED, never rounded |
| `WAIT_DAYS_OVER` | 2 days over a 28-day target | WaitTargetCell line B from 1.00× to under 2.00× (28 rows; PW-9001-000137 is 30/28) |
| `WAIT_WITHIN_DAYS` | 14 days inside a 28-day target | WaitTargetCell line B, within-target (35 rows) |
| `WAIT_ZERO` | 0 days | WaitTargetCell, 11 rows. Rendered as a literal zero, never blank |
| `WAIT_ZERO_NOTE` | Received on this date | WaitTargetCell line B, zero-wait |
| `WAIT_SUSPENDED` | Clock suspended | WaitTargetCell line B. A word, never an icon. 0 rows today, built |
| `WAIT_ARIA` | Waiting time 871 days against a 28-day target; 31 times over. | WaitTargetCell accessible name |
| `NEWS2_LINE` | NEWS2 1 of 17 | UrgencyNews2Cell line 1, 15px/600 tabular. Denominator always printed; NEWS2_MAX is 17 |
| `NORMALISED_LINE` | normalised 0.075 | UrgencyNews2Cell line 2, 12px muted, always 3dp. 0.08 appears nowhere |
| `NEWS2_ZERO_ARIA` | NEWS2 0 of 17. Six vital signs near normal. This is a score, not a judgement that the patient is well. | UrgencyNews2Cell scored-zero, 148 rows. Never 'low urgency', 'low risk', 'stable', 'normal' |
| `NOT_SCORED` | Not scored | UrgencyNews2Cell line 1, refused and skipped |
| `REASON_PAEDIATRIC` | Paediatric refusal | UrgencyNews2Cell line 2, 3 rows |
| `REASON_NO_OBSERVATION` | No observation to cite | UrgencyNews2Cell line 2, 0 rows today, built |
| `REASON_UNRESOLVED` | Evidence did not resolve | UrgencyNews2Cell line 2; score still renders on line 1 |
| `AWAITING_AGENT` | Awaiting urgency agent | UrgencyNews2Cell mid-run. Not a zero and not an empty cell |
| `VERDICT_WAIT` | Ahead on waiting time | WhyThisPositionCell line 1. The commonest verdict: 87 of 299 adjacent same-band same-tier pairs are two NEWS2-0 referrals |
| `VERDICT_NEWS2` | Ahead on NEWS2 | WhyThisPositionCell line 1 |
| `VERDICT_BOTH` | Ahead on both | WhyThisPositionCell line 1 |
| `VERDICT_TIER` | Tier decided this | WhyThisPositionCell line 1, row below across the breach divider |
| `VERDICT_BAND` | Category decided this | WhyThisPositionCell line 1, row below in a different band |
| `VERDICT_NO_SCORES` | Scores did not decide | WhyThisPositionCell line 2, tier and band boundary states |
| `FOIL_LINE` | vs PW-9001-000026 | WhyThisPositionCell line 2. Read from the ordered array at render time, never hardcoded |
| `FOIL_ABOVE` | vs PW-9001-000191, above | WhyThisPositionCell last-in-tier |
| `CONTRIB_ROW_U` | urgency contributed | ContributionDisplay row 1, fixed order |
| `CONTRIB_ROW_W` | waiting contributed | ContributionDisplay row 2 |
| `CONTRIB_ROW_P` | composite priority | ContributionDisplay row 3 |
| `CONTRIB_COLS` | A / B / difference | ContributionDisplay header row, 18px |
| `CONTRIB_CLOSING` | Waiting time put A ahead by +0.111. NEWS2 pulled A back by −0.105. A is ahead by +0.006. | ContributionDisplay 13px closing sentence, computed, never model-generated |
| `HAND_CHECK` | Add the right-hand column. If it does not come to the difference, this screen is wrong. | ContributionDisplay, beneath the table |
| `CONTRIB_REFUSED` | These two are separated by a category or a waiting-target tier. The scores did not decide it, so no arithmetic is shown. | ContributionDisplay refused. Printing numbers that did not decide the ordering is a fabricated explanation |
| `CONTRIB_PRERUN` | No scores exist for this hospital-day yet, so there is no arithmetic to show. | ContributionDisplay pre-run |
| `PERCENTILE_SENTENCE` | No referral in the Urgent category has waited longer. | ContributionDisplay / expander. Ties share the percentile, so the longest wait in an 84-row band is 0.994, never 1.000. 'waited longer than 100%' is forbidden |
| `ACT_COMPARE` | Compare | ActionRail control 1, 64px |
| `ACT_ACCEPT` | Accept | ActionRail control 2, 72px |
| `ACT_ACCEPTED` | Accepted | ActionRail control 2 after recording; sized at 72 so it fits without reflow |
| `ACT_MOVE` | Move | ActionRail control 3, 46px. NEVER gated where a position exists |
| `ACT_DISCLOSURE_ARIA` | Show evidence | ActionRail 24×24 chevron accessible name |
| `ACCEPT_DISABLED_UNEXPANDED` | Expand to read the evidence first | ActionRail line B, 33ch = 211px inside 232 |
| `ACCEPT_DISABLED_UNRANKED` | No ranked position to accept | ActionRail line B, outside-the-ranking rows |
| `MOVE_DISABLED_PRERUN` | No ranking yet — no position to move | ActionRail line B pre-run, 36ch = 230px inside 232 |
| `SUBMITTING` | Recording… | ActionRail / modal submitting. Inline 12px label, no spinner, no overlay |
| `EXP_PINNED_HEADER` | PW-9001-000208 · position 15 of 305 | RowEvidenceExpander 24px pinned header above the scrolling body |
| `EXP_H1` | Position and what decided it | Expander section 1 heading, 74px section. Not renameable, not droppable |
| `EXP_H2` | The waiting-target rule | Expander section 2 heading, 140px |
| `EXP_H3` | NEWS2 | Expander section 3 heading, 202px |
| `EXP_H4` | Read but not scored | Expander section 4 heading, 150px. The single most important section in the product |
| `EXP_H5` | On the record, not used in the score | Expander section 5 heading, 230px |
| `EXP_H6` | Capacity | Expander section 6 heading, 92px |
| `EXP_H7` | Citations | Expander section 7 heading, 256px |
| `EXP_H8` | Audit fields | Expander section 8, a closed <details> summary, 24px |
| `EXP_S1_POSITION` | Position 15 of 305 · Urgent · past the 28-day target | Expander section 1 line 1 |
| `EXP_S1_VERDICT` | Ahead of PW-9001-000026 on waiting time; behind it on NEWS2. | Expander section 1 line 2 |
| `EXP_S1_ARITHMETIC` | Show the arithmetic | Expander section 1 disclosure control; opens the 72px ContributionDisplay in place |
| `EXP_S1_PRERUN` | No ranking exists for this hospital-day, so this referral has no position and nothing decided one. | Expander section 1 pre-run. The heading still renders — the fixed order is the safety argument |
| `EXP_S2_RULE` | RULE-CRT-URGENT — 28 days from referral for a CPC 1 referral. | Expander section 2 line 1 |
| `EXP_S2_FIRED` | 871 days waited. 843 days past the target. The rule fired. | Expander section 2 |
| `EXP_S2_NOT_FIRED` | 91 days waited against a 91-day target. The rule did not fire. | Expander section 2, PW-9001-000020 |
| `EXP_S2_NO_RULE` | No waiting-target rule applies to CPC 2 or to a referral with no category. RULE-CRT-URGENT covers CPC 1 at 28 days, RULE-CRT-SEMI covers CPC 3 at 91 days, and there is no third. 143 of these 308 referrals have no target. | Expander section 2, no-target rows |
| `EXP_S2_TIER` | Because the rule fired, this referral is ordered above every Urgent referral still inside the target, whatever their NEWS2. 75 above the line, 9 below. | Expander section 2, with the ADR011_WHY control |
| `RULE_NOT_FIRED` | A rule that did not fire says only that the rule did not fire. | Expander section 2 and section 8 |
| `EXP_S3_TOTAL` | NEWS2 1 of 17 — recomputed here from the same six values, and it agrees with the stored score. | Expander section 3 line 1 |
| `EXP_S3_VITAL_ROW` | Heart rate 108 → 1 of 3 | Expander section 3, six 20px rows. All six always shown, including the zeros |
| `EXP_S3_VITAL_LABELS` | Respiratory rate / Oxygen saturation / Systolic blood pressure / Heart rate / Consciousness (AVPU) / Temperature | Expander section 3 row labels, fixed order, matching NEWS2_VITALS |
| `EXP_S3_DISAGREE` | Recomputed 2, stored 1. These disagree. Neither is shown as the answer; this is a fault, not a rounding difference. | Expander section 3, recompute mismatch. Defect authority |
| `EXP_S3_NORMALISE_CONTROL` | How 1 of 17 becomes 0.075 | Expander section 3, 22px disclosure control. The five-line paragraph moved out of the section body into here |
| `CALIBRATION_NOTE` | 1 of 17 maps to 0.075 on a 0-to-1 scale. The mapping has four anchors — 0→0.000, 4→0.300, 6→0.600, 7→1.000 — with straight lines between and saturation above 7, so on this data the score can only ever take eight values: 0.000, 0.075, 0.150, 0.225, 0.300, 0.450, 0.600 and 1.000. The anchors are NEWS2's own escalation thresholds, not a fitted curve. It is stored to three decimals because agent_scores.score is numeric(4,3), not because it is that precise. Retuning the anchors changes the spread of the top few per cent and never the tie at the bottom: 148 of these 308 referrals score 0 and share exactly 0.000. | Expander section 3 normalisation disclosure, five lines |
| `EXP_S3_REFUSED` | No NEWS2 score was written for this referral. Specialty 0601 is Paediatric ENT and NEWS2 is validated in adults, so the urgency agent refused it rather than scoring a child on an adult scale (ADR-007). The six values were still recorded and are listed below without sub-scores and without a total. | Expander section 3, the 3 tail rows |
| `EXP_S3_LOADING` | Reading this referral's observation… | Expander section 3 loading; six 20px neutral rows beneath. Sections 2, 4, 5 and 8 render immediately |
| `EXP_S3_ERROR` | GET /referrals/9001/PW-9001-000208/context returned 500. The six values are not shown. The position above is unchanged. | Expander section 3 error, with a Retry control |
| `EXP_S4_SENTENCE_LOW` | A score of 1 means those six were near normal. It does not mean this patient is near normal. | Expander section 4, first thing in the section, two lines. Renders for NEWS2 ≤ 2 — 268 of 308 rows |
| `EXP_S4_SENTENCE_HIGH` | A score of 4 means those six were abnormal enough to score. It does not mean the reason for this referral is in those six. | Expander section 4, NEWS2 ≥ 3 — 40 of 308 rows |
| `EXP_S4_PAIN` | Pain 10 of 10 — recorded, not scored | Expander section 4 value row 1, observations[-1].pain |
| `EXP_S4_DBP` | Diastolic blood pressure 94 mmHg — recorded, not scored | Expander section 4 value row 2, observations[-1].dbp |
| `EXP_S4_MTS` | MTS category Orange — recorded, not scored | Expander section 4 value row 3, observations[-1].mts_category |
| `EXP_S4_CONDITION` | Condition C43.9 (ICD-10-AM) — recorded, not scored | Expander section 4 value row 4, conditions[] primary |
| `EXP_S4_ABSENT` | MTS category not recorded | Expander section 4, the 3 paediatric rows, which carry icts_category instead. Absence stated, never blanked |
| `EXP_S5_CONDITION_ROW` | C43.9 — primary | Expander section 5. 408 condition rows across 308 referrals: 208 have one, 100 have two. Every one is listed |
| `CONDITION_PROVENANCE` | The record stores an ICD-10-AM code and a label that is only the code written out — "Condition C43.9". There is no plain-English term, and snomed_ct_id is null on all 408 condition rows in this cohort. The code is drawn at random from the specialty's condition mix when the dataset is generated (generate.py:472) and never reads the patient's vital signs or triage category. It is a record field, not evidence for this position. | Expander section 5, three lines |
| `EXP_S5_MTS_ROW` | MTS category Orange | Expander section 5 |
| `MTS_PROVENANCE` | Not used in the score, and not given a colour here. Inside a category it is close to a coin flip: on this hospital-day the 84 Urgent referrals split 44 orange / 40 red, and across both hospitals the 155 Urgent referrals split 77 red / 75 orange with 3 carrying no MTS category. No observation in this dataset carries a chief complaint, which is what a Manchester Triage assessment is made from (ADR-004). | Expander section 5, four lines |
| `EXP_S5_ICTS` | ICTS category green — recorded on paediatric referrals in place of MTS. Not used. | Expander section 5, the 3 tail rows |
| `CAPACITY_LIMIT_AND_EFFECT` | Capacity never enters a patient's own score and can never move anyone into a different category or across the waiting-target tier. It sets one exchange rate between urgency and waiting time for the whole hospital-day. Move that rate across its documented range, 0.500 to 0.900, and 272 of these 305 referrals sit at a different position; the largest single move is 51 places. This referral sits at 10 at 0.500 and at 34 at 0.900. | Expander section 6, four lines at 18px = 72 + 20 heading = 92px. Recomputed client-side, never hardcoded |
| `CAPACITY_PRERUN` | No run, so no exchange rate has been set. Capacity has changed nothing on this screen. | Expander section 6 pre-run |
| `EXP_S7_ROLE_URGENCY` | Urgency (1) | Expander section 7 role group heading, fixed order Urgency, Timeframe, Capacity, Multi-list |
| `EXP_S7_ROLE_TIMEFRAME` | Timeframe (1) | Expander section 7 role group heading |
| `EXP_S7_ROLE_CAPACITY` | Capacity (3) | Expander section 7 role group heading; the three ward bed-status nodes |
| `EXP_S7_URGENCY_ONE_NOTE` | One urgency citation: the score node. The six vital signs are that score's own citations and are recomputed in full above. | Expander section 7. Corrects the assumption of six urgency citations |
| `MULTILIST_ZERO` | Multi-list (0) — this coordinator does not cite multi-list evidence. Structurally zero on every referral, not missing data. | Expander section 7, CitationChip structurally-empty |
| `CITATION_FACT` | bed status W-9001-02, 30 August 2026 20:00 — 91 occupied, 1 free, 98.91%, status R | CitationChip line 1, 13px. occupancy_pct is occupied/(occupied+free), never occupied/nominal_beds |
| `CITATION_UNRESOLVED` | This citation did not resolve. It points at a node with no triples loaded, so the audit trail is incomplete here. IRI: {iri} | CitationChip unresolved. Full weight, IRI printed as visible DOM text, never dropped, never counted out of the role total |
| `CITATION_RESOLVING` | Resolving… {evidence_type} {evidence_key} | CitationChip, the unresolved shape from GET /runs/.../scores. Never fabricate a fact from a key |
| `CITATION_EMPTY_DEFECT` | This position cites no evidence. Every placement is written with at least one citation, so this is a fault in the audit trail, not an empty result. | CitationChip empty-array-decision-held. 3px left border |
| `CITATION_EMPTY_NO_DECISION` | No ranking has been written for this hospital-day, so there are no citations to show yet. | CitationChip empty-array-no-decision. Disambiguated from the defect using the orchestrator's own knowledge, never guessed |
| `GRAPH_DEFERRED` | A visual provenance graph of these citations is deferred. Everything it would draw is listed above. | Expander section 7 last line, 18px |
| `EXP_S8_SUMMARY` | Audit fields — decision id, run id, coordinator version, rule checks, stored rationale | Expander section 8 <details> summary, closed by default, 24px |
| `EXP_S8_RULE_CHECKS` | RULE-CRT-URGENT fired · RULE-TRIAGE-TURNAROUND did not fire · RULE-ORDER passed · RULE-TIEBREAK passed | Expander section 8, opened |
| `EXP_S8_IDS` | decision dec-{uuid4} · run {run_id} · coordinator {semantic_version}, capacity direction {dir}, alpha 0.5–0.9, score source live | Expander section 8, opened |
| `RATIONALE_DEFECT` | The coordinator stores a one-line rationale per referral. All 308 in this decision end with the same clause — "urgency weighted more heavily than waiting time" — because it describes one number that applies to the whole hospital-day, not this patient. It is kept here for audit and is deliberately never rendered as this patient's reasoning. | Expander section 8, opened. rationale_summary is never rendered verbatim anywhere else |
| `DOCK_EMPTY` | Pin two referrals to compare them. Press c on a row, or use Compare. | PairwiseCompareDock empty, 44px |
| `DOCK_IDENTITY` | PW-9001-000208 · Urgent · CPC 1 · 871 days, 31× the 28-day target · NEWS2 1 of 17 | PairwiseCompareDock 28px identity band, A left / B right in two 612px halves |
| `STEP1_HEADING` | STEP 1 — CATEGORY | PairwiseCompareDock steps band, 400px column 1 |
| `STEP2_HEADING` | STEP 2 — WAITING TARGET | PairwiseCompareDock, 400px column 2 |
| `STEP3_HEADING` | STEP 3 — SCORE INSIDE THE TIER | PairwiseCompareDock, 400px column 3 |
| `VERDICT_DECIDES` | Decides this pair | PairwiseCompareDock 20px verdict chip |
| `VERDICT_TIED` | Tied — goes on | PairwiseCompareDock verdict chip |
| `VERDICT_NOT_REACHED` | Not reached | PairwiseCompareDock verdict chip, rendered greyed and read, never hidden |
| `STEP1_TIE` | Both are Urgent, CPC 1. The category does not separate them. | PairwiseCompareDock step 1 |
| `STEP1_DECIDES` | A is Urgent (CPC 1), B is Semi-urgent (CPC 3). Category decides this pair; nothing below it was consulted. | PairwiseCompareDock step 1 |
| `STEP2_TIE` | Both are past their 28-day target. The tier does not separate them. | PairwiseCompareDock step 2 |
| `STEP2_DECIDES` | A is past its 28-day target; B is inside it. The tier decides this pair at any score — ADR-011, open. | PairwiseCompareDock step 2 |
| `STEP3_PRERUN` | No scores exist for this hospital-day. Steps 1 and 2 are everything the record can decide on its own. | PairwiseCompareDock step 3 pre-run. Steps 1 and 2 work with no run |
| `TIE_WARNING` | These two are separated by 0.0004 of composite priority. That is not a clinical distinction. The order between them is deterministic — the earlier referral date goes first — but it is not meaningful. | PairwiseCompareDock 32px band. Fires below 0.001 or on identical urgency. The star pair's gap is 0.0057, so it does NOT fire there |
| `IDENTICAL_URGENCY` | Both referrals score NEWS2 0 of 17. On this hospital-day 148 of 308 referrals do, and 87 of the 299 adjacent pairs inside a category and tier are two such referrals. The urgency score cannot separate these two; only waiting time did. | PairwiseCompareDock tie warning, identical-urgency form. The common case, 29.1% |
| `ALPHA_FLIP` | Capacity set one exchange rate between urgency and waiting time for this whole hospital-day. Across its documented range, 0.500 to 0.900, this pair flips: at 0.500 A is above B; at 0.900 B is above A. Capacity — not either patient — decides this one. | PairwiseCompareDock alpha-sensitivity line. Recomputed client-side, two multiplications, no endpoint |
| `ALPHA_STABLE` | Capacity set one exchange rate between urgency and waiting time for this whole hospital-day. Across its documented range, 0.500 to 0.900, A stays above B. This pair does not turn on capacity. | PairwiseCompareDock alpha-sensitivity line, stable form |
| `DOCK_ONE_UNRANKED` | B is outside the ranking: specialty 0601, refused by the urgency agent. There is no score to compare and no contribution is computed. | PairwiseCompareDock one-not-scored |
| `DOCK_CLOSE` | Close comparison | PairwiseCompareDock control |
| `INLINE_HEADING` | Record your order for PW-9001-000208 | Inline reason strip, 72px, in-band move |
| `INLINE_MOVE_STATEMENT` | Moving from position 15 to position 9. Same category, same waiting-target tier. | Inline reason strip |
| `REASON_LABEL` | Reason — required. Recorded against your clinician ID. | Inline strip and modal, coded select label |
| `REASON_PLACEHOLDER` | Choose a reason | Coded select, unselected |
| `REASON_FREETEXT_LABEL` | Further detail — optional | Inline strip input; modal 3-row textarea |
| `INLINE_RECORD` | Record | Inline reason strip primary. Nothing is written until this is pressed |
| `INLINE_CANCEL` | Cancel | Inline reason strip secondary |
| `REASON_EMPTY_ERROR` | Choose a reason. This field is written to the audit trail and cannot be empty. | Inline strip and modal. Required stated in text, never by an asterisk alone, never a silent no-op |
| `MODAL_HEADING_BAND` | This move crosses a clinical priority category. | OverrideDialog, 18px/600, no icon. THE ONE MODAL IN THE PRODUCT |
| `MODAL_HEADING_TIER` | This move crosses the waiting-target tier. | OverrideDialog heading, tier variant |
| `MODAL_HEADING_UNRANKED` | This referral has no position. You are recording an order for it. | OverrideDialog heading, outside-the-ranking row |
| `MODAL_DISCLOSURE_BAND` | RULE-ORDER: no referral is ranked above one of higher clinical priority. PW-9001-000208 is Urgent (CPC 1). PW-9001-000117 is Routine (CPC 2). Moving the Routine referral above the Urgent one breaks that rule. Those categories were set by a clinician at triage, not by this system. | OverrideDialog step 2, the disclosure. ALWAYS precedes the attestation |
| `MODAL_DISCLOSURE_TIER` | Inside a category, every referral past its waiting target is ordered above every referral inside it, at any score. That is ADR-011 and it is an open clinical question in this project — it is not signed off. You are moving PW-9001-000009 from inside the 28-day target to above 75 referrals that are past it. If you think the tiering is wrong, this is exactly the thing to record. | OverrideDialog step 2, tier variant. Open-question framing, not hard-rule framing |
| `MODAL_TABLE_HEADINGS` | This referral / The row it would sit above | OverrideDialog two-column comparison, identical field order in both columns so the eye compares vertically |
| `MODAL_TABLE_FIELDS` | Pathway / Category / Waiting time / Target / NEWS2 / Position | OverrideDialog comparison table row labels, fixed order |
| `MODAL_UNPLACED` | Not currently placed | OverrideDialog comparison table, outside-the-ranking row |
| `ATTESTATION` | I have read the rule above. | OverrideDialog step 3, 24×24 checkbox in a 44px hit row. Unchecked, never pre-ticked. Alone enables step 4 |
| `REASON_OPT_CLINICAL` | Clinical concern | Coded reason select → CLINICAL-CONCERN |
| `REASON_OPT_NEWINFO` | New information | Coded reason select → NEW-INFORMATION |
| `REASON_OPT_PATIENT` | Patient factor | Coded reason select → PATIENT-FACTOR |
| `REASON_OPT_CAPACITY` | Capacity factor | Coded reason select → CAPACITY-FACTOR |
| `REASON_OPT_DATA` | Data error | Coded reason select → DATA-ERROR |
| `REASON_OPT_OTHER` | Other | Coded reason select → OTHER |
| `MODAL_PRIMARY` | Record this order | OverrideDialog 40px action. NOT destructive-styled |
| `MODAL_SECONDARY` | Cancel | OverrideDialog 40px action |
| `MODAL_SHORTCUT` | Move it to the top of its own category instead | OverrideDialog, performs the common correction without abandoning the dialog |
| `REASON_WIRE` | CLINICAL-CONCERN: patient deteriorating, seen in ED Tuesday | POST /overrides reason. The API carries ONE reason string, so the code is prefixed into it |
| `REASON_WIRE_EMPTY` | CLINICAL-CONCERN: no further detail given | POST /overrides reason when the free-text box is empty. Deterministic, satisfies minLength 1, never ends on a bare colon |
| `ACCEPT_WIRE` | ACCEPTED: position confirmed | AcceptAction, POST /overrides reason with from_position == to_position, rule_warning_accepted false |
| `OVERRIDE_RECORDED` | Recorded. PW-9001-000208 now sits at 9, by you. | OverrideDialog recorded; focus returns to the originating row |
| `OVERRIDE_FAILED` | Not recorded. POST /overrides returned 400. The row has been put back where it was; your reason is still in the box. | OverrideDialog post-failed. A row that stays moved after a failed write is a lie about what is recorded |
| `OVERRIDE_NO_DECISION` | Not recorded. POST /overrides returned 400: that decision id is not in the database. Nothing was written. | OverrideDialog error-no-decision |
| `TAIL_HEADING` | Outside the ranking — 3 referrals | OutsideRankingRegion 80px heading block, line 1 at 17px/600 |
| `TAIL_SUBLINE` | Not scored, not placed. This is not a low position. | OutsideRankingRegion heading line 2, 13px |
| `TAIL_BODY` | Specialty 0601 is Paediatric ENT. NEWS2 is validated in adults, so the urgency agent refused these referrals rather than scoring them low (ADR-007). An adult-scaled score for a child would be in range, ordinally plausible and clinically meaningless. Everything a clinician recorded is still shown at full weight: category, waiting time and target. | OutsideRankingRegion heading lines 3-4, 12px |
| `TAIL_SOURCE_RUN` | Membership from the urgency agent's own refused_paediatric bucket. | OutsideRankingRegion, post-run |
| `TAIL_SOURCE_PRERUN` | Membership from specialty_hipe. No run has reported yet. | OutsideRankingRegion pre-run — the region still renders, because the refusal is a property of the specialty |
| `TAIL_NEWS2_NOTE` | PW-9001-000098 has a recorded NEWS2 of 4 — one of only 14 referrals in this cohort scoring 4 or more, and only 6 score higher. It was refused for its specialty, not its physiology. | OutsideRankingRegion / expander section 3 refused state |
| `TAIL_SUB_NO_OBS` | Not scored — no observation to cite (0 referrals) | OutsideRankingRegion sub-heading. Its own words and its own action: report a data gap, not override |
| `TAIL_SUB_UNEXPLAINED` | In the cohort, absent from the decision, no reason recorded ({n} referrals) | OutsideRankingRegion sub-heading. NEVER merged into the paediatric count |
| `TAIL_UNEXPLAINED_BODY` | These referrals are in the cohort and not in the decision. The coordinator stamps exclusion_reason 'missing_urgency_score' on every exclusion whatever the cause, so it cannot say why. This is a data-quality incident, not a coverage statement. Report it; do not override it. | OutsideRankingRegion unexplained-absence |
| `EMPTY_COHORT` | No referral data for 9001 on 31 August 2026. This dataset covers 17–30 August 2026 for two hospitals. | EmptyErrorStateFamily state 1: a 280px panel replacing the list body only. Chrome and selector stay live |
| `EMPTY_COHORT_ACTION` | Go to 30 August 2026 | EmptyErrorStateFamily state 1, the one 40px primary action |
| `HTTP_ERROR` | GET /hospitals/9001/cohort/2026-08-30 returned 502. Nothing is shown for this hospital-day. | EmptyErrorStateFamily state 2: a line in the ledger. Names the UPSTREAM retrieval path, never /api |
| `AUTH_ERROR` | Not authorised. The retrieval API rejected the bearer token held by the orchestrator. Set RETRIEVAL_BEARER_TOKENS in the orchestrator's environment and restart it. The browser never holds this token. | EmptyErrorStateFamily state 2, 401 variant |
| `ORCH_UNREACHABLE` | The orchestrator did not answer on this origin. The browser holds no retrieval token, so there is no fallback. Restart the orchestrator service. | EmptyErrorStateFamily state 2, same-origin failure |
| `PARTIAL` | Showing 142 of 308 referrals. The rest did not load. This is not the whole list. | EmptyErrorStateFamily. A partial list is NEVER rendered without this line and both numbers |
| `LOADING` | Loading cohort… | LoadingRule, one line in the ledger, only past 400ms. No skeleton table anywhere |
| `FIND_HINT` | Use your browser's find (Ctrl+F / Cmd+F) to jump to a pathway number — every row is on the page. | RankedTableShell footer. All 308 rows are always in the DOM |
| `KEYBOARD_HINT` | e evidence · c compare · a accept · m move · [ ] jump band | RankedTableShell footer |
| `EXPORT_FOOTER` | Synthetic data. Decision support, not a decision. Urgency is NEWS2 only — six vital signs. 9001 St Brendan's, 30 August 2026, run {run_id}. Ordered under ADR-011, an open question; not final. | Every export and screenshot. Not dismissible, not collapsible |

---

## 7. Functional requirements

Numbered and testable. "The band boundary is visible without colour" is testable; "the UI
is clear" is not.

| id | requirement | how to verify |
|---|---|---|
| F1 | The product is ONE route, /h/:hospital/d/:date, plus a redirect from /. There is no page-level navigation, no dashboard, no patient page, no settings screen and no separate XAI page (AppScaffoldAndDataLayer, S1). Every surface in this pack is an in-screen region of that route, the bottom dock, the named tail region, or the single modal. | Grep the built bundle for router definitions: exactly one data route plus one redirect. Assert document.querySelectorAll('nav').length === 0 at every state including error and empty. |
| F2 | ONE grid, six fixed tracks, at every width from 1280 up: Rail (position+pathway, sticky left) 192 \| Category and timeframe 176 \| Waiting time and target 256 \| Urgency (NEWS2) 184 \| Why this position 192 \| Actions (sticky right) 248 = 1248px content inside 16px page gutters at 1280. table-layout:fixed inside one overflow-x:auto container (RankedTableShell). There are no specialty and no flags columns at any width - both are deleted. | At 1280x720 measure the six <col>/<th> computed widths and assert exactly [192,176,256,184,192,248] and their sum === 1248. Assert exactly six <th> at 1280, 1440 and 1920. Assert document.documentElement.scrollWidth === clientWidth at all three. |
| F3 | Above 1440px CSS width, content width = viewport - 32 and the ENTIRE surplus goes to column 5 (Why this position) only. At 1440: content 1408, column 5 = 352, the other five tracks unchanged (192/176/256/184/248). | At 1440x900 assert the six widths are [192,176,256,184,352,248] summing to 1408, and that no track other than column 5 differs from its 1280 value. |
| F4 | Sticky chrome is exactly 172px desk and 196px present, composed in this fixed order with these fixed heights, each unchanged in EVERY state so no state change moves the list: context bar 40/44, scope line 24/28, reconciliation ledger 28/32, ordering strip 40/48, column header 40/44. scroll-padding-block-start equals the same figure; band group headers are position:sticky;top:172px (196 present). | Sum the five chrome elements' offsetHeight: === 172 at --row-h 48 and === 196 at 56. Drive every state of every strip (pre-run, running, ranked, filtered, mismatch, loading, error, re-run confirm) and assert none of the five heights changes. Assert getComputedStyle(scroller).scrollPaddingBlockStart === '172px'. |
| F5 | Every disclosure in the chrome - the four scope-line clauses, the hospital-day selector, ADR011_FULL behind [Why this matters], the tier divider's Why?, the urgency-caveat clause - expands BELOW the sticky stack, pushes the list, and is never a modal, never a tooltip and never sticky. None of them changes the 172px. | Open each disclosure in turn and assert the summed chrome height is still 172 and that the first list row's offsetTop increased by exactly the disclosure's height. |
| F6 | Row height is DERIVED, not assumed: --row-h is 48px desk (4 top pad + 24px line box A + 16px line box B + 4 bottom pad) and 56px present (4 + 28 + 20 + 4, type up one step). Every cell renders EXACTLY TWO line boxes, never three. No text anywhere in a row is below 12px. Density is one token flip of --row-h and --type-step; there is no second stylesheet and no root-font-size toggle (AppScaffoldAndDataLayer). | Assert every <tr> offsetHeight === 48 (then 56). For each of the six cells assert the count of block-level text lines <= 2. Assert min computed font-size across the row subtree >= 12px. Grep for a second media-query stylesheet or an html{font-size} toggle: zero matches. |
| F7 | The dependent geometry is re-derived from --row-h and published: band group header 40/44; breach tier divider 32/36; Outside-the-ranking heading block 80/88 opened by a 24px gap and a 3px rule; row expander max-height 520/560; pairwise dock 208/240; inline reason strip 72/80. Total scroll height for 9001/2026-08-30 ranked = 308x48 + 5x40 + 2x32 + 107 = 15,155px desk and 17,655px present. | Measure each element type's offsetHeight against the table. Assert scroller.scrollHeight === 15155 (+/- 1) at --row-h 48 with the tail region present and no expander open. |
| F8 | The above-the-fold count is TEN rows at 1280x720 desk, not fourteen: list viewport 720-172 = 548, Urgent group header 40, (548-40)/48 = 10.58 so rows 1-10 are fully visible and row 11 is clipped. Present density: 8 rows. 1440x900: 14 rows. Dock open: 6 desk / 4 present / 10 at 1440. Every demo narrative, screen and caption uses these figures. | At 1280x720 with the list scrolled to top, count <tr> elements whose bounding box is entirely between 172 and 720: assert 10. Repeat at --row-h 56 (assert 8) and 1440x900 (assert 14). Open the dock and re-assert 6. |
| F9 | Every referral row is in the DOM at all times. No virtualisation, no windowing, no overscan, no measureElement (C5). Rows are memoised and keyed by pathway_number, never by array index. | With the 308-row cohort loaded and scrolled to top, document.querySelectorAll('tr[data-pathway]').length === 308. Ctrl/Cmd+F for 'PW-9001-000024' (index 220 in cohort order) finds and highlights it without scrolling first. Grep the bundle for a virtualiser import: zero matches. |
| F10 | NO COLUMN SORTING ANYWHERE (R4). No sort control, no sortable affordance, no 'sorted' state, no aria-sort, no scope caption, and no role=button, tabindex or click listener on any <th>. Ordering is the coordinator's and is never re-derived client-side except for the two computations this pack names as the interface's own arithmetic (the alpha-sensitivity re-sort and the pairwise contributions), both of which are labelled as such. | Assert no <th> carries aria-sort, role, tabindex or a click listener. Grep the bundle for 'aria-sort', 'sortBy', 'Sorts within': zero matches. Click every header cell 10 times and assert the rendered pathway_number sequence is byte-identical before and after. |
| F11 | The browser NEVER calls the retrieval service. All calls go same-origin to the orchestrator: GET /ui/cohort/{h}/{date}, GET /ui/decision/{h}/{date}, GET /ui/runs/{run_id}, GET /ui/context/{h}/{pw}, POST /ui/runs, POST /ui/overrides, GET /ui/health. Retrieval has no CORS middleware and its bearer token must never reach the browser. User-facing error strings name the UPSTREAM retrieval path, never the /ui proxy path. | Record every network request across a full session including a run and an override: assert every URL begins with the page origin and none matches :8000 or /hospitals/ or /referrals/ or /decisions/. Force a 502 and assert the visible string contains 'GET /hospitals/9001/cohort/2026-08-30' and '502'. |
| F12 | One formatting module owns every number rendered anywhere (AppScaffoldAndDataLayer): leading zero always; normalised urgency 3dp; signed contributions 3dp with an explicit + or -; wait days 0dp; the row multiplier FLOORED to an integer; the expander multiplier 1dp; units always attached; font-variant-numeric:tabular-nums on every numeric cell; numerics right-aligned, identifiers and prose left-aligned, nothing centred. | Grep for toFixed/Intl.NumberFormat outside that module: zero matches. Screenshot 20 wait cells and 20 urgency cells at 400% zoom and assert digits align vertically with a constant decimal count per column. Assert Math.floor is used for the row multiplier by feeding 2.9 and asserting '2x'. |
| F13 | The list is divided into FIVE band groups in SEVERITY_RANK order - Urgent (cpc 1), Semi-urgent (cpc 3), Routine (cpc 2), No category recorded (cpc null), Excluded (cpc 4) - followed by the Outside-the-ranking tail region. The Excluded header RENDERS at zero rows. cpc 4 and cpc null are two separate tails and are never merged (ADR-006). | For 9001/2026-08-30 assert six region headings in that DOM order with the Excluded heading present and reading 0 referrals. Load 9002/2026-08-30 and assert the counts read 71/94/90/46/0 with nothing hardcoded. |
| F14 | Each BandGroupHeader carries on line 1, in this order: band name in words, CPC code, referral count, ranked count, not-ranked count where non-zero, and the target in days or 'no waiting target applies'. The ranked/not-ranked split is MANDATORY because the three paediatric refusals carry cpc 2, 2 and null, so their removal is otherwise invisible. Line 2 carries the breach split, and pre-run also DISPLAY_ORDER. | Post-run assert the Routine heading contains '86 ranked' and '2 outside the ranking', and the No-category heading contains '54 ranked' and '1 outside the ranking'. Assert the Urgent heading contains 'target 28 days' and '75 past the 28-day target, 9 within'. |
| F15 | A band boundary is carried by at least three redundant non-colour channels simultaneously: a >=12px gap, a >=2px full-bleed rule, and the header's own words. Band identity must survive with every colour token forced to one greyscale value. | Apply a stylesheet forcing all colour custom properties to a single grey; screenshot at 1280x720. A reader can still count six regions and name each one from text alone. |
| F16 | BreachTierDivider is drawn ONLY in the ranked state and only inside CPC 1 and CPC 3, at the crt_breached true->false transition (after row 75 of 84 in Urgent, after row 55 of 81 in Semi-urgent for 9001/2026-08-30). It is a 32px row (36 present) whose 1px rule spans columns 2-5 only and does not cross the frozen rails, with a 12px caption and a 'Why?' control at a 24x24 target opening an inline 3-line disclosure. It is styled as a structural fact, never as an error, warning or defect. | Ranked, assert exactly two divider elements and zero in Routine, No-category and Excluded. Assert the rule element's bounding box starts at x>=192 and ends at x<=1000. Assert the divider carries none of the defect authority tokens. Open Why? and assert the anchor row's scroll offset is unchanged. |
| F17 | There is NO breach tier divider PRE-RUN, because pre-run order is referral_date (R5) so breached and within-target rows interleave and no single transition exists. Pre-run the band header carries the split as a count and states PRE_RUN_TIER_NOTE - 'The tier line is drawn once a ranking exists.' | With no decision held, assert zero divider elements and assert the Urgent heading contains '75 of 84 are past the 28-day target' and 'drawn once a ranking exists'. |
| F18 | Referrals the urgency agent refused sit in the OutsideRankingRegion below the Excluded header, opened by a 24px gap and a 3px full-bleed rule (double a band separator) and an 80px heading block (88 present) reading TAIL_HEADING / TAIL_SUBLINE / TAIL_BODY. The region is never collapsible, and a refused referral NEVER appears in place among ranked rows - the three 0601 rows are verified non-contiguous in cohort order (indices 57, 193, 220). | Assert no row with specialty_hipe 0601 appears above the tail heading in DOM order. Assert the region has no collapse control. Assert the heading contains 'This is not a low position.' |
| F19 | Tail rows render on the SAME six tracks at the same row height, with their category chip and wait meter at FULL normal weight because those are clinician-recorded facts. The rail's position sub-column is NOT rendered for them; the cell carries the visually-hidden NO_POSITION_ARIA string. Their Accept is disabled with ACCEPT_DISABLED_UNRANKED in visible text; Move stays ENABLED; Compare and the disclosure stay enabled. | For PW-9001-000098, PW-9001-000146 and PW-9001-000024 assert: chip text non-empty; wait cells show 330, 101 and 70 days with a rendered track; no position numeral in the DOM; the row's accessible name contains 'No position. This referral is outside the ranking.'; Accept has [disabled] plus an adjacent visible reason; Move has no disabled attribute. |
| F20 | The four not-ranked categories - refused_paediatric, skipped (no observation to cite), graph_projection_failed, and absent-with-no-reason-reported - get four separately labelled counts, four separate sub-headings and four separate destinations. They are NEVER summed into one 'excluded' figure. The coordinator stamps exclusion_reason 'missing_urgency_score' on every exclusion regardless of cause, so attribution comes from specialty_hipe plus the urgency agent's four-bucket report, and anything the orchestrator cannot attribute renders under its own sub-heading. | Grep the view model and the DOM for any element whose text equals the sum of two or more bucket counts: none. Stub an unattributable absence and assert it renders under 'Absent from the ranking, reason not reported' and is NOT added to the paediatric count. |
| F21 | position is a flat unique integer 1..305 across the whole decision, never restarted per group (ADR-006). Any 'nth of 84 in this category' figure is secondary text in the expander only and never appears in the rail. | Collect every rendered position numeral: assert the multiset equals {1..305} exactly, with no duplicates and no gaps, and that the rail cell contains no '/' or 'of'. |
| F22 | ReferralRailCell merges position and pathway into one 192px sticky cell (R1). Line 1: a permanently reserved 16px A/B marker slot, the position numeral right-aligned and MUTED at 15px tabular, then pathway_number at 13px tabular left-aligned and NEVER truncated - if the chosen face is wider, the pathway drops to 12px rather than clipping. Line 2: specialty code then name at 12px muted. No patient name, date of birth, MRN or IHI appears anywhere in the product, because the context endpoint returns none. | Assert no pathway cell has text-overflow:ellipsis or a clipped scrollWidth. Assert the A/B slot occupies 16px when unpinned. Grep the bundle and every payload render path for 'name', 'dob', 'mrn', 'ihi': zero matches in row or expander output. |
| F23 | PRE-RUN, absence is expressed STRUCTURALLY, not by placeholder glyphs (R5): the rail's 34px position sub-column is NOT RENDERED and the pathway sub-column expands, the A/B marker slot stays; columns 4 and 5 render EMPTY cells whose two header cells are replaced by ONE header cell spanning both tracks (376px) captioned PRE_RUN_COLUMN_HEADER. There is no em dash, no zero and no 'Not yet scored' repeated 308 times. | With GET /ui/decision returning no held decision, assert: zero position numerals in the DOM; thead contains a single <th colspan=2> whose text contains 'Not ranked yet' and 'No agent has scored this hospital-day'; the urgency and why cells have empty textContent; and the string 'Not yet scored' occurs at most once in the whole document. |
| F24 | CategoryTimeframeChip has exactly THREE form levels and no border-weight coding: filled ground for Urgent, outline for Semi-urgent, plain text for Routine / No category recorded / Excluded. Meaning is carried by the words, printed in full in every case, plus line 2's target status in words. | Assert exactly three distinct chip treatments exist across all five categories. Assert no chip rule uses a 1px-vs-2px border distinction. Force greyscale and assert all five categories remain nameable from text. |
| F25 | The within-target state renders as NEUTRAL TEXT and is never a tick, never a success colour, never 'OK'. The copy names the rule that did or did not fire: 'Past the 28-day target' beats 'overdue'; 'Within the 28-day target' means only that RULE-CRT-URGENT did not fire. 'Routine' line 2 reads 'No target for this category', never blank. 'No category recorded' is never 'Low', never 'Unassigned' and is never greyed out. | Grep the copy dictionary for tick glyphs, 'OK', 'Low', 'Unassigned', 'compliant', 'on track': zero matches in any category or wait context. Assert no within-target cell uses a success token (there is no success level in the taxonomy - see F81). |
| F26 | WaitTargetCell gives waiting time the visual dominance on the row, because it is the variable that discriminates: 213 distinct adjusted_wait_days across 308 rows against a NEWS2 column where 148 tie at exactly 0. Line box A holds the 140x10px meter left and the days count right-aligned in 92px at 20px/600 tabular - the LARGEST numeral on the row. Line box B holds the target statement at 12px. Dominance order: wait numeral > category chip > NEWS2 integer > normalised score = position numeral. | Measure computed font-size and weight of each element on a row and assert that ordering. Assert the position numeral uses the muted authority level and is never the largest numeral. |
| F27 | The meter uses a per-band square-root scale over that band's OWN observed maximum ratio, so nothing is ever clipped and there is no overflow to draw: CPC 1 domain 0-31.107x (1x at 25.1px, 2x at 35.5px, 5x at 56.1px, 10x at 79.4px, 31.107x at 140.0px); CPC 3 domain 0-9.099x (1x at 46.4px, 2x at 65.6px, 5x at 103.8px, 9.099x at 140.0px). The 1x target is a separate 2px-wide 18px-tall mark overshooting the track 4px above and below. Square root is permitted only because it is monotonic: it may compress magnitude and can never reverse two patients. | Recompute 140*sqrt(ratio/bandMax) for 20 rows in each band and assert the rendered fill widths match to 1px. Assert the band maxima are read from the cohort (31.107 and 9.099 for 9001) and not hardcoded: load 9002 and assert different domains. |
| F28 | WaitTargetCell line 2 has eight disjoint states: past-target at 2.00x or above prints the FLOORED integer multiplier (a row never claims a larger overshoot than it has); past-target from 1.00x to under 2.00x (28 rows: 9 CPC-1, 19 CPC-3) prints days over, because '1x the target' reads as compliant; AT-TARGET at exactly 1.00x prints 'At the 91-day target' - never 'Within', never '1x', never a tick - with the fill terminating on the LEFT edge of the 2px tick at 45.4px, never past it and never overlapping it; within-target (35 rows) is a state word; no-target (143 rows) renders an empty outlined track with NO fill and NO target mark, a visibly different KIND of cell, while line 1 still prints the days; zero-wait (11 rows) renders a 2px origin stub plus the literal '0 days'; suspended prints 'Clock suspended' as a word. | Verified live reference rows: PW-9001-000208 871/28 = 31.107x renders '31x the 28-day target'; PW-9001-000137 30/28 = 1.07x renders '2 days over a 28-day target'; PW-9001-000020 91/91 renders 'At the 91-day target' with crt_breached false and fill width === tick left edge; a Routine row renders an outlined track with fill width 0 and no tick; a zero-wait row's fill computed width >= 2px with text containing '0 days'. Assert no row cell matches /\d+\.\dx/. |
| F29 | The meter is strictly redundant (F17 of the prior set holds): applying display:none to it leaves both text lines carrying the days, the target and the breach state in words. It is aria-hidden and presentational, and the cell carries a full accessible name. | Apply .wait-meter{display:none} and screenshot: every wait cell still states the days, the target and the breach state. Assert the meter element has aria-hidden=true and the cell's accessible name matches WAIT_ARIA. |
| F30 | UrgencyNews2Cell renders exactly TWO lines. Line 1 is PRIMARY and hand-checkable: 'NEWS2 1 of 17' at 15px/600 tabular, the denominator ALWAYS printed because NEWS2_MAX is 17 (temperature's top band is 2, every other component's is 3). Line 2 demotes the computed value: 'normalised 0.075' at 12px muted, always 3dp. The third line both prior specs carried ('6 vitals cited') is CUT per R2; the citation count survives in expander section 7's role heading. | Assert exactly two lines in the cell. Assert line 1's computed font-size and weight exceed line 2's. Assert every rendered denominator is 17 and that '0.08' appears nowhere in the bundle or the DOM. |
| F31 | There is NO bar, meter, gauge, ring, sparkline, colour ramp or confidence indicator of any kind in the urgency cell, at any state. Nothing in agent.agent_scores carries an uncertainty, and 148 of 308 rows would render an empty bar that reads as missing data for half the list. | Assert the urgency cell subtree contains only text nodes - no svg, canvas, progress, meter, or width-driven div. |
| F32 | A NEWS2 score of 0 (148 rows) renders in a form STRUCTURALLY IDENTICAL to any other scored value - 'NEWS2 0 of 17' / 'normalised 0.000'. It is never blank, never an em dash, never zero-width, and never labelled 'low urgency', 'not urgent', 'low risk', 'stable', 'normal' or 'no concern'. | Assert the 148 zero-scoring cells have the same DOM structure and class list as a scoring cell. Grep the copy dictionary for those six adjectives in any urgency context: zero matches. |
| F33 | The urgency cell has seven disjoint renderings that never share a string and never render as the same glyph: scored; scored-zero; awaiting (mid-run) 'Awaiting urgency agent' with line 2 absent; refused 'Not scored' / 'Paediatric refusal'; skipped 'Not scored' / 'No observation to cite'; evidence-unresolved (score on line 1, 'Evidence did not resolve' on line 2); and PRE-RUN, where the WHOLE COLUMN is absent per F23. | Render all seven in a fixture: assert seven distinct textContent values, none of which is '-', '0' or ''. Assert the pre-run case removes the column rather than filling cells. |
| F34 | WhyThisPositionCell answers the contrastive question in words and NAMES ITS FOIL, so the claim is checkable by looking one row down. Line 1 at 13px is the verdict; line 2 at 12px muted is 'vs {pathway_number}'. The column header reads 'Why this position' / 'vs the row below'. There is no graphic: the prior 6px two-segment hatched strip is deleted (a 6px mark subtends about 12.7 arcmin at projector distance, and a share of a total is not a contribution to a difference). Signed arithmetic appears ONLY in the dock and the expander. | Assert no collapsed row cell matches /[+-]?0\.\d{3}/. Assert every ranked row's line 2 contains a pathway number that equals the pathway of the adjacent row in the same band and tier taken from the held ordered array. Assert the cell subtree contains no svg or width-driven element. |
| F35 | WhyThisPositionCell has fixed boundary states: tier-boundary reads 'Tier decided this' / 'Scores did not decide'; band-boundary reads 'Category decided this' / 'Scores did not decide'; last-in-tier compares against the row ABOVE and says so; outside-the-ranking renders an EMPTY cell because there is no position and so no comparison; pre-run the whole column is absent. 'Ahead on waiting time' with a zero urgency term is the commonest verdict on this cohort: 87 of the 299 adjacent same-band same-tier pairs are two NEWS2-0 referrals. | For the row immediately above each tier divider assert 'Tier decided this' and 'Scores did not decide'. For the last row of each band assert 'Category decided this'. For a tail row assert the cell's textContent is empty. |
| F36 | ContributionDisplay is ONE renderer shared by dock step 3 and expander section 1, so the two surfaces cannot disagree: a three-row four-column table at 15px tabular, fixed 3dp, right-aligned, with an explicit + or - on EVERY figure including a negative one, rows in the fixed order 'urgency contributed' / 'waiting contributed' / 'composite priority', columns A / B / difference (18px header + 3x18px = 72px), followed by one COMPUTED closing sentence at 13px that is never model-generated. It is a contribution to a DIFFERENCE, never a share of a total, and alpha never appears as a bare coefficient. | Grep for a second contribution renderer: exactly one component. For a same-band same-tier pair recompute alpha*(u_a-u_b) and (1-alpha)*(w_a-w_b) independently and assert the rendered figures match to 3dp with signs. Reference pair at alpha 0.7: PW-9001-000208 (u 0.075, w 0.9940, p 0.3507) above PW-9001-000026 (u 0.225, w 0.6250, p 0.3450) - waiting +0.111, NEWS2 -0.105, net +0.006. |
| F37 | ContributionDisplay REFUSES to compute when the pair is separated by a band or a breach tier: the table is not rendered and a sentence naming the deciding boundary replaces it. Printing numbers that did not decide the ordering is a fabricated explanation. Pre-run the table is absent and says no scores exist. | Pin a CPC-1 row against a CPC-3 row: assert no arithmetic table exists in the DOM and the replacement sentence names the category. Repeat across the tier divider and assert the tier sentence. Pre-run assert the table is absent. |
| F38 | ActionRail is four controls in a fixed order at fixed widths inside the 232px content of the 248px sticky right track, never reordered and never conditionally omitted: Compare 64, Accept 72 (sized so 'Accepted' fits the same box without reflow), Move 46, disclosure 24, separated by three 8px gaps = 230px. All are 13px text labels at 24px height. The disclosure's accessible name is 'Show evidence'; its state is carried by aria-expanded and by the expander actually appearing - it is a control, not an information channel. | Measure the four control bounding boxes: assert widths [64,72,46,24], gaps 8, all heights >= 24, and total <= 232. Assert the order is constant across all rail states. Toggle Accept to 'Accepted' and assert the control's width is unchanged. |
| F39 | A disabled control is disabled WITH A VISIBLE REASON rendered as text on line box B of the row at 12px - never a title attribute, never a tooltip - and line box B never collapses the row when empty. Measured to fit the 232px track: ACCEPT_DISABLED_UNEXPANDED 211px, MOVE_DISABLED_PRERUN 230px, ACCEPT_DISABLED_UNRANKED 179px. | For each disabled state assert the reason string is in the DOM as visible text with no title attribute, that its rendered width <= 232px on one line, and that the row's offsetHeight is unchanged from an enabled row. |
| F40 | Overriding is NEVER harder to reach than accepting. Accept is disabled until that row's evidence has been rendered at least once this session (one expansion arms it permanently for that row); Move is NEVER gated wherever a position exists, and Move is ENABLED on Outside-the-ranking rows because from_position and to_position are both nullable in OverrideIn. | On a freshly loaded ranked list assert every Accept is disabled and every Move is enabled. Expand one row, collapse it, assert only that row's Accept is now enabled. On a tail row assert Accept disabled and Move enabled. |
| F41 | ACCEPT IS AUDITED (R6). AcceptAction posts POST /ui/overrides -> POST /overrides with from_position === to_position === the row's current position, reason exactly 'ACCEPTED: position confirmed', rule_warning_accepted false, plus override_id (UI-generated), decision_id (held by the orchestrator), hospital_hipe, pathway_number and clinician_id. There is no accept endpoint in the 11-path API; this is the only write path that exists. Accepting never requires a reason and never opens a dialog. | Click Accept and inspect the request body: assert from_position === to_position, reason === 'ACCEPTED: position confirmed', rule_warning_accepted === false. Assert no <dialog> opened and no reason field was presented. |
| F42 | An accepted row's Accept control becomes the disabled label 'Accepted' in the same 72px box and rail line 2 is replaced by ACCEPTED_RESIDUE ('Accepted 14:07'), at the same visual weight as any other row and never as an error or a success state. The residue SURVIVES a hospital/date switch, because the orchestrator holds an override log keyed by (hospital, date, pathway) that the UI refetches on every route change. It does NOT survive an orchestrator restart, and the ledger says so in words rather than silently showing an unaccepted list. There is no undo: the way to change an acceptance is to record a move. | Accept a row, switch to 9002/2026-08-30 and back, assert the residue is still rendered. Restart the orchestrator and assert the UI falls back to pre-run with the in-memory sentence visible. Grep for an undo control on an accepted row: none. |
| F43 | If the accept write fails, the row shows NO residue, the control returns to 'Accept', and the failure names the endpoint and the status code. A row that looks accepted after a failed write is a lie about what is recorded. The acceptance count is NOT a term in the reconciliation ledger. | Stub a 400 on POST /overrides: assert rail line 2 shows the specialty again (no residue), the control reads 'Accept', and the visible failure string contains 'POST /overrides' and '400'. Assert the ledger still shows exactly six terms. |
| F44 | There is no bulk accept, no accept-all, no select-all checkbox and no multi-row selection anywhere in the product. | Grep the DOM at every state and the bundle for a select-all or bulk action control: zero matches. |
| F45 | RowEvidenceExpander is a full-width row inserted directly beneath the expanded row that PUSHES the list and never overlays. 16px inset each side, TWO columns of 592px with a 32px gutter (16+592+32+592+16 = 1248), text measure capped at 68ch per column, max-height 520px desk / 560px present with overflow-y:auto on the BODY only, and a 24px pinned header restating the pathway number. Sections are separated by a 16px gap. | Assert the expander row's width === 1248 and the two column widths === 592 with a 32px gap. Assert max-height 520 at --row-h 48 and that only the body scrolls. Assert the row plus expander measures 568px. |
| F46 | The expander presents EIGHT sections in a FIXED reading order, because the order is the safety argument, and a section that has nothing to show is replaced by its own explanatory sentence rather than removed. LEFT: (1) position and what decided it 74px; (2) the waiting-target rule 56px; (3) NEWS2, all six components 197px; (4) Read but not scored 92px; (5) On the record, not used in the score 110px - 529px plus four 16px gaps = 593px. RIGHT: (6) Capacity for this specialty and what it changed 128px; (7) Citations grouped by role 252px typical; (8) Audit fields as a closed <details> 24px - 404px plus two gaps = 436px. | Assert the eight headings appear in that DOM order in EVERY expander state including pre-run, refused and error. Measure the left column at 593px and assert sections 1-3 sum to 359px. |
| F47 | Sections 1-3 (359px, the safety core) are guaranteed ABOVE the expander's own internal scroll fold at both densities: position and what decided it, the waiting-target rule, and the six NEWS2 components with their total, visible without scrolling of any kind. | Open an expander at 1280x720 and assert the section-3 total line's bounding box is inside the expander's visible area with scrollTop === 0. |
| F48 | Section 3 shows ALL SIX NEWS2 sub-scores including every one that scores 0, each as 'vital, value, arrow, sub-score', right-aligned tabular, then a rule and 'Total -> 1 of 17', then HAND_CHECK ('Add the right-hand column. If it does not come to 1, this screen is wrong.'). Sub-scores are recomputed CLIENT-SIDE from the committed rubric and MUST equal the stored news2 for every referral; if they ever disagree the screen says so rather than silently showing either number. | For PW-9001-000208 assert six rows reading rr 17->0, spo2 99->0, sbp 140->0, hr 108->1, avpu A->0, temp 36.4->0 and a total of 1 equal to the stored value. Batch-recompute all 308 in TS and assert 308/308 agreement. Force a disagreement in a fixture and assert the mismatch statement renders instead of a number. |
| F49 | The client-side recompute reproduces four rubric traps exactly: systolic blood pressure is NOT a descending ladder (>=220 scores 3, the same as <=90); AVPU is binary (A->0, V/P/U->3); temperature's top band is 2, which is why NEWS2_MAX is 17; and temp arrives as a JSON STRING and must be parsed before scoring. | Unit-test the four traps with sbp 230, avpu 'V', temp '39.5' as a string and a temp band boundary, asserting 3, 3, 2 and correct parsing. Assert NEWS2_MAX is a named constant equal to 17 and appears nowhere as 18 or 20. |
| F50 | Section 3 states the calibration in plain language - CALIBRATION_NOTE: four anchors 0->0.000, 4->0.300, 6->0.600, 7->1.000 with straight lines between; only EIGHT values are reachable on this data; three decimals is the storage column's precision, not a claim of precision. | Assert the four anchor pairs appear verbatim and the eight-reachable-values sentence is present. Independently compute 0 + (1/4)*0.30 === 0.075 and assert the rendered normalised value matches. |
| F51 | Section 4 'Read but not scored' names every recorded field the agent saw and could not score - at minimum pain, diastolic blood pressure, MTS category and the ICD-10-AM condition - and carries READ_NOT_SCORED, which distinguishes 'those six were near normal' from 'this patient is near normal'. For a REFUSED row, section 3 is replaced by the refusal statement but section 4 STILL RENDERS THE SIX VITAL VALUES with no sub-scores and no total, because PW-9001-000098 carries a recorded NEWS2 of 4 and hiding that would be less honest than the refusal. | For PW-9001-000208 assert the section names pain 10, dbp 94, MTS Orange and C43.9 and contains the near-normal distinction. For PW-9001-000098 assert section 3 shows the refusal statement, section 4 shows six vital values, and no total and no sub-score is rendered. |
| F52 | Section 5 lists EVERY condition on the record (408 rows across 308 referrals: 208 have one, 100 have two) with CONDITION_PROVENANCE and MTS_PROVENANCE attached. The record's stored label is the literal placeholder 'Condition C43.9' and snomed_ct_id is null on all 408 rows. The UI must not ship an ICD-10-AM dictionary and must not invent a plain-English term for any code. | For a two-condition referral assert both codes render. Grep the bundle for any ICD-10-AM lookup table or code->English map: zero matches. Assert the quoted label string is present verbatim. |
| F53 | Section 6 states capacity's REAL effect (C2) with its two limits alongside, using CAPACITY_LIMIT_AND_EFFECT: capacity never enters an individual's score and can never move anyone across a CPC band or across the waiting-target tier, but it DOES set the exchange rate between urgency and waiting time, and at the other end of the documented 0.50-0.90 range 272 of these 305 referrals sit at a different position. The claim 'capacity does not separate two patients in the same specialty' is FORBIDDEN - it is false, and coordinator/app/priority.py's own docstring is wrong. | Grep the copy for 'cannot reorder', 'does not separate' or equivalent: zero matches. Assert both the limit sentence and the effect sentence are present and that the 272 figure is computed at render time, not a literal in the bundle. |
| F54 | Section 7 uses the held decision's citations first and GET /ui/evidence only as a fallback, grouped by role in the fixed order Urgency, Timeframe, Capacity, Multi-list, each with a count. The coordinator emits exactly ONE urgency citation (the score node), not six - the six vitals are that score's own citations and live in section 3 labelled as recomputed. multi_list is never emitted by this coordinator at all, so its group is structurally zero forever and is labelled MULTILIST_ZERO rather than left to read as missing data. | Assert the urgency group heading reads 'Urgency (1) - the urgency score node for this run' and contains exactly one entry. Assert the multi-list heading carries the structural sentence and is never rendered as an error or an absence. |
| F55 | CitationChip renders one cited node as a 32px two-line entry: line 1 the resolved fact at 13px, line 2 the IRI at 12px monospace middle-ellipsised at 420px with the full string revealed on focus and always selectable. An UNRESOLVED citation (type null, empty properties) stays in the list at FULL WEIGHT with its complete IRI printed as visible DOM text and CITATION_UNRESOLVED beside it - never dropped, never blank, never tooltip-only, never counted out of the role's total. The scores endpoint's different unresolved shape ({evidence_type, evidence_key}) renders as 'Resolving...' plus the key and never fabricates a fact from a key. | Stub one entry with type:null: assert its IRI is present in the DOM as text (not in a title attribute), that the role count is unchanged, and that its computed opacity and font-size match a resolved entry. |
| F56 | An EMPTY evidence array is disambiguated BEFORE it is rendered, using the orchestrator's own knowledge of whether it holds a decision - the UI must never guess. No decision held -> 'no ranking has been written'. Decision held but evidence empty -> CITATION_EMPTY_DEFECT at defect authority with a 3px left border, because write-time validation guarantees every placement has at least one citation, so this is a fault in the audit trail and not an empty result. | With no decision held assert the no-ranking sentence. With a decision held and evidence stubbed empty assert the defect sentence and the 3px left border. Verified live today: GET /evidence/9001/2026-08-30/PW-9001-000208 returns 200 with an empty array because no decision exists. |
| F57 | Section 8 is a CLOSED <details> holding rationale_summary and rule_checks, labelled as audit fields with RATIONALE_DEFECT stated above it. rationale_summary is NEVER rendered on a row, in a tooltip, in the dock, or as this patient's reasoning: all 308 strings carry the same clause about capacity pressure, generated by a single midpoint test on alpha, so it describes a hospital-day parameter and would contradict the honest contribution arithmetic printed two inches away. Rule checks render as neutral text with the rule id, the numbers and the outcome, closing with RULE_NOT_FIRED. | Grep the row and dock render trees for rationale_summary: zero references. Assert it appears only inside a <details> closed by default with the defect sentence above it. Assert no rule-check row contains a tick glyph or a success token. |
| F58 | Expander sections 2, 3, 4, 5 and 6 render FULLY from the cohort payload plus one context call with NO agent run. Sections 1 and 7 are present with their own explanatory sentence and are NEVER removed, because the fixed order is the safety argument and a missing heading breaks it. | With no decision held, expand any row and assert eight headings, five fully populated sections, and explanatory sentences under 1 and 7. |
| F59 | ReconciliationLedger is ONE 28px line (32 present) pinned under the ordering strip, SIX terms in a fixed order separated by a middot and 12px of space, never by colour, each a filter toggle at a 24x24 target: LEDGER_1..LEDGER_6. The ranked string measures 164 characters = 1050px of the 1248px track; the counts-unavailable variant is 185 characters = 1184px and still holds on one line. It is never a warning callout. | Assert exactly six toggles, one line, and rendered width <= 1248 in both variants. Post-run assert scored + outside-the-ranking + not-scored + absent === cohort size, rendered as digits on screen. Assert the ledger uses no warning token, no icon and no role=alert. |
| F60 | The ledger has seven exact states: pre-run renders LEDGER_PRERUN and asserts nothing no source reported; running renders the scored-so-far form; ranked renders all six terms with the arithmetic adding up on screen; filtered adds a second line stating the fraction and that positions are unchanged; mismatch renders LEDGER_MISMATCH at defect authority with a 3px left border and both numbers named; loading renders every count as an em dash, never 0, because a zero is a claim about the cohort; error states the counts are unknown and names the failing endpoint. | Drive all seven and assert seven distinct strings. In loading assert no count renders as '0'. In mismatch assert both the 304 and the 308 figure are printed and the defect border is present. |
| F61 | 'skipped' and 'graph_projection_failed' are NOT separable from any retrieval endpoint - an absent pathway in GET /runs/.../scores is just absent. Without the urgency agent's own four-bucket report those counts render 'unavailable' with LEDGER_UNAVAILABLE ('Not the same as zero.'), never 0. | Stub the orchestrator to omit the bucket report: assert no bucket count renders as '0' and the unavailable string with 'Not the same as zero.' appears. |
| F62 | Ledger terms are FILTERS: each toggles with aria-pressed and a polite live-region announcement of the resulting row count. Filtering HIDES rows and NEVER reorders and NEVER renumbers; aria-rowcount reflects the filtered count; FILTER_FEEDBACK ('showing 64 of 308 / positions unchanged') renders in the ledger AND in every affected group header. 'Clear filter' appears at a 24px target whenever any filter is active. Activating term 4 scrolls to and focuses the Outside-the-ranking heading. No filter survives a hospital-day switch. | Apply a filter: assert the remaining rows' position numerals are identical to the unfiltered view, that both count strings render, that aria-rowcount changed, and that a Clear filter control >= 24x24 appeared. Switch day and assert the filter is gone. |
| F63 | OrderingStripAndPreRunBanner is EXACTLY TWO lines at 12px in a fixed 40px strip (48 present) in EVERY state, so no state change moves the list. Line 1 says what the current order is and where it came from; line 2 carries the standing caveat. It is never a badge, never an icon, never amber, never role=alert. | Drive all seven strip states (pre-run, running, ready, ranked, rule-fired, re-run confirm, error) and assert offsetHeight === 40 and exactly two text lines each time. |
| F64 | THE PRE-RUN STATE IS A BANNER, NOT A PANEL (R5). Line 1 carries the ONE canonical PRE_RUN string, reused verbatim in the ordering strip, the state family and the export footer; line 2 carries DISPLAY_ORDER ('Referral date order - a display order, not a ranking.'), repeated in every group header. The 308-row cohort stays FULLY RENDERED beneath it and costs zero fold rows. | With no decision held assert 308 rows are rendered, the strip is still 40px, and ten rows are above the fold. Grep for the pre-run string: it appears from exactly one constant. Assert no panel element pushes the first row below 172px. |
| F65 | The ordering strip carries RULE_LINE with RULE-TIEBREAK's actual promise - earlier referral date first among referrals ALSO tied on category, target breach and score (ADR-013), not oldest-first within the band - and ADR011_SHORT on one line with a [Why this matters] control appending ADR011_FULL as a non-sticky disclosure. The ordering is presented as PROVISIONAL for as long as ADR-011 is open; no surface may describe it as clinically prioritised, final or signed off. There is no 'checked 14:02' timestamp anywhere: no such field exists in the data contract. | Assert both strings render at the ranked state, that neither element uses a warning token, role=alert or an icon, and that [Why this matters] toggles aria-expanded on an inline element below the strip. Grep for 'checked' followed by a time: zero matches. Grep for 'final', 'signed off', 'clinically prioritised' as claims: zero matches outside the not-signed-off sentences. |
| F66 | ScopeLine is a permanent 24px strip (28 present) carrying four clauses at 12px separated by middots, each a keyboard-reachable text control at a 24px minimum target opening an inline disclosure BELOW the strip that pushes the list. There is NO dismiss control and no close control, ever, at any state including error and empty, and it is baked into every export and screenshot. The urgency caveat is 0px in the sticky stack: this cohort's measured figures live in the third clause's disclosure, not in a 56px header block. | Assert the four clauses are in the DOM at every state, that no dismiss control exists, that activating one toggles aria-expanded and increases the first row's offsetTop, and that the summed chrome height is still 172. |
| F67 | Every printed statistic names its denominator and its scope, and the two populations are never merged: THIS hospital-day (9001/2026-08-30: 268 of 308 score NEWS2 2 or less; 20 of the 84 marked Urgent score 0 = 23.8%; MTS within CPC 1 splits 44 orange / 40 red) and BOTH hospitals on that date (48 of 155 Urgent score 0 = 31.0%; 77 red / 75 orange with 3 carrying no MTS category, of 155). Dataset-wide figures (correlation with triage category never above 0.253) appear only in the scope-line disclosure, labelled with their scope. | Collect every numeric claim in the copy dictionary and assert each is accompanied by a denominator and a scope word. Assert '31.0%' appears nowhere in the row grid. Assert '269' and 'NEWS2 1 -> 86' appear nowhere. |
| F68 | ContextBarAndHospitalDaySelector is a 40px bar (44 present) carrying, on one line at 14px: the selected hospital-day in full words, a 'Change hospital-day' DISCLOSURE, the clinician-id text input labelled CLINICIAN_FIELD, and the run control. The 2x14 selector grid is NOT permanently in the bar: it opens BELOW the bar and pushes the list, at 24x24px cells with a real 20px day-number header row and two row labels (footprint about 486x88). That is what makes both the 40px bar and SC 2.5.8 true at once. | Assert the bar is 40px collapsed and that the grid is absent from the DOM or hidden when collapsed. Open it and measure every cell bounding box >= 24x24 and the first row's offsetTop increased by 88. |
| F69 | Selector cell state is carried by border weight PLUS a glyph, never by fill alone: 1px outline = cohort only; 1px outline plus a filled 8px square = ranked in this session; 2px ring = selected. Ranked markers come EXCLUSIVELY from the orchestrator's own in-session run history. Probing GET /decisions across the 28 cells is FORBIDDEN: when a decision exists that call resolves every placement's citations through roughly 1,500 sequential SPARQL round trips, so probing is fast only while every cell is empty and degrades exactly as the demo gets better. | Assert the selector issues at most one request on mount and none per cell; record all network traffic while opening it and assert zero requests match /decisions/. Force greyscale and assert selected / ranked / plain remain distinguishable. |
| F70 | The selector shows 28 hospital-days as a SELECTOR, not a dataset: no totals row, no 'worst day', no trend line and no cross-hospital or cross-day comparison of any kind. Only two hospitals (9001 St Brendan's, 9002 Kilbrannan) and 14 dates (2026-08-17..2026-08-30) exist; 2026-08-16 and 2026-08-31 are reachable by URL edit and fall through to the empty-cohort state. No count is hardcoded: 9001 is 308 rows at 84/81/88/55/0 and 9002 is 301 at 71/94/90/46/0 with 6 paediatric rows. | Assert 28 cells, two row labels, and no aggregate cell. Navigate to /h/9001/d/2026-08-31 and assert the empty-cohort panel with EMPTY_COHORT. Load 9002 and assert the group headers and the tail count differ from 9001 with no literal 308, 84 or 3 in the bundle. |
| F71 | The URL is the state and is deep-linkable. Switching hospital or date is a route change that aborts in-flight polls, clears list state, closes any open expansion, comparison or override, refetches the cohort AND the orchestrator's override log, and asks ONCE before discarding a half-typed override reason. The copy never claims to have cancelled a server-side run it did not cancel. | Start a run, type into a reason field, switch day: assert exactly one confirm appears, that the post-switch message says the run continues, and that returning to the original day restores the accept/override residue from the refetched log. |
| F72 | RunProgressPanel shows TWO independent counters with TWO DIFFERENT DENOMINATORS - urgency n of 305 (308 minus 3 paediatric refusals) and capacity n of 308, because the capacity agent iterates the whole cohort with no refusal of any kind - plus elapsed seconds, at 13px tabular inside the 40px context bar. Never one bar, never a percentage, never a spinner, never an overlay, never a modal. The only animation during a run is the digits changing. | During a run assert two numeric counters exist with denominators 305 and 308 respectively, that no element has role=progressbar with a single aggregate value, and that no '%' character appears in the run copy. Assert a single '305' denominator is never used for capacity. |
| F73 | While a run is in flight the list does NOT reorder, gains no position numerals, and no row moves under the cursor - only the urgency cells fill in place. A row scored by capacity but not urgency reads 'Awaiting urgency agent', never a blank and never a zero. RUN_WITHHOLD states in words that no positions are shown until both agents finish and that 3 paediatric referrals will not be scored while capacity scores all 308. | Record the DOM order of pathway numbers at t=0 and every second until completion: assert the sequence is byte-identical and no position numeral renders before Show ranking is pressed. |
| F74 | 'Show ranking' is the ONLY way positions ever appear - one explicit, user-initiated transition. It applies positions and re-sorts in a single UNSTAGGERED 220ms FLIP over viewport rows only, transform and opacity only, keyed by pathway_number, pinning the reader's anchor row (record the focused row's pixel offset before, restore it after). Numerals and meter widths NEVER tween: values swap instantly, only position animates, because a tweening wait figure displays day counts that were never true of any patient. | Assert no reorder occurs without the control being activated. Instrument the wait numeral's textContent during the transition and assert exactly two values with no intermediate. Assert the focused row's viewport offset is within 1px of its pre-transition value. |
| F75 | Under prefers-reduced-motion:reduce the FLIP is disabled ENTIRELY, the dock appears without a slide, and the delta sub-column ('moved' / 'up 12' / 'down 3' / em dash) borrowed from column 5 for exactly one refresh is the WHOLE treatment. This is an accessibility fallback and is therefore MUST, priced inside RunProgressPanel - it can never be a COULD. | With prefers-reduced-motion:reduce assert no transform transition runs, the dock has no slide, and the 44px delta column is present with integer deltas for every moved row. |
| F76 | Run state is reported honestly across eleven states: idle, starting, running, stalled, one-agent-complete, scores-but-no-ranking (show the scores, refuse to invent positions), ready (stating how many rows will move), decision, cancelled, failed, restarted. A HEALTHY RUN CAN EXIT NON-ZERO: the urgency agent returns 1 when anything was skipped or a graph projection failed, so exit code 1 with a non-empty skipped dict is success-with-exclusions and is NEVER reported as failure. TIMING IS NOT VERIFIED: copy says 'about 30 seconds' and the stall threshold is set from one measured run, not from a round number. | Drive all eleven states and assert eleven distinct strings. Stub exit code 1 with a non-empty skipped dict and assert the ranking still renders with the skipped count reported. Grep the copy for '8-15 seconds': zero matches. |
| F77 | Run state is NEVER inferred from GET /runs/{run_id}/hospitals/{h}/scores alone, because it returns HTTP 200 with an empty object for an arbitrary unknown run_id, making a stale run_id indistinguishable from a run that just started. The orchestrator, which minted the run_id, is the only authority; when it has no held run for a hospital-day the UI falls back to pre-run and SAYS SO (RESTARTED). | Request a fabricated run_id and assert the UI renders the restarted sentence rather than 0 of 305. Assert the browser never derives 'running' from an empty scores object. |
| F78 | Re-running an already-ranked hospital-day requires an INLINE, non-modal confirm in the ordering strip stating the true consequence (RERUN_CONFIRM: a second POST appends its placements to the graph alongside the first and the two cannot be told apart there), backed by a 409 from the orchestrator unless confirm_duplicate is passed. Stopping is 'Stop watching' and the copy does not claim to have killed anything it did not kill. | Rank a day, press Run again: assert an inline confirm appears in the strip, that it is not a <dialog>, and that its text names the append behaviour. Assert POST /ui/runs without confirm_duplicate returns 409 with an explicit body. |
| F79 | PairwiseCompareDock is the centrepiece and is MUST: ONE dock, the three-step sort-key version, a 208px bottom dock spanning the full 1248px width (240 present), not a modal and not a side panel. Layout: 28px identity band (A left, B right, two 612px halves with a 24px gutter, each carrying pathway_number, category, day count against target, waiting days and 'NEWS2 n of 17'); 118px steps band (three 400px columns with 24px gaps: STEP 1 CATEGORY, STEP 2 WAITING TARGET, STEP 3 SCORE INSIDE THE TIER, each 16px heading + 20px verdict chip + sentence, with step 3's sentence replaced by the 72px ContributionDisplay when reached); 18px computed closing sentence; 32px two-line tie-warning and alpha-sensitivity band; 12px padding. Steps stack to one column below 1000px. | Assert the dock's offsetHeight === 208 (240 present) and the four bands measure 28/118/18/32. Assert the three step columns are 400px with 24px gaps summing to 1248. At 999px assert the steps are stacked. |
| F80 | NEWS2 SUB-SCORES DO NOT APPEAR IN THE DOCK - twelve sub-scores would double its height or push type below 12px, and hand-checking is the expander's job (C4, FDA CDS Criterion 4). The identity band carries both TOTALS, which is what makes a tie visible. | Assert the dock subtree contains no per-vital rows and exactly two 'NEWS2 n of 17' strings. |
| F81 | Each dock step renders exactly one of three verdicts - 'Decides this pair', 'Tied - goes on', 'Not reached' - and steps that were not reached are rendered GREYED AND LABELLED, never hidden, because showing them unreached teaches the structure of the ordering. Steps 1 and 2 come entirely from the cohort payload and work with NO run; step 3 says so when no scores exist. | Compare a CPC-1 row with a CPC-3 row: assert step 1 reads 'Decides this pair' and steps 2 and 3 both read 'Not reached' and are present in the DOM. With no decision held assert steps 1 and 2 still render full sentences. |
| F82 | The dock fires TIE_WARNING whenever the composite priority difference is below 0.001 or the two urgency scores are identical, and IDENTICAL_URGENCY when both score NEWS2 0. This is the COMMON case, not the edge case: 87 of the 299 adjacent same-band same-tier pairs are two NEWS2-0 referrals. | Pin two NEWS2-0 referrals in the same band and tier: assert both strings render and that the 148-of-308 and 87-of-299 figures are computed at render time, not literals. |
| F83 | The alpha-sensitivity line is ALWAYS shown once step 3 is reached, in one of two forms (ALPHA_FLIP or ALPHA_STABLE), recomputed CLIENT-SIDE by re-evaluating both priorities at alpha 0.5 and 0.9 - two multiplications, no endpoint - and NEVER hardcoded. Alpha is never printed as a bare coefficient on a row or in the identity headers; it appears only as the two endpoints of its documented [0.50, 0.90] range next to the outcome each produces. There is no slider and no control that changes alpha. | Grep the bundle for the literals 272, 2026, 51 and 0.68: zero matches (all must be computed). Assert no input, range or drag handle is bound to alpha. Pin a pair that flips and one that does not and assert the two different sentences. |
| F84 | c on a focused row compares it with the row IMMEDIATELY BELOW, because the adjacent pair is the question actually being asked. Shift+c pins A; Shift+Up/Down then walks B up and down the list with the arithmetic updating live. A and B are marked in the table ONLY by a 13px/700 letter in the rail's permanently reserved 16px slot plus 'pinned as A' in the row's accessible name - never a background, because gap, rule, tier and focus ring have already spent the background channel. The dock never traps focus and never steals it from the list; Esc closes. | Focus a row, press c: assert the dock opens on that row and the one below. Assert the marker is a text glyph in the rail and that the row's computed background is unchanged from an unpinned row. Assert focus remains on the row after the dock opens and that Tab does not enter a focus trap. |
| F85 | THE STAR CASE IS NOT POSITION 1 AND NO COPY MAY SAY IT IS. Reproducing the committed sort key, PW-9001-000208 sits at position 10 / 15 / 34 at alpha 0.5 / 0.7 / 0.9, because 12 breached Urgent referrals score NEWS2 4 or more. Position 1 at every alpha in the documented range is PW-9001-000191 (NEWS2 7, 152 days). No foil is ever hardcoded: it is read from the ordered array at render time (the named pair holds at alpha 0.7 and at no other tested value). | Grep the bundle and copy for 'Position 1 of 305' and for any hardcoded foil pathway: zero matches. Assert the rendered position for PW-9001-000208 equals the held decision's value and that the foil equals the array-adjacent row at the alpha actually in force. |
| F86 | Override has exactly TWO weights and the clinician never chooses which - the geometry does (OverrideDialogAndInlineReasonStrip). Inside the same band AND the same breach tier: non-modal, a 72px inline reason strip beneath the row (80 present) with a required coded select, an optional free-text input, and Record / Cancel; nothing is written until Record, and it DOES write POST /overrides because reason has minLength 1 and there is no other write path. Across a band OR across the breach tier: THE ONE MODAL, a native <dialog> at 620x520. | Shift+Down within Urgent-past-target: assert no <dialog> opens, a 72px inline strip appears, and Record issues a POST. Shift+Up from the top of Semi-urgent into Urgent: assert showModal() is called. Boundary detection is client-side: target band differs, or crt_breached differs within the same band. |
| F87 | The modal's reading order is FIXED and load-bearing: (1) a specific 18px/600 heading with no icon; (2) THE DISCLOSURE - the named rule in plain English with the actual numbers, then BOTH patients as a fixed two-column table with identical field order in both columns (Pathway, Category, Waiting target, Day count, Waiting time, NEWS2, Position from->to), never prose; (3) THEN THE ATTESTATION, a 24x24 checkbox in a 44px hit row; (4) the required coded reason select at 40px plus an optional 3-row textarea; (5) actions at 40px. Disclosure ALWAYS precedes attestation. 520px of dialog inside a 720px viewport leaves 100px of margin, so the whole reading order fits without scrolling. | Assert the five regions appear in that DOM order, that the attestation input is later in tab order than the rule text and the comparison table, and that the dialog's scrollHeight <= its clientHeight at 1280x720. |
| F88 | The attestation is unchecked by default, is NEVER pre-ticked, and ALONE enables the reason select. There is no 'do not show this again'. The primary action is not destructive-styled and never reads as an error confirm. The copy never frames the act as disagreement: never 'override the AI recommendation', never 'why do you disagree', never an 'are you sure'. | Open the modal: assert checkbox.checked === false, the reason select carries [disabled], and no element in the dialog carries a destructive token. Grep the copy for 'disagree', 'are you sure', 'override the AI': zero matches. |
| F89 | There is ONE canonical reason list with display labels and wire values: Clinical concern/CLINICAL-CONCERN, New information/NEW-INFORMATION, Patient factor/PATIENT-FACTOR, Capacity factor/CAPACITY-FACTOR, Data error/DATA-ERROR, Other/OTHER. Because the API carries ONE reason string, the coded value is prefixed: '{VALUE}: {free text}', or '{VALUE}: no further detail given' when the free text is empty - deterministic, satisfying minLength 1, and never ending on a bare colon. A blank reason is rejected inline with REASON_EMPTY_ERROR, never as a second modal and never as a silent no-op. | Assert exactly six options with those labels and values. Submit with an empty free-text field and inspect the body for the 'no further detail given' suffix. Submit with no coded value and assert an inline field error, no network request and no second dialog. |
| F90 | If POST /overrides fails, the row REVERTS to its prior position, the failure names the endpoint and the status code verbatim (OVERRIDE_FAILED), and the typed text is preserved. A row that stays moved after a failed write is a lie about what is recorded. A recorded override leaves OVERRIDE_RESIDUE on rail line 2 at the same weight as any other row, with the full reason in the expander, never styled as an error, a correction or a deviation. | Stub a 400: assert the row's rendered position returns to its original value, the visible string contains 'POST /overrides' and '400', and the textarea still holds the typed text. Record one successfully and assert the residue persists across a re-render and uses neither the error nor the warning authority level. |
| F91 | There is exactly ONE modal in the entire product and exactly ONE showModal() call site in the bundle. Nothing else interrupts - not the run, not a breach, not a rule check, not an empty state, not the stop-run confirm, not the re-run guard, not a filter change. The modal traps focus, returns focus to the moved row on close, and Esc cancels without writing; a dirty form raises an inline confirm INSIDE the same dialog, never a second stacked modal. | Grep the bundle for <dialog>, showModal(), role=alertdialog and any modal library: exactly one call site. Drive every other confirm and assert none is a dialog. Open the modal, type, press Esc: assert the confirm renders inside the same dialog element. |
| F92 | PRE-RUN the Move control is disabled with MOVE_DISABLED_PRERUN in visible text, because POST /overrides requires a decision_id that does not exist and would be rejected with 400. An override IS representable on an Outside-the-ranking row: from_position null, to_position set, and the move table reads 'Not currently placed'. | With no decision held assert every Move is disabled and the reason string is in the DOM, not in a title attribute. Open the override flow from a 0601 row and assert the request body has from_position null and a non-null to_position. |
| F93 | EmptyErrorStateFamily makes FOUR absences that must not look alike, all in place inside the table's own scroll container with the chrome still mounted: (1) NO RANKING YET is a BANNER in the ordering strip with all 308 rows rendered beneath; (2) EMPTY COHORT is a 280px panel replacing the list BODY only, chrome and selector intact; (3) NETWORK/HTTP ERROR is a line in the ledger naming the endpoint and status verbatim; (4) UNRESOLVED EVIDENCE is a per-entry treatment inside the expander at full weight with the IRI printed. Every variant states its denominator; the defect variants carry a 3px left border; no illustration, no mascot, no meaning-carrying icon, at most one 40px primary action. | Drive all four and assert four distinct headings and four distinct treatments. Assert the no-ranking state still renders 308 rows and costs zero fold rows. Verified live: /decisions returns 404 for every hospital-day; cohort 2026-08-31 returns 200 with referrals: []. |
| F94 | A partial list is NEVER rendered without the ledger saying it is partial with BOTH numbers (PARTIAL: 'Showing 142 of 308 referrals. The rest did not load. This is not the whole list.'), stated before any row is drawn. Nothing in this family is dismissible; nothing auto-retries silently; every error state leaves the hospital-day selector operable so another day can be tried without a reload; focus moves to the heading on state change with a polite announcement. No generic apology anywhere. | Truncate the cohort response to 142 rows: assert the partial sentence renders with both figures before the first <tr>. Grep the copy for 'something went wrong', 'oops', 'sorry': zero matches. Force a 502 and assert the selector still responds to clicks. |
| F95 | LoadingRule settles loading once: THERE IS NO SKELETON TABLE anywhere in the product. Below 400ms nothing renders at all (the cohort measures 50ms for 111,331 bytes). Past 400ms, ONE line of text in the reconciliation ledger. Wherever any count would render during loading it renders as an EM DASH, never 0. The only skeletons in the product are the six neutral rows in expander section 3 while the lazy per-row context call is in flight; sections 2, 4, 5 and 8 render immediately from data already held. aria-busy is set on the grid only while a request that would change row count is in flight. | Delay the cohort response to 200ms: assert nothing renders. Delay to 1000ms: assert 'Loading cohort...' appears exactly once and no count reads 0. Grep the cell components for skeleton markup outside expander section 3: zero matches. |
| F96 | The keyboard model is the projector navigation model: role=grid, aria-rowcount on the grid, aria-rowindex on every row, roving tabindex on the ROW so the whole list is ONE tab stop and a second Tab leaves it. Up/Down or j/k step rows; Home/End; PageUp/PageDown; Enter or Right expands, Esc or Left collapses; Alt+Left / Alt+Right move between the four ActionRail controls inside the focused row and Alt+Down returns focus to the row. Left/Right remain collapse/expand, so there is no collision. | Tab into the list: focus lands on a row, a second Tab leaves entirely. Press Alt+Right four times and assert focus visits Compare, Accept, Move, disclosure; Alt+Down returns to the row. Press Left and assert it collapses rather than moving between controls. |
| F97 | ALL single-key shortcuts (j, k, c, a, m, e, r, h, [, ]) are active ONLY when focus is inside the grid and are INERT whenever a text input or textarea has focus - WCAG 2.2 SC 2.1.4. The prior c/p collision is resolved to c. The clinician-id field and every override text field suppress them. | Focus the clinician-id input and type 'charmer': assert no compare, accept, move, evidence or run action fires and the field contains the typed text. Focus a row and press each letter: assert each fires exactly once. |
| F98 | [ and ] jump the structural boundaries: SIX pre-run (five group headers plus the tail heading) and EIGHT once ranked (plus the two tier dividers). Inside the open selector grid the same keys step the day instead. Tail rows are in keyboard row navigation and in aria-rowcount and are never skipped by arrow keys. | Pre-run, from row 1 press ']' six times and assert focus lands on each boundary in order then stops. Ranked, assert eight. Arrow through the tail region and assert all three 0601 rows receive focus. |
| F99 | Rows NEVER reorder on a background poll and never move under the cursor: a row that moves under the cursor is a mis-click on an override control. The only reordering in the product is the explicit Show ranking action or a clinician's own recorded move. Collapsing a band group never changes order or positions. There is no zebra striping - band grouping, the tier divider and the focus row are already three meaningful backgrounds. | Poll for 60s with the pointer over an action control and assert zero DOM reorders. Collapse and expand every group and assert the position multiset is unchanged. Assert no nth-child background rule exists. |
| F100 | The semantic authority taxonomy has exactly FOUR levels and NO success level, and every state is tagged to one: NEUTRAL (default row content, rule outcomes, within-target, resolved citations), MUTED (position numeral, normalised score, secondary lines, foil line), STRUCTURAL (band headers, tier divider, tail region heading, ordering strip, ledger, scope line), DEFECT (ledger mismatch, evidence-empty-with-decision-held, unresolved citation, HTTP error, partial list) which alone carries the 3px left border. The absence of a success level is deliberate: a rule that did not fire says only that the rule did not fire. | Enumerate every state in the pack and assert each maps to exactly one of the four levels. Grep for a success/positive token in the stylesheet: zero definitions. Assert only DEFECT-level states carry the 3px left border. |
| F101 | The orchestrator (S8) is the single source of ranking truth and the reason the whole design works. ONE process, ONE cohort fetch, ONE score fetch. It shells the coordinator CLI once to mint and POST 'dec-{uuid4()}' - the only way decision_id becomes reachable, since no GET endpoint returns it and GET /decisions returns a DIFFERENT identifier that POST /overrides rejects with 400 - then in the same request re-derives band, severity_rank, wait_normalised, priority and alpha by importing rank_cohort on the same referral dicts with the SAME capacity-direction value read from ONE shared constant. It asserts the imported ordering equals the CLI's and REFUSES to serve the decision if it does not. | Force the two computations to disagree by passing a different --capacity-direction: assert the orchestrator returns an error and the UI renders the failed state rather than a ranking. Assert decision_id is present in every POST /overrides body and is never the graph IRI 'decision/9001/2026-08-30'. |
| F102 | The orchestrator PREFETCHES all 308 contexts once per hospital-day at first cohort request (measured ~15ms each, about 4.6s serially) and serves news2 alongside the cohort. This is what makes the full NEWS2 column, the distribution figures, the dock's tie warning and the expander's six sub-scores all work with ZERO agents running, so the demo survives the run path never being built. It also imports urgency_agent.run.run_for_cohort rather than shelling it, reading CohortRunResult's four bucket dicts directly - they are keyed by pathway_number, so per-row attribution comes free. | With no agent run, load the route and assert every ranked-state-independent surface is populated: 308 NEWS2 integers, the scope-line figures, the dock's steps 1 and 2, and expander sections 2-6. Assert the cohort response carries news2 and that the browser makes no per-row context call for the collapsed list. |
| F103 | The UI NEVER reads the ranking back from GET /decisions (C10). A second POST APPENDS its placements rather than replacing them, so that endpoint can return two interleaved rankings; GET /runs/{unknown}/... returns 200 with {}; and resolving a decision's citations costs roughly 1,500 sequential SPARQL round trips. Position, band, severity_rank, urgency_score, wait_normalised, priority, alpha, rule_checks and citations all come from the orchestrator's own held view model. | Record every network request across a full session including a run, a compare, an expand and an override: assert zero requests to a path matching /decisions/. |
| F104 | R13 FALLBACK. The urgency agent is on origin/urgency_agent (PR #9 open), NOT main - git ls-tree main \| grep -ci urgency returns 0, and all 27 files including news2.py and calibration.yml live only on the unmerged branch. If the merge slips, transcribe the NEWS2 rubric and the four calibration anchors into web/src/news2.ts as committed constants with the source commit named ON SCREEN, and permanently render the skipped and graph_projection_failed counts as 'unavailable' rather than 0. Nothing else in this design changes: the branch's rubric matches this pack's transcription exactly. | With the agent absent, assert expander section 3 still recomputes 308/308 correctly from web/src/news2.ts, that the source commit hash is visible on screen, and that ledger terms 5 and 6 read 'unavailable' with 'Not the same as zero.' |
| F105 | The MUST list is ONE flat list of 25 MUST items totalling 24.0h, inside the 26h left after the orchestrator's 6-8h of the 35. SHOULD (ExportFiltersAndRankedMarkers, 2h) is absent by default and nothing else changes shape without it. COULD (ProvenanceGraph, 7h) is not built; its entry point in the expander is a 12px note (GRAPH_DEFERRED), never a disabled button, because a disabled button implies the feature is one permission away. | Check the built product against the 25-item MUST list. Assert no disabled provenance-graph control exists and that the deferral note renders as text. Assert removing the SHOULD items changes no other component's geometry. |

---

## 8. Data contract

Every field that appears on screen, its source, and the caveat that must travel with it.
A field with a caveat may not be displayed without it.

| field | source | shown as | caveat |
|---|---|---|---|
| pathway_number | GET /ui/cohort/{h}/{date} (proxies GET /hospitals/{h}/cohort/{date}) -> referrals[].pathway_number. Verified 308 rows, all non-null, format PW-{hipe}-{6 digits} plus 7 PW-DEMO-0n rows. | ReferralRailCell line 1, left-aligned 13px tabular in a 116px sub-column, NEVER truncated (drop to 12px rather than clip). Also the React key, the join key across every endpoint, the dock identity band, the modal comparison table, and the string a clinician reads aloud. Selectable and copyable with a polite live-region confirmation. | Seven rows are PW-DEMO-01..07, the deliberately shaped demo cases. PW-9001-000208 is NOT one of them - it is an ordinary generated referral and must never be introduced as a planted or hand-built case. It is also NOT position 1: it sits at 10 / 15 / 34 at alpha 0.5 / 0.7 / 0.9. |
| hospital_hipe / as_of_date | GET /ui/cohort/{h}/{date} top level, and the route /h/:hospital/d/:date. | Context bar in full words (HOSPITAL_DAY: "St Brendan's / Sunday 30 August 2026 / 308 referrals"), the URL, and burned into every export. | Only two hospitals (9001 St Brendan's, 9002 Kilbrannan) and 14 dates, 2026-08-17..2026-08-30. 2026-08-16 and 2026-08-31 return 200 with referrals: [] and are reachable by URL edit. Hospital names are chrome only and appear in no clinical statement. |
| specialty_hipe | GET /ui/cohort/{h}/{date} -> referrals[].specialty_hipe. Verified 9001/2026-08-30: 1800 n=98, 0300 n=64, 0600 n=54, 0100 n=44, 2600 n=29, 0700 n=16, 0601 n=3. | ReferralRailCell line 2 as code then name at 12px muted ('0300 Dermatology'), and in expander sections 6 and 8. Names from core.ref_codes: 1800 Orthopaedics, 0300 Dermatology, 0600 Otolaryngology (ENT), 0100 Cardiology, 2600 General Surgery, 0700 Gastro-Enterology, 0601 Paediatric ENT. There is no specialty COLUMN at any width. | specialty_hipe === '0601' is the ONLY signal available for paediatric attribution: the context endpoint returns no demographics and no age, and ADR-007 keys the refusal on specialty. 9002 has 6 such rows, not 3 - never hardcode. Pre-run this field alone populates the Outside-the-ranking region. |
| cpc | GET /ui/cohort/{h}/{date} -> referrals[].cpc. Verified 9001/2026-08-30: 1 n=84, 3 n=81, 2 n=88, null n=55, 4 n=0. Verified 9002: 71 / 94 / 90 / 46 / 0. | CategoryTimeframeChip line 1 with the adjective in sentence case first and the code appended ('Urgent / CPC 1'); band group membership and header order; the dock's step 1; the modal's boundary detection. | SEVERITY_RANK maps 1->1, 3->2, 2->3, so CPC 3 OUTRANKS CPC 2 - stated once, in the Semi-urgent group header (SEVERITY_NOTE), and it is the permanent reason there is no column sorting. cpc null is UNKNOWN priority, not low priority (UNKNOWN_NOT_LOW). cpc 4 Excluded and cpc null are two SEPARATE tails (ADR-006), never merged, and the zero-row Excluded header renders anyway. |
| crt_threshold_days | GET /ui/cohort/{h}/{date} -> referrals[].crt_threshold_days. Verified constant within band: 28 for all 84 cpc-1, 91 for all 81 cpc-3, null for all 88 cpc-2 and all 55 cpc-null (143 nulls). | Once in the band group header ('target 28 days'), and inside the row's line-2 target statement. Never as its own 308-row column. | Only two values ever occur, 28 and 91. The 143 null rows render GROUP_HEADER_NO_TARGET / WAIT_NO_TARGET in words - never blank, never 0, never a dash - and their meter track renders as an empty outline with no fill and no target mark. |
| crt_breached | GET /ui/cohort/{h}/{date} -> referrals[].crt_breached. Verified: cpc 1 {true 75, false 9}, cpc 3 {true 55, false 26}, null on all cpc 2 and all cpc null. | CategoryTimeframeChip line 2 in words ('Past the 28-day target' / 'Within the 28-day target'); the band header's breach split; the BreachTierDivider position; the dock's step 2; the override's tier-crossing detection. | The comparison is STRICTLY greater-than, so exactly 28 or exactly 91 days is WITHIN - PW-9001-000020 at 91/91 has crt_breached false and is the single at-target row in this cohort. This field sits ABOVE priority in the sort key (CRT_BREACHED_RANK {True:2, False:1, None:0}), so it is a hard tier. That tiering is ADR-011, status OPEN: no decision written under it may be presented as final. 'Within' is never a tick, never a success state. |
| adjusted_wait_days | GET /ui/cohort/{h}/{date} -> referrals[].adjusted_wait_days. Verified 0 nulls, range 0..871, 213 distinct values, 11 rows at exactly 0. | WaitTargetCell line box A, right-aligned in 92px at 20px/600 tabular - the LARGEST numeral on the row. Also the dock identity band and the modal comparison table. | This is the variable that actually discriminates - 213 distinct values against a NEWS2 column where 148 of 308 tie at exactly 0 - which is why it gets the dominance: display prominence is a measured mediator of automation bias (RR 1.26, 95% CI 1.11-1.44), so the honest thing to make prominent is waiting time. It equals days_since_received, not days_since_referral. |
| days_since_referral / days_since_received | GET /ui/cohort/{h}/{date} -> referrals[]. Verified different on the star case: 882 vs 871. | Expander section 2 only, both printed together with the sentence 'The ranking uses the later clock.' | Two clocks exist and disagree by up to 11 days on real rows. Showing one on the row is acceptable ONLY because the expander shows both; the gap must never be invisible. |
| referral_date / referral_received_date | GET /ui/cohort/{h}/{date} -> referrals[]; also GET /ui/context/{h}/{pw} -> referral. | Expander section 2 in full words. referral_date is also the PRE-RUN display order for all 308 rows (R5). | referral_date is the FINAL tiebreak in the committed sort key (band_order, severity_rank, -crt_rank, -priority, referral_date, pathway_number) - not 'oldest first within the band'. Any copy claiming oldest-first within a category is wrong (ADR-013). Pre-run this ordering is labelled DISPLAY_ORDER: 'a display order, not a ranking'. |
| triage_status | GET /ui/cohort/{h}/{date} -> referrals[].triage_status. Verified 307 'triaged', 1 'awaiting_triage'. | The No-category group header sub-line and the expander. Not a row column. | 54 of the 55 no-category referrals are recorded as TRIAGED with no category recorded - they fell through triage. Copy must say '1 of the 55 is awaiting triage', never imply all 55 are. |
| days_awaiting_triage | GET /ui/cohort/{h}/{date} -> referrals[].days_awaiting_triage. Verified non-null on exactly ONE row: PW-DEMO-05, value 64, cpc null, specialty 0100. | CategoryTimeframeChip line 2 on that one row, shortened to fit the 160px track: 'Triage day 64 of 21'. The full RULE-TRIAGE-TURNAROUND sentence lives in the group header and the expander, because the long form measures 186px in a 160px track. | RULE-TRIAGE-TURNAROUND (21 days) has exactly one candidate row in this cohort. It is not a property of the no-category group as a whole. |
| currently_suspended | GET /ui/cohort/{h}/{date} -> referrals[].currently_suspended. Verified FALSE on all 308 rows. | WaitTargetCell line 2 when true: 'Clock suspended', as a word, never an icon. | Zero rows in this cohort. The state must still be built or a regenerated dataset breaks the cell. Do not cite the demo as evidence that it works. |
| observations[-1].news2 | GET /ui/context/{h}/{pw} (proxies GET /referrals/{h}/{pw}/context) -> observations[-1].news2, prefetched once per hospital-day by the orchestrator and served alongside the cohort. Verified 9001/2026-08-30 PER REFERRAL: 0->148, 1->85, 2->35, 3->26, 4->8, 5->3, 6->2, 7->1, summing to 308; 268 of 308 (87.0%) score 2 or less; 20 of the 84 Urgent referrals score 0 (23.8%). | UrgencyNews2Cell line 1 as the PRIMARY element, 'NEWS2 1 of 17' at 15px/600 tabular with the denominator ALWAYS printed. Also both halves of the dock identity band, the modal comparison table, and expander section 3's total. | THE COUNTING RULE IS PER REFERRAL, NOT PER OBSERVATION ROW: the display rule is observations[-1] regardless of how many observation rows exist, so NEWS2 1 is 85 referrals and NEVER 86. Row-counting is wrong for display. (Verified first-hand against the cached dumps: 9001 has 308 observation rows for 308 referrals and 9002 has 301 for 301, one each, so on today's data the two counts coincide at 1->85; the brief's '309 rows, one referral has two' does not reproduce and is NOT VERIFIED - the per-referral rule is mandatory either way.) NEWS2_MAX is 17 (temperature's top band is 2, every other component's is 3) - not 18, not the generator's cap of 20. |
| observations[-1] rr / spo2 / sbp / hr / avpu / temp | GET /ui/context/{h}/{pw} -> observations[-1]. Verified star case PW-9001-000208: rr 17, spo2 99, sbp 140, hr 108, avpu 'A', temp '36.4'. | Expander section 3 ONLY, six rows of 'vital, value, arrow, sub-score' with the right column right-aligned tabular, a rule, and 'Total -> 1 of 17', followed by HAND_CHECK. Labelled as RECOMPUTED by this interface. | temp arrives as a JSON STRING and must be parsed. Rubric traps to reproduce exactly: sbp is NOT a descending ladder (>=220 scores 3, the same as <=90); avpu is binary (A->0, V/P/U->3); temperature's top band is 2. All six are shown INCLUDING the ones scoring 0, because a normal vital is evidence of normality and not an absence of evidence, and because citing only the abnormal ones makes the arithmetic unreconstructable (FDA CDS Criterion 4). If the recomputed total ever disagrees with the stored value the screen says so rather than showing either number. |
| observations[-1].pain / observations[-1].dbp | GET /ui/context/{h}/{pw} -> observations[-1]. Verified star case: pain 10, dbp 94. | Expander section 4 'Read but not scored', as text inside READ_NOT_SCORED. | Both are in the record and both are OUTSIDE the six NEWS2 inputs. This is what makes the star case honest - the screen shows NEWS2 1 while also showing that the record holds a heart rate of 108 and a pain score of 10 of 10. For a REFUSED row these still render alongside the six vitals with no sub-scores and no total. |
| observations[-1].mts_category - NOT EVIDENCE (C3) | GET /ui/context/{h}/{pw} -> observations[-1].mts_category. Verified 9001/2026-08-30 within CPC 1: 44 orange / 40 red. Across both hospitals within CPC 1: 77 red / 75 orange with 3 carrying no MTS category, of 155. Null on exactly the three paediatric rows. | ONE place only: expander section 5 'On the record, not used in the score', as plain text with MTS_PROVENANCE and its measured split beside it. It gets NO colour channel and appears in no chip, badge, legend or filter. | NOT EVIDENCE. Within a band it takes only two values and is close to a coin flip (ADR-004), and 0 of 609 observations across both hospitals carry a chief complaint - which is what an MTS assessment would actually be made from - so it is the CPC band relabelled. The five MTS hues are a national triage standard with fixed target times and must never be reused for another axis. |
| observations[-1].chiefcomplaint / observations[-1].icts_category | GET /ui/context/{h}/{pw} -> observations[-1]. Verified first-hand: chiefcomplaint null on all 609 observations across both hospitals. icts_category non-null on exactly the 3 paediatric rows in 9001 (green, green, yellow). | chiefcomplaint is shown NOWHERE. icts_category appears only in the expander for the three tail rows, as a record field. | chiefcomplaint being universally null is the load-bearing fact behind the MTS argument and must be stated with its 609 denominator wherever MTS is discussed. |
| conditions[].icd10am_code - NOT EVIDENCE (C3) | GET /ui/context/{h}/{pw} -> conditions[]. Verified 408 condition rows across 308 referrals: 208 have one, 100 have two. | Expander section 5 ONLY, as a record field with CONDITION_PROVENANCE attached, ALL conditions listed and not only the primary. Never on a row, never in a chip, never in a filter, never as evidence. | NOT EVIDENCE. generate.py:472 draws the code by rng.choice over the specialty's condition mix, independent of vitals, acuity and triage category; HOW_THE_DATA_WAS_MADE.md 5.3 confirms latent_hazard never reads the diagnosis; mean NEWS2 by condition is flat (0.73-1.03). Putting a diagnosis on a row would dress a random draw as clinical context. This also kills 'a melanoma was missed' as the narrative (C1): the thesis is about the INSTRUMENT, not a planted case. |
| conditions[].condition_label / conditions[].snomed_ct_id | GET /ui/context/{h}/{pw} -> conditions[]. Verified first-hand: condition_label is the literal placeholder 'Condition {code}' on all 408 rows; snomed_ct_id is null on all 408. | Quoted verbatim in expander section 5 as evidence that the record holds no clinical text. | The UI must NOT ship an ICD-10-AM dictionary and must NOT render any English gloss such as 'Malignant melanoma of skin'. That would be the only uncited string on a screen whose entire claim is traceability, and it would attach a diagnosis to a random draw. |
| triage_events[] | GET /ui/context/{h}/{pw} -> triage_events[]. Star case: TE-9001-000208, sent 2024-04-16, triaged 2024-05-03, triage_outcome 1, triage_category 1, turnaround_days 17. | Expander sections 2 and 8 as recorded facts with dates. | triage_events[].triage_category is a THIRD category field alongside the cohort's cpc and RankingIn.triage_category. Never display it as if it were the cohort's cpc without naming its source. |
| capacity.wards[].latest_bed_status | GET /ui/context/{h}/{pw} -> capacity.wards[].latest_bed_status. Verified star case, specialty 0300: W-9001-03 79.12% G, W-9001-01 89.01% G, W-9001-02 98.91% R with 7 outliers and 3 awaiting admission over 24h, snapshot 2026-08-30T20:00. | Expander section 6 only, as sentences naming the ward id, the percentage and the counts. | occupancy_pct arrives as a STRING and is occupied/(occupied+free), NEVER occupied/nominal_beds - W-9001-02 has nominal 45 against occupied 91. Ward fields are nested under latest_bed_status, not at ward level. Capacity is a hospital-day property and appears on NO row. |
| capacity.clinic_sessions[] | GET /ui/context/{h}/{pw} -> capacity.clinic_sessions[]. Verified star case: CL-9001-0300, last three sessions 4, 6 and 5 slots free. | Expander section 6, one sentence naming the clinic and the last three sessions' free slots. | The same specialty-level payload is returned for every referral in that specialty (64 rows share 0300), so it must be framed as ONE SCORE FOR THE SPECIALTY, never as a fact about this patient and never as 'identical for all 64 referrals' - the code keeps the last value per specialty rather than asserting they agree. |
| position | Orchestrator's held decision, GET /ui/decision/{h}/{date}, from coordinator.app.ranking.rank_cohort. NEVER from retrieval's GET /decisions (C10). | ReferralRailCell line 1, right-aligned in a 34px sub-column at 15px tabular MUTED. PRE-RUN the sub-column is NOT RENDERED at all; on a tail row it is not rendered and the cell carries NO_POSITION_ARIA. | Flat unique integer 1..305 across the whole decision, never restarted per group (ADR-006). Deliberately NOT the largest numeral on the row. A dash or placeholder glyph in a right-aligned numeric column destroys the vertical scan and reads as a rank, which is why absence is structural rather than typographic. |
| urgency_score - EIGHT REACHABLE VALUES | Orchestrator's held decision -> rankings[].urgency_score, numeric(4,3) in [0,1]. Calibration verified in urgency-agent/urgency_agent/calibration.yml: anchors (0, 0.000), (4, 0.300), (6, 0.600), (7, 1.000), linear between, saturating above 7. | UrgencyNews2Cell line 2, DEMOTED: 'normalised 0.075' at 12px muted, always 3dp. Also a signed term in ContributionDisplay. | Because the observed NEWS2 range on this data is 0..7, ONLY EIGHT VALUES ARE REACHABLE: 0.000, 0.075, 0.150, 0.225, 0.300, 0.450, 0.600, 1.000. 148 of 308 rows are exactly 0.000. NEWS2 1 maps to EXACTLY 0.075; 0.08 is a different number and appears nowhere in the product. Three decimals is the storage column's precision, not a claim of precision - which is why the integer is primary and this is secondary (C4). Render 3dp only where the number does arithmetic (the dock and the expander), never as a row primary. |
| capacity_score | Orchestrator's held decision -> rankings[].capacity_score. | Nowhere on a row and nowhere as a per-patient figure. Referenced only in expander section 6 as a SPECIALTY-level input to scarcity. | NOT VERIFIED: no capacity agent run exists for any hospital-day, so no real capacity_score, scarcity or alpha value has ever been observed. ADR-007 is RESOLVED (capacity_score is a PRESSURE score, so scarcity = capacity) and the direction in force is recorded in coordinator_version - read it from there, never assume it. |
| alpha / scarcity / ALPHA_MIN / ALPHA_MAX | Orchestrator's held decision. alpha = 0.5 + 0.4 * scarcity, computed ONCE per decision from the mean of the DISTINCT specialty capacity scores (7 distinct specialties in this cohort). ALPHA_MIN 0.5 and ALPHA_MAX 0.9 verified as constants in coordinator/app/priority.py. | As an exchange rate in words in the decision header ('urgency-to-waiting-time exchange rate 0.68 / 0.32') and as the two ENDPOINTS of its documented range next to the outcome each produces (ALPHA_FLIP / ALPHA_STABLE). NEVER as a bare coefficient on a row, never in the dock identity headers, never as a slider. | C2: CAPACITY DOES AFFECT ORDERING. Reproduced first-hand for 9001/2026-08-30: 272 of 305 referrals sit at a different position between alpha 0.5 and 0.9, 2,026 of 9,707 same-band same-tier pairs reverse (20.9%), largest single move 51 places. Two limits must be stated alongside: alpha never enters an individual's score, and no value of alpha can move anyone across a CPC band or across the CRT tier. coordinator/app/priority.py's own docstring says capacity cannot reorder within a band - that docstring is WRONG and must never be repeated in copy. |
| wait_normalised | Orchestrator's held decision -> rankings[].wait_normalised. Percentile rank WITHIN BAND with ties sharing the rank, (count_less + count_equal/2)/n (ADR-010). Verified for PW-9001-000208: 0.9940. | NEVER as a bare number. It appears ONLY as a signed contribution in ContributionDisplay and as PERCENTILE_SENTENCE in plain English ('No referral in the Urgent category has waited longer.'). | ADR-010 promises it is used for sorting and never displayed as a number; honoured exactly. Because ties share the percentile, the longest wait in an 84-row band scores 0.994, NOT 1.000 - so 'waited longer than 100%' is forbidden. The percentile is computed over SCORED referrals only, so the Routine band is n=86 and the no-category band n=54, not 88 and 55. |
| priority | Orchestrator's held decision -> rankings[].priority = alpha * urgency_score + (1 - alpha) * wait_normalised (coordinator/app/priority.py). | ONLY as the third row of ContributionDisplay, with its two components and their difference at 3dp with signs. | There is NO fused priority score, AI score, triage score or risk score column anywhere in the product. A single number implies a measured quantity with real variance when 148 of 308 of its urgency inputs are exactly 0.000, and it is not comparable across bands or breach tiers because both sit above it in the sort key. |
| band / severity_rank | Orchestrator's held decision, from coordinator.app.bands.order_by_band. NOT present in retrieval's RankingIn schema (verified against the live OpenAPI). | Drives group membership and header order. severity_rank itself is never printed; its consequence is stated once as SEVERITY_NOTE in the Semi-urgent header. | This is the primary reason the orchestrator view model exists: band, severity_rank, wait_normalised, priority, alpha and scarcity are ALL absent from every retrieval read endpoint. GET /decisions returns only {decision, placements[{placement, position, referral, pathway_number, evidence[]}]} - no urgency_score and no rationale_summary either. |
| rule_checks[] | Orchestrator's held decision -> rankings[].rule_checks = {rule_id, passed, detail}. Rule ids and thresholds from core.ref_rules: RULE-CRT-URGENT 28d, RULE-CRT-SEMI 91d, RULE-TRIAGE-TURNAROUND 21d, RULE-ORDER, RULE-TIEBREAK. | Per-referral rules as neutral one-line statements in expander section 8. RULE-ORDER and RULE-TIEBREAK ONCE in the list-level ordering strip (RULE_LINE), never on 305 rows. | RULE-ORDER and RULE-TIEBREAK are properties of the whole ORDERING and cannot live on a row. RULE-ORDER cannot fail by construction under ADR-004, so its resting state is 'holds' - a standing property, not a callout. A passing check is never a tick, never a success state: RULE_NOT_FIRED. NOT VERIFIED that GET /decisions surfaces rule_checks at all - another reason the orchestrator holds the payload it received. |
| rationale_summary - NOT EVIDENCE (C3) | Orchestrator's held decision -> rankings[].rationale_summary, from coordinator/app/decision.py::build_rationale_summary. | Expander section 8 ONLY, inside a CLOSED <details>, labelled as an audit field with RATIONALE_DEFECT stated above it. NEVER on a row, never in a tooltip, never in the dock, never as this patient's reasoning. | NOT EVIDENCE. _alpha_weight_phrase returns one of exactly two strings on a single midpoint test against alpha, so all 308 strings in a decision carry the same clause about capacity pressure and describe a hospital-day parameter, not a patient. Rendering it per row would directly contradict the honest contribution arithmetic printed two inches away in the dock. |
| excluded[] / exclusion_reason | Orchestrator's held decision -> RankedCohort.excluded, from coordinator.app.ranking.rank_cohort. | Populates OutsideRankingRegion and the ledger's terms 4-6. | CRITICAL: the coordinator stamps exclusion_reason 'missing_urgency_score' on EVERY exclusion regardless of cause, so paediatric refusal, no-observation and graph-projection-failure all arrive with the SAME string - exactly the ADR-007 collapse the UI must not reproduce. Attribution comes from specialty_hipe plus the urgency agent's four-bucket report; anything the orchestrator cannot attribute renders under its own sub-heading as 'Absent from the ranking, reason not reported' and is NEVER folded into the paediatric count. |
| buckets {scorable, refused_paediatric, skipped, graph_projection_failed} | Orchestrator only, read directly from urgency_agent.run.CohortRunResult's four dicts (imported, not shelled). Exposed by NONE of retrieval's 11 endpoints. Verified 9001/2026-08-30: 305 scorable, 3 refused paediatric, 0 skipped. | Ledger terms 4, 5 and 6, each a filter toggle and a jump target; the tail region's sub-headings. | The buckets are keyed by pathway_number, so per-row attribution comes free. 'skipped' and 'graph_projection_failed' are NOT recoverable by set difference from any retrieval endpoint - an absent pathway in GET /runs/.../scores is just absent - so without the agent's report those two counts render 'unavailable' with 'Not the same as zero.', never 0. A healthy run can exit 1 when either bucket is non-empty; that is success-with-exclusions, not failure. |
| evidence[] {role, iri, type, properties} | The held decision's citations first; GET /ui/evidence as a fallback. Roles: urgency \| capacity \| timeframe \| multi_list. | Expander section 7 as a flat list grouped by role in fixed order with a count per role. CitationChip: resolved fact at 13px, IRI at 12px monospace middle-ellipsised at 420px, full string on focus, always selectable. | The coordinator emits exactly ONE urgency citation (the score node), not six - the six vitals are that score's own citations and live in section 3. multi_list is never emitted by this coordinator at all, so its group is structurally zero FOREVER and must be labelled MULTILIST_ZERO. Verified today the array is EMPTY for every pathway because no decision exists, and the endpoint returns 200 with an empty array for a placement that was never written - so an empty array is AMBIGUOUS and must be disambiguated using the orchestrator's own decision state. A citation with type null and empty properties is a state the service deliberately does not drop; the UI mirrors that refusal exactly. GET /evidence accepts a role query parameter; section 7 uses ONE unscoped call and role= is noted only as an option for lazy per-section loading. |
| scores[pw][agent] {score, method, agent_version, as_of_date, citations[]} | GET /runs/{run_id}/hospitals/{h}/scores, proxied by the orchestrator as GET /ui/runs/{run_id} for PROGRESS ONLY. | Drives the two run counters: urgency = pathways carrying an 'urgency' key (n of 305), capacity = the same for 'capacity' (n of 308). | Returns HTTP 200 with an empty object for an ARBITRARY UNKNOWN run_id, so a stale run_id is indistinguishable from a run that just started and would sit at 0 of 305 forever - only the orchestrator knows the difference. Its citations are a DIFFERENT, UNRESOLVED shape ({evidence_type, evidence_key}) with no properties: render as 'Resolving...' plus the key and never fabricate a fact from a key. TWO DIFFERENT DENOMINATORS: urgency refuses 0601 and capacity does not, so a single '305' would put '308 of 305' on stage. |
| decision_id | Orchestrator only. It is the Postgres key 'dec-{uuid4()}' assigned inside coordinator/app/cli.py. | Not displayed anywhere. Sent in every POST /ui/overrides body, including the AcceptAction write. | HARD INTEGRATION GAP: no GET endpoint returns it. GET /decisions returns the graph IRI 'decision/9001/2026-08-30', a DIFFERENT identifier that POST /overrides rejects with 400. Without the orchestrator holding it, the whole override AND accept loop is unreachable. |
| run_id | Orchestrator-minted via POST /ui/runs {hospital_hipe, as_of_date} -> {run_id, decision_id, started_at}. There is NO HTTP run trigger anywhere in the repo: urgency agent, capacity agent and coordinator are all CLIs with a caller-assigned --run-id. | The decision header ('Ranking from run {run_id}') and the export footer. | No /runs listing endpoint exists in the 11-path OpenAPI, so run_id cannot be recovered after the fact. The orchestrator owns run history; on container restart the held state is gone and the UI falls back to pre-run and SAYS SO (RESTARTED), never pretends. |
| coordinator_version | Orchestrator's held decision. Format '{semver}+capacity={direction},alpha=[{min},{max}],scores={source}'. | Decision header, PARSED: the capacity direction in force and the score source. A 'scores=fixture' value triggers a persistent, non-dismissible 'Fixture scores - not a live agent run' label (ADR-008). | This string is the ONLY place the decision-shaping assumptions are recoverable after the fact (ADR-007, ADR-008). Parse it; never hardcode 'pressure' or 'live'. |
| override_id / clinician_id / from_position / to_position / reason / rule_warning_accepted | POST /ui/overrides -> POST /overrides. Verified REQUIRED against the live OverrideIn schema: override_id, decision_id, hospital_hipe, pathway_number, clinician_id, reason (minLength 1, non-blank). Optional and NULLABLE: from_position, to_position. Boolean with default: rule_warning_accepted. | override_id is UI-generated and never displayed. clinician_id is a text input in the context bar labelled CLINICIAN_FIELD. reason is displayed back as OVERRIDE_RESIDUE on rail line 2 and in full in the expander. | The bearer token carries no per-caller identity, so clinician_id is ATTRIBUTION AND NOT AUTHENTICATION and the field label must say so. The API carries ONE reason string, so the coded value is prefixed: '{VALUE}: {free text}' or '{VALUE}: no further detail given'. from_position/to_position being nullable is what makes an override representable on an unranked tail row, and what makes the audited Accept (from_position === to_position) legal. |
| UI-COMPUTED: accept record and override log | POST /ui/overrides with from_position === to_position, reason 'ACCEPTED: position confirmed', rule_warning_accepted false. The orchestrator keeps an in-memory override log keyed by (hospital, date, pathway) and serves it with the decision. | ACCEPTED_RESIDUE on rail line 2 and the disabled 'Accepted' label in the action rail. Refetched on every route change. | There is no accept endpoint in the 11-path API; this is the only write path that exists. The log is IN MEMORY: it survives a hospital/date switch and a re-render, and does NOT survive an orchestrator restart - and the ledger says so in words rather than silently showing an unaccepted list. The acceptance count is deliberately NOT a ledger term: the ledger reconciles the cohort against the ranking, and acceptances are not an absence. |
| UI-COMPUTED: over-target multiplier and meter geometry | adjusted_wait_days / crt_threshold_days, in the browser. Verified band maxima: cpc 1 max 31.107x (min 0.036x), cpc 3 max 9.099x (min 0.000x). | Row line 2 as a FLOORED INTEGER at 2.00x and above; days over between 1.00x and 2.00x; WAIT_AT_TARGET at exactly 1.00x. Meter fill = 140 * sqrt(ratio / band max). Expander at 1dp with the arithmetic and an explicit statement that this interface computed the ratio while the days and the threshold come from the record. | FLOOR, never round: 2.9x renders '2x', so a row never claims a larger overshoot than it has. Undefined for the 143 null-threshold rows, which print the no-target words and never a division result. The band maximum is read from the cohort at render time - 9002's domains differ. |
| UI-COMPUTED: NEWS2 sub-scores | Recomputed client-side from the committed rubric (urgency-agent/urgency_agent/news2.py, or web/src/news2.ts under the R13 fallback) against observations[-1]. | Expander section 3, six rows plus a total, labelled as recomputed by this interface. | The recomputed total MUST equal the stored news2 for every referral (independently verified 308/308 in a prior pass). If it ever disagrees the screen says so rather than showing either number silently - the hand-checkability is the FDA CDS Criterion 4 property this surface exists to deliver. |
| UI-COMPUTED: signed contributions to the gap | alpha * (u_a - u_b) and (1 - alpha) * (w_a - w_b), against the adjacent row in the SAME band and SAME tier taken from the orchestrator's own ordered array at render time. | ContributionDisplay only - dock step 3 and expander section 1 - at 3dp with explicit signs, both terms always shown including a negative one. Never on a collapsed row. | Contribution to a DIFFERENCE, never a share of a total: a share of a total is a different quantity answering a different question. Must NOT be computed at all when the pair is separated by a band or a tier. THE FOIL IS READ FROM THE ORDERED ARRAY AT RENDER TIME AND NEVER HARDCODED: the pack's worked pair holds at alpha 0.7 and at no other tested value (at 0.5 the row below is PW-9001-000009, at 0.9 it is PW-9001-000138). |
| UI-COMPUTED: alpha sensitivity | Two client-side re-sorts (or two multiplications for a single pair) of the held decision at alpha 0.5 and 0.9 using the committed sort key reproduced in TS. Under 5ms for 305 rows. | The decision header sentence (CAPACITY_LIMIT_AND_EFFECT) and the dock's fourth band (ALPHA_FLIP / ALPHA_STABLE). | COMPUTED, NEVER HARDCODED - the figures depend on the cohort and 9002 will differ. Reproduced for 9001/2026-08-30: 272 of 305 at a different position, 2,026 of 9,707 pairs reversed (20.9%), largest move 51 places, PW-9001-000208 at 10 / 15 / 34. The surface REPORTS; it never offers a control that changes alpha. |
| UI-COMPUTED: reconciliation arithmetic | Set difference on pathway_number between the cohort (308) and the held decision's rankings (305) plus excluded (3), plus the agent's bucket report. | ReconciliationLedger, six terms whose arithmetic adds up on screen. | If the terms do not sum to the cohort size the UI says so LOUDLY with both numbers named (LEDGER_MISMATCH) at defect authority, rather than papering over it. Term 1 is cohort length; term 2 is pathways carrying an 'urgency' key in the held score map; term 3 is placements in the held decision; terms 4-6 come from the agent's four-bucket report. |
| UI-COMPUTED: tie and adjacency frequencies | Computed first-hand from the committed formulas against live data: of the 299 adjacent same-band same-tier pairs, 87 (29.1%) have both referrals at NEWS2 0 and therefore urgency 0.000. | The dock's TIE_WARNING and IDENTICAL_URGENCY strings; the WhyThisPositionCell's commonest verdict. | The tie warning is the COMMON case, not the edge case, and the copy must say so with its denominator. Computed at render time, never a literal. |
| GET /referrals/{h}/{pw}/wait-counters | Live endpoint. Verified behaviour: without as_of_date it returns 422; with ?as_of_date=2026-08-30 it returns 404 'no referral data for that date' for PW-9001-000208, a referral that IS in that date's cohort. | NOTHING. This endpoint is bound to no surface. | Possible service defect - NOT VERIFIED either way. Nothing in this design may depend on it and no requirement above references it. |

---

## 9. Accessibility

- WCAG 2.2 SC 1.4.1 Use of Colour (Level A): no clinical state is ever carried by colour
  alone. Band identity uses a >=12px gap plus a >=2px rule plus the header's words; breach
  state uses 'Past'/'Within' in words plus the 2px target mark; the refusal uses a 17px
  region heading; selector cells use border weight plus a glyph; the ledger separates terms
  with a middot, never a hue. THE ACCEPTANCE TEST is a stylesheet forcing every colour token
  to one greyscale value: the screen must remain readable and every distinction countable.
  That is a screenshot test, not a code review.
- WCAG 2.2 SC 1.4.11 Non-text Contrast (AA): the meter track outline, the 2px 1x target
  mark, the focus ring, the category chip's outline level, the tier divider rule, the tail
  region's 3px rule and the defect 3px left border all meet 3:1 against their adjacent
  background. The target mark overshoots the track 4px above and below so 'the fill has
  crossed the tick' is a topological judgement rather than a colour one.
- WCAG 2.2 SC 1.4.3 Contrast (Minimum) (AA): all body and secondary text meets 4.5:1,
  including the 12px muted 'normalised 0.075' line, the 12px foil line, the 12px disabled-
  reason line and the 12px ledger. 'Muted' is a lightness step inside the 4.5:1 envelope,
  never below it. Nothing in the product renders below 12px (R2: cut a line rather than
  shrink type).
- WCAG 2.2 SC 2.4.11 Focus Not Obscured (Minimum) (AA) and W3C failure F110: scroll-padding-
  block-start equals the FULL 172px sticky stack (196px present), so no arrow-key, j/k,
  Home/End, PageUp/PageDown or [ / ] move can leave the focused row underneath the chrome.
  Tested by keyboard traversal of all 308 rows plus every boundary jump, not by inspection.
- WCAG 2.2 SC 2.4.7 Focus Visible (AA): a 2px focus ring at >=3:1 sits on the ROW, never on
  an inner cell. The ring is COMPOSITED as per-cell inset box-shadow so it reads as one
  continuous ring across both frozen boundaries - a ring painted on the <tr> is unreliable
  across table engines and is painted over at the left edge by the sticky cell's own opaque
  ground. The focused-row-plus-frozen-edge case must be drawn explicitly in the deliverable
  so the developer copies it rather than guesses.
- WCAG 2.2 SC 2.5.8 Target Size (Minimum) (AA): every interactive control is at least 24x24
  CSS px including padding, at the 48px row height - the four ActionRail controls (24px
  tall, 64/72/46/24 wide), the six ledger filter segments, the band header collapse, the
  four scope-line clauses, the tier divider's 'Why?', the dock's Swap/Unpin/Close, and every
  selector cell at 24x24 (the prior 24x20 failed the pack's own criterion, which is why the
  grid moved out of the 40px bar into a disclosure). Verify by measuring bounding boxes, not
  by trusting a token.
- WCAG 2.2 SC 2.1.1 Keyboard and 2.1.2 No Keyboard Trap (A): every function is reachable by
  keyboard. Up/Down or j/k step rows; Home/End; PageUp/PageDown; [ and ] jump the six pre-
  run / eight ranked structural boundaries; Enter or Right expands, Esc or Left collapses;
  Alt+Left / Alt+Right move between the four action-rail controls and Alt+Down returns to
  the row; c compare, Shift+c pin A, Shift+Up/Down walk B or reorder, a accept, m or o move,
  e evidence, r run, h toggle hospital. The dock does NOT trap focus; the one modal does and
  returns focus to the originating row on close.
- WCAG 2.2 SC 2.1.4 Character Key Shortcuts (A) - the criterion both prior specs omitted:
  every single-key shortcut is active ONLY when focus is inside the grid and is INERT
  whenever a text input or textarea has focus. That focus-scoping is the stated conformance
  route (no remapping UI is provided). The clinician-id field and both override text fields
  exercise it. The prior c/p collision is resolved to c.
- WCAG 2.2 SC 4.1.2 Name, Role, Value (A): role=grid on the table, aria-rowcount on the
  grid, aria-rowindex on every row, roving tabindex on the ROW so the whole list is ONE tab
  stop, aria-expanded on every disclosure (row expander, tier divider Why?, scope clauses,
  selector, ADR-011 Why this matters), aria-pressed on every ledger filter segment, and
  aria-busy on the grid only while a request that would change row count is in flight. aria-
  rowcount reflects the FILTERED count when a filter is active.
- WCAG 2.2 SC 1.3.1 Info and Relationships (A): band group headers are exposed as row-group
  labels so a screen-reader user hears 'Urgent, 84 referrals' before the rows inside it. The
  tier divider's rule is aria-hidden while its caption stays in the accessibility tree as a
  row-group label, and the divider is not focusable as a row. The expander's identity block
  is its FIRST content, so a screen-reader user hears WHO before WHAT. The Outside-the-
  ranking heading is a jump target from ledger term 4 and from the scope line's paediatric
  clause.
- Absence is never left to a screen reader to interpret. PRE-RUN the position sub-column and
  columns 4 and 5 are NOT RENDERED, and the reason is stated once in the merged header cell
  (PRE_RUN_COLUMN_HEADER) and once in the banner - there is no em dash and no 308-times-
  repeated placeholder. In the tail region the rail carries the visually-hidden
  NO_POSITION_ARIA string. A bare dash announced as 'dash' or as silence is a failure.
- The waiting-time meter is aria-hidden and presentational. Its accessible content is the
  two text lines, and the cell carries a complete accessible name (WAIT_ARIA: 'Waiting time
  871 days against a 28-day target; 31 times over.'). No information exists only in the
  graphic, which is why display:none on the meter changes no meaning.
- WCAG 2.2 SC 4.1.3 Status Messages (AA): a polite live region announces the two run
  counters on change AT MOST every 3 seconds (not every poll), the resulting row count after
  a filter toggle, the copy confirmation for a pathway number or an IRI, and every state
  change in the empty/error family. Nothing announces assertively; nothing steals focus
  except the one modal.
- WCAG 2.2 SC 3.3.4 Error Prevention (Legal, Financial, Data) (AA): the override modal
  satisfies review-confirm-correct before submission - the move is shown, the rule is named
  with its real numbers, both patients are compared in a two-column table with identical
  field order, and the attestation is a distinct step AFTER the disclosure. Nothing is
  written until Record. The inline in-band strip writes only on Record as well.
- WCAG 2.2 SC 3.3.1 Error Identification, 3.3.2 Labels or Instructions and 3.3.3 Error
  Suggestion (A/AA): a blank reason produces an inline field error naming the field and why
  it cannot be empty ('This field is written to the audit trail and cannot be empty.'),
  never a second modal and never a silent no-op. Every required field is labelled as
  required IN TEXT, not by an asterisk alone. Every disabled control carries its reason as
  visible DOM text.
- WCAG 2.2 SC 2.2.2 Pause, Stop, Hide (A) and SC 3.2.5 Change on Request (AAA, honoured
  deliberately): nothing auto-updates in a way that moves content. Rows never reorder on a
  background poll. The only reordering in the product is 'Show ranking' or a clinician's own
  recorded move. The only animation during a run is the digits changing.
- prefers-reduced-motion: reduce disables the 220ms FLIP entirely, disables the dock's
  slide, and leaves the static delta column ('moved' / 'up 12' / 'down 3') as the WHOLE
  treatment. Because that column is the accessibility fallback it is MUST, priced inside
  RunProgressPanel - an accessibility fallback can never be a COULD. There is no stagger
  even in the motion path, because staggering harms multi-object tracking.
- WCAG 2.2 SC 1.4.4 Resize Text (AA) and 1.4.12 Text Spacing (AA): the layout survives 200%
  text zoom and the 1.4.12 spacing overrides with no clipping and no loss of function. The
  fixed-height chrome strips must become auto-height under those overrides rather than
  clipping their text, and the table scrolls inside its own container rather than the page
  scrolling sideways.
- WCAG 2.2 SC 1.4.10 Reflow (AA): the ranked list is data requiring two-dimensional layout,
  so horizontal scrolling INSIDE the table's own overflow-x container is permitted;
  document.body must never scroll sideways at any width from 1280 up. Every non-table
  surface reflows to a single column - the dock's three step columns stack below 1000px. The
  product is scoped to >=1280 CSS px for the demo; a 320px claim would require a specified
  chrome reflow that this pack does not yet contain (see open questions).
- No information is EVER carried by a tooltip, a title attribute or a hover-only state -
  tooltips fail keyboard, touch and fast scanning alike. The full IRI, the disabled-Accept
  and disabled-Move reasons, the rule text, the tier divider's disclosure and every caveat
  are in the DOM as visible or focus-revealed text.
- The one modal is a native <dialog> opened with showModal(): focus is trapped, Esc cancels
  without writing, focus returns to the originating row. A dirty form raises an inline
  confirm INSIDE the same dialog - never a second stacked modal, which would break focus
  management and the interruption budget at once. There is exactly one showModal() call site
  in the bundle.
- Projector legibility (C7) is treated as an accessibility constraint, not a stylistic one:
  nothing primary may depend on 3dp numerals, a 6px strip, 11px ticks, or
  dashed/dotted/hatched borders. At 1280x720 on a projector a 6px strip subtends about 12.7
  arcmin and a 1px dash pattern about 2.1 arcmin, and that arithmetic models neither
  projector contrast, keystone nor compression. Lead with words and integers; the single
  density lever is --row-h (48/56) plus one type step, set from a measurement in the room.

---

## 10. Build order

1. 1. OrchestratorService (3.0h) — FIRST, because it blocks everything: nothing in web/ can
   render a real number until /api/cohort joins news2 onto the 308 rows. Ship it standalone
   and prove it with curl before a single React component exists. DONE WHEN: curl
   localhost:8080/api/cohort/9001/2026-08-30 returns 308 referrals each carrying news2, and
   the browser has never seen the bearer token.
2. 2. AppScaffoldAndDataLayer (0.75h) — Vite/TS, the one route, the fetch layer, the
   formatting module, --row-h / --type-step / --exp-gap. Nothing visual yet.
3. 3. RankedTableShell (2.5h) — the six tracks, the 172px sticky stack, frozen edges, the
   composited focus ring, scroll-padding and scroll-margin. Assert [192,176,256,184,192,248]
   summing to 1248 and no horizontal body scroll before anything else lands in it.
4. 4. THE FOUR CLINICIAN-RECORDED CELLS: ReferralRailCell (0.25h), CategoryTimeframeChip
   (0.5h), WaitTargetCell (0.75h), UrgencyNews2Cell (0.5h). FIRST DEMOABLE ARTEFACT, and it
   needs no agent run at all: 308 real rows with real waits, real categories and real NEWS2.
   If the week goes wrong, this is the demo.
5. 5. BandGroupHeader (0.75h) + OutsideRankingRegion (0.5h) — the five bands including the
   zero-row Excluded header, and the three paediatric refusals pulled into their named tail.
   The thesis is now visible pre-run: 148 rows at NEWS2 0, three refusals, and nothing
   computed by an agent.
6. 6. ScopeLine (0.5h) + ReconciliationLedger (0.5h) + OrderingStripAndPreRunBanner (0.75h)
   + ContextBarAndHospitalDaySelector (0.75h) — the whole 172px chrome closes. The pre-run
   screen is now complete and honest end to end, and every claim on it is measurable. SECOND
   DEMOABLE MILESTONE, and the safest possible fallback for 14 September.
7. 7. RowEvidenceExpander, sections 2, 3, 4 and 5 (1.75h of its 2.75h) + CitationChip
   (0.25h) — these four render fully from cohort plus one context call with no run. Section
   4 is the point of the product and it is reachable before any agent has ever executed.
8. 8. RunProgressPanel (1.25h) — 616 denominator, two counters, the withhold rule, Show
   ranking with the delta column. First live agent run. THIRD MILESTONE: a real ranked list
   on screen.
9. 9. BreachTierDivider (0.5h) + WhyThisPositionCell (0.75h) + ContributionDisplay (0.5h) —
   the ordering becomes legible: the two tier lines, the verdict in words with its foil
   named, and the signed arithmetic.
10. 10. RowEvidenceExpander, sections 1, 6, 7 and 8 (1.0h) — the four that need a held
   decision. The expander is now all eight sections in their fixed order.
11. 11. PairwiseCompareDock (1.75h) — the centrepiece. Three sort-key steps, the tie warning
   that fires on 29.1% of adjacent pairs, and the alpha-sensitivity line. Rehearse it on
   PW-9001-000208 vs PW-9001-000026, and on PW-9001-000191 at position 1.
12. 12. ActionRail (0.75h) + AcceptAction (0.25h) — the read-only product becomes a recording
   one. Accept writes through POST /overrides with the held decision_id, which is the first
   proof the integration gap is closed.
13. 13. OverrideDialogAndInlineReasonStrip (2.5h) — the inline strip first (it is the common
   path and needs no attestation), then the one modal. Restored by explicit decision and
   built last among the load-bearing work because everything it names must already exist on
   screen.
14. 14. EmptyErrorStateFamily (0.5h) + LoadingRule (0.25h) — the empty cohort panel, the
   upstream error line, the 400ms rule and the em-dash-never-zero sweep. Deliberately last:
   by now every real state exists to be tested against.
15. 15. PRESENT-DENSITY AND PROJECTOR PASS (inside the 2h of slack against 26h) — flip
   --row-h to 56 and --type-step to 1, re-verify the 196px chrome, the 8-row fold, and that
   nothing reflows. Force every colour token to one grey and confirm six regions are still
   countable and nameable.
16. 16. IF HOURS SURVIVE, in this order: ExportAndFilters, then WaitMeterGraphic, then
   PinnedRowTreatment. None is load-bearing; each is droppable without another component
   changing shape.

---

## 11. Amendments applied

This pack went through five verification rounds. Each of the following was a superseded
value that a reader of an earlier draft would have built wrongly. They are recorded so
that if you find an older number anywhere, you know which one wins.

- GRID TEXT, rail arithmetic: '192 = 8 pad + 16 A/B marker + 4 + 34 position + 10 + 116
  pathway + 8 pad' → the pathway sub-column is 112px, not 116px. 8+16+4+34+10+112+8 = 192.
  'PW-9001-000208' at 13px tabular measures ~109px and still fits without truncation.
- ReferralRailCell ANATOMY: 'pathway_number 116px' → 112px.
- ReferralRailCell PRE-RUN STATE: 'the pathway expands to 164px' → 156px. Pre-run rail = 8 +
  16 A/B + 4 + 156 pathway + 8 = 192.
- THE DECISION HEADER IS DELETED everywhere it appears (screens, RunProgressPanel 'decision'
  state, CAPACITY_LIMIT_AND_EFFECT's 'decision header and expander section 6'). Its line 2
  measured 197 chars against a 195-char break-even. Its content dissolves into OrderingStrip
  line 1 (ORDER_RANKED) and expander section 6.
- STICKY CHROME: with the decision header deleted the stack is 5 strips — 40+24+28+40+40 =
  172 desk, 44+28+32+48+44 = 196 present. scroll-padding-block-start and band-group-header
  top take the same figures.
- EXPANDER LAYOUT: 'TWO columns of 592px with a 32px gutter' → SINGLE column, 1216px content
  inside 16px insets, measure capped at 68ch.
- EXPANDER SECTION BUDGETS: old 74 / 56 / 197 / 92 / 110 / 128 / 252 / 24 → new 74 / 140 /
  202 / 150 / 230 / 92 / 256 / 24, in canon's fixed order, with an explicit 16px inter-
  section gap published as a token (--exp-gap). Sum = 1168 + 7×16 = 1280 in a 520px (desk) /
  560px (present) scrolling body.
- EXPANDER FOLD: 'left column sums to 593px so sections 1-3 sit above the internal scroll
  fold' → sections 1-3 now measure 74+16+140+16+202 = 448px inside a 496px body (520 minus
  the 24px pinned header), so the safety core still clears the fold and section 4's heading
  is visible at its edge.
- EXPANDER SECTION 3: the five-line normalisation paragraph (CALIBRATION_NOTE) moves OUT of
  the section body into its own disclosure behind EXP_S3_NORMALISE_CONTROL. Section 3 = 20
  heading + 20 total + 6×20 sub-scores + 20 agreement + 22 control = 202.
- EXPANDER SECTION 1 + ContributionDisplay: 74px cannot hold a 72px table. The signed
  arithmetic now sits behind the EXP_S1_ARITHMETIC disclosure inside section 1.
  ContributionDisplay is still one renderer shared with the dock's step 3.
- EXPANDER SECTION 6: at 92px the ward and clinic-session detail does not fit. It moves to
  section 7, where those bed_status nodes are the capacity citations anyway. Section 6 =
  heading + CAPACITY_LIMIT_AND_EFFECT (4 lines).
- EXPANDER OPEN BEHAVIOUR (new, must be published): opening an expander scrolls its row to
  the top of the list viewport. scroll-margin-block-start: 172px desk / 196px present on
  every row.
- PYTHONHASHSEED: DELETE every mention. It only ever existed to make
  coordinator/app/cli.py's fixture_scores deterministic (lines 147 and 159 use built-in
  hash()). The orchestrator composes coordinator functions directly and never passes
  --score-source fixture, so the fixture path is unreachable and is never demoed.
- RunProgressPanel DATA, 'urgency is n of 305 and capacity n of 308' → BOTH are n of 308.
  Verified on origin/urgency_agent: urgency_agent.run.run_for_cohort iterates every entry of
  cohort['referrals'] and refuses 0601 inside the loop. Progress denominator is 616 = two
  agents × 308.
- RUN_STATUS string: 'Scoring · urgency {n} of 305 · capacity {n} of 308' → 'urgency {n} of
  308 · capacity {n} of 308'.
- RUN_WITHHOLD string: '3 paediatric referrals will not be scored; capacity scores all 308'
  → both agents read all 308; the urgency agent refuses 3 of them. A refusal is an outcome,
  not a skipped row.
- RunProgressPanel TIMING: '8-15 seconds' → 'about 20 to 30 seconds'. Say 20-30s on stage;
  set the stall threshold from the first measured run, not from a round number.
- POST /api/runs must be a plain `def`, NOT `async def`. Both agents use synchronous httpx;
  an async handler blocks the event loop and starves the 1s progress poll.
- The in-memory decision is keyed on (hospital_hipe, as_of_date), not on hospital alone.
- The empty-cohort guard must be RE-IMPLEMENTED in the orchestrator. Verified: it exists
  only at coordinator/app/cli.py main() ('Empty cohort -- nothing to rank.'), which the
  orchestrator does not call. 2026-08-16 and 2026-08-31 return 200 with referrals: [] and
  are reachable by URL edit.
- Ranking runs are restricted to the latest day with data, 2026-08-30. VERIFIED:
  get_referral_context(hospital_hipe, pathway_number) takes NO date and retrieval does ORDER
  BY as_of_date DESC LIMIT 1, so the evidence horizon is date-blind. The selector BROWSES 28
  hospital-days and offers to RUN on one. New strings CTX_RUN_DISABLED_DATE and
  RUN_DATE_LOCK_BODY.
- news2 is NOT in the cohort payload. Verified: 14 fields per referral, no vitals. The
  orchestrator harvests it during the agents' /context pass and carries it in the decision
  view model; the UI never re-fetches it per row.
- ENDPOINT NAMESPACE: every /ui/* path in the pack → /api/*. GET /api/cohort/{h}/{date},
  /api/context/{h}/{pw}, /api/decision/{h}/{date}, /api/runs/{run_id}; POST /api/runs,
  /api/overrides. User-facing error strings still name the UPSTREAM retrieval path.
- ORCHESTRATOR HOURS: canon priced ZERO. must_list has 24 web components and no
  orchestrator, while five components assume one exists. OrchestratorService is now MUST #1
  at 3.0h.
- must_hours: 26.75 → 24.0.
- PairwiseCompareDock: 2.25h → 1.75h (A/B marker work removed).
- WaitTargetCell: 1.75h → 0.75h. The per-band square-root meter, its 1x tick, the 31.107x
  and 9.099x domains and the zero-wait stub are ALL DELETED. The cell is two text lines: the
  days numeral at 20px/600 tabular right-aligned in 92px, and the target statement. Nothing
  in the cell was carrying meaning the words did not already carry (F17 already required
  that).
- ReferralRailCell 0.5h → 0.25h and RankedTableShell 3.0h → 2.5h: the A/B treatment is now
  the reserved 16px slot and its letter only — no row-level pinned styling, no marker in the
  dock's steps band, no persistence across route changes.
- EmptyErrorStateFamily: four owned states → two, 1.0h → 0.5h. NOTHING IS REMOVED FROM THE
  SCREEN. 'No ranking yet' is already the OrderingStrip banner (PRE_RUN) and 'unresolved
  evidence' is already CitationChip's unresolved state; the family now owns only the empty-
  cohort panel and the network/HTTP line. All four absences still render and still look
  different from one another.
- BandGroupHeader 1.25 → 0.75h, ReconciliationLedger 0.75 → 0.5h, CategoryTimeframeChip 0.75
  → 0.5h: their loading/error variants are the two-state family's em-dash rule, not per-
  component work.
- RowEvidenceExpander refused state: 'PW-9001-000098 carries a recorded NEWS2 of 4, the
  joint-highest tier in this cohort' is WRONG. Measured distribution 0→148, 1→85, 2→35,
  3→26, 4→8, 5→3, 6→2, 7→1: 14 referrals score 4 or more and 6 score higher. Corrected in
  TAIL_NEWS2_NOTE.
- RowEvidenceExpander section 5: 'condition_label the literal placeholder Condition C43.9'
  is only the star case. Verified: the label is ALWAYS the string 'Condition ' + the
  ICD-10-AM code — 32 distinct labels across 408 condition rows, snomed_ct_id null on every
  one. CONDITION_PROVENANCE now states the general form.
- LEDGER_6: 'no reason reported' → 'no reason recorded'.
- ScopeLine dataset-wide figures (correlation ≤ 0.253, 51.1% score 0, 88.2% ≤ 2) are real
  but come from urgency-agent/urgency_agent/calibration.yml on origin/urgency_agent,
  measured against 609 observations in data v1.1 — a different denominator from this
  cohort's 308. They are kept out of SCOPE_C3_BODY, which now carries only first-hand
  figures for this hospital-day and for both hospitals on 30 August.
- OrderingStripAndPreRunBanner 0.5 → 0.75h: it now absorbs the deleted decision header's
  content in ORDER_RANKED. Alpha is NOT printed there — it appears only in expander section
  6 with both endpoints of its documented range and the outcome each produces.
- GET /referrals/{h}/{pw}/wait-counters: re-verified today. Without as_of_date it returns
  422; with as_of_date=2026-08-30 it returns 404 'no referral data for that date' for
  PW-9001-000208, which IS in that date's cohort. Bind nothing to it.
- RunProgressPanel 'a healthy run can exit non-zero': still true in general, but for
  9001/2026-08-30 the urgency agent exits 0. Verified: `return 0 if not result.skipped and
  not result.graph_projection_failed else 1` — refused_paediatric alone does not set exit 1.
  Composed in-process, exit codes are gone entirely; the orchestrator reads
  CohortRunResult's four dicts, which are keyed by pathway_number so per-row attribution
  comes free.

---

## 12. Open items, resolved

Five verification rounds ran against this pack. The final designer review returned
**ready: true** — *"I can draw every MUST surface tomorrow"* — with seven items outstanding,
none of them geometry and none of them scope. They are resolved here rather than left for
you to discover.

**1. The override dialog needed an internal vertical budget.** Its named blocks sum to about
606px in the band-crossing variant (heading 24 + tier disclosure 90 + the 7-row table 126 +
attestation + coded reason + free text + actions), against a stated 520px dialog. The dialog
is therefore **620 × 656 max-height**, which is the full space available at 720px viewport
less 32px margins top and bottom, and the 606px variant fits with 50px to spare. The
non-tier variant is shorter and pins to content height. If a future string pushes past 656,
the free-text area scrolls internally — never the attestation, which must always be visible
above the confirm control.

**2. The run panel's running, stalled and failed states had no declared surface.** They live
in the **ordering strip**, not the 40px context bar. The bar holds the run control and the
counters only; the strip's line 1 carries `RUN_STATUS` while a run is in flight and the
stalled and failed strings when it is not. This keeps the context bar at a fixed 40px in
every state, which the chrome budget depends on.

**3. The screens in section 4 predate the final amendments.** Section 3 (geometry), section
5 (components) and section 6 (strings) are post-amendment and win wherever they disagree.
Concretely: the rail is 112 and 156, not 116 and 164; there is no decision header; the
expander is single-column with the eight settled sections; and no `PYTHONHASHSEED` is set.
Read section 4 for layout intent and the later sections for numbers.

**4. The wait cell carried the deleted meter's width.** With the square-root meter cut, the
remainder is 240 − 92 = **148px**, not 140. Corrected in place.

**5. Two figures for the expander body, both correct, describing different things.** Total
section content is **1280px**. The scrolling body is **496px** (520 max-height less the 24px
pinned header). The safety core, sections 1 to 3, is 74 + 140 + 202 + two 16px gaps =
**448px**, which fits inside 496. There is no contradiction; the pack simply never said
which measurement was which.

**6. The selector's row-label column was too narrow.** `SELECTOR_ROW_9001` measures about
237px at 12px, so the grid is **573px wide** (237 label + 14 cells × 24px), not 486. The two
rows are fixed-width and the grid opens below the context bar rather than inside it, so this
costs nothing in the sticky stack.

**7. Two measurements were stated at the wrong type size.** `CTX_HOSPITAL_DAY` is a 14px bar
line, so 52 characters is about **384px**, not the 333px quoted at the 12px rate. It still
fits the 1248px bar comfortably. Where a `used_by` note gives a pixel figure, check it
against the type size of the surface it sits on, not the 12px body rate.

### What remains genuinely uncertain

Not defects, but things nobody has been able to settle yet:

- **The end-to-end path has never been executed once.** `GET /decisions/9001/2026-08-30`
  returns 404 for every hospital-day, and the coordinator's own docs record that every
  verification ran on synthetic scores. The first real run will find things this pack cannot.
- **The `POST /scores` half of the run is unmeasured.** `GET /context` is solid at ~13.6ms
  over 100 sequential calls, but each write does a Postgres insert plus an awaited Oxigraph
  SPARQL update, and nobody has timed it. The 20–30s run estimate could move.
- **PR #9 is unmerged**, so the urgency agent is vendored from a branch. That is a people
  risk, not a technical one: the merge is a verified fast-forward with no possible conflict.
- **Two fixes sit outside this track.** The `compute_scarcity` empty-list guard and the
  `hash()` determinism fix both belong to the coordinator, and the demo is not truthful
  without them.
