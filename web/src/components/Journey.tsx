/** One person's real dates, in two shapes, because they are two different
 *  stories and one axis cannot hold both. Intake is five events inside about a
 *  month: a dated list, which is how a sequence of steps reads. The wait is
 *  years: an axis to scale, because its LENGTH is the argument.
 *
 *  The axis draws the two spans rather than asserting them in copy -- past the
 *  CRT target, and since anyone measured this person -- so they are compared by
 *  eye. The staleness READING lives with the vitals, one section above; what is
 *  left here is its length. */
export interface Event {
  key: string; date: string; label: string
  detail?: string; clinical?: boolean; target?: boolean
}

const DAY = 86_400_000
const days = (a: string, b: string) => Math.round((new Date(b).getTime() - new Date(a).getTime()) / DAY)
const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString('en-IE', { day: 'numeric', month: 'short', year: 'numeric' })
const fmtN = (n: number) => n.toLocaleString('en-IE')

export function Journey({ events, today, waitDays: waitProp, targetDays, className = '' }: {
  events: Event[]
  today: string
  /** `adjusted_wait_days` — the SAME number the header, the rule chip and the
   *  breach tier use. Never recompute the wait from the last intake event: that
   *  is the triage date, while every other figure on the page is measured from
   *  the date the referral was RECEIVED, and adjusted wait also excludes
   *  suspended time, so it cannot be derived from the dates here at all. */
  waitDays?: number
  /** The CRT threshold in days, from core.ref_codes. The target sits this far
   *  into the wait, not this far past the triage date. */
  targetDays?: number | null
  className?: string
}) {
  const ev = events.filter((e) => e.date).sort((a, b) => a.date.localeCompare(b.date))
  if (!ev.length) return null

  const intake = ev.filter((e) => !e.target)
  const last = intake[intake.length - 1] ?? ev[0]
  const target = ev.find((e) => e.target)
  const intakeDays = days(ev[0].date, last.date)
  // fall back to the old derivation only when the caller supplies nothing
  const waitDays = Math.max(waitProp ?? days(last.date, today), 1)
  const clinical = [...intake].reverse().find((e) => e.clinical)
  const silentDays = clinical ? days(clinical.date, today) : 0
  /** Distance along the axis, measured BACK from today so the end of the axis
   *  is always "now" and the wait length is the authoritative one. */
  const pctBack = (daysAgo: number) =>
    Math.max(0, Math.min(100, ((waitDays - daysAgo) / waitDays) * 100))
  const pct = (d: string) => pctBack(days(d, today))

  // The span past the target, drawn rather than described, and derived from the
  // same threshold the rule chip cites.
  const overdueDays = targetDays != null ? waitDays - targetDays : (target ? days(target.date, today) : 0)
  const overdue = overdueDays > 0 && (targetDays != null || !!target)
  const overdueFrom = targetDays != null ? pctBack(overdueDays) : (target ? pct(target.date) : 0)
  // the marker and the overdue span are the same point, so they cannot drift
  const targetPct = targetDays != null ? pctBack(Math.max(overdueDays, 0)) : (target ? pct(target.date) : 0)
  const silent = !!clinical && silentDays > 30
  const silentFrom = clinical ? pct(clinical.date) : 0

  return (
    <div className={`journey ${className}`.trim()}>
      <div className="j-cols">
        <div className="j-intake">
          <div className="j-h">Getting on the list <span className="num">{fmtN(intakeDays)} days</span></div>
          <ol className="j-steps">
            {intake.map((e) => (
              <li key={e.key} className={e.clinical ? 'is-clinical' : ''}>
                <span className="j-d num">{fmtDate(e.date)}</span>
                <span className="j-t">{e.label}</span>
                {e.detail && <span className="j-x">{e.detail}</span>}
              </li>
            ))}
          </ol>
        </div>

        <div className="j-waiting">
          <div className="j-h">
            Waiting since <span className="num">{fmtN(waitDays)} days</span>, to scale
          </div>
          <div className="j-axis">
            {silent && <div className="j-silence" style={{ left: `${silentFrom}%`, right: 0 }} />}
            <div className="j-line" />
            {/* drawn AFTER the line so it recolours that stretch of the axis
                itself: the part of the wait that is past target. */}
            {overdue && (
              <div className="j-overdue" style={{ left: `${overdueFrom}%`, right: 0 }}
                   role="img" aria-label={`past target by ${fmtN(overdueDays)} days`} />
            )}
            {target && (
              <div className={'j-mark is-target' + (targetPct < 12 ? ' is-early' : '')}
                   style={{ left: `${targetPct}%` }}>
                <i />
                <span className="j-mt">{target.label}</span>
                <span className="j-md num">{fmtDate(target.date)}</span>
              </div>
            )}
            <div className="j-mark is-now" style={{ left: '100%' }}>
              <i />
              <span className="j-mt">today</span>
              <span className="j-md num">{fmtDate(today)}</span>
            </div>
          </div>

          <ul className="j-legend">
            {overdue && (
              <li className="j-leg is-overdue">
                <i aria-hidden />past target by <strong className="num">{fmtN(overdueDays)} days</strong>
              </li>
            )}
            {target && !overdue && (
              <li className="j-leg">
                <i aria-hidden />
                <strong className="num">{fmtN(Math.abs(overdueDays))} days</strong> until the target
              </li>
            )}
            {silent && (
              <li className="j-leg is-silent">
                <i aria-hidden />unmeasured for <strong className="num">{fmtN(silentDays)} days</strong>
              </li>
            )}
          </ul>
        </div>
      </div>
    </div>
  )
}
