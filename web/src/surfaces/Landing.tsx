import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Mark } from '../components/Mark'

const fmt = (n: number) => n.toLocaleString('en-IE')

/** The opener. Both figures are counted from the live cohort.
 *
 *  WORDING TRAP: this screen sees a LIST, not a population, so the lead counts
 *  rows -- "referrals are on this list" -- and must never become "people are
 *  waiting". Not a hedge: no disclaimer, and the synthetic-data label was
 *  removed at the client's instruction and does not come back.
 */
export function Landing({ hospital, date, name, hospitals, onHospital, onEnter }: {
  hospital: string; date: string; name: string
  hospitals: Array<{ hipe: string; name: string }>
  onHospital: (h: string) => void
  onEnter: () => void
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
              <strong className="num">{fmt(rows.length)}</strong> referrals are on this
              list at {name}. The longest has waited{' '}
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

        {/* The selector stays on this screen: the two figures above are
            counted from whichever hospital is chosen. */}
        <div className="landing-pick">
          <label className="landing-sel">
            <span className="lab">Hospital</span>
            <select value={hospital} onChange={(e) => onHospital(e.target.value)}>
              {hospitals.map((h) => <option key={h.hipe} value={h.hipe}>{h.name}</option>)}
            </select>
          </label>
          <button className="landing-go" onClick={onEnter} disabled={!ready}>
            See the hospital &rarr;
          </button>
        </div>
      </div>
    </div>
  )
}
