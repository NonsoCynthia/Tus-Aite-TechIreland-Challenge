import { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'motion/react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { Run as RunT } from '../lib/types'

const fmt = (n: number) => n.toLocaleString('en-IE')

const PHASES = [
  { key: 'scoring_urgency',  agent: 'Urgency agent',  reads: 'six vital signs, per referral' },
  { key: 'scoring_capacity', agent: 'Capacity agent', reads: 'ward pressure and clinic booking' },
  { key: 'ranking',          agent: 'Coordinator',    reads: 'both scores, one ordered list' },
] as const

/** The run, shown honestly.
 *
 *  The bar counts rows committed to agent.agent_scores, polled from the same
 *  endpoint the coordinator reads. It cannot advance unless work happened, and
 *  it never interpolates between polls: it steps when data arrives.
 */
export function Run({ hospital, date, runnable, onDone }: {
  hospital: string; date: string; runnable: string | null; onDone: () => void
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

  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current) }, [])

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
            }
          }
        } catch { /* a dropped poll is not a failed run */ }
      }, 700)
    } catch (e) {
      setErr(String(e)); setBusy(false)
    }
  }

  const pct = run && run.total ? (run.scored / run.total) * 100 : 0
  const phaseIdx = run ? PHASES.findIndex((p) => p.key === run.status) : -1
  const done = run?.status === 'done'

  return (
    <div className="run-dark" data-surface="dark">
    <div className="pad">
      <div className="lede">
        <h1>Run the agents</h1>
        <p className="lede-p">
          Two agents score every referral, then the coordinator orders them. Nothing is
          precomputed: the bar below counts rows as they are committed, so it cannot move
          unless work is happening.
        </p>
      </div>

      <div className="run-panel">
        <div className="run-top">
          <button className="run-btn" onClick={start} disabled={busy || !rankable}>
            {busy ? 'Running…' : done ? 'Run again' : 'Run for this hospital-day'}
          </button>
          <div className="run-meta">
            <span className="num">{hospital}</span> ·{' '}
            <span className="num">{new Date(date).toLocaleDateString('en-IE',
              { day: 'numeric', month: 'long', year: 'numeric' })}</span>
            {run && <> · <span className="num run-id">{run.run_id}</span></>}
          </div>
        </div>

        {!rankable && (
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
        )}

        {err && <div className="err">{err}</div>}

        {run && (
          <>
            <div className="run-bar">
              <motion.i
                animate={{ width: `${pct}%` }}
                transition={still ? { duration: 0 } : { duration: 0.2, ease: 'linear' }}
              />
            </div>
            <div className="run-count">
              <motion.span key={run.scored} className="num run-n"
                initial={still ? false : { opacity: 0.55 }} animate={{ opacity: 1 }}
                transition={{ duration: 0.14 }}>{fmt(run.scored)}</motion.span>
              <span className="run-of num"> / {fmt(run.total)} scores committed</span>
              {run.cohort_size > 0 && (
                <span className="muted"> · {fmt(run.cohort_size)} referrals, each read twice</span>
              )}
            </div>

            <ol className="lanes">
              {PHASES.map((p, i) => {
                const state = done || (phaseIdx > i) ? 'done' : phaseIdx === i ? 'live' : 'todo'
                return (
                  <li key={p.key} className={'lane is-' + state}>
                    <i className="lane-dot" />
                    <span className="lane-a">{p.agent}</span>
                    <span className="lane-r">{p.reads}</span>
                    <span className="lane-s num">
                      {p.key === 'scoring_urgency' && run.urgency_scored > 0 && `${fmt(run.urgency_scored)} scored`}
                      {p.key === 'scoring_capacity' && run.capacity_scored > 0 && `${fmt(run.capacity_scored)} scored`}
                      {p.key === 'ranking' && run.ranked > 0 && `${fmt(run.ranked)} placed`}
                      {state === 'live' && !run.urgency_scored && 'working'}
                    </span>
                  </li>
                )
              })}
            </ol>

            {done && (
              <div className="run-done">
                <div className="run-done-h">
                  <span className="num">{fmt(run.ranked)}</span> placed ·{' '}
                  <span className="num">{fmt(run.refused_paediatric)}</span> outside the ranking ·{' '}
                  urgency weighted <span className="num">{Math.round((run.alpha ?? 0) * 100)}%</span>
                </div>
                <p className="run-done-p">
                  The <span className="num">{fmt(run.refused_paediatric)}</span> outside are
                  paediatric referrals. NEWS2 is validated in adults, so the agent refuses them
                  rather than scoring a child on an adult scale. That is a statement about
                  coverage, not a low position.
                </p>
                <button className="run-go" onClick={onDone}>See the order &rarr;</button>
              </div>
            )}

            {run.status === 'failed' && (
              <div className="err"><strong>The run failed.</strong> <span className="muted">{run.error}</span></div>
            )}
          </>
        )}
      </div>
    </div>
    </div>
  )
}
