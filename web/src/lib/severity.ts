/** The severity scale, in one place.
 *
 *  Four steps, driven by a NUMBER rather than a category, used for every "this
 *  needs attention" state in the product. See tokens.css for why the steps look
 *  the way they do and for the measured contrast of each.
 *
 *  The bands below are chosen against the real observed ranges, not invented.
 *  Each range is the range of the quantity its own band function is CALLED
 *  with, recounted from the live API over all 14 hospital-days at 9001
 *  (2026-08-17 to 2026-08-30, 283 to 308 referrals a day):
 *
 *    wait / target      0.000x -> 31.107x  adjusted_wait_days / crt_days, over the
 *                                          154-165 rows a day that have a target
 *                                          (165 of the 308 on 2026-08-30; the other
 *                                          143 are Routine or Uncategorised and have
 *                                          no target, so they enter no range at all)
 *    reading age        0 -> 871 days      one observation per referral, and every
 *                                          referral has one, on all 14 days
 *    NEWS2 sub-score    0 -> 3             six per patient; five of the six reach 3,
 *                                          temperature never exceeds 1
 *    occupancy          79.12 -> 100.00    7 wards, 85% is the safe line
 *    clinic booked      0.520 -> 1.000     7 clinics, cited_pressure of the one cited
 *                                          session
 *
 *  The last two are identical on all 14 days, and that is a property of the
 *  data rather than a coincidence: the ward and clinic queries carry no date
 *  predicate, so every hospital-day is served the same 2026-08-30T20:00 ward
 *  snapshot and the same 2026-08-28 clinic session.
 *
 *  TWO BOTTOM ENDS WERE WRONG IN PRINT and are corrected above: the wait ratio
 *  read 0.036x and the reading age read 12 days. Neither is the minimum of
 *  anything. Referrals received on the day they are counted have a wait of 0
 *  and a ratio of exactly 0.000x -- 2 of them on 2026-08-30, 3 on 2026-08-17 --
 *  and 12 of the 308 readings on 2026-08-30 were taken on the as-of date, an
 *  age of 0 days. 0.036 is 1/28, the smallest NON-ZERO ratio on the newest day,
 *  and 12 is a count of rows, not a number of days.
 *
 *  Nothing renders this block and no boundary below reads it: a ratio at or
 *  under 1 and an age under 90 days both score 0, so the two corrected figures
 *  land exactly where the wrong ones did and NO BAND MOVES. What the block is
 *  for is the claim that the boundaries were fitted to real data, which is the
 *  one thing a reviewer checks it for -- so a figure in it that no measurement
 *  produces costs the whole scale its provenance. Recount from the API; never
 *  carry a figure over from a neighbouring comment.
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
