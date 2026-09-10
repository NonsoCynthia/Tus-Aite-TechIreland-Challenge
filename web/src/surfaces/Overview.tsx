import { useQuery } from '@tanstack/react-query'
import {
  Activity, BedDouble, Building2, CalendarDays, Check, Clock, Gauge, Layers,
  Stethoscope, TrendingUp, TriangleAlert, Users,
} from 'lucide-react'
import { api, BANDS, bandOf } from '../lib/api'
import { crtDays, failed, ruleStatement, specialtyFull, specialtyName } from '../lib/ref'
import type { CohortReferral, Decision, Reference } from '../lib/types'
import './overview.css'

/* ---------------------------------------------------------------------------
   Constants that are CITED, not assumed. Everything else on this surface is
   counted at render time from a payload.
--------------------------------------------------------------------------- */

/** Safe-operating occupancy. Bagust, Place & Posnett, BMJ 1999;319:155-8. */
const SAFE_OCCUPANCY = 85

/** Colour is never the only channel: the GAR letter always resolves to a word. */
const GAR_WORD = { G: 'Green', A: 'Amber', R: 'Red' } as const

/** NTPF Outpatient Waiting List by Speciality, OpenData_OPNational02_2026.csv,
 *  snapshot 2026-07-30, 682,279 people over the 57 non-SDC specialties.
 *
 *  NTPF publishes the bands in months. The day boundaries are the generator's
 *  own — dataset/generator/generate.py:256 draws every wait from these exact
 *  cut points — so bucketing this hospital on 183/365/548 compares like with
 *  like rather than inventing a days-per-month constant. */
const NTPF_SNAPSHOT = '2026-07-30'
const NTPF_TOTAL = 682_279
const NTPF_BANDS = [
  { key: '0–6 months', lo: 0, hi: 183, share: 0.596263, n: 406_818 },
  { key: '6–12 months', lo: 183, hi: 365, share: 0.225673, n: 153_972 },
  { key: '12–18 months', lo: 365, hi: 548, share: 0.104321, n: 71_176 },
  { key: '18 months +', lo: 548, hi: Infinity, share: 0.073743, n: 50_313 },
] as const

/** dataset/out/referral_daily.csv: 70,022 rows, and `removal_date` is null in
 *  every one of them. The list in this dataset only ever accretes. */
const DAILY_ROWS = 70_022

/** Reading age, bucketed. The boundaries are the ones observation_age already
 *  reports against (a year, two years), extended downwards so the shape shows. */
const AGE_BUCKETS = [
  { key: 'under 3 months', lo: 0, hi: 90 },
  { key: '3–6 months', lo: 90, hi: 180 },
  { key: '6–12 months', lo: 180, hi: 365 },
  { key: '1–2 years', lo: 365, hi: 730 },
  { key: 'over 2 years', lo: 730, hi: Infinity },
] as const

/** Rules whose subject is the whole list, not one referral. Counting them per
 *  referral would imply 305 independent verdicts where there is one. */
const WHOLE_LIST = new Set(['RULE-ORDER', 'RULE-TIEBREAK'])

type Ops = Awaited<ReturnType<typeof api.operations>>
type Ward = Ops['wards'][number]
type Clinic = Ops['clinics'][number]
/** Only the four fields every panel here needs off a react-query result. */
type Q<T> = { isPending: boolean; isError: boolean; error: unknown; data: T | undefined }
type OpsQuery = Q<Ops>

const fmt = (n: number) => n.toLocaleString('en-IE')
const pct = (x: number, digits = 1) => `${(x * 100).toFixed(digits)}%`
const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IE', { day: 'numeric', month: 'short' })
const longDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IE', { day: 'numeric', month: 'long', year: 'numeric' })
const clockTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-IE', { hour: '2-digit', minute: '2-digit' })
/** Day of the month. The chart's lead line already names the month. */
const dayNum = (iso: string) => String(new Date(iso).getDate())

/** Upper-middle median, the convention the rest of the product already uses. */
const median = (xs: number[]) => {
  if (!xs.length) return 0
  const s = [...xs].sort((a, b) => a - b)
  return s[Math.floor(s.length / 2)]
}

/* ---------------------------------------------------------------------------
   Aggregation. Two figures are counted the honest way and never any other:
   a breach is of the referrals that HAVE a target, and the referrals with no
   target at all get their own count rather than a denominator to hide in.
--------------------------------------------------------------------------- */

function summarise(rows: CohortReferral[]) {
  const withTarget = rows.filter((r) => r.crt_threshold_days != null)
  const breached = withTarget.filter((r) => r.crt_breached === true)
  const waits = rows.map((r) => r.adjusted_wait_days ?? 0)
  const bands = new Map<string, number>()
  for (const r of rows) bands.set(bandOf(r.cpc), (bands.get(bandOf(r.cpc)) ?? 0) + 1)
  const wait = (d: { lo: number; hi: number }) =>
    waits.filter((w) => w >= d.lo && w < d.hi).length
  return {
    total: rows.length,
    withTarget: withTarget.length,
    noTarget: rows.length - withTarget.length,
    breached: breached.length,
    median: median(waits),
    longest: waits.length ? Math.max(...waits) : 0,
    bands,
    waitBands: NTPF_BANDS.map((b) => ({ ...b, here: wait(b) })),
    suspended: rows.filter((r) => r.currently_suspended === true).length,
    awaitingTriage: rows.filter((r) => r.triage_status !== 'triaged').length,
  }
}

type SpecRow = ReturnType<typeof bySpecialty>[number]

/** What the capacity agent computed, per SPECIALTY.
 *
 *  ward_pressure, clinic_pressure and capacity_score are identical for every
 *  referral inside a specialty and differ between specialties — verified on the
 *  live decision, and the reason `capacity_score` is documented in types.ts as
 *  "specialty-level, identical for every referral in a specialty". Reading one
 *  ranking's capacity_detail and calling it the hospital's figure would be
 *  wrong; so would drawing it against a person. It is drawn against a specialty.
 */
function agentCapacity(d: Decision | undefined) {
  const m = new Map<string, { ward: number | null; clinic: number | null; score: number }>()
  for (const r of d?.rankings ?? []) {
    if (m.has(r.specialty_hipe)) continue
    m.set(r.specialty_hipe, {
      ward: r.capacity_detail?.ward_pressure ?? null,
      clinic: r.capacity_detail?.clinic_pressure ?? null,
      score: r.capacity_score,
    })
  }
  return m
}

function bySpecialty(rows: CohortReferral[], clinics: Clinic[] | undefined) {
  const groups = new Map<string, CohortReferral[]>()
  for (const r of rows) {
    const g = groups.get(r.specialty_hipe) ?? []
    g.push(r)
    groups.set(r.specialty_hipe, g)
  }
  return [...groups.entries()]
    .map(([code, g]) => {
      const withTarget = g.filter((r) => r.crt_threshold_days != null)
      const waits = g.map((r) => r.adjusted_wait_days ?? 0)
      return {
        code,
        n: g.length,
        withTarget: withTarget.length,
        breached: withTarget.filter((r) => r.crt_breached === true).length,
        median: median(waits),
        longest: Math.max(...waits),
        clinic: clinics?.find((c) => c.specialty_hipe === code),
      }
    })
    .sort((a, b) => b.n - a.n)
}

/* ------------------------------------------------------------------------- */

/** The hospital overview as an instrument panel.
 *
 *  Everything that used to be a paragraph here is now something you can read a
 *  number off. The staleness prose became a distribution; the bed-pressure
 *  prose became a table with free beds, DTOC, surge, outliers and the specialty
 *  each ward actually backs; "specialty 0600" became Otolaryngology (ENT).
 *
 *  Four things are held to on every panel. A breach is always of the 165 that
 *  have a target, never of the 308. A reading's age always travels with the
 *  reading. Every colour carries a word beside it. And capacity is only ever
 *  shown as one number for the whole hospital-day — priority.py guarantees it
 *  cannot reorder two people, so nothing here may imply that it did.
 */
export function Overview({ hospital, date, name, reference, onOpenList }: {
  hospital: string; date: string; name: string
  reference: Reference | undefined
  onOpenList: () => void
}) {
  const cohort = useQuery({
    queryKey: ['cohort', hospital, date],
    queryFn: () => api.cohort(hospital, date),
  })
  // ~3.3s uncached: every ward's latest snapshot, every clinic's session
  // series, and one context per referral for the observation ages.
  const ops = useQuery({
    queryKey: ['operations', hospital, date],
    queryFn: () => api.operations(hospital, date),
    staleTime: Infinity,
  })
  // 404 until a run has produced one. Normal, not an error.
  const dec = useQuery<Decision>({
    queryKey: ['decision', hospital, date],
    queryFn: () => api.decision(hospital, date),
    retry: false,
  })
  const days = useQuery({
    queryKey: ['hospital-days', hospital],
    queryFn: () => api.hospitalDays(hospital),
    staleTime: 5 * 60_000,
  })

  if (cohort.isPending) {
    return <div className="pad"><p className="muted">Reading the waiting list…</p></div>
  }
  if (cohort.error) {
    return (
      <div className="pad">
        <div className="err">
          <strong>Could not load the waiting list.</strong>
          <div className="muted num">{String(cohort.error)}</div>
        </div>
      </div>
    )
  }

  const rows = cohort.data.referrals
  const s = summarise(rows)
  const specs = bySpecialty(rows, ops.data?.clinics)
  const d = dec.data
  const noRun = dec.isError

  return (
    <div className="pad ov">
      <header className="ov-head">
        <div>
          <span className="lab">Hospital overview</span>
          <h1>Where the list stands</h1>
        </div>
        <div className="ov-head-meta">
          <span><Building2 size={13} strokeWidth={1.75} aria-hidden />{name} · <span className="num">{hospital}</span></span>
          <span><CalendarDays size={13} strokeWidth={1.75} aria-hidden />{longDate(date)}</span>
        </div>
      </header>

      <ReadoutBand s={s} d={d} noRun={noRun} ops={ops} reference={reference} />

      <div className="ov-cols">
        <SpecialtyPanel specs={specs} s={s} reference={reference} ops={ops} d={d} noRun={noRun} />
      </div>

      <div className="ov-thirds">
        <NationalPanel s={s} />
        <StalenessPanel ops={ops} />
        <RulePanel d={d} noRun={noRun} reference={reference} onOpenList={onOpenList} />
      </div>

      <div className="ov-thirds ov-pair">
        <IntakePanel days={days} date={date} />
        <ClinicPanel ops={ops} reference={reference} d={d} />
      </div>

      <WardPanel ops={ops} reference={reference} d={d} />
    </div>
  )
}

/* --- 1. the readout band -------------------------------------------------- */

function ReadoutBand({ s, d, noRun, ops, reference }: {
  s: ReturnType<typeof summarise>
  d: Decision | undefined
  noRun: boolean
  ops: OpsQuery
  reference: Reference | undefined
}) {
  const urgentDays = crtDays(reference, 1)
  const semiDays = crtDays(reference, 3)
  const wards = ops.data?.wards
  const freeBeds = wards?.reduce((a, w) => a + (w.free ?? 0), 0)
  const overSafe = wards?.filter((w) => w.occupancy_pct >= SAFE_OCCUPANCY).length

  return (
    <section className="ov-band" aria-label="Headline readouts">
      <Readout icon={Users} k="on the list" v={fmt(s.total)}
               n={BANDS.map((b) => `${fmt(s.bands.get(b.key) ?? 0)} ${b.key}`).join(' · ')} />
      <Readout icon={Clock} k="have a target" v={fmt(s.withTarget)}
               n={`Urgent ${urgentDays ?? '—'}d · Semi-Urgent ${semiDays ?? '—'}d`} />
      <Readout icon={TriangleAlert} k="past target" v={fmt(s.breached)} accent
               n={`${pct(s.withTarget ? s.breached / s.withTarget : 0, 0)} of the ${fmt(s.withTarget)} that have one`} />
      <Readout icon={Layers} k="no target at all" v={fmt(s.noTarget)}
               n="Routine and Uncategorised carry no timeframe — nothing here can be late" />
      <Readout icon={Clock} k="median wait" v={fmt(s.median)} unit="days"
               n={`longest ${fmt(s.longest)} days`} />
      <Readout icon={Gauge} k="α · weight on urgency" v={d ? d.alpha.toFixed(3) : '—'}
               n={d ? 'one number for the whole hospital-day' : 'no run for this day yet'} />
      <Readout icon={Activity} k="scarcity" v={d ? d.scarcity.toFixed(3) : '—'}
               n={d ? `read as ${d.capacity_direction} · ADR-007` : noRun ? 'not scored' : 'reading…'} />
      <Readout icon={Stethoscope} k="awaiting triage" v={fmt(s.awaitingTriage)}
               n={`${fmt(s.total - s.awaitingTriage)} triaged · ${fmt(s.suspended)} currently suspended`} />
      <Readout icon={BedDouble} k="beds free now"
               v={freeBeds == null ? '—' : fmt(freeBeds)}
               n={overSafe == null
                 ? (ops.isError ? 'the ward snapshots are unavailable' : 'reading the ward snapshots…')
                 : `${overSafe} of ${wards?.length} wards at or over the ${SAFE_OCCUPANCY}% line`} />
    </section>
  )
}

function Readout({ icon: Icon, k, v, unit, n, accent }: {
  icon: typeof Gauge; k: string; v: string; unit?: string; n?: string; accent?: boolean
}) {
  return (
    <div className={'ov-ro' + (accent ? ' is-accent' : '')}>
      <div className="lab ov-ro-k"><Icon size={12} strokeWidth={1.9} aria-hidden />{k}</div>
      <div className="ov-ro-v num">{v}{unit && <span className="ov-ro-u"> {unit}</span>}</div>
      {n && <div className="ov-ro-n">{n}</div>}
    </div>
  )
}

/* --- panel chrome --------------------------------------------------------- */

function Panel({ icon: Icon, title, note, cite, children }: {
  icon: typeof Gauge; title: string; note?: string; cite?: string
  children: React.ReactNode
}) {
  return (
    <section className="ov-panel">
      <h2 className="ov-panel-h">
        <Icon size={14} strokeWidth={1.9} aria-hidden />
        <span>{title}</span>
        {note && <span className="ov-panel-note">{note}</span>}
      </h2>
      <div className="ov-panel-b">{children}</div>
      {cite && <div className="ov-cite">{cite}</div>}
    </section>
  )
}

function PanelState({ q, children }: {
  q: { isPending: boolean; isError: boolean; error: unknown }; children: React.ReactNode
}) {
  if (q.isPending) return <p className="ov-quiet">Reading…</p>
  if (q.isError) return <p className="ov-quiet">Not available · <span className="num">{String(q.error)}</span></p>
  return <>{children}</>
}

/** A horizontal bar. The number always sits beside it, so the bar is a second
 *  channel rather than the only one. */
function Bar({ v, max = 1 }: { v: number; max?: number }) {
  const w = max > 0 ? Math.min(100, Math.max(0, (v / max) * 100)) : 0
  return (
    <span className="ov-bar" aria-hidden>
      <i className="ov-bar-f" style={{ width: `${w}%` }} />
    </span>
  )
}

/* --- 2. by specialty ------------------------------------------------------ */

function SpecialtyPanel({ specs, s, reference, ops, d, noRun }: {
  specs: SpecRow[]
  s: ReturnType<typeof summarise>
  reference: Reference | undefined
  ops: OpsQuery
  d: Decision | undefined
  noRun: boolean
}) {
  const maxN = Math.max(...specs.map((x) => x.n), 1)
  const cap = agentCapacity(d)
  const refused = new Set(d?.refused_paediatric ?? [])

  return (
    <Panel icon={Stethoscope} title="By specialty"
           note={`${specs.length} specialties · core.ref_specialties`}
           cite={`Ward pressure and capacity score are the agent's own working and are SPECIALTY-level: every referral inside a specialty carries the identical figure, which is why capacity can set α for the hospital-day and still never reorder two people. Clinic pressure is booked ÷ total on the one session the agent read, and matches what it scored wherever a specialty was scored at all.${
             noRun ? ' No run for this day yet, so the agent columns are empty.' : ''}`}>
      <div className="scroll-x">
        <table className="ov-t">
          <thead>
            <tr>
              <th>Specialty</th>
              <th className="c-n">Waiting</th>
              <th className="c-bar">Share of list</th>
              <th className="c-n">Has a target</th>
              <th className="c-n">Past target</th>
              <th className="c-n">Median wait</th>
              <th className="c-n">Longest</th>
              <th className="c-bar">Ward pressure<span className="ov-th-sub">agent</span></th>
              <th className="c-bar">Clinic pressure<span className="ov-th-sub">cited session</span></th>
              <th className="c-n">Capacity score<span className="ov-th-sub">agent</span></th>
            </tr>
          </thead>
          <tbody>
            {specs.map((x) => {
              const a = cap.get(x.code)
              const clinicP = a?.clinic ?? x.clinic?.cited_pressure ?? null
              // 0601 is refused rather than scored: NEWS2 is validated in
              // adults. A coverage statement, not a missing number.
              const isRefused = !a && rowsRefused(refused, x.code, d)
              return (
                <tr key={x.code}>
                  <td className="c-name">{specialtyFull(reference, x.code)}</td>
                  <td className="c-n num">{fmt(x.n)}</td>
                  <td className="c-bar"><Bar v={x.n} max={maxN} /></td>
                  <td className="c-n num">{x.withTarget ? fmt(x.withTarget) : <span className="ov-none">none</span>}</td>
                  <td className="c-n num">
                    {x.withTarget === 0
                      ? <span className="ov-none">no target</span>
                      : <>{fmt(x.breached)}<span className="ov-of"> of {fmt(x.withTarget)}</span></>}
                  </td>
                  <td className="c-n num">{fmt(x.median)}<span className="ov-of">d</span></td>
                  <td className="c-n num">{fmt(x.longest)}<span className="ov-of">d</span></td>
                  <td className="c-bar"><Meter v={a?.ward ?? null} empty={isRefused ? 'refused' : noRun ? 'no run' : '—'} /></td>
                  <td className="c-bar"><Meter v={clinicP} empty="—" /></td>
                  <td className="c-n num">
                    {a ? a.score.toFixed(3) : <span className="ov-none">{isRefused ? 'refused' : noRun ? 'no run' : '—'}</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr>
              <td>All specialties</td>
              <td className="c-n num">{fmt(s.total)}</td>
              <td />
              <td className="c-n num">{fmt(s.withTarget)}</td>
              <td className="c-n num">{fmt(s.breached)}<span className="ov-of"> of {fmt(s.withTarget)}</span></td>
              <td className="c-n num">{fmt(s.median)}<span className="ov-of">d</span></td>
              <td className="c-n num">{fmt(s.longest)}<span className="ov-of">d</span></td>
              <td colSpan={3} className="ov-of">
                {d
                  ? `α ${d.alpha.toFixed(3)} · scarcity ${d.scarcity.toFixed(3)} — one pair of numbers for the whole hospital-day`
                  : 'no decision for this hospital-day'}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      {(ops.isPending || ops.isError) && (
        <p className="ov-quiet">
          {ops.isPending
            ? 'Clinic pressure is still loading.'
            : <>Clinic pressure is unavailable · <span className="num">{String(ops.error)}</span></>}
        </p>
      )}
    </Panel>
  )
}

/** True when this specialty produced no ranking because it was refused, not
 *  because nothing has run. `refused_paediatric` holds pathway numbers. */
function rowsRefused(refused: Set<string>, code: string, d: Decision | undefined): boolean {
  if (!d || refused.size === 0) return false
  return !d.rankings.some((r) => r.specialty_hipe === code)
}

/** A 0–1 pressure, as a bar with its number. Neutral: a busy clinic is not an
 *  Urgent referral and may not borrow its hue. */
function Meter({ v, empty }: { v: number | null; empty: string }) {
  if (v == null) return <span className="ov-none">{empty}</span>
  return (
    <span className="ov-inline">
      <Bar v={v} />
      <span className="num ov-inline-n">{v.toFixed(2)}</span>
    </span>
  )
}

/* --- 3. against the national picture -------------------------------------- */

function NationalPanel({ s }: { s: ReturnType<typeof summarise> }) {
  const maxShare = Math.max(
    ...s.waitBands.map((b) => Math.max(b.share, s.total ? b.here / s.total : 0)),
  )
  return (
    <Panel icon={Layers} title="Against the national picture"
           note="adjusted wait, NTPF bands"
           cite={`NTPF Outpatient Waiting List by Speciality · OpenData_OPNational02_2026.csv · snapshot ${NTPF_SNAPSHOT} · ${fmt(NTPF_TOTAL)} people across the 57 non-SDC specialties. Band edges in days (183 / 365 / 548) are the generator's own, so both sides are cut the same way.`}>
      <div className="ov-nat">
        {s.waitBands.map((b) => {
          const here = s.total ? b.here / s.total : 0
          const delta = here - b.share
          return (
            <div className="ov-nat-row" key={b.key}>
              <div className="ov-nat-k">{b.key}</div>
              <div className="ov-nat-pair">
                <div className="ov-nat-line">
                  <span className="ov-nat-w">here</span>
                  <Bar v={here} max={maxShare} />
                  <span className="num ov-nat-n">{fmt(b.here)}<span className="ov-of"> · {pct(here)}</span></span>
                </div>
                <div className="ov-nat-line is-nat">
                  <span className="ov-nat-w">nationally</span>
                  <Bar v={b.share} max={maxShare} />
                  <span className="num ov-nat-n">{fmt(b.n)}<span className="ov-of"> · {pct(b.share)}</span></span>
                </div>
              </div>
              <div className="ov-nat-d num">
                {delta >= 0 ? '+' : '−'}{Math.abs(delta * 100).toFixed(1)}
                <span className="ov-of"> pp {delta >= 0 ? 'more' : 'fewer'} here</span>
              </div>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

/* --- 4. intake over the days that hold a cohort --------------------------- */

function IntakePanel({ days, date }: {
  days: Q<Awaited<ReturnType<typeof api.hospitalDays>>>
  date: string
}) {
  const list = days.data?.days ?? []
  const first = list[0]
  const last = list[list.length - 1]
  const deltas = list.slice(1).map((d, i) => ({ date: d.date, add: d.referrals - list[i].referrals }))
  const maxAdd = Math.max(...deltas.map((x) => x.add), 1)

  return (
    <Panel icon={TrendingUp} title="Intake"
           note={list.length ? `${list.length} days holding a cohort` : undefined}
           cite={`Net change per day. dataset/out/referral_daily.csv holds ${fmt(DAILY_ROWS)} rows and removal_date is null in every one, so net change is intake: nothing has ever left this list.`}>
      <PanelState q={days}>
        {!first && <p className="ov-quiet">No day in this hospital's history holds a cohort.</p>}
        {first && last && (
          <>
            <div className="ov-intake-lead">
              <span className="num ov-fig">{fmt(first.referrals)}</span>
              <span className="ov-of">on {shortDate(first.date)}</span>
              <span className="ov-arrow" aria-hidden>→</span>
              <span className="num ov-fig">{fmt(last.referrals)}</span>
              <span className="ov-of">on {shortDate(last.date)}</span>
              <span className="ov-intake-net num">+{fmt(last.referrals - first.referrals)}</span>
              <span className="ov-of">added, 0 removed</span>
            </div>
            <div className="ov-cols-chart" role="img"
                 aria-label={`Referrals added per day: ${deltas.map((x) => `${shortDate(x.date)} plus ${x.add}`).join(', ')}`}>
              {deltas.map((x) => (
                <div className={'ov-col' + (x.date === date ? ' is-on' : '')} key={x.date}>
                  <span className="ov-col-n num">{x.add > 0 ? `+${x.add}` : '0'}</span>
                  <span className="ov-col-track">
                    <i style={{ height: `${(x.add / maxAdd) * 100}%` }} />
                  </span>
                  <span className="ov-col-k num">{dayNum(x.date)}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </PanelState>
    </Panel>
  )
}

/* --- 5. staleness, drawn ---------------------------------------------------
   The prose block this replaces said 140 / 871 / 48 / 12 in five lines. Same
   four facts, plus the shape they came from, as one instrument. */

function StalenessPanel({ ops }: {
  ops: OpsQuery
}) {
  const age = ops.data?.observation_age
  const ages = Object.values(ops.data?.clinical ?? {})
    .map((c) => c.reading_age_days)
    .filter((x): x is number => x != null)
  const hist = AGE_BUCKETS.map((b) => ({
    ...b, n: ages.filter((a) => a >= b.lo && a < b.hi).length,
  }))
  const maxN = Math.max(...hist.map((h) => h.n), 1)

  return (
    <Panel icon={Clock} title="Age of the newest reading"
           note={age ? `${fmt(age.n)} readings` : undefined}
           cite="Every person here has exactly one set of vitals, taken when the referral letter arrived and never revisited. A normal reading this old is an absence of information, not reassurance.">
      <PanelState q={ops}>
        {age && (
          <>
            <div className="ov-mini">
              <Mini k="median" v={fmt(age.median)} u="d" />
              <Mini k="mean" v={fmt(age.mean)} u="d" />
              <Mini k="oldest" v={fmt(age.max)} u="d" />
              <Mini k="over 1 year" v={fmt(age.over_1y)} />
              <Mini k="over 2 years" v={fmt(age.over_2y)} />
            </div>
            {ages.length > 0 && (
              <div className="ov-hist">
                {hist.map((h) => (
                  <div className={'ov-hist-row' + (h.lo >= 365 ? ' is-past-year' : '')} key={h.key}>
                    <span className="ov-hist-k">{h.key}</span>
                    <Bar v={h.n} max={maxN} />
                    <span className="num ov-hist-n">{fmt(h.n)}</span>
                  </div>
                ))}
                <div className="ov-hist-mark">
                  below the rule: a year old or older —{' '}
                  <span className="num">{fmt(age.over_1y)}</span> readings
                </div>
              </div>
            )}
          </>
        )}
      </PanelState>
    </Panel>
  )
}

function Mini({ k, v, u }: { k: string; v: string; u?: string }) {
  return (
    <div className="ov-mini-i">
      <div className="ov-mini-v num">{v}{u && <span className="ov-of">{u}</span>}</div>
      <div className="lab">{k}</div>
    </div>
  )
}

/* --- 6. the rule board, in summary ---------------------------------------- */

function RulePanel({ d, noRun, reference, onOpenList }: {
  d: Decision | undefined; noRun: boolean
  reference: Reference | undefined; onOpenList: () => void
}) {
  if (!d) {
    return (
      <Panel icon={Activity} title="Rules"
             note={noRun ? 'no decision for this hospital-day' : undefined}>
        <p className="ov-quiet">
          {noRun
            ? 'Nothing has been scored yet, so no rule has been tested. Run the agents from the top bar.'
            : 'Reading the decision…'}
        </p>
      </Panel>
    )
  }

  const tally = new Map<string, { tested: number; failed: number }>()
  for (const r of d.rankings) {
    for (const c of r.rule_checks ?? []) {
      const t = tally.get(c.rule_id) ?? { tested: 0, failed: 0 }
      t.tested += 1
      if (!c.passed) t.failed += 1
      tally.set(c.rule_id, t)
    }
  }
  const carrying = d.rankings.filter((r) => failed(r.rule_checks).length > 0).length
  const ids = (reference?.rules ?? []).map((r) => r.rule_id)
    .filter((id) => tally.has(id))
  for (const id of tally.keys()) if (!ids.includes(id)) ids.push(id)

  return (
    <Panel icon={Activity} title="Rules"
           note={`${fmt([...tally.values()].reduce((a, b) => a + b.tested, 0))} checks · ${fmt(d.rankings.length)} placements`}
           cite="A summary. The full board, with every statement and threshold, is on the Decision record.">
      <div className="ov-rules">
        {ids.map((id) => {
          const t = tally.get(id)!
          const whole = WHOLE_LIST.has(id)
          const held = whole
            ? (id === 'RULE-ORDER' ? d.rule_order_passed : d.rule_tiebreak_passed)
            : t.failed === 0
          return (
            <div className="ov-rule" key={id}>
              <div className="ov-rule-top">
                <span className="num ov-rule-id">{id}</span>
                <span className={'ov-verdict ' + (held ? 'is-ok' : 'is-bad')}>
                  {held
                    ? <><Check size={12} strokeWidth={2.5} aria-hidden />holds</>
                    : <><TriangleAlert size={12} strokeWidth={2.25} aria-hidden />
                        {whole ? 'violated' : `${fmt(t.failed)} past target`}</>}
                </span>
              </div>
              <div className="ov-rule-st">{ruleStatement(reference, id)}</div>
              <div className="ov-rule-m num">
                {whole
                  ? 'tested once, over the whole list'
                  : `${fmt(t.failed)} of ${fmt(t.tested)} tested`}
              </div>
            </div>
          )
        })}
      </div>
      <div className="ov-rule-foot">
        <span className="num">{fmt(carrying)}</span> of{' '}
        <span className="num">{fmt(d.rankings.length)}</span> placed referrals carry at least
        one breached timeframe.
        <button className="ov-link" onClick={onOpenList}>
          Open the ranked order
        </button>
      </div>
    </Panel>
  )
}

/* --- 7. clinic capacity ---------------------------------------------------- */

function ClinicPanel({ ops, reference, d }: {
  ops: OpsQuery
  reference: Reference | undefined
  d: Decision | undefined
}) {
  const clinics = ops.data?.clinics ?? []
  const cap = agentCapacity(d)

  return (
    <Panel icon={CalendarDays} title="Clinic capacity"
           note={clinics.length ? `${clinics.length} clinics · the cited session is marked` : undefined}
           cite={'DATASET_README.md:623 — "most outpatient referrals need a clinic appointment, not a bed, so this is where the real constraint usually sits". The capacity agent read ONE session per clinic; every other session in the series is context and was not scored. The last column is that session\u2019s pressure, and it is the number the agent used.'}>
      <PanelState q={ops}>
        <div className="scroll-x">
          <table className="ov-t">
            <thead>
              <tr>
                <th>Specialty</th>
                <th>Clinic</th>
                <th className="c-n">Booked</th>
                <th className="c-n">Free slots</th>
                <th className="c-bar">Booked across the series</th>
                <th>Session series</th>
                <th className="c-n">Cited session</th>
                <th className="c-n">Pressure then</th>
                <th className="c-n">As scored<span className="ov-th-sub">agent</span></th>
              </tr>
            </thead>
            <tbody>
              {clinics.map((c) => {
                const ratio = c.slots_total ? c.slots_booked / c.slots_total : 0
                return (
                  <tr key={c.clinic_code ?? c.specialty_hipe}>
                    <td className="c-name">{specialtyName(reference, c.specialty_hipe)}</td>
                    <td className="num c-dim">{c.clinic_code ?? '—'}</td>
                    <td className="c-n num">{fmt(c.slots_booked)}<span className="ov-of"> of {fmt(c.slots_total)}</span></td>
                    <td className="c-n num">{fmt(c.slots_available)}</td>
                    <td className="c-bar">
                      <span className="ov-inline">
                        <Bar v={ratio} />
                        <span className="num ov-inline-n">{pct(ratio, 0)}</span>
                      </span>
                    </td>
                    <td><Sessions clinic={c} /></td>
                    <td className="c-n num">
                      {c.cited_session_date
                        ? <span className="ov-cited-tag">{shortDate(c.cited_session_date)}</span>
                        : <span className="ov-none">none cited</span>}
                    </td>
                    <td className="c-n num">{pct(c.cited_pressure, 0)}</td>
                    <td className="c-n num">
                      {cap.get(c.specialty_hipe)?.clinic?.toFixed(3)
                        ?? <span className="ov-none">{d ? 'not scored' : 'no run'}</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </PanelState>
    </Panel>
  )
}

/** The session series as columns, with the one row the agent actually read
 *  marked in clay — the single accent on this page. */
function Sessions({ clinic }: { clinic: Clinic }) {
  const ss = clinic.sessions
  if (!ss.length) return <span className="ov-none">no sessions</span>
  const label = ss.map((x) => {
    const p = x.slots_total ? Math.round((x.slots_booked / x.slots_total) * 100) : 0
    return `${shortDate(x.session_date)} ${p}%${x.session_date === clinic.cited_session_date ? ' (cited)' : ''}`
  }).join(', ')
  return (
    <span className="ov-spark" role="img" aria-label={`Booked share by session: ${label}`}>
      {ss.map((x) => {
        const p = x.slots_total ? x.slots_booked / x.slots_total : 0
        const cited = x.session_date === clinic.cited_session_date
        return (
          <span className={'ov-spark-c' + (cited ? ' is-cited' : '')} key={x.session_date}>
            <i style={{ height: `${Math.max(4, p * 100)}%` }} />
          </span>
        )
      })}
      <span className="ov-spark-k num">{shortDate(ss[0].session_date)}–{shortDate(ss[ss.length - 1].session_date)}</span>
    </span>
  )
}

/* --- 8. ward pressure ------------------------------------------------------ */

function WardPanel({ ops, reference, d }: {
  ops: OpsQuery
  reference: Reference | undefined
  d: Decision | undefined
}) {
  const wards = ops.data?.wards ?? []
  const totals = wards.reduce((a, w) => ({
    occupied: a.occupied + (w.occupied ?? 0), free: a.free + (w.free ?? 0),
    outliers: a.outliers + w.outliers, dtoc: a.dtoc + w.dtoc, surge: a.surge + w.surge,
    over9: a.over9 + w.over_9h, over24: a.over24 + w.over_24h,
  }), { occupied: 0, free: 0, outliers: 0, dtoc: 0, surge: 0, over9: 0, over24: 0 })

  return (
    <Panel icon={BedDouble} title="Ward pressure"
           note={wards.length ? `${wards.length} wards · latest snapshot only` : undefined}
           cite={`The ${SAFE_OCCUPANCY}% mark is the safe-operating threshold (Bagust, Place & Posnett, BMJ 1999;319:155-8). The agent reads this snapshot and no other — there is no bed series behind α. What it derives is one ward-pressure figure per specialty, shown in the specialty table above; it sets α for the whole hospital-day and priority.py cannot let it reorder two people.`}>
      <PanelState q={ops}>
        <div className="scroll-x">
          <table className="ov-t">
            <thead>
              <tr>
                <th>Ward</th>
                <th>Primary for</th>
                <th>Also backs</th>
                <th className="c-bar">Occupancy</th>
                <th className="c-n">Free</th>
                <th className="c-n">Occupied</th>
                {/* every abbreviation is expanded: DATASET_README 7.11 */}
                <th className="c-n">Outliers<span className="ov-th-sub">another specialty</span></th>
                <th className="c-n">DTOC<span className="ov-th-sub">delayed transfer</span></th>
                <th className="c-n">Surge<span className="ov-th-sub">beds opened</span></th>
                <th className="c-n">Over 9h<span className="ov-th-sub">awaiting a bed</span></th>
                <th className="c-n">Over 24h<span className="ov-th-sub">awaiting a bed</span></th>
                <th>Status</th>
                <th className="c-n">As of</th>
              </tr>
            </thead>
            <tbody>
              {wards.map((w) => <WardRow key={w.ward_id} w={w} reference={reference} />)}
            </tbody>
            <tfoot>
              <tr>
                <td>All wards</td>
                <td /><td /><td />
                <td className="c-n num">{fmt(totals.free)}</td>
                <td className="c-n num">{fmt(totals.occupied)}</td>
                <td className="c-n num">{fmt(totals.outliers)}</td>
                <td className="c-n num">{fmt(totals.dtoc)}</td>
                <td className="c-n num">{fmt(totals.surge)}</td>
                <td className="c-n num">{fmt(totals.over9)}</td>
                <td className="c-n num">{fmt(totals.over24)}</td>
                <td /><td />
              </tr>
            </tfoot>
          </table>
        </div>
      </PanelState>
    </Panel>
  )
}

function WardRow({ w, reference }: { w: Ward; reference: Reference | undefined }) {
  const gar = (w.gar_status ?? 'G') as keyof typeof GAR_WORD
  const over = w.occupancy_pct >= SAFE_OCCUPANCY
  const also = w.specialties.filter((c) => !w.primary_for.includes(c))
  return (
    <tr>
      <td className="c-name num">
        {w.ward_id.replace(/^W-\d+-/, 'Ward ')}
        {w.nominal_beds != null && <span className="ov-sub num">nominal {fmt(w.nominal_beds)}</span>}
      </td>
      <td className="c-name">
        {w.primary_for.length
          ? w.primary_for.map((c) => specialtyName(reference, c)).join(', ')
          : <span className="ov-none">none</span>}
      </td>
      <td className="c-dim">
        {also.length ? also.map((c) => specialtyName(reference, c)).join(', ') : <span className="ov-none">—</span>}
      </td>
      <td className="c-bar">
        <span className="ov-occ">
          <span className="ov-occ-track">
            <i className="ov-occ-fill" style={{ width: `${Math.min(100, w.occupancy_pct)}%` }} />
            <i className="ov-occ-safe" style={{ left: `${SAFE_OCCUPANCY}%` }} />
          </span>
          <span className="num ov-occ-n">
            {w.occupancy_pct.toFixed(1)}%
            <span className="ov-of"> · {over ? `over the ${SAFE_OCCUPANCY}% line` : `under the ${SAFE_OCCUPANCY}% line`}</span>
          </span>
        </span>
      </td>
      <td className="c-n num">{w.free ?? '—'}</td>
      <td className="c-n num">{w.occupied ?? '—'}</td>
      <td className="c-n num">{fmt(w.outliers)}</td>
      <td className="c-n num">{fmt(w.dtoc)}</td>
      <td className="c-n num">{fmt(w.surge)}</td>
      <td className="c-n num">{fmt(w.over_9h)}</td>
      <td className="c-n num">{fmt(w.over_24h)}</td>
      <td>
        <span className={'ov-gar is-' + gar}><i aria-hidden />{GAR_WORD[gar]}</span>
      </td>
      <td className="c-n num c-dim">{shortDate(w.snapshot)} {clockTime(w.snapshot)}</td>
    </tr>
  )
}
