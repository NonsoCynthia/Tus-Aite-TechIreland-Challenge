/** The severity scale, in one place: four steps, driven by a NUMBER rather than
 *  a category. Band boundaries are fitted to the ranges the live API actually
 *  produces -- recount from it, never adjust one by eye. Step colours and their
 *  measured contrast: tokens.css. See BUILD_LEDGER.md.
 *
 *  NOT driven by NEWS2 total, capacity score or alpha: each is constant across a
 *  specialty or the whole hospital-day, so a scale on it would be flat. */
export type Sev = 0 | 1 | 2 | 3 | 4

/** The absence of a severity, not a low one. */
export const NONE: Sev = 0

/** How far past target, as a multiple. */
export function sevWaitRatio(ratio: number | null): Sev {
  if (ratio == null || ratio <= 1) return 0
  if (ratio < 2) return 1
  if (ratio < 5) return 2
  if (ratio < 10) return 3
  return 4
}

/** Age of the single reading. A stale normal reading is an absence of
 *  information, not reassurance, so age escalates on its own. */
export function sevReadingAge(days: number | null): Sev {
  if (days == null) return 0
  if (days < 90) return 0
  if (days < 365) return 1
  if (days < 730) return 3
  return 4
}

/** One vital's NEWS2 contribution. Steps 0/1/3/4, not 0/1/2/3: a sub-score of 3
 *  is the top of the published rubric and must be unmistakable. */
export function sevNews2Sub(score: number | null): Sev {
  if (score == null) return 0
  if (score <= 0) return 0
  if (score === 1) return 1
  if (score === 2) return 3
  return 4
}

/** The safe-operating occupancy line, as a percentage. Bagust, Place & Posnett,
 *  "Dynamics of bed use in accommodating emergency admissions", BMJ
 *  1999;319:155-8: bed-crisis risk rises slowly to about 85% average occupancy
 *  and steeply above it. Exported because it is BOTH a band boundary here and
 *  the line drawn on the ward chart; two copies drift apart. */
export const SAFE_OCCUPANCY = 85
/** The step-3 boundary. Exported for the same reason: a screen that names a
 *  threshold in words must read it from the band that draws it. */
export const CROWDED_OCCUPANCY = 95

export function sevOccupancy(pct: number | null): Sev {
  if (pct == null) return 0
  if (pct < SAFE_OCCUPANCY) return 0
  if (pct < CROWDED_OCCUPANCY) return 1
  if (pct < 100) return 3
  return 4
}

/** Clinic slots booked over total. 1.0 means fully booked OR no clinic at all
 *  (slots_total 0 returns 1.0 upstream), so the caller must say which. */
export function sevBooked(ratio: number | null): Sev {
  if (ratio == null) return 0
  if (ratio < 0.75) return 0
  if (ratio < 0.9) return 1
  if (ratio < 1) return 3
  return 4
}

/** A pass/fail rule carries no magnitude, so it goes straight to "high". */
export const sevBreach = (passed: boolean): Sev => (passed ? 0 : 3)

/** Data that does not reconcile. Outranks any clinical state: the number on
 *  screen cannot be trusted. */
export const SEV_INTEGRITY: Sev = 4
