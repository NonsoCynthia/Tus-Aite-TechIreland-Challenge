import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from './lib/api'
import { Mark } from './components/Mark'
import { Overview } from './surfaces/Overview'
import { List } from './surfaces/List'
import { Patient } from './surfaces/Patient'
import { Run } from './surfaces/Run'
import { Landing } from './surfaces/Landing'

export type Surface = 'landing' | 'overview' | 'run' | 'list'

const HOSPITALS = [
  { hipe: '9001', name: "St Brendan's University Hospital" },
  { hipe: '9002', name: 'Kilbrannan Regional Hospital' },
]
// Hospital-days are DISCOVERED, never hardcoded: a batch loaded while the
// service is up must appear in the selector without a frontend change.

export function App() {
  const [hospital, setHospital] = useState('9001')
  const [date, setDate] = useState<string | null>(null)
  const [surface, setSurface] = useState<Surface>('landing')
  const [patient, setPatient] = useState<string | null>(null)
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
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

  if (!date || !days.data) {
    return (
      <div className="boot">
        <Mark size={34} draw />
        <span>{days.error ? 'Cannot reach the service.' : 'Reading the waiting lists\u2026'}</span>
      </div>
    )
  }
  const runnable = days.data.runnable
  const name = HOSPITALS.find((h) => h.hipe === hospital)?.name ?? hospital

  if (surface === 'landing') {
    return <Landing hospital={hospital} date={date} name={name}
                    onEnter={() => setSurface('overview')} />
  }

  return (
    <div className="app">
      <header className="topbar">
        <button className="brand-lockup" onClick={() => setSurface('landing')} aria-label="Back to the start">
          <Mark size={30} />
          <div className="brand-text">
            <div className="brand-word">Tús Áite</div>
            <div className="brand-sub">decision support</div>
          </div>
        </button>

        <div className="scope">
          <select className="picker" value={hospital} onChange={(e) => setHospital(e.target.value)}
                  aria-label="Hospital">
            {HOSPITALS.map((h) => <option key={h.hipe} value={h.hipe}>{h.name}</option>)}
          </select>
          <select className="picker num" value={date} onChange={(e) => setDate(e.target.value)}
                  aria-label="Hospital-day">
            {days.data.days.map((d) => (
              <option key={d.date} value={d.date}>
                {new Date(d.date).toLocaleDateString('en-IE', { day: 'numeric', month: 'long', year: 'numeric' })}
                {' · '}{d.referrals} waiting
                {d.date === runnable ? '' : ' · view only'}
              </option>
            ))}
          </select>
        </div>

        <nav className="surfaces" aria-label="Views">
          {(['overview', 'run', 'list'] as Surface[]).map((k) => (
            <button key={k} className={'surf' + (surface === k ? ' is-on' : '')}
                    onClick={() => { setSurface(k); setPatient(null) }} aria-current={surface === k}>
              {k === 'overview' ? 'Overview' : k === 'run' ? 'Run the agents' : 'The order'}
            </button>
          ))}
        </nav>

        <div className="status">
          <span className={'dot ' + (health.data?.status === 'ok' ? 'ok' : 'bad')} />
          <span className="status-txt">
            {health.data ? `service ${health.data.status}` : 'connecting'}
          </span>
        </div>
      </header>

      <main>
        {surface === 'overview' && <Overview hospital={hospital} date={date} name={name} />}
        {surface === 'run' && (
          <Run hospital={hospital} date={date} runnable={runnable}
               onDone={() => setSurface('list')} />
        )}
        {surface === 'list' && (patient
          ? <Patient hospital={hospital} date={date} pathway={patient} onBack={() => setPatient(null)} />
          : <List hospital={hospital} date={date} onOpen={setPatient} />)}
      </main>
    </div>
  )
}
