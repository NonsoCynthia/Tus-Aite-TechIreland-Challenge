import { useQuery } from '@tanstack/react-query'
import { api, bandOf } from '../lib/api'
import type { CohortReferral } from '../lib/types'

/** Safe-operating occupancy. Bagust, Place & Posnett, BMJ 1999;319:155-8. */
const SAFE_OCCUPANCY = 85
const GAR = { G: 'Green', A: 'Amber', R: 'Red' } as const

const fmt = (n: number) => n.toLocaleString('en-IE')

/** Everything here is counted from the cohort payload. Nothing is estimated,
 *  and the two figures people usually get wrong are stated the honest way:
 *  breaches are of the referrals that HAVE a target, and the number with no
 *  target at all is given its own tile rather than hidden in a denominator. */
function summarise(rows: CohortReferral[]) {
  const withTarget = rows.filter((r) => r.crt_threshold_days != null)
  const breached = rows.filter((r) => r.crt_breached === true)
  const bands = new Map<string, number>()
  for (const r of rows) bands.set(bandOf(r.cpc), (bands.get(bandOf(r.cpc)) ?? 0) + 1)
  const waits = rows.map((r) => r.adjusted_wait_days ?? 0).sort((a, b) => a - b)
  const median = waits.length ? waits[Math.floor(waits.length / 2)] : 0
  const longest = waits.length ? waits[waits.length - 1] : 0
  const worst = breached
    .map((r) => ({ r, over: (r.adjusted_wait_days ?? 0) - (r.crt_threshold_days ?? 0) }))
    .sort((a, b) => b.over - a.over)[0]
  return { total: rows.length, withTarget, breached, bands, median, longest, worst }
}

export function Overview({ hospital, date, name }: { hospital: string; date: string; name: string }) {
  const q = useQuery({
    queryKey: ['cohort', hospital, date],
    queryFn: () => api.cohort(hospital, date),
  })
  // ~3.3s uncached: every ward's latest snapshot plus one context per referral
  // for the observation ages. Cached per hospital-day by the orchestrator.
  const ops = useQuery({
    queryKey: ['operations', hospital, date],
    queryFn: () => api.operations(hospital, date),
    staleTime: Infinity,
  })

  if (q.isPending) return <div className="pad"><p className="muted">Loading the waiting list…</p></div>
  if (q.error) return (
    <div className="pad">
      <div className="err">
        <strong>Could not load the waiting list.</strong>
        <div className="muted num">{String(q.error)}</div>
      </div>
    </div>
  )

  const s = summarise(q.data.referrals)
  const pctBreached = s.withTarget.length
    ? Math.round((s.breached.length / s.withTarget.length) * 100) : 0

  return (
    <div className="pad">
      <div className="lede">
        <h1>Who is waiting at {name}</h1>
        <p className="lede-p">
          <strong className="num">{fmt(s.total)}</strong> people are on this outpatient list.
          A clinician has already sorted them into Urgent, Semi-Urgent and Routine — this
          system never changes that. It suggests an order <em>inside</em> each group and
          shows its reasoning.
        </p>
      </div>

      <div className="tiles">
        <Tile figure={fmt(s.total)} label="on the list"
              note={`${fmt(s.bands.get('Urgent') ?? 0)} Urgent · ${fmt(s.bands.get('Semi-Urgent') ?? 0)} Semi-Urgent`} />
        <Tile figure={fmt(s.breached.length)} accent
              label={`past their target`}
              note={`of the ${fmt(s.withTarget.length)} that have one — ${pctBreached}%`} />
        <Tile figure={fmt(s.total - s.withTarget.length)}
              label="have no target at all"
              note="Routine and uncategorised referrals carry no clinical timeframe" />
        <Tile figure={fmt(s.median)} label="days, median wait"
              note={`the longest has waited ${fmt(s.longest)} days`} />
      </div>

      {s.worst && (
        <div className="worst">
          <div className="worst-k">Furthest past target</div>
          <div className="worst-v">
            <span className="num big">{fmt(s.worst.over)}</span> days beyond a{' '}
            <span className="num">{s.worst.r.crt_threshold_days}</span>-day target
            <span className="muted"> · {s.worst.r.pathway_number} · {bandOf(s.worst.r.cpc)}</span>
          </div>
        </div>
      )}

      {ops.data?.observation_age && (
        <div className="stale">
          <div className="stale-lead">
            <span className="num big">{fmt(ops.data.observation_age.median)}</span> days
            <span className="stale-lab"> since the newest clinical reading, typically</span>
          </div>
          <p className="stale-p">
            Every person here has exactly one set of vital signs, taken when their referral
            letter arrived, and never revisited — the national outpatient dataset records the
            pathway, not the person. The oldest reading on this list is{' '}
            <strong className="num">{fmt(ops.data.observation_age.max)}</strong> days old.{' '}
            <strong className="num">{fmt(ops.data.observation_age.over_1y)}</strong> are over a
            year old and <strong className="num">{fmt(ops.data.observation_age.over_2y)}</strong>{' '}
            are over two. A normal reading that old is an absence of information, not reassurance.
          </p>
        </div>
      )}

      {ops.data && ops.data.wards.length > 0 && (
        <section className="wards">
          <h2 className="sec-h">
            Beds right now
            <span className="sec-note">
              latest snapshot, {ops.data.wards.length} wards · the 85% mark is the
              safe-operating threshold (Bagust, <em>BMJ</em> 1999)
            </span>
          </h2>
          <div className="ward-grid">
            {ops.data.wards.map((w) => (
              <div className="ward" key={w.ward_id}>
                <div className="ward-top">
                  <span className="ward-id num">{w.ward_id.replace(/^W-\d+-/, 'Ward ')}</span>
                  <span className={'gar gar-' + (w.gar_status ?? 'G')}>
                    <i /> {GAR[(w.gar_status ?? 'G') as keyof typeof GAR]}
                  </span>
                </div>
                <div className="ward-track">
                  <i className="ward-fill" style={{ width: `${Math.min(100, w.occupancy_pct)}%` }} />
                  <i className="ward-safe" style={{ left: `${SAFE_OCCUPANCY}%` }} />
                </div>
                <div className="ward-bottom">
                  <span className="num ward-pct">{w.occupancy_pct.toFixed(1)}%</span>
                  <span className="ward-tr">
                    {w.over_24h > 0
                      ? <><strong className="num">{w.over_24h}</strong> over 24h</>
                      : w.over_9h > 0
                        ? <><strong className="num">{w.over_9h}</strong> over 9h</>
                        : 'no long waits'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <div className="bands">
        {['Urgent', 'Semi-Urgent', 'Routine', 'Uncategorised'].map((b) => {
          const n = s.bands.get(b) ?? 0
          const pct = s.total ? (n / s.total) * 100 : 0
          return (
            <div className="band-row" key={b}>
              <span className="band-name">{b}</span>
              <span className="band-track"><i className={'band-fill cat-' + b.toLowerCase().replace('-', '')}
                    style={{ width: `${pct}%` }} /></span>
              <span className="band-n num">{fmt(n)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Tile({ figure, label, note, accent }: {
  figure: string; label: string; note?: string; accent?: boolean
}) {
  return (
    <div className={'tile' + (accent ? ' is-accent' : '')}>
      <div className="tile-fig num">{figure}</div>
      <div className="tile-label">{label}</div>
      {note && <div className="tile-note">{note}</div>}
    </div>
  )
}
