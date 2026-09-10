/** The severity scale, in one place.
 *
 *  Four steps, driven by a NUMBER rather than a category, used for every "this
 *  needs attention" state in the product. See tokens.css for why the steps look
 *  the way they do and for the measured contrast of each.
 *
 *  The bands below are chosen against the real observed ranges, not invented:
 *
 *    wait / target      0.036x -> 31.1x   (165 rows; 143 have no target at all)
 *    reading age        12 -> 871 days    (all 308)
 *    NEWS2 sub-score    0 -> 3            (six per patient)
 *    occupancy          79.1 -> 100.0     (7 wards, 85% is the safe line)
 *    clinic booked      0.52 -> 1.00      (7 clinics)
 *
 *  Deliberately NOT driven by: NEWS2 total (148 of 308 tie at exactly 0),
 *  capacity score (identical for every referral in a specialty) or alpha (one
 *  number for the whole hospital-day). A scale on any of those would be flat
 *  across half the list and would imply discrimination the number cannot make.
 */
export type Sev = 0 | 1 | 2 | 3 | 4

/** 0 means "no mark at all" -- the absence of a severity is not a severity. */
export const NONE: Sev = 0

/** How far past target, as a multiple. Within target scores nothing. */
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

/** One vital's NEWS2 contribution. Steps 0/1/3/4 rather than 0/1/2/3: a
 *  sub-score of 3 is the top of the published rubric for five of the six
 *  parameters and must be unmistakable, so it skips a step. */
export function sevNews2Sub(score: number | null): Sev {
  if (score == null) return 0
  if (score <= 0) return 0
  if (score === 1) return 1
  if (score === 2) return 3
  return 4
}

/** The safe-operating occupancy line, as a percentage.
 *
 *  Bagust, Place & Posnett, "Dynamics of bed use in accommodating emergency
 *  admissions: stochastic simulation model", BMJ 1999;319:155-8: the risk of a
 *  bed crisis rises slowly up to about 85% average occupancy and steeply above
 *  it. It is a published operating threshold, not a house rule, which is why it
 *  is worth stating once.
 *
 *  Exported because it is BOTH a band boundary here and a line drawn on the
 *  ward chart. Two copies would let the line and the colour under it drift a
 *  point apart, and the drawn line is the only thing that says what the colour
 *  means. One constant, both jobs. */
export const SAFE_OCCUPANCY = 85

/** Occupancy against the safe-operating line. */
export function sevOccupancy(pct: number | null): Sev {
  if (pct == null) return 0
  if (pct < SAFE_OCCUPANCY) return 0
  if (pct < 95) return 1
  if (pct < 100) return 3
  return 4
}

/** Clinic slots booked over total. 1.0 has two causes -- fully booked, and no
 *  clinic at all (slots_total 0 returns 1.0 upstream) -- so the caller must
 *  say which; this only grades the number. */
export function sevBooked(ratio: number | null): Sev {
  if (ratio == null) return 0
  if (ratio < 0.75) return 0
  if (ratio < 0.9) return 1
  if (ratio < 1) return 3
  return 4
}

/** A rule that fired. Timeframe breaches are graded by how far past; a
 *  pass/fail rule with no magnitude goes straight to "high" rather than
 *  pretending to a gradation it does not have. */
export const sevBreach = (passed: boolean): Sev => (passed ? 0 : 3)

/** Data that does not reconcile. The loudest thing the product can say, because
 *  it means a number on screen cannot be trusted -- which outranks any clinical
 *  state, since a clinician can act on a bad number. */
export const SEV_INTEGRITY: Sev = 4
