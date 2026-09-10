import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Building2, CalendarDays, Gauge, ListOrdered, Lock, Play, ScrollText, Waypoints,
} from 'lucide-react'
import { api } from './lib/api'
import { Overview } from './surfaces/Overview'
import { List } from './surfaces/List'
import { Patient } from './surfaces/Patient'
import { Run } from './surfaces/Run'
import { Landing } from './surfaces/Landing'
import { CohortGraphSurface } from './surfaces/CohortGraph'
import { DecisionRecord } from './surfaces/DecisionRecord'
import type { Decision } from './lib/types'

export type Surface = 'overview' | 'list' | 'graph' | 'record'

const HOSPITALS = [
  { hipe: '9001', name: "St Brendan's University Hospital" },
  { hipe: '9002', name: 'Kilbrannan Regional Hospital' },
]
// Hospital-days are DISCOVERED, never hardcoded: a batch loaded while the
// service is up must appear in the selector without a frontend change.

/** The rail, grouped.
 *
 *  "Run the agents" used to sit here as a verb between two nouns, which read as
 *  a place rather than an action and left the graph with no home. Running is now
 *  a primary action in the top bar; the rail holds only destinations. */
const NAV: Array<{ group: string; items: Array<{ key: Surface; label: string; icon: typeof Gauge }> }> = [
  { group: 'Hospital', items: [{ key: 'overview', label: 'Overview', icon: Gauge }] },
  { group: 'The list', items: [{ key: 'list', label: 'Ranked order', icon: ListOrdered }] },
  {
    group: 'Evidence',
    items: [
      { key: 'graph', label: 'Knowledge graph', icon: Waypoints },
      { key: 'record', label: 'Decision record', icon: ScrollText },
    ],
  },
]

export function App() {
  const [hospital, setHospital] = useState('9001')
  const [date, setDate] = useState<string | null>(null)
  const [entered, setEntered] = useState(false)
  const [surface, setSurface] = useState<Surface>('overview')
  const [patient, setPatient] = useState<string | null>(null)
  const [runOpen, setRunOpen] = useState(false)

  const health = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 20_000 })
  // seed data: fetched once for the life of the tab, never refetched
  const ref = useQuery({ queryKey: ['reference'], queryFn: api.reference, staleTime: Infinity })
  const days = useQuery({
    queryKey: ['hospital-days', hospital],
    queryFn: () => api.hospitalDays(hospital),
    staleTime: 5 * 60_000,
  })
  // default to the newest day that actually holds data, whatever that turns
  // out to be, and follow it if the hospital changes
  useEffect(() => {
    const r = days.data?.runnable
    if (r && (date === null || !days.data?.days.some((d) => d.date === date))) setDate(r)
  }, [days.data, date])

  const dec = useQuery<Decision>({
    queryKey: ['decision', hospital, date],
    queryFn: () => api.decision(hospital, date!),
    enabled: !!date, retry: false,
  })

  if (!date || !days.data) {
    return (
      <div className="boot" data-surface="dark">
        <img src="/brand/tus-aite-lockup-white.png" alt="Tús Áite" height={26} />
        <span>{days.error ? 'Cannot reach the service.' : 'Reading the waiting lists…'}</span>
      </div>
    )
  }

  const runnable = days.data.runnable
  const name = HOSPITALS.find((h) => h.hipe === hospital)?.name ?? hospital
  const rankable = runnable == null || date === runnable

  if (!entered) {
    return (
      <Landing hospital={hospital} date={date} name={name} hospitals={HOSPITALS}
               onHospital={setHospital} onEnter={() => setEntered(true)} />
    )
  }

  const go = (k: Surface) => { setSurface(k); setPatient(null) }

  return (
    <div className="app">
      <aside className="rail" data-surface="dark">
        <button className="rail-brand" onClick={() => setEntered(false)} aria-label="Back to the start">
          <img src="/brand/tus-aite-lockup-white.png" alt="Tús Áite" />
          {/* the kit: "in any clinical setting the words decision support
              travel with the mark" -- as a descriptor behind a hairline, not as
              type competing with the wordmark */}
          <span className="rail-descriptor">decision support</span>
        </button>

        <nav className="rail-nav" aria-label="Views">
          {NAV.map((g) => (
            <div className="rail-group" key={g.group}>
              <div className="lab rail-lab">{g.group}</div>
              {g.items.map(({ key, label, icon: Icon }) => (
                <button key={key} className={'rail-item' + (surface === key ? ' is-on' : '')}
                        onClick={() => go(key)} aria-current={surface === key}>
                  <Icon size={16} strokeWidth={1.75} aria-hidden />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="rail-foot">
          {/* README feature 1: "labels every generated record as synthetic in
              the graph AND the UI". It appeared nowhere until now. */}
          <div className="synthetic">
            <span className="synthetic-dot" aria-hidden />
            Synthetic data · no real patient
          </div>
          <SystemStatus health={health.data} />
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="scope">
            <label className="picker-wrap">
              <Building2 size={15} strokeWidth={1.75} aria-hidden />
              <select className="picker" value={hospital} aria-label="Hospital"
                      onChange={(e) => { setHospital(e.target.value); setPatient(null) }}>
                {HOSPITALS.map((h) => <option key={h.hipe} value={h.hipe}>{h.name}</option>)}
              </select>
            </label>
            <label className="picker-wrap">
              <CalendarDays size={15} strokeWidth={1.75} aria-hidden />
              <select className="picker num" value={date} aria-label="Hospital-day"
                      onChange={(e) => { setDate(e.target.value); setPatient(null) }}>
                {days.data.days.map((d) => (
                  <option key={d.date} value={d.date}>
                    {new Date(d.date).toLocaleDateString('en-IE',
                      { day: 'numeric', month: 'long', year: 'numeric' })}
                    {' · '}{d.referrals} waiting
                    {d.date === runnable ? '' : ' · view only'}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="topbar-right">
            {dec.data && <RunPill decision={dec.data} />}
            {rankable ? (
              <button className="cta" onClick={() => setRunOpen(true)}>
                <Play size={14} strokeWidth={2.25} fill="currentColor" aria-hidden />
                {dec.data ? 'Run again' : 'Run the agents'}
              </button>
            ) : (
              // Not a disabled button. A disabled control cannot be focused and
              // its title never shows, so the reason has to be on the surface.
              <span className="cta-locked">
                <Lock size={13} strokeWidth={2} aria-hidden />
                Read only —{' '}
                {runnable && <>scoring happens on{' '}
                  {new Date(runnable).toLocaleDateString('en-IE',
                    { day: 'numeric', month: 'long' })}</>}
                <button className="cta-why" onClick={() => setRunOpen(true)}>why?</button>
              </span>
            )}
          </div>
        </header>

        <main className="content">
          {surface === 'overview' && (
            <Overview hospital={hospital} date={date} name={name}
                      reference={ref.data} onOpenList={() => go('list')} />
          )}
          {surface === 'list' && (patient
            ? <Patient hospital={hospital} date={date} pathway={patient}
                       reference={ref.data} onBack={() => setPatient(null)} />
            : <List hospital={hospital} date={date} reference={ref.data} onOpen={setPatient} />)}
          {surface === 'graph' && (
            <CohortGraphSurface hospital={hospital} date={date}
                                onOpenPatient={(pw) => { setPatient(pw); setSurface('list') }} />
          )}
          {surface === 'record' && (
            <DecisionRecord hospital={hospital} date={date} reference={ref.data} />
          )}
        </main>
      </div>

      {runOpen && (
        <Run hospital={hospital} date={date} runnable={runnable}
             onClose={() => setRunOpen(false)}
             onSeeGraph={() => { setRunOpen(false); go('graph') }}
             onSeeList={() => { setRunOpen(false); go('list') }} />
      )}
    </div>
  )
}


/** What the decision IS, kept in the chrome rather than repeated on every
 *  surface: which run produced the order on screen, how it is weighted, and how
 *  old it is. Alpha lives only here and in the orchestrator's memory -- it is
 *  not in agent.decision_rankings, so this pill is the only durable display of
 *  the number that produced the ranking. */
function RunPill({ decision }: { decision: Decision }) {
  const built = new Date(decision.built_at)
  const mins = Math.max(0, Math.round((Date.now() - built.getTime()) / 60_000))
  const age = mins < 1 ? 'just now' : mins < 60 ? `${mins}m ago` : `${Math.round(mins / 60)}h ago`
  return (
    <div className="runpill" title={`decision ${decision.decision_id}`}>
      <span className="runpill-id num">{decision.run_id.replace(/^run-/, '')}</span>
      <span className="runpill-sep" aria-hidden />
      <span className="runpill-a">
        urgency <strong className="num">{Math.round(decision.alpha * 100)}%</strong>
      </span>
      <span className="runpill-sep" aria-hidden />
      <span className="runpill-age num">{age}</span>
    </div>
  )
}

/** Three services, named. "service ok" said nothing about which service; the
 *  reference layer and the graph are separate connections that can fail
 *  independently, and a panel going quiet should be traceable from here. */
function SystemStatus({ health }: { health: Awaited<ReturnType<typeof api.health>> | undefined }) {
  const s = health?.sources
  const parts: Array<[string, boolean]> = [
    ['service', health?.status === 'ok'],
    ['records', s?.postgres === 'ok'],
    ['graph', s?.oxigraph === 'ok'],
  ]
  return (
    <div className="sysstat">
      {/* The state used to be carried ONLY by a 5px dot going from green to
          red, and the dot was aria-hidden -- so the one indicator telling a
          clinician whether the numbers on screen are current failed WCAG 2.2
          SC 1.4.1 outright. The word travels now, and the hues are off the
          reserved triage set. */}
      {parts.map(([k, up]) => (
        <span key={k} className={'sysstat-i' + (up ? ' is-up' : '')}>
          <i aria-hidden />{k}
          <b>{up ? 'ok' : 'down'}</b>
        </span>
      ))}
    </div>
  )
}
