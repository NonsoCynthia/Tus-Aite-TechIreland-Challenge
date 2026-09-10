/** Arithmetic shared by more than one surface, so that two surfaces can never
 *  print two different answers to the same question.
 *
 *  Nothing here grades, bands or decides. lib/severity.ts owns the scale;
 *  lib/news2.ts owns the clinical rubric. This file only counts.
 */

/** Median wait, in days. ONE convention, and it is the standard one: on an even
 *  n the arithmetic mean of the two middle values.
 *
 *  Overview.tsx used to take the upper-middle element instead. Recomputed across
 *  the 14 hospital-days of 9001 (GET /api/cohort/9001/<date>, adjusted_wait_days)
 *  the two conventions disagree on four of them:
 *
 *      date          n    mean-of-two   upper-middle
 *      2026-08-19   284       141           141      (lower-middle read 140)
 *      2026-08-21   286       141           142
 *      2026-08-22   286       142           143
 *      2026-08-30   308       140           140      (lower-middle read 139)
 *
 *  On 2026-08-21 and 2026-08-22 that difference reached the screen: neither day
 *  holds a decision, so both surfaces render their pre-ranking figures, and one
 *  hospital-day carried two different "median wait" numbers -- 142 on Overview
 *  and 141 on the list, then 143 and 142.
 *
 *  The rounding is part of the convention, not a detail: every
 *  adjusted_wait_days in this dataset is a whole number, so two middle values an
 *  odd distance apart average to a half-day. Math.round takes half UP, and the
 *  figure printed is a whole number of days.
 *
 *  Both surfaces import this. There is no second copy to keep in sync, which is
 *  what produced the disagreement in the first place.
 *
 *  Callers: Overview.tsx (summarise, bySpecialty) and List.tsx (the pre-ranking
 *  figures). ops.observation_age.median is the API's own median of a different
 *  quantity and is not computed here.
 */
export function median(xs: number[]): number {
  if (!xs.length) return 0
  const s = [...xs].sort((a, b) => a - b)
  const n = s.length
  return n % 2 ? s[(n - 1) / 2] : Math.round((s[n / 2 - 1] + s[n / 2]) / 2)
}
