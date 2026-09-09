import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Mark } from '../components/Mark'

const fmt = (n: number) => n.toLocaleString('en-IE')

/** The opener.
 *
 *  An empty waiting room, and two true sentences. A row of chairs IS a waiting
 *  list, which is also what the mark draws, so the photograph and the logo are
 *  saying the same thing before a single number appears.
 *
 *  Both figures are counted from the live cohort, not written down.
 */
export function Landing({ hospital, date, name, onEnter }: {
  hospital: string; date: string; name: string; onEnter: () => void
}) {
  const q = useQuery({ queryKey: ['cohort', hospital, date], queryFn: () => api.cohort(hospital, date) })
  const rows = q.data?.referrals ?? []
  const longest = rows.reduce((m, r) => Math.max(m, r.adjusted_wait_days ?? 0), 0)
  const ready = rows.length > 0

  return (
    <div className="landing">
      <img className="landing-img" src="/brand/chairs.png" alt="" aria-hidden="true" />
      <div className="landing-scrim" />

      <div className="landing-in">
        <div className="landing-mark">
          <Mark size={62} draw />
        </div>

        <h1 className="landing-word">Tús Áite</h1>
        <p className="landing-sub">decision support &middot; Irish for <em>first place</em></p>

        <p className="landing-lead">
          {ready ? (
            <>
              <strong className="num">{fmt(rows.length)}</strong> people are waiting at{' '}
              {name}. The longest has waited{' '}
              <strong className="num">{fmt(longest)}</strong> days.
            </>
          ) : (
            <>Reading the waiting list&hellip;</>
          )}
        </p>

        <p className="landing-thesis">
          A clinician has already decided who is urgent. This does not change that.
          It suggests an order <em>within</em> each group, and shows every piece of
          evidence it used.
        </p>

        <button className="landing-go" onClick={onEnter} disabled={!ready}>
          See the hospital &rarr;
        </button>
      </div>
    </div>
  )
}
