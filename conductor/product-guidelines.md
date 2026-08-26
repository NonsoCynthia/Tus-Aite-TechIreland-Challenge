# Product Guidelines

> How this product speaks, looks, and behaves. In a clinical decision-support tool, wording is a
> safety surface, not decoration. These rules are binding on UI copy, rationale text, LLM prompts,
> and the pitch deck alike.

## Quick Reference

1. **Never show a score without its evidence.** A number with no citation is a black box, which is
   exactly what this project exists to eliminate.
2. **The system suggests; the clinician decides.** Never use verbs that imply the system acted —
   no "admitted", "scheduled", "assigned", "approved", "triaged".
3. **Never make a diagnostic claim.** Report signals and categories, not conditions.
4. **Say which rule fired, by name.** "NEWS2 aggregate 7" beats "high urgency". "Outside 13-week CRT"
   beats "overdue".
5. **Overrides are first-class, never failures.** The UI must never frame a clinician override as a
   correction, error, or deviation.
6. **Uncertainty is stated, not hidden.** Missing vitals, stale bed status, and low-confidence signals
   are shown, not silently defaulted.
7. **Every number on screen is traceable to a triple.** If it can't be walked back to graph evidence,
   it doesn't belong on screen.
8. **Synthetic data is labelled as synthetic, everywhere.** In the UI, in exports, in screenshots, in
   the demo. No exceptions.

## Voice and Tone

**Clinical, plain, and specific.** The reader is a clinician under time pressure who will not forgive
padding. Prefer the shortest phrasing that keeps the evidence attached.

**Confident about mechanism, humble about judgement.** State plainly what the system computed and
which rule produced it. Never imply the ranking is correct — only that it is derived and traceable.

**No persuasion in clinical surfaces.** Marketing voice belongs in the deck, never in the ranked list.

### Verbs

| Use | Avoid | Why |
|---|---|---|
| ranked, scored, flagged, cited, surfaced | decided, triaged, approved, prioritised (as a system act) | The system does not act on patients |
| shows signals consistent with | indicates, diagnoses, suggests the patient has | Non-diagnostic boundary |
| recorded, logged | corrected, fixed, resolved | Overrides are not corrections |
| within / outside CRT | on time / late | Names the actual rule |

### Rationale Text Rules

Per-patient rationale is the core product surface. Every rationale must:

- Name the **urgency signals** that contributed, with their values (`NEWS2 aggregate 7`, `MTS category
  Orange`, `referral age 96 days`).
- Name the **capacity constraints** that contributed (`Ward B occupancy 104%`, `no cardiology bed
  before 14:00`).
- Name the **CPC** and whether the CRT window is intact.
- Be reconstructible: every claim in the text corresponds to a `cites` edge in the graph. The LLM
  writes prose *from* cited evidence; it never introduces a fact the graph does not contain.
- Never speculate about cause, outcome, or diagnosis.

Template shape:

> Ranked #3. Urgent CPC, referred 31 days ago — **outside** the 28-day CRT. NEWS2 aggregate 7
> (respiratory rate 24, SpO₂ 92%). Cardiology beds at 104% occupancy; earliest availability 14:00.

Anti-example (rejected — unsourced, diagnostic, and system-as-actor):

> ~~This patient looks quite unwell and should probably be seen first — likely sepsis. We've moved
> them to the top of the list.~~

## Interface Principles

- **The ranked list is the product.** Everything else is supporting surface.
- **Evidence is one interaction away, never buried.** Expanding a row shows the cited signals and
  constraints; no navigation away from the list.
- **Override controls are always visible**, not hidden behind a menu. If overriding is harder than
  accepting, the human-in-the-loop claim is cosmetic.
- **Rule violations are loud.** A CPC/CRT violation gets a distinct, unmissable treatment — it is the
  single most important thing the validation layer produces.
- **Explain at every handoff point.** Where the urgency agent hands to the coordinator, and the
  coordinator to the clinician, the UI shows what crossed the boundary.

## Accessibility

- Never encode urgency by colour alone — MTS categories carry colour names (Red, Orange, Yellow,
  Green, Blue) and must also be labelled in text.
- Target WCAG 2.2 AA contrast. Clinical displays are read on poor monitors in bright rooms.
- Full keyboard operation for accept, reorder, and override. Clinicians are faster on keys than mice.

## Terminology

Use the Irish clinical terms, spelled out on first use in any given view, then abbreviated:
Clinical Prioritisation Category (CPC), Clinically Recommended Timeframe (CRT), Manchester Triage
System (MTS), National Early Warning Score 2 (NEWS2), Irish Children's Triage System (ICTS),
Emergency Medicine Early Warning System (EMEWS). Full glossary lives in the proposal, section 15.

Use Irish/British spelling throughout: prioritisation, randomised, recognised, colour.

## Responsible AI Statements

Every surface that shows a ranking carries, at minimum:

- A visible statement that output is decision support requiring clinician sign-off.
- A visible synthetic-data label.
- Access to the audit trail for any ranked position.

The compliance boundary is documented once, in the track's decisions log, and referenced — never
restated in a way that could drift.
