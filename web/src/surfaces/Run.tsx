import { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, Waypoints, ListOrdered, X } from 'lucide-react'
import { api } from '../lib/api'
import type { Run as RunT } from '../lib/types'
import './run.css'

const fmt = (n: number) => n.toLocaleString('en-IE')

/** What each agent reads, stated as inputs rather than description.
 *  `reads` is the evidence it will cite; `cites` is how many rows per referral,
 *  which is the number the counter is climbing towards. */
const AGENTS = [
  {
    key: 'scoring_urgency', name: 'Urgency', method: 'NEWS2, scale 1',
    reads: 'resp · SpO₂ · systolic · pulse · AVPU · temp',
    cites: '6 rows per referral, zeros included',
  },
  {
    key: 'scoring_capacity', name: 'Capacity', method: 'ward + clinic pressure',
    reads: 'primary ward bed status · latest clinic session',
    cites: '2 rows per referral, shared across the specialty',
  },
  {
    key: 'ranking', name: 'Coordinator', method: 'α·urgency + (1−α)·wait',
    reads: 'both scores · CPC band · target breach · referral date',
    cites: 'one ordered list, 5 rules tested per referral',
  },
] as const

/** The run, as an overlay rather than a destination.
 *
 *  It used to be a nav item -- a verb sitting between two nouns -- on a page
 *  that was 80% empty until someone pressed the one button on it. Running is an
 *  action, so it is a top-bar CTA that opens this, and the surface it resolves
 *  into is the graph it just built.
 *
 *  The bar counts rows committed to agent.agent_scores, polled from the same
 *  endpoint the coordinator reads. It cannot advance unless work happened, and
 *  it never interpolates between polls: it steps when data arrives.
 */
export function Run({ hospital, date, runnable, onClose, onSeeGraph, onSeeList }: {
  hospital: string; date: string; runnable: string | null
  onClose: () => void; onSeeGraph: () => void; onSeeList: () => void
}) {
  // Evidence is date-blind: GET /referrals/{h}/{pw}/context takes no date and
  // returns the most recent observation whichever day is asked about. Scoring
  // an older day would cite readings taken after it, so only the newest day
  // holding data can honestly be ranked.
  const rankable = runnable == null || date === runnable
  const [run, setRun] = useState<RunT | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const timer = useRef<number | null>(null)
  const still = useReducedMotion()
  const qc = useQueryClient()

  const cohort = useQuery({
    queryKey: ['cohort', hospital, date], queryFn: () => api.cohort(hospital, date),
  })
  const n = cohort.data?.referrals.length ?? 0

  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current) }, [])
  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape' && !busy) onClose() }
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [busy, onClose])

  async function start() {
    setErr(null); setBusy(true); setRun(null)
    try {
      const { run_id } = await api.startRun(hospital, date)
      timer.current = window.setInterval(async () => {
        try {
          const r = await api.run(run_id)
          setRun(r)
          if (r.status === 'done' || r.status === 'failed') {
            if (timer.current) window.clearInterval(timer.current)
            setBusy(false)
            if (r.status === 'done') {
              qc.invalidateQueries({ queryKey: ['decision', hospital, date] })
              qc.invalidateQueries({ queryKey: ['overrides', hospital, date] })
              qc.invalidateQueries({ queryKey: ['health'] })
            }
          }
        } catch { /* a dropped poll is not a failed run */ }
      }, 700)
    } catch (e) {
      setErr(String(e)); setBusy(false)
    }
  }

  const pct = run && run.total ? (run.scored / run.total) * 100 : 0
  const phaseIdx = run ? AGENTS.findIndex((p) => p.key === run.status) : -1
  const done = run?.status === 'done'
  const committed = (k: string) =>
    k === 'scoring_urgency' ? run?.urgency_scored ?? 0
      : k === 'scoring_capacity' ? run?.capacity_scored ?? 0
        : run?.ranked ?? 0

  return (
    <div className="runlay" data-surface="dark" role="dialog" aria-modal="true"
         aria-label="Run the agents">
      <div className="runlay-head">
        <div className="runlay-t">
          <span className="lab">Agent run</span>
          <h1>{hospital} · {new Date(date).toLocaleDateString('en-IE',
            { day: 'numeric', month: 'long', year: 'numeric' })}</h1>
        </div>
        <button className="runlay-x" onClick={onClose} disabled={busy}
                aria-label="Close">
          <X size={18} strokeWidth={1.75} />
        </button>
      </div>

      <div className={"runlay-body" + (run ? "" : " is-idle")}>
        {!rankable ? (
          <div className="run-locked">
            <strong>This day can be read, but not scored.</strong>
            <p>
              The evidence call carries no date: it returns the most recent observation on
              record whichever day you ask about. Scoring{' '}
              {new Date(date).toLocaleDateString('en-IE', { day: 'numeric', month: 'long' })}{' '}
              would cite readings taken after it. Runs happen on{' '}
              {runnable && new Date(runnable).toLocaleDateString('en-IE',
                { day: 'numeric', month: 'long', year: 'numeric' })}, the newest day holding data.
            </p>
          </div>
        ) : (
          <>
            {/* Pre-run is a readout of what is about to happen on what data,
                not a paragraph about agents. */}
            <div className="run-plan">
              <Readout k="cohort" v={fmt(n)} u="referrals" />
              <Readout k="agents" v="2" u="per referral" />
              <Readout k="scores" v={fmt(n * 2)} u="to commit" />
              <Readout k="citations" v={fmt(n * 8)} u="at 8 per referral" />
              <Readout k="alpha range" v="0.50–0.90" u="set by scarcity" />
              <Readout k="direction" v="pressure" u="ADR-007" />
            </div>

            <ol className="lanes">
              {AGENTS.map((p, i) => {
                const state = done || phaseIdx > i ? 'done' : phaseIdx === i ? 'live' : 'todo'
                const c = committed(p.key)
                const denom = p.key === 'ranking' ? n : n
                return (
                  <li key={p.key} className={'lane is-' + state}>
                    <div className="lane-bar">
                      <motion.i
                        animate={{ width: `${denom ? Math.min(100, (c / denom) * 100) : 0}%` }}
                        transition={still ? { duration: 0 } : { duration: 0.2, ease: 'linear' }} />
                    </div>
                    <div className="lane-id">
                      <span className="lane-n">{p.name}</span>
                      <span className="lane-m num">{p.method}</span>
                    </div>
                    <div className="lane-reads">
                      <span className="lane-r">{p.reads}</span>
                      <span className="lane-c">{p.cites}</span>
                    </div>
                    <div className="lane-count num">
                      {state === 'todo' ? <span className="lane-idle">queued</span>
                        : <><strong>{fmt(c)}</strong><span className="lane-of">
                          /{fmt(denom)} {p.key === 'ranking' ? 'placed' : 'committed'}</span></>}
                    </div>
                  </li>
                )
              })}
            </ol>

            {run && (
              <div className="run-total">
                <div className="run-bar">
                  <motion.i animate={{ width: `${pct}%` }}
                    transition={still ? { duration: 0 } : { duration: 0.2, ease: 'linear' }} />
                </div>
                <div className="run-total-t num">
                  <motion.span key={run.scored} className="run-n"
                    initial={still ? false : { opacity: 0.5 }} animate={{ opacity: 1 }}
                    transition={{ duration: 0.14 }}>{fmt(run.scored)}</motion.span>
                  <span className="run-of"> / {fmt(run.total)} rows in agent.agent_scores</span>
                  <span className="run-id">{run.run_id}</span>
                </div>
              </div>
            )}

            {err && <div className="err">{err}</div>}
            {run?.status === 'failed' && (
              <div className="err"><strong>The run failed.</strong>{' '}
                <span className="muted">{run.error}</span></div>
            )}

            {done && run && (
              <div className="run-done">
                <div className="run-done-nums">
                  <Readout k="placed" v={fmt(run.ranked)} u="in the order" big />
                  <Readout k="outside" v={fmt(run.refused_paediatric)} u="paediatric, not scored" />
                  <Readout k="alpha" v={(run.alpha ?? 0).toFixed(3)} u="weight on urgency" big />
                  <Readout k="scarcity" v={(run.scarcity ?? 0).toFixed(3)} u="mean ward+clinic pressure" />
                </div>
                <p className="run-done-p measure">
                  The <strong className="num">{fmt(run.refused_paediatric)}</strong> outside are
                  paediatric referrals. NEWS2 is validated in adults, so the agent refuses them
                  rather than scoring a child on an adult scale — a statement about coverage,
                  not a low position.
                </p>
                <div className="run-go">
                  <button className="cta" onClick={onSeeGraph}>
                    <Waypoints size={14} strokeWidth={2} aria-hidden />
                    See what it cited
                  </button>
                  <button className="cta is-ghost" onClick={onSeeList}>
                    <ListOrdered size={14} strokeWidth={2} aria-hidden />
                    See the order
                  </button>
                </div>
              </div>
            )}

            {!run && (
              <button className="run-start" onClick={start} disabled={busy}>
                <Play size={16} strokeWidth={2.25} fill="currentColor" aria-hidden />
                {busy ? 'Starting…' : `Score ${fmt(n)} referrals`}
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function Readout({ k, v, u, big }: { k: string; v: string; u: string; big?: boolean }) {
  return (
    <div className={'readout' + (big ? ' is-big' : '')}>
      <div className="lab">{k}</div>
      <div className="readout-v num">{v}</div>
      <div className="readout-u">{u}</div>
    </div>
  )
}
