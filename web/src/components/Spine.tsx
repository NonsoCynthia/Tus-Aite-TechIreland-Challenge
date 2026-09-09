import type { Ranking } from '../lib/types'

/** The mark's geometry, carrying data.
 *
 *  VERTICAL (the list): the axis is rank within a category; each bar's length is
 *  wait ÷ target, so a bar crossing the stem's full reach is a referral past its
 *  target; the side says which term put them there. Clay marks only the
 *  breached, which keeps the kit's "one accent" rule true even at 84 rows.
 *
 *  If a bar cannot be given a real length -- Routine and Uncategorised have no
 *  target at all, 143 of 308 -- it is drawn as an open tick, never a full bar.
 *  A missing target is not a zero.
 */
export function SpineBar({ r, w = 96 }: { r: Ranking; w?: number }) {
  const target = r.crt_threshold_days
  const wait = r.adjusted_wait_days ?? 0
  const hasTarget = target != null && target > 0

  // urgency contributes alpha * score; waiting contributes (1 - alpha) * percentile.
  const uTerm = r.alpha * r.urgency_score
  const wTerm = (1 - r.alpha) * r.wait_normalised
  const leadIsWait = wTerm >= uTerm

  if (!hasTarget) {
    return (
      <span className="spine" style={{ width: w }} title="no target for this category">
        <i className="spine-stem" />
        <i className="spine-tick" style={{ left: leadIsWait ? '52%' : '40%' }} />
      </span>
    )
  }
  const ratio = wait / target
  const over = ratio > 1
  // sqrt keeps a 31x overflow on the same axis as a 1.2x one without either
  // becoming invisible. The numeral beside it always carries the true value.
  const len = Math.min(1, Math.sqrt(Math.min(ratio, 1)))
  const overLen = over ? Math.min(1, Math.sqrt(Math.min(ratio / 8, 1))) : 0

  return (
    <span className="spine" style={{ width: w }}
          title={`${wait} days against a ${target}-day target`}>
      <i className="spine-stem" />
      <i className={'spine-bar' + (leadIsWait ? ' is-wait' : ' is-urgency')}
         style={{ width: `${len * 44}%` }} />
      {over && <i className="spine-over" style={{ width: `${overLen * 44}%` }} />}
    </span>
  )
}
