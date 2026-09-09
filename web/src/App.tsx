import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from './lib/api'
import { Mark } from './components/Mark'
import { Overview } from './surfaces/Overview'
import { List } from './surfaces/List'
import { Patient } from './surfaces/Patient'
import { Run } from './surfaces/Run'

export type Surface = 'overview' | 'run' | 'list'

const HOSPITALS = [
  { hipe: '9001', name: "St Brendan's University Hospital" },
  { hipe: '9002', name: 'Kilbrannan Regional Hospital' },
]
/** 14 days loaded, 2026-08-17..08-30. Only the latest is honest to RANK: the
 *  evidence call carries no date and returns the most recent observation
 *  whichever day you ask for, so scoring an earlier day cites later readings. */
export const DATES = Array.from({ length: 14 }, (_, i) => `2026-08-${17 + i}`)
export const RUNNABLE_DATE = DATES[DATES.length - 1]

export function App() {
  const [hospital, setHospital] = useState('9001')
  const [date, setDate] = useState(RUNNABLE_DATE)
  const [surface, setSurface] = useState<Surface>('overview')
  const [patient, setPatient] = useState<string | null>(null)
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  const name = HOSPITALS.find((h) => h.hipe === hospital)?.name ?? hospital

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand-lockup">
          <Mark size={30} />
          <div className="brand-text">
            <div className="brand-word">Tús Áite</div>
            <div className="brand-sub">decision support</div>
          </div>
        </div>

        <div className="scope">
          <select className="picker" value={hospital} onChange={(e) => setHospital(e.target.value)}
                  aria-label="Hospital">
            {HOSPITALS.map((h) => <option key={h.hipe} value={h.hipe}>{h.name}</option>)}
          </select>
          <select className="picker num" value={date} onChange={(e) => setDate(e.target.value)}
                  aria-label="Hospital-day">
            {DATES.map((d) => (
              <option key={d} value={d}>
                {new Date(d).toLocaleDateString('en-IE', { day: 'numeric', month: 'long', year: 'numeric' })}
                {d === RUNNABLE_DATE ? '' : ' · view only'}
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
          <Run hospital={hospital} date={date} onDone={() => setSurface('list')} />
        )}
        {surface === 'list' && (patient
          ? <Patient hospital={hospital} date={date} pathway={patient} onBack={() => setPatient(null)} />
          : <List hospital={hospital} date={date} onOpen={setPatient} />)}
      </main>
    </div>
  )
}
