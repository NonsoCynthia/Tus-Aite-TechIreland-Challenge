import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { Mark } from '../components/Mark'

const fmt = (n: number) => n.toLocaleString('en-IE')

/** The opener.
 *
 *  An empty waiting room. A row of chairs IS a waiting list, which is also what
 *  the mark draws, so the photograph and the logo are saying the same thing
 *  before a single number appears.
 *
 *  Both figures are counted from the live cohort, not written down.
 *
 *  WORDING. The photograph is documentary -- a real waiting room, real people's
 *  chairs -- and it lends whatever sits over it the authority of a photograph.
 *  "308 people are waiting" therefore read as a headcount of that room, and
 *  this screen is in no position to assert one: it can see a list, not a
 *  population. It says what it can actually see instead. A referral is a row on
 *  this list; the count of rows is a fact about the list, and the sentence now
 *  claims exactly that and no more.
 *
 *  This is NOT a hedge and must not become one. The synthetic-data label was
 *  removed at the client's explicit instruction and does not come back, and no
 *  disclaimer replaces it. The fix is in the noun, which costs the screen
 *  nothing: the number is as large, as immediate and as true as it was.
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

        {/* The selector belongs here, not only behind the door: the two
            figures above are counted from whichever hospital is chosen, and
            with no control on this screen they always read 9001. */}
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
