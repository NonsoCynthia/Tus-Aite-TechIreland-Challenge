/** One person's real dates, in two shapes, because they are two different
 *  stories and one axis cannot hold both.
 *
 *  Intake is five events inside about a month: a dated list, which is how a
 *  sequence of steps actually reads.
 *  The wait is years: an axis to scale, because its LENGTH is the argument.
 *
 *  The single clinical reading sits at the end of the list and the start of the
 *  axis, so the eye lands on the one measurement and then travels the whole
 *  empty line that follows it.
 */
export interface Event {
  key: string; date: string; label: string
  detail?: string; clinical?: boolean; target?: boolean
}

const DAY = 86_400_000
const days = (a: string, b: string) => Math.round((new Date(b).getTime() - new Date(a).getTime()) / DAY)
const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString('en-IE', { day: 'numeric', month: 'short', year: 'numeric' })
const fmtN = (n: number) => n.toLocaleString('en-IE')

export function Journey({ events, today }: { events: Event[]; today: string }) {
  const ev = events.filter((e) => e.date).sort((a, b) => a.date.localeCompare(b.date))
  if (!ev.length) return null

  const intake = ev.filter((e) => !e.target)
  const last = intake[intake.length - 1] ?? ev[0]
  const target = ev.find((e) => e.target)
  const intakeDays = days(ev[0].date, last.date)
  const waitDays = Math.max(days(last.date, today), 1)
  const clinical = [...intake].reverse().find((e) => e.clinical)
  const silentDays = clinical ? days(clinical.date, today) : 0
  const pct = (d: string) => Math.max(0, Math.min(100, (days(last.date, d) / waitDays) * 100))

  return (
    <div className="journey">
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
            {clinical && silentDays > 30 && <div className="j-silence" />}
            <div className="j-line" />
            {target && (
              <div className={'j-mark is-target' + (pct(target.date) < 12 ? ' is-early' : '')}
                   style={{ left: `${pct(target.date)}%` }}>
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
          {clinical && silentDays > 30 && (
            <p className="j-silence-note">
              <strong className="num">{fmtN(silentDays)} days</strong> since anyone measured
              this person. The shaded length is that wait, drawn to scale.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
