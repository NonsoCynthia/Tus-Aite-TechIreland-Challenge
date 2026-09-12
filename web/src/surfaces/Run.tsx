import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, Waypoints, ListOrdered, X } from 'lucide-react'
import { api } from '../lib/api'
import { crtDays } from '../lib/ref'
import { sevBreach, sevWaitRatio } from '../lib/severity'
import { SevChip } from '../components/Severity'
import type { CohortReferral, Reference, Run as RunT } from '../lib/types'
import './run.css'

const fmt = (n: number) => n.toLocaleString('en-IE')

/** Stroke weight is a role: 1.75 chrome, 2.25 signal. Size comes from --icon /
 *  --icon-sm through .ico / .ico-s in app.css. */
const CHROME = 1.75
const SIGNAL = 2.25

/** The state the run is about to change, counted from the cohort itself.
 *
 *  A breach count is of the referrals that HAVE a target, never of the whole
 *  cohort: Routine and Uncategorised have none. Thresholds come from
 *  core.ref_codes via crtDays(), never from this file. */
function cohortBefore(rows: CohortReferral[], ref: Reference | undefined) {
  let withTarget = 0, past = 0, worst = 0, longest = 0
  for (const r of rows) {
    const wait = r.adjusted_wait_days ?? 0
    if (wait > longest) longest = wait
    const target = crtDays(ref, r.cpc) ?? r.crt_threshold_days
    if (target == null || target <= 0) continue
    withTarget += 1
    const ratio = wait / target
    if (ratio > 1) { past += 1; if (ratio > worst) worst = ratio }
  }
  return { n: rows.length, withTarget, noTarget: rows.length - withTarget, past, worst, longest }
}

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
    cites: 'one ordered list, 2-3 rules tested per referral',
  },
] as const

/** The run, as an overlay rather than a destination.
 *
 *  The bar counts rows committed to agent.agent_scores, polled from the same
 *  endpoint the coordinator reads. It never interpolates between polls, so it
 *  cannot advance unless work happened. */
export function Run({ hospital, name, date, runnable, onClose, onSeeGraph, onSeeList }: {
  hospital: string; name: string; date: string; runnable: string | null
  onClose: () => void; onSeeGraph: () => void; onSeeList: () => void
}) {
  // Evidence is date-blind: /referrals/{h}/{pw}/context takes no date and returns
  // the newest observation, so scoring an older day would cite readings taken
  // after it. Only the newest day holding data can be ranked.
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
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  // the same key App uses, so this reads the cache rather than asking again
  const ref = useQuery({ queryKey: ['reference'], queryFn: api.reference, staleTime: Infinity })
  const n = cohort.data?.referrals.length ?? 0
  const before = cohortBefore(cohort.data?.referrals ?? [], ref.data)

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
        <div className="runlay-head-in">
        <div className="runlay-t">
          <span className="lab">Agent run</span>
          <h1>{name} · {new Date(date).toLocaleDateString('en-IE',
            { day: 'numeric', month: 'long', year: 'numeric' })}</h1>
        </div>
        <button className="runlay-x" onClick={onClose} disabled={busy}
                aria-label="Close">
          <X className="ico" strokeWidth={CHROME} />
        </button>
        </div>
      </div>

      <div className="runlay-body">
        {!rankable ? (
          <div className="run-locked">
            <strong>This day can be read, but not scored.</strong>
            <p>
              The evidence call carries no date and returns the newest observation on record, so
              scoring{' '}
              {new Date(date).toLocaleDateString('en-IE', { day: 'numeric', month: 'long' })}{' '}
              would cite readings taken after it. Runs happen on{' '}
              {runnable && new Date(runnable).toLocaleDateString('en-IE',
                { day: 'numeric', month: 'long', year: 'numeric' })}, the newest day holding data.
            </p>
          </div>
        ) : (
          <>
            {/* What the run will CHANGE: the cohort as it stands on the left,
                what will be true of it on the right. Every figure on the left is
                counted from the cohort payload. It leaves once the run starts. */}
            <AnimatePresence initial={false}>
              {!run && (
                <motion.div className="run-ba" key="ba"
                            exit={{ opacity: 0 }}
                            transition={{ duration: still ? 0 : 0.2 }}>
                  <section className="run-ba-c">
                    <span className="lab">Right now, before the run</span>
                    {cohort.isError ? (
                      <ul className="run-ba-l">
                        <li>The cohort could not be read, so there is nothing to state about it.</li>
                      </ul>
                    ) : before.n === 0 ? (
                      <ul className="run-ba-l">
                        <li>{cohort.isLoading ? 'Reading the cohort…' : 'No referrals on this day.'}</li>
                      </ul>
                    ) : (
                      <ul className="run-ba-l">
                        {/* NOT "N people are waiting": this screen sees a LIST
                            of referral rows, not a population. Same wording as
                            Landing.tsx about the same cohort. Not a hedge -- no
                            disclaimer, no synthetic-data label. */}
                        <li>
                          <b className="num">{fmt(before.n)}</b> referrals are on this list. The
                          longest has waited <b className="num">{fmt(before.longest)}</b> days.
                        </li>
                        <li>
                          <b className="num">{fmt(before.withTarget)}</b> of them have a target
                          date. The other <b className="num">{fmt(before.noTarget)}</b> are Routine
                          or Uncategorised and have no target at all, so nothing in those groups
                          can be late.
                        </li>
                        <li>
                          {before.past > 0 ? (
                            <>
                              <SevChip sev={sevBreach(false)}>
                                <b className="num">{fmt(before.past)}</b> past target
                              </SevChip>{' '}
                              of that <b className="num">{fmt(before.withTarget)}</b>, and the
                              worst is{' '}
                              <SevChip sev={sevWaitRatio(before.worst)}>
                                <b className="num">{before.worst.toFixed(1)}x</b> over
                              </SevChip>.
                            </>
                          ) : (
                            <>None of the <b className="num">{fmt(before.withTarget)}</b> with a
                            target is past it.</>
                          )}
                        </li>
                        <li>
                          Nobody holds a position. No score, no citation and no rule check exists
                          for any of them yet.
                        </li>
                      </ul>
                    )}
                  </section>
                  <section className="run-ba-c">
                    <span className="lab">After it</span>
                    <ul className="run-ba-l">
                      <li>
                        One order, built inside each CPC category and never across one.
                      </li>
                      <li>
                        Inside a category, past target comes first and priority decides the rest: a
                        breach is a tier above a score, not a bigger number.
                      </li>
                      <li>
                        Every position carries the evidence it cited, up to{' '}
                        <b className="num">8</b> rows per referral: six vitals and two capacity.
                      </li>
                      <li>
                        Two to three rules tested per referral, each with its result on the record.
                      </li>
                      <li>
                        Paediatric referrals are refused rather than scored. NEWS2 is validated in
                        adults, and a refusal is a statement about coverage.
                      </li>
                    </ul>
                  </section>
                </motion.div>
              )}
            </AnimatePresence>

            {/* the instrument values: what is about to happen, on what data */}
            <div className="run-plan">
              <Readout k="cohort" v={fmt(n)} u="referrals" />
              <Readout k="agents" v="2" u="per referral" />
              <Readout k="scores" v={fmt(n * 2)} u="at most, 2 per referral" />
              <Readout k="citations" v={fmt(n * 8)} u="at most, 8 per referral" />
              <Readout k="alpha range" v="0.50–0.90" u="set by scarcity" />
              <Readout k="direction" v={health.data?.capacity_direction ?? "…"} u="ADR-007" />
            </div>

            <ol className="lanes" aria-label="Agent progress">
              {AGENTS.map((p, i) => {
                const state = done || phaseIdx > i ? 'done' : phaseIdx === i ? 'live' : 'todo'
                const c = committed(p.key)
                // Capacity scores everyone; urgency refuses paediatric specialties
                // and the coordinator places only what urgency scored, so those two
                // lanes can never reach the cohort size. The refusal count arrives
                // with the run, so until then the denominator is the cohort.
                const refused = run?.refused_paediatric ?? 0
                const denom = p.key === 'scoring_capacity' ? n : Math.max(1, n - refused)
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
                          /{fmt(denom)} {p.key === 'ranking' ? 'placed' : 'committed'}
                          {refused > 0 && p.key !== 'scoring_capacity' &&
                            <> · {fmt(refused)} refused</>}</span></>}
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
                <div className="run-total-t num" role="status" aria-live="polite">
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
                {before.n > 0 && (
                  <p className="run-done-p measure">
                    Before this run, <strong className="num">{fmt(before.past)}</strong> of the{' '}
                    <strong className="num">{fmt(before.withTarget)}</strong> referrals with a
                    target were past it, and none held a position.{' '}
                    <strong className="num">{fmt(run.ranked)}</strong> hold one now, inside their
                    own category, past target first, each carrying what it cited.
                  </p>
                )}
                {/* No count here: the "outside" readout above is it. */}
                <p className="run-done-p measure">
                  NEWS2 is validated in adults, so the agent refuses paediatric referrals rather
                  than scoring a child on an adult scale: a coverage statement, not a low
                  position.
                </p>
                <div className="run-go">
                  <button className="cta" onClick={onSeeGraph}>
                    <Waypoints className="ico-s" strokeWidth={CHROME} aria-hidden />
                    See what it cited
                  </button>
                  <button className="cta is-ghost" onClick={onSeeList}>
                    <ListOrdered className="ico-s" strokeWidth={CHROME} aria-hidden />
                    See the order
                  </button>
                </div>
              </div>
            )}

            {!run && (
              <button className="run-start" onClick={start} disabled={busy}>
                <Play className="ico" strokeWidth={SIGNAL} fill="currentColor" aria-hidden />
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
