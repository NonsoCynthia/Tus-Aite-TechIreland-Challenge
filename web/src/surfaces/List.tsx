import { useEffect, useMemo, useState } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useQuery } from '@tanstack/react-query'
import { api, bandOf, BANDS } from '../lib/api'
import type { CohortReferral, Decision } from '../lib/types'

const fmt = (n: number) => n.toLocaleString('en-IE')

type Row = CohortReferral & {
  position?: number
  urgency_score?: number
  wait_normalised?: number
  news2?: number | null
  reading_age_days?: number | null
  obs_datetime?: string | null
}

/** Order within a band, and what decided it.
 *  Pre-run there is no position: rows sit in referral-date order and the screen
 *  says so, because a display order is not a ranking. */
function useRows(hospital: string, date: string) {
  const cohort = useQuery({ queryKey: ['cohort', hospital, date], queryFn: () => api.cohort(hospital, date) })
  const ops = useQuery({ queryKey: ['operations', hospital, date], queryFn: () => api.operations(hospital, date), staleTime: Infinity })
  const decision = useQuery<Decision>({
    queryKey: ['decision', hospital, date], queryFn: () => api.decision(hospital, date),
    retry: false, staleTime: 5_000,
  })

  const rows = useMemo<Row[]>(() => {
    if (!cohort.data) return []
    const clinical = ops.data?.clinical ?? {}
    const placed = new Map(decision.data?.rankings.map((r) => [r.pathway_number, r]) ?? [])
    return cohort.data.referrals.map((r) => {
      const p = placed.get(r.pathway_number)
      const c = clinical[r.pathway_number]
      return {
        ...r,
        position: p?.position,
        urgency_score: p?.urgency_score,
        wait_normalised: p?.wait_normalised,
        news2: c?.news2 ?? null,
        reading_age_days: c?.reading_age_days ?? null,
        obs_datetime: c?.obs_datetime ?? null,
      }
    })
  }, [cohort.data, ops.data, decision.data])

  return { rows, decision: decision.data, loading: cohort.isPending, error: cohort.error }
}

export function List({ hospital, date, onOpen }: { hospital: string; date: string; onOpen: (pw: string) => void }) {
  const { rows, decision, loading, error } = useRows(hospital, date)
  const [tab, setTab] = useState('Urgent')

  const refused = new Set(decision?.refused_paediatric ?? [])
  const groups = useMemo(() => {
    const g: Record<string, Row[]> = { Urgent: [], 'Semi-Urgent': [], Routine: [], Uncategorised: [], Outside: [] }
    for (const r of rows) (refused.has(r.pathway_number) ? g.Outside : g[bandOf(r.cpc)]).push(r)
    for (const k of Object.keys(g)) {
      g[k].sort((a, b) =>
        a.position != null && b.position != null
          ? a.position - b.position
          : a.referral_date.localeCompare(b.referral_date))
    }
    return g
  }, [rows, decision])

  if (loading) return <div className="pad"><p className="muted">Loading…</p></div>
  if (error) return <div className="pad"><div className="err">{String(error)}</div></div>

  const ranked = decision != null
  const tabKeys = [...BANDS.map((b) => b.key), 'Outside'] as string[]

  return (
    <div className="pad">
      <div className="lede">
        <h1>{ranked ? 'Suggested order' : 'The list, before any ranking'}</h1>
        <p className="lede-p">
          {ranked ? (
            <>Every Urgent patient is seen before every Semi-Urgent patient — no score moves
            anyone between groups. Inside a group the order weighs how unwell someone looks
            against how long they have waited, at{' '}
            <strong className="num">{Math.round(decision.alpha * 100)}%</strong> to{' '}
            <strong className="num">{Math.round((1 - decision.alpha) * 100)}%</strong>, set
            once for the whole hospital. Every reading below was taken the week the
            referral arrived and never repeated, so its date is also how long that
            person has been unmeasured.</>
          ) : (
            <>No agent has scored this hospital-day. These are the referrals a clinician
            recorded, in referral-date order — <em>a display order, not a ranking</em>.</>
          )}
        </p>
      </div>

      <Tabs.Root value={tab} onValueChange={setTab}>
        <Tabs.List className="tabs" aria-label="Clinical category">
          {tabKeys.map((k) => (
            <Tabs.Trigger key={k} value={k} className="tab">
              <span className={'tab-swatch cat-' + k.toLowerCase().replace('-', '')} />
              {k === 'Outside' ? 'Outside the ranking' : k}
              <span className="tab-n num">{groups[k]?.length ?? 0}</span>
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        {tabKeys.map((k) => (
          <Tabs.Content key={k} value={k} className="tab-panel">
            {k === 'Outside' ? (
              <p className="panel-note">
                Not scored, not placed. <strong>This is not a low position.</strong> NEWS2 is
                validated in adults, so the urgency agent refuses paediatric specialties
                rather than scoring a child on an adult scale. Their category and waiting
                time are shown in full, because a clinician recorded those.
              </p>
            ) : (
              <p className="panel-note">
                {BANDS.find((b) => b.key === k)?.target
                  ? <>Target: seen within <strong className="num">{BANDS.find((b) => b.key === k)!.target}</strong> days
                    {' · '}<strong className="num">{groups[k].filter((r) => r.crt_breached).length}</strong> already past it</>
                  : <>No clinical timeframe applies to this category, so nothing here can be “late”.</>}
              </p>
            )}
            <RowTable rows={groups[k] ?? []} ranked={ranked} outside={k === 'Outside'} onOpen={onOpen} />
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </div>
  )
}

const PAGE = 20

function RowTable({ rows, ranked, outside, onOpen }: { rows: Row[]; ranked: boolean; outside: boolean; onOpen: (pw: string) => void }) {
  const [page, setPage] = useState(0)
  // switching category resets to the top of that category, never mid-list
  useEffect(() => { setPage(0) }, [rows])

  if (!rows.length) return <p className="muted pad-y">Nobody in this group.</p>

  const pages = Math.ceil(rows.length / PAGE)
  const from = page * PAGE
  const slice = rows.slice(from, from + PAGE)

  return (
    <>
    <table className="rows">
      <thead>
        <tr>
          <th className="c-rank">{outside ? '' : ranked ? 'Order' : ''}</th>
          <th className="c-id">Referral</th>
          <th className="c-wait">Waited <span className="th-sub">against target</span></th>
          <th className="c-n2">How unwell <span className="th-sub">NEWS2, and the date it was measured</span></th>
          <th className="c-why">{ranked && !outside ? 'Why here' : ''}</th>
        </tr>
      </thead>
      <tbody>
        <AnimatePresence initial={false}>
          {slice.map((r, i) => (
            <PatientRow key={r.pathway_number} r={r} i={i}
                        ranked={ranked} outside={outside} onOpen={onOpen} />
          ))}
        </AnimatePresence>
      </tbody>
    </table>

    {pages > 1 && (
      <nav className="pager" aria-label="Pages within this category">
        <span className="pager-of num">
          {from + 1}&ndash;{Math.min(from + PAGE, rows.length)} of {rows.length}
          {ranked && <span className="muted"> &middot; in suggested order</span>}
        </span>
        <span className="pager-btns">
          <button className="pg" onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}>Previous</button>
          {Array.from({ length: pages }, (_, i) => i).map((i) => (
            <button key={i} className={'pg pg-n num' + (i === page ? ' is-on' : '')}
                    onClick={() => setPage(i)} aria-current={i === page}>{i + 1}</button>
          ))}
          <button className="pg" onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
                  disabled={page === pages - 1}>Next</button>
        </span>
      </nav>
    )}
    </>
  )
}

function PatientRow({ r, ranked, outside, onOpen, i }: { r: Row; ranked: boolean; outside: boolean; onOpen: (pw: string) => void; i: number }) {
  const still = useReducedMotion()
  const target = r.crt_threshold_days
  const wait = r.adjusted_wait_days ?? 0
  const over = target != null && wait > target
  const ratio = target ? wait / target : null
  const age = r.reading_age_days

  return (
    <motion.tr
        className="row is-clickable" tabIndex={0} role="button"
        layout={still ? false : 'position'}
        layoutId={`row-${r.pathway_number}`}
        initial={still ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={still ? { duration: 0 } : {
          // stagger only across a page, never the whole 305: a queue that takes
          // seconds to appear reads as slow, not considered
          delay: Math.min(i, 20) * 0.014,
          duration: 0.26, ease: [0.2, 0, 0, 1],
        }}
        onClick={() => onOpen(r.pathway_number)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(r.pathway_number) } }}>
      <td className="c-rank num">
        {outside ? <span className="muted">—</span> : r.position != null ? r.position : ''}
      </td>
      <td className="c-id">
        <div className="pw num">{r.pathway_number}</div>
        <div className="sub">specialty {r.specialty_hipe}</div>
      </td>
      <td className="c-wait">
        <div className="wait-n num">{fmt(wait)} days</div>
        <div className="sub">
          {target == null ? 'no target for this category'
            : over ? <><span className="over num">{ratio! >= 10 ? Math.round(ratio!) : ratio!.toFixed(1)}× over</span> a {target}-day target</>
              : <>within a {target}-day target</>}
        </div>
      </td>
      <td className="c-n2">
        <div className="n2 num">NEWS2 {r.news2 ?? '—'}<span className="of"> of 17</span></div>
        <div className={'sub' + (age != null && age > 365 ? ' stale-flag' : '')}>
          {r.obs_datetime == null ? 'no reading' : <>
            measured {new Date(r.obs_datetime).toLocaleDateString('en-IE',
              { day: 'numeric', month: 'short', year: 'numeric' })}
            {age != null && age > 365 && <> · <strong>never since</strong></>}
          </>}
        </div>
      </td>
      <td className="c-why">
        {ranked && !outside && r.urgency_score != null && r.wait_normalised != null
          ? <Contribution urgency={r.urgency_score} wait={r.wait_normalised} />
          : null}
      </td>
    </motion.tr>
  )
}

/** Both terms, always. The weight alone would mislead: urgency carries most of
 *  it but almost no spread, so waiting time does the discriminating. */
function Contribution({ urgency, wait }: { urgency: number; wait: number }) {
  const u = Math.max(0, Math.min(1, urgency))
  const w = Math.max(0, Math.min(1, wait))
  return (
    <div className="contrib" title={`urgency ${u.toFixed(3)} · waiting ${w.toFixed(3)}`}>
      <div className="contrib-row">
        <span className="contrib-lab">unwell</span>
        <span className="contrib-track"><i style={{ width: `${u * 100}%` }} /></span>
      </div>
      <div className="contrib-row">
        <span className="contrib-lab">waited</span>
        <span className="contrib-track"><i className="is-wait" style={{ width: `${w * 100}%` }} /></span>
      </div>
    </div>
  )
}
