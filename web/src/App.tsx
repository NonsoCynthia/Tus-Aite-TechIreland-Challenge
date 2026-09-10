import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Building2, CalendarDays, Gauge, ListOrdered, Lock, Play, RefreshCw, ScrollText, Waypoints,
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

/** What GET (and POST .../refresh) hand back for a hospital's days. Taken from
 *  the client rather than restated, so a change to the endpoint's shape is a
 *  type error here rather than a silent one. */
type Days = Awaited<ReturnType<typeof api.hospitalDays>>

const dayLong = (d: string) =>
  new Date(d).toLocaleDateString('en-IE', { day: 'numeric', month: 'long', year: 'numeric' })
const dayShort = (d: string) =>
  new Date(d).toLocaleDateString('en-IE', { day: 'numeric', month: 'long' })
const dayCount = (k: number) => `${k} ${k === 1 ? 'day holds' : 'days hold'} a cohort`

/** Stroke weight is a ROLE, not a taste: 1.75 for chrome (a nav item, a picker
 *  adornment, a close button), 2.25 for signal (the thing that starts work).
 *  Size comes from --icon / --icon-sm through .ico / .ico-s in app.css, so no
 *  pixel number is typed at a call site. */
const CHROME = 1.75
const SIGNAL = 2.25

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
  const [probing, setProbing] = useState(false)
  const [probeSaid, setProbeSaid] = useState<string | null>(null)

  const qc = useQueryClient()
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

  // a different hospital is a different question; the last answer is not about it
  useEffect(() => { setProbeSaid(null) }, [hospital])

  /** D3. The day selector is DISCOVERED, by probing a 60-day window, and the
   *  orchestrator caches the answer per hospital for the life of the process
   *  (orchestrator/app/main.py:120-165). So a batch loaded while the service is
   *  up cannot appear on its own: something has to clear that cache and probe
   *  again. POST /api/hospital-days/{h}/refresh does exactly that and has been
   *  implemented, and in api.ts, with no caller since it was written.
   *
   *  It reports what CHANGED rather than just finishing, because "I pressed it
   *  and nothing moved" is indistinguishable from "it did not work". */
  async function checkForNewData() {
    setProbing(true); setProbeSaid(null)
    const before = qc.getQueryData<Days>(['hospital-days', hospital])
    try {
      const fresh = (await api.refreshDays(hospital)) as Days
      // the POST returns the freshly probed answer, so it IS the query's data
      qc.setQueryData(['hospital-days', hospital], fresh)

      const was = before?.days.length ?? 0
      const now = fresh.days.length
      const newRunnable = fresh.runnable !== (before?.runnable ?? null)
      const newest = fresh.runnable ? dayShort(fresh.runnable) : 'none'

      if (now !== was || newRunnable) {
        // every cohort, decision, operations and overrides query is keyed
        // [name, hospital, date]; the day list itself was just set from the
        // response and does not need re-probing.
        qc.invalidateQueries({
          predicate: (q) => q.queryKey[0] !== 'hospital-days' && q.queryKey[1] === hospital,
        })
        qc.invalidateQueries({ queryKey: ['health'] })
      }

      setProbeSaid(
        now === was && !newRunnable
          ? `No new data. ${dayCount(now)}, the newest ${newest}.`
          : `${dayCount(now)}, where ${was} did before. ` + (newRunnable
            ? `${newest} is now the newest, so it is the day that can be scored.`
            : `${newest} is still the newest, so it is still the day that can be scored.`),
      )
    } catch {
      setProbeSaid('Could not reach the service to ask.')
    }
    setProbing(false)
  }

  const dec = useQuery<Decision>({
    queryKey: ['decision', hospital, date],
    queryFn: () => api.decision(hospital, date!),
    enabled: !!date, retry: false,
  })

  if (!date || !days.data) {
    return (
      <div className="boot" data-surface="dark">
        {/* height 26 put the WORDMARK CAP HEIGHT at 26 x 266/676 = 10.2px, under
            the kit's 13px floor, on the first screen of the demo. 40px puts it
            at 15.7px. The lockup carries no descriptor of its own, and the kit
            requires the words in a clinical setting, so they travel below it. */}
        <div className="boot-brand">
          <img className="boot-mark" src="/brand/tus-aite-lockup-white.png" alt="Tús Áite" />
          <span className="boot-descriptor">decision support</span>
        </div>
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
          {/* F1/F2. The lockup is 2552x676 but its INK is 2209x502, so a CSS
              height renders only 74% of it as artwork and the wordmark's cap
              height is 266/676 of that height. At the old 22px the cap was
              8.7px, a third under the kit's 13px floor, and the Jost ExtraLight
              stems resampled to 0.39 CSS px and antialiased away. 40px puts the
              cap at 15.7px and the stems at 0.71px, and is the largest size the
              kit's own clear-space rule allows: 151px of lockup plus a cap
              height of gutter on each side is 182px of the 188px the rail has.

              Below 1440 the rail collapses to a 48px content box, where no
              amount of scaling saves a wordmark. The kit says so itself: "below
              13px cap height, drop the wordmark and use the mark alone." The
              <source> hands over the VECTOR mark, which is what the same rule
              points at, and app.css sizes it to 24px. */}
          <picture>
            <source media="(max-width: 1439px)" srcSet="/brand/tus-aite-mark-white.svg" />
            <img src="/brand/tus-aite-lockup-white.png" alt="Tús Áite" />
          </picture>
          {/* the kit: "in any clinical setting the words decision support
              travel with the mark". True at BOTH sizes: collapsed, they wrap to
              two lines under the mark rather than going away. */}
          <span className="rail-descriptor">decision support</span>
        </button>

        <nav className="rail-nav" aria-label="Views">
          {NAV.map((g) => (
            <div className="rail-group" key={g.group}>
              <div className="lab rail-lab">{g.group}</div>
              {g.items.map(({ key, label, icon: Icon }) => (
                <button key={key} className={'rail-item' + (surface === key ? ' is-on' : '')}
                        onClick={() => go(key)} aria-current={surface === key}>
                  <Icon className="ico" strokeWidth={CHROME} aria-hidden />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="rail-foot">
          <SystemStatus health={health.data} />
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="scope">
            <label className="picker-wrap">
              <Building2 className="ico-s" strokeWidth={CHROME} aria-hidden />
              <select className="picker" value={hospital} aria-label="Hospital"
                      onChange={(e) => { setHospital(e.target.value); setPatient(null) }}>
                {HOSPITALS.map((h) => <option key={h.hipe} value={h.hipe}>{h.name}</option>)}
              </select>
            </label>
            <label className="picker-wrap">
              <CalendarDays className="ico-s" strokeWidth={CHROME} aria-hidden />
              <select className="picker num" value={date} aria-label="Hospital-day"
                      onChange={(e) => { setDate(e.target.value); setPatient(null) }}>
                {days.data.days.map((d) => (
                  <option key={d.date} value={d.date}>
                    {dayLong(d.date)}
                    {/* the same noun as the landing: this counts ROWS on a
                        list, which is all the service can see, not people in a
                        room. One word, and it is no longer a headcount. */}
                    {' · '}{d.referrals} referrals
                    {d.date === runnable ? '' : ' · view only'}
                  </option>
                ))}
              </select>
            </label>

            {/* D3. The selector shows what was discovered when this process
                first asked. This is how you ask again. */}
            <button className="probe" onClick={checkForNewData}
                    disabled={probing} aria-busy={probing}>
              <RefreshCw className="ico-s" strokeWidth={CHROME} aria-hidden />
              {probing ? 'Looking…' : 'Check for new data'}
            </button>
            {probeSaid && (
              <span className="probe-said" role="status" aria-live="polite">{probeSaid}</span>
            )}
          </div>

          <div className="topbar-right">
            {dec.data && <RunPill decision={dec.data} />}
            {rankable ? (
              <button className="cta" onClick={() => setRunOpen(true)}>
                <Play className="ico-s" strokeWidth={SIGNAL} fill="currentColor" aria-hidden />
                {dec.data ? 'Run again' : 'Run the agents'}
              </button>
            ) : (
              // Not a disabled button. A disabled control cannot be focused and
              // its title never shows, so the reason has to be on the surface.
              // D4. The old string was "Read only - scoring happens on 30
              // August", which is true on every view-only day and reads as
              // though 30 August were the day you had selected. Both days are
              // named now, and each is said to be a different thing.
              <span className="cta-locked">
                <Lock className="ico-s" strokeWidth={CHROME} aria-hidden />
                <span>
                  Viewing <b className="num">{dayShort(date)}</b>, which can be read but
                  not scored.{runnable && <> Scoring runs on{' '}
                    <b className="num">{dayShort(runnable)}</b>, the newest day holding data.</>}
                </span>
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
        <Run hospital={hospital} name={name} date={date} runnable={runnable}
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
