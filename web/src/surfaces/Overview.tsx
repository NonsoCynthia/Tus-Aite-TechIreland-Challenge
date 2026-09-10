import { useQuery } from '@tanstack/react-query'
import {
  Activity, BedDouble, Building2, CalendarCheck, CalendarDays, Check, Clock, Gauge,
  Layers, ListOrdered, Lock, Minus, Play, Scale, Stethoscope, TrendingUp, TriangleAlert,
  Users,
} from 'lucide-react'
import { api, BANDS, bandOf } from '../lib/api'
import {
  breachPhrase, crtDays, failed, rule, ruleStatement, specialtyFull, specialtyName,
} from '../lib/ref'
import { SevBar, SevChip } from '../components/Severity'
import {
  SAFE_OCCUPANCY, SEV_INTEGRITY, sevBooked, sevBreach, sevOccupancy, sevReadingAge, type Sev,
} from '../lib/severity'
/** Median wait. ONE home, lib/stats.ts, shared with List.tsx -- the two surfaces
 *  used to hold a copy each and printed 142 against 141 on 2026-08-21. */
import { median } from '../lib/stats'
import type { CohortReferral, Decision, Reference } from '../lib/types'
import './overview.css'

/* ---------------------------------------------------------------------------
   Constants that are CITED, not assumed. Everything else on this surface is
   counted at render time from a payload.
--------------------------------------------------------------------------- */

/* Safe-operating occupancy -- Bagust, Place & Posnett, BMJ 1999;319:155-8 -- is
   imported from lib/severity above, beside the bands that grade against it.
   It used to be declared here as well, a second time in components/AgentInputs
   and a third time implicitly as sevOccupancy's first boundary. A drawn safe
   line that can drift from the band edge grading the same number is the
   "never hardcode a threshold" fault in another costume: one declaration. */

/** Colour is never the only channel: the GAR letter always resolves to a word. */
const GAR_WORD = { G: 'Green', A: 'Amber', R: 'Red' } as const

/** --icon-sm. The token floor for an icon that carries meaning; the readouts
 *  used to draw theirs at 12px, the smallest mark in the product. */
const ICON = 14

/** NTPF Outpatient Waiting List by Speciality, OpenData_OPNational02_2026.csv,
 *  snapshot 2026-07-30, 682,279 people over the 57 non-SDC specialties.
 *
 *  NTPF publishes the bands in months. The day boundaries below are the ones
 *  every wait in this dataset was cut on, so bucketing this hospital on
 *  183/365/548 compares like with like rather than inventing a days-per-month
 *  constant. */
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

/** How many day-columns the intake chart will draw. Past this the chart scrolls
 *  and the panel says how many of the series it is showing: 59 columns in a
 *  ~400px panel leaves 3.8px each, and a count label centred on a 3.8px track
 *  lands on top of its neighbours on both sides. */
const INTAKE_COLUMNS = 30

/** Reading age, bucketed. The boundaries are the ones observation_age already
 *  reports against (a year, two years), extended downwards so the shape shows.
 *  Severity comes from sevReadingAge, never from these edges. */
const AGE_BUCKETS = [
  { key: 'under 3 months', lo: 0, hi: 90 },
  { key: '3–6 months', lo: 90, hi: 180 },
  { key: '6–12 months', lo: 180, hi: 365 },
  { key: '1–2 years', lo: 365, hi: 730 },
  { key: 'over 2 years', lo: 730, hi: Infinity },
] as const

/** Rules whose subject is the whole list, and where each one's verdict actually
 *  lives on the decision.
 *
 *  This was a Set of two IDs read by a two-way branch, so a third whole-list
 *  rule added to core.ref_rules would have silently rendered RULE-TIEBREAK's
 *  verdict under its own name. A lookup cannot do that: a whole-list rule with
 *  no entry here has no verdict to show, and the board says so. */
const WHOLE_LIST_VERDICT: Record<string, ((d: Decision) => boolean) | undefined> = {
  'RULE-ORDER': (d) => d.rule_order_passed,
  'RULE-TIEBREAK': (d) => d.rule_tiebreak_passed,
}

/** core.ref_rules marks a whole-list rule `applies_to: 'all'`. Counting one per
 *  referral would imply 305 independent verdicts where there is one. */
const isWholeList = (ref: Reference | undefined, id: string): boolean =>
  id in WHOLE_LIST_VERDICT || rule(ref, id)?.applies_to === 'all'

type Ops = Awaited<ReturnType<typeof api.operations>>
type Ward = Ops['wards'][number]
type Clinic = Ops['clinics'][number]
type Session = Clinic['sessions'][number]
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
/** The calendar day a timestamp falls on, as the API writes dates. */
const dayOf = (iso: string) => iso.slice(0, 10)

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
 *  referral inside a specialty and differ between specialties, which is why
 *  `capacity_score` is documented in types.ts as "specialty-level, identical for
 *  every referral in a specialty". Reading one ranking's capacity_detail and
 *  calling it the hospital's figure would be wrong; so would drawing it against
 *  a person. It is drawn against a specialty.
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

/* ---------------------------------------------------------------------------
   Reconciliation. Two independent counts of the same list, plus the decision's
   own account of it. A gap here means a number on this page cannot be trusted,
   which outranks any clinical state, so it renders at SEV_INTEGRITY.
--------------------------------------------------------------------------- */

type Check = { holds: boolean; said: string }

function reconcile(total: number, ops: OpsQuery, d: Decision | undefined): Check[] {
  const out: Check[] = []
  const opsTotal = ops.data?.cohort
  if (opsTotal != null) {
    out.push({
      holds: opsTotal === total,
      said: `${fmt(total)} on the waiting list, ${fmt(opsTotal)} in the operational context`,
    })
  }
  if (d) {
    // Set union, never a sum: refused_paediatric is a subset of excluded here,
    // and adding the two would over-count the same three referrals.
    const accounted = new Set<string>([
      ...d.rankings.map((r) => r.pathway_number),
      ...d.excluded.map((e) => e.pathway_number),
      ...d.refused_paediatric,
      ...d.skipped,
    ])
    out.push({
      holds: accounted.size === total,
      said: `${fmt(accounted.size)} of ${fmt(total)} accounted for by the decision`
        + ` (${fmt(d.rankings.length)} placed, ${fmt(d.excluded.length)} excluded, by set union)`,
    })
  }
  return out
}

/* ------------------------------------------------------------------------- */

/** The hospital overview as an instrument panel.
 *
 *  Everything that used to be a paragraph here is now something you can read a
 *  number off. The staleness prose became a distribution; the bed-pressure
 *  prose became a table with free beds, DTOC, surge, outliers and the specialty
 *  each ward actually backs; "specialty 0600" became Otolaryngology (ENT).
 *
 *  Five things are held to on every panel. A breach is always of the 165 that
 *  have a target, never of the 308. A reading's age always travels with the
 *  reading. Every colour carries a word beside it. Capacity is only ever shown
 *  as one number for the whole hospital-day, because priority.py guarantees it
 *  cannot reorder two people. And every panel says the day its figures were
 *  actually taken on, which is not always the day selected above.
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
  // A 404 is the ordinary "nothing has run yet" state. Anything else is a
  // failure to read a decision that may well exist, and the two cannot be told
  // apart by isError alone.
  const decErr = dec.error instanceof Error ? dec.error.message : String(dec.error ?? '')
  const noRun = dec.isError && decErr.includes('404')
  const decFailed = dec.isError && !noRun
  const decNote = d ? null
    : noRun ? 'no run for this day yet'
    : decFailed ? 'the decision could not be read'
    : 'reading the decision…'

  return (
    <div className="pad ov">
      <header className="ov-head">
        <div>
          <span className="lab">Hospital overview</span>
          <h1>Where the list stands</h1>
        </div>
        <div className="ov-head-meta">
          <span><Building2 size={ICON} strokeWidth={1.75} aria-hidden />{name} · <span className="num">{hospital}</span></span>
          <span><CalendarDays size={ICON} strokeWidth={1.75} aria-hidden />{longDate(date)}</span>
        </div>
      </header>

      <IntegrityBand checks={reconcile(s.total, ops, d)} />

      {decFailed && (
        <p className="ov-quiet">
          The decision for this day could not be read, so the agent columns are empty:{' '}
          <span className="num">{decErr}</span>
        </p>
      )}
      {noRun && <BeforeRanking date={date} runnable={days.data?.runnable} />}

      <ReadoutBand s={s} d={d} decNote={decNote} reference={reference} />

      <div className="ov-cols">
        <SpecialtyPanel specs={specs} s={s} reference={reference} ops={ops} d={d} noRun={noRun} />
      </div>

      <div className="ov-thirds">
        <NationalPanel s={s} />
        <StalenessPanel ops={ops} />
        <RulePanel d={d} decNote={decNote} reference={reference} onOpenList={onOpenList} />
      </div>

      <div className="ov-thirds ov-pair">
        <IntakePanel days={days} date={date} />
        <ClinicPanel ops={ops} reference={reference} d={d} date={date} />
      </div>

      <WardPanel ops={ops} reference={reference} date={date} />
    </div>
  )
}

/* --- 0. integrity, and the state before anything has been ranked ---------- */

/** The loudest thing this surface can say. Quiet while the counts agree; a
 *  solid block the moment they do not, because a clinician can act on a bad
 *  number long before anyone notices it was bad. */
function IntegrityBand({ checks }: { checks: Check[] }) {
  if (!checks.length) return null
  const broken = checks.filter((c) => !c.holds)
  if (!broken.length) {
    return (
      <p className="ov-recon">
        <Scale size={ICON} strokeWidth={1.9} aria-hidden />
        Counts reconcile: {checks.map((c) => c.said).join('; ')}.
      </p>
    )
  }
  return (
    <div className="ov-recon is-broken" role="alert">
      <SevChip sev={SEV_INTEGRITY}>
        <TriangleAlert size={ICON} strokeWidth={2.25} aria-hidden />
        does not reconcile
      </SevChip>
      <div className="ov-recon-b">
        {broken.map((c) => <div key={c.said} className="num">{c.said}.</div>)}
        <div className="ov-recon-n">
          Every figure on this page is drawn from these counts. Until they agree, nothing
          below is safe to act on.
        </div>
      </div>
    </div>
  )
}

/** No decision means this surface is the whole product: the list as it stands,
 *  before anything has been ranked. Said plainly, with the way forward. */
function BeforeRanking({ date, runnable }: { date: string; runnable: string | null | undefined }) {
  const here = runnable == null || runnable === date
  return (
    <section className="ov-before" aria-label="Before ranking">
      <h2 className="ov-before-h">
        <ListOrdered size={ICON} strokeWidth={1.9} aria-hidden />
        Nothing has been ranked for this day
      </h2>
      <p>
        This is the list before any ranking: who is waiting and for how long, which of them
        have a target and which have none, how stale the readings are, and how much bed and
        clinic room the hospital has. What is missing is the agents' account of it. There is
        no α, no scarcity, no placement and no rule verdict, so those cells read "no run"
        rather than zero.
      </p>
      <p className="ov-before-cta">
        {here ? (
          <>
            <Play size={ICON} strokeWidth={2.25} aria-hidden />
            Run the agents from the top bar to rank it.
          </>
        ) : (
          <>
            <Lock size={ICON} strokeWidth={2} aria-hidden />
            This day is read only. Scoring happens on {longDate(runnable)}, the newest day
            that holds a list, because evidence is date-blind and scoring an earlier day
            would cite readings taken after it.
          </>
        )}
      </p>
    </section>
  )
}

/** D2. `core.bed_status` and `core.clinic_sessions` are read latest-first with
 *  no date predicate, so every one of the 14 hospital-days is served the same
 *  rows. The payload carries the true date on every ward and every clinic; the
 *  panel shows it, and says plainly when it is not the day selected. */
function AsOf({ what, taken, selected, source }: {
  what: string; taken: string[]; selected: string; source: string
}) {
  const days = [...new Set(taken.map(dayOf))].sort()
  if (!days.length) return null
  const span = days.length === 1
    ? longDate(days[0])
    : `${longDate(days[0])} to ${longDate(days[days.length - 1])}`
  if (!days.some((x) => x !== selected)) {
    return (
      <p className="ov-asof">
        <CalendarCheck size={ICON} strokeWidth={1.9} aria-hidden />
        {what} as of {span}, the day selected above.
      </p>
    )
  }
  return (
    <div className="ov-asof is-off">
      <SevChip sev={SEV_INTEGRITY}>
        <CalendarDays size={ICON} strokeWidth={2} aria-hidden />
        <span className="num">{span}</span>
      </SevChip>
      <span>
        {what} are as of {span}, not {longDate(selected)}, the day selected above. {source}
      </span>
    </div>
  )
}

/* --- 1. the readout band -------------------------------------------------- */

function ReadoutBand({ s, d, decNote, reference }: {
  s: ReturnType<typeof summarise>
  d: Decision | undefined
  decNote: string | null
  reference: Reference | undefined
}) {
  const urgentDays = crtDays(reference, 1)
  const semiDays = crtDays(reference, 3)

  return (
    <section className="ov-band" aria-label="Headline readouts">
      <Readout icon={Users} k="on the list" v={fmt(s.total)}
               n={BANDS.map((b) => `${fmt(s.bands.get(b.key) ?? 0)} ${b.key}`).join(' · ')} />
      <Readout icon={Clock} k="have a target" v={fmt(s.withTarget)}
               n={`Urgent ${urgentDays ?? '—'}d · Semi-Urgent ${semiDays ?? '—'}d`} />
      {/* A pass/fail with no magnitude at hospital level: either some referral
          is past its target or none is. sevBreach is the scale for exactly
          that, and it replaces a 3px clay edge that said nothing at distance. */}
      <Readout icon={TriangleAlert} k="past target" v={fmt(s.breached)}
               sev={sevBreach(s.breached === 0)}
               n={`${pct(s.withTarget ? s.breached / s.withTarget : 0, 0)} of the ${fmt(s.withTarget)} that have one`} />
      <Readout icon={Layers} k="no target at all" v={fmt(s.noTarget)}
               n="Routine and Uncategorised carry no timeframe, so nothing here can be late" />
      <Readout icon={Clock} k="median wait" v={fmt(s.median)} unit="days"
               n={`longest ${fmt(s.longest)} days`} />
      {/* The guarantee this carries, one number for the whole hospital-day and
          therefore one that cannot reorder anyone, was stated in four separate
          paragraphs across this file, the graph legend and the patient page. It
          belongs on the number, once. */}
      <Readout icon={Gauge} k="α · weight on urgency" v={d ? d.alpha.toFixed(3) : '—'}
               n={d ? 'hospital-day scope · cannot reorder anyone' : decNote ?? undefined} />
      <Readout icon={Activity} k="scarcity" v={d ? d.scarcity.toFixed(3) : '—'}
               n={d ? `read as ${d.capacity_direction} · ADR-007` : decNote ?? undefined} />
      <Readout icon={Stethoscope} k="awaiting triage" v={fmt(s.awaitingTriage)}
               n={`${fmt(s.total - s.awaitingTriage)} triaged · ${fmt(s.suspended)} currently suspended`} />
    </section>
  )
}

function Readout({ icon: Icon, k, v, unit, n, sev = 0 }: {
  icon: typeof Gauge; k: string; v: string; unit?: string; n?: string; sev?: Sev
}) {
  return (
    <div className="ov-ro">
      <div className="lab ov-ro-k"><Icon size={ICON} strokeWidth={1.9} aria-hidden />{k}</div>
      <div className="ov-ro-v num">
        <SevChip sev={sev}>{v}{unit && <span className="ov-ro-u"> {unit}</span>}</SevChip>
      </div>
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
        <Icon size={ICON} strokeWidth={1.9} aria-hidden />
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

/** A horizontal bar with no severity attached: a share, a count, a magnitude
 *  that is context rather than a state. The number always sits beside it. */
function Bar({ v, max = 1 }: { v: number; max?: number }) {
  const w = max > 0 ? Math.min(100, Math.max(0, (v / max) * 100)) : 0
  return (
    <span className="ov-bar" aria-hidden>
      <i className="ov-bar-f" style={{ width: `${w}%` }} />
    </span>
  )
}

/** A 0–1 pressure that IS a state, drawn on the one severity scale. */
function SevMeter({ v, sev, empty, label }: {
  v: number | null; sev: Sev; empty: string; label: string
}) {
  if (v == null) return <span className="ov-none">{empty}</span>
  return (
    <span className="ov-inline">
      <SevBar sev={sev} value={v} height={8} label={label} />
      <span className="num ov-inline-n">{v.toFixed(2)}</span>
    </span>
  )
}

/** A 0–1 pressure carrying no severity: the agent's own working, shown as the
 *  agent's. Neutral, because a busy ward is not an Urgent referral. */
function Meter({ v, empty }: { v: number | null; empty: string }) {
  if (v == null) return <span className="ov-none">{empty}</span>
  return (
    <span className="ov-inline">
      <Bar v={v} />
      <span className="num ov-inline-n">{v.toFixed(2)}</span>
    </span>
  )
}

/* --- clinic pressure has two meanings at 1.0 ------------------------------ */

/** capacity-agent/capacity_agent/scoring.py:93 returns exactly 1.0 when
 *  `slots_total` is 0, so "every slot taken" and "no clinic ran that day" are
 *  the same number. Only the session behind it can tell them apart. */
function citedSession(c: Clinic | undefined): Session | undefined {
  if (!c?.cited_session_date) return undefined
  return c.sessions.find((x) => x.session_date === c.cited_session_date)
}
const noSlots = (c: Clinic | undefined): boolean => citedSession(c)?.slots_total === 0
/** The cited session is not in the series returned, so 1.0 cannot be resolved. */
const pressureUnresolved = (c: Clinic | undefined): boolean =>
  !!c?.cited_session_date && citedSession(c) == null && c.cited_pressure === 1

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
           note={`${specs.length} specialties · core.ref_specialties`}>
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
              <th className="c-bar">Ward pressure<span className="ov-th-sub">agent · beds and escalation, per specialty</span></th>
              <th className="c-bar">Clinic pressure<span className="ov-th-sub">booked ÷ total, cited session</span></th>
              <th className="c-n">Capacity score<span className="ov-th-sub">agent · identical within a specialty</span></th>
            </tr>
          </thead>
          <tbody>
            {specs.map((x) => {
              const a = cap.get(x.code)
              const clinicP = a?.clinic ?? x.clinic?.cited_pressure ?? null
              // 0601 is refused by the URGENCY agent, so it is never PLACED.
              // Capacity still scored it. NEWS2 is validated in
              // adults. A coverage statement, not a missing number.
              const isRefused = !a && rowsRefused(refused, x.code, d)
              const empty = isRefused ? 'not ranked' : noRun ? 'no run' : '—'
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
                  {/* ward_pressure is 0.6 x occupancy + 0.4 x an escalation
                      flag, not an occupancy, so the 85% line does not apply to
                      it and neither does sevOccupancy. It stays the agent's
                      working. The occupancy itself is graded, on the ward
                      table, against the line it belongs to. */}
                  <td className="c-bar"><Meter v={a?.ward ?? null} empty={empty} /></td>
                  <td className="c-bar">
                    {noSlots(x.clinic)
                      ? <span className="ov-none">no clinic that day</span>
                      : <SevMeter v={clinicP} sev={sevBooked(clinicP)} empty="—"
                                  label={`clinic ${pct(clinicP ?? 0, 0)} booked on the cited session`} />}
                  </td>
                  <td className="c-n num">
                    {/* The urgency agent refused this specialty; the capacity
                        agent did not, and scored every referral in 0601. What
                        is absent is a PLACEMENT, so that is what the cell says. */}
                    {a ? a.score.toFixed(3) : <span className="ov-none">{empty}</span>}
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
                  ? `α ${d.alpha.toFixed(3)} · scarcity ${d.scarcity.toFixed(3)}: one pair of numbers for the whole hospital-day`
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

/* --- 3. against the national picture -------------------------------------- */

function NationalPanel({ s }: { s: ReturnType<typeof summarise> }) {
  const maxShare = Math.max(
    ...s.waitBands.map((b) => Math.max(b.share, s.total ? b.here / s.total : 0)),
  )
  return (
    <Panel icon={Layers} title="Against the national picture"
           note="adjusted wait, NTPF bands"
           cite={`NTPF Outpatient Waiting List by Speciality · OpenData_OPNational02_2026.csv · snapshot ${NTPF_SNAPSHOT} · ${fmt(NTPF_TOTAL)} people across the 57 non-SDC specialties. Both sides are cut on the same day boundaries: 183 / 365 / 548.`}>
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
  const all = list.slice(1).map((d, i) => ({ date: d.date, add: d.referrals - list[i].referrals }))
  const capped = all.length > INTAKE_COLUMNS
  const deltas = capped ? all.slice(-INTAKE_COLUMNS) : all
  const maxAdd = Math.max(...deltas.map((x) => x.add), 1)
  const note = list.length
    ? capped
      ? `${fmt(list.length)} days holding a cohort · last ${INTAKE_COLUMNS} charted`
      : `${fmt(list.length)} days holding a cohort`
    : undefined

  return (
    <Panel icon={TrendingUp} title="Intake" note={note}
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
            {/* One label per column rather than every delta concatenated into a
                single ~900-character string, which is what a 60-day series used
                to hand a screen reader. */}
            <div className="ov-chart-wrap">
              <div className="ov-cols-chart" role="list"
                   aria-label={`Referrals added per day, ${fmt(deltas.length)} days`}>
                {deltas.map((x) => (
                  <div className={'ov-col' + (x.date === date ? ' is-on' : '')} key={x.date}
                       role="listitem" aria-label={`${shortDate(x.date)}: ${x.add} added`}>
                    <span className="ov-col-n num" aria-hidden>{x.add > 0 ? `+${x.add}` : '0'}</span>
                    <span className="ov-col-track" aria-hidden>
                      <i style={{ height: `${(x.add / maxAdd) * 100}%` }} />
                    </span>
                    <span className="ov-col-k num" aria-hidden>{dayNum(x.date)}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </PanelState>
    </Panel>
  )
}

/* --- 5. staleness, drawn --------------------------------------------------- */

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
           cite="One set of vitals per person, taken when the referral letter arrived and never revisited. A normal reading this old is an absence of information, not reassurance.">
      <PanelState q={ops}>
        {age && (
          <>
            <div className="ov-mini">
              <Mini k="median" v={fmt(age.median)} u="d" sev={sevReadingAge(age.median)} />
              <Mini k="mean" v={fmt(age.mean)} u="d" sev={sevReadingAge(age.mean)} />
              <Mini k="oldest" v={fmt(age.max)} u="d" sev={sevReadingAge(age.max)} />
              <Mini k="over 1 year" v={fmt(age.over_1y)}
                    sev={age.over_1y > 0 ? sevReadingAge(365) : 0} />
              <Mini k="over 2 years" v={fmt(age.over_2y)}
                    sev={age.over_2y > 0 ? sevReadingAge(730) : 0} />
            </div>
            {ages.length > 0 && (
              <div className="ov-hist">
                {hist.map((h) => {
                  const sev = sevReadingAge(h.lo)
                  // Where the rule is drawn and where the ramp steps are the
                  // same fact, so they are read from the same place. This was
                  // `h.lo >= 365`, a boundary re-derived beside the scale that
                  // already owns it: sevReadingAge is what "a year old" means
                  // here, and 365 is only ever its argument. The same test
                  // List.tsx:477 uses to count year-old readings.
                  const pastYear = sev >= sevReadingAge(365)
                  return (
                    <div className={'ov-hist-row' + (pastYear ? ' is-past-year' : '')} key={h.key}>
                      <span className="ov-hist-k">{h.key}</span>
                      <SevBar sev={sev} value={h.n / maxN} height={8}
                              label={`${h.key}: ${fmt(h.n)} readings`} />
                      <span className="num ov-hist-n">{fmt(h.n)}</span>
                    </div>
                  )
                })}
                <div className="ov-hist-mark">
                  below the rule: a year old or older,{' '}
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

function Mini({ k, v, u, sev = 0 }: { k: string; v: string; u?: string; sev?: Sev }) {
  return (
    <div className="ov-mini-i">
      <div className="ov-mini-v num">
        <SevChip sev={sev}>{v}{u && <span className="ov-mini-u">{u}</span>}</SevChip>
      </div>
      <div className="lab">{k}</div>
    </div>
  )
}

/* --- 6. the rule board, in summary ---------------------------------------- */

function RulePanel({ d, decNote, reference, onOpenList }: {
  d: Decision | undefined; decNote: string | null
  reference: Reference | undefined; onOpenList: () => void
}) {
  if (!d) {
    return (
      <Panel icon={Activity} title="Rules" note={decNote ?? undefined}>
        <p className="ov-quiet">No rule has been tested against this hospital-day.</p>
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
  // split out, because "past a CRT target" and "past the triage turnaround
  // window" are different claims and only the first is what the readout band
  // above counts as past target
  const crtBreached = d.rankings.filter((r) =>
    failed(r.rule_checks).some((c) => c.rule_id.startsWith('RULE-CRT-'))).length
  // EVERY rule in core.ref_rules, tested or not.
  //
  // This was filtered to `tally.has(id) || isWholeList(...)`, which kept a rule
  // only when some referral carried a check for it. A per-referral rule that
  // nothing was ever tested against therefore vanished from this board, while
  // DecisionRecord.tsx -- drawn straight from reference.rules -- went on
  // reporting the same rule as "not tested". Two audit surfaces disagreeing
  // about whether a rule exists is worse than either answer on its own.
  //
  // The filter also made the "not tested" branch below unreachable: any id that
  // survived it either had tested >= 1 or took the whole-list path, so the one
  // case the branch was written for could not occur.
  const ids = (reference?.rules ?? []).map((r) => r.rule_id)
  // Still a union, never the reference alone: a rule the coordinator tested
  // that core.ref_rules does not carry is a fact about this decision and keeps
  // its place, with whatever statement the reference can give it.
  for (const id of tally.keys()) if (!ids.includes(id)) ids.push(id)
  const untested = ids.filter((id) => !isWholeList(reference, id) && !tally.has(id)).length
  const perReferral = [...tally.entries()]
    .filter(([id]) => !isWholeList(reference, id))
    .reduce((a, [, b]) => a + b.tested, 0)

  return (
    <Panel icon={Activity} title="Rules"
           note={`${fmt(ids.length)} rules · ${fmt(perReferral)} per-referral checks`}>
      {/* The board is drawn from the reference, so it has a state the decision
          cannot fill: the rules have not arrived yet. Saying so is not the same
          as a decision that tested nothing. */}
      {!reference?.rules?.length && (
        <p className="ov-quiet">
          core.ref_rules has not arrived, so this board shows only the rules this decision
          carried a check for.
        </p>
      )}
      <div className="ov-rules" tabIndex={0} role="group" aria-label="Rule board">
        {ids.map((id) => {
          const t = tally.get(id) ?? { tested: 0, failed: 0 }
          const whole = isWholeList(reference, id)
          const verdict = WHOLE_LIST_VERDICT[id]
          const held: boolean | null = whole
            ? (verdict ? verdict(d) : null)
            : t.tested === 0 ? null : t.failed === 0
          return (
            <div className="ov-rule" key={id}>
              <div className="ov-rule-top">
                <span className="num ov-rule-id">{id}</span>
                {held == null ? (
                  // TWO ways to reach "no verdict", and they are different
                  // claims: a per-referral rule that no referral was tested
                  // against, and a whole-list rule this decision payload
                  // carries no verdict field for. The word matches
                  // DecisionRecord.tsx, so the two audit surfaces read alike.
                  <span className="ov-verdict is-none">
                    <Minus size={ICON} strokeWidth={2.5} aria-hidden />
                    {whole ? 'no verdict' : 'not tested'}
                  </span>
                ) : held ? (
                  <span className="ov-verdict is-ok">
                    <Check size={ICON} strokeWidth={2.5} aria-hidden />holds
                  </span>
                ) : (
                  <SevChip sev={sevBreach(held)}>
                    <TriangleAlert size={ICON} strokeWidth={2.25} aria-hidden />
                    {whole ? 'violated' : breachPhrase(id, t.failed)}
                  </SevChip>
                )}
              </div>
              <div className="ov-rule-st">{ruleStatement(reference, id)}</div>
              <div className="ov-rule-m num">
                {whole
                  ? verdict
                    ? 'tested once, over the whole list'
                    : 'a whole-list rule this decision carries no verdict field for'
                  : t.tested === 0
                    ? 'not tested against any referral'
                    : `${fmt(t.failed)} of ${fmt(t.tested)} tested`}
              </div>
            </div>
          )
        })}
      </div>
      <div className="ov-rule-foot">
        {/* This is 131 while the readout band says 130 past target, and the two
            differ for a real reason: 130 referrals are past a CRT target, and
            one more sat untriaged past the 21-day turnaround window with no
            category and therefore no target at all. Said, rather than left as
            two numbers a page apart. */}
        <span className="num">{fmt(carrying)}</span> of{' '}
        <span className="num">{fmt(d.rankings.length)}</span> placed referrals carry at least
        one breached rule: <span className="num">{fmt(crtBreached)}</span> past a CRT target
        {carrying > crtBreached && (
          <>, and <span className="num">{fmt(carrying - crtBreached)}</span> past the triage
          turnaround window with no category to be late against</>
        )}.
        {/* An untested rule is not a passing rule, and the board no longer
            hides it. Counted here so the reader is told the board holds a rule
            this day says nothing about, without having to scan for it. */}
        {untested > 0 && (
          <span>
            <span className="num">{fmt(untested)}</span>
            {untested === 1
              ? ' rule in core.ref_rules was tested against no referral on this day, so this'
                + ' hospital-day says nothing about whether it holds.'
              : ' rules in core.ref_rules were tested against no referral on this day, so this'
                + ' hospital-day says nothing about whether they hold.'}
          </span>
        )}
        <button className="ov-link" onClick={onOpenList}>
          Open the ranked order
        </button>
      </div>
    </Panel>
  )
}

/* --- 7. clinic capacity ---------------------------------------------------- */

function ClinicPanel({ ops, reference, d, date }: {
  ops: OpsQuery
  reference: Reference | undefined
  d: Decision | undefined
  date: string
}) {
  const clinics = ops.data?.clinics ?? []
  const cap = agentCapacity(d)
  const cited = clinics.map((c) => c.cited_session_date).filter((x): x is string => x != null)
  const citedDays = [...new Set(cited.map(dayOf))]

  return (
    <Panel icon={CalendarDays} title="Clinic capacity"
           note={clinics.length
             ? `${clinics.length} clinics · cited ${citedDays.length === 1 ? shortDate(citedDays[0]) : 'session marked'}`
             : undefined}
           cite={'DATASET_README.md:623: "most outpatient referrals need a clinic appointment, not a bed, so this is where the real constraint usually sits". The agent read ONE session per clinic; every other session in the series is context and was not scored.'}>
      <PanelState q={ops}>
        <AsOf what="Cited clinic sessions" taken={cited} selected={date}
              source="core.clinic_sessions is read latest-first with no date filter, so every hospital-day is served this same series." />
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
                const empty = noSlots(c)
                const unresolved = pressureUnresolved(c)
                // booked + available must account for every slot. When it does
                // not, the row's arithmetic is broken and the pressure drawn
                // from it cannot be trusted.
                const slotsHold = c.slots_booked + c.slots_available === c.slots_total
                const off = c.cited_session_date != null && dayOf(c.cited_session_date) !== date
                return (
                  <tr key={c.clinic_code ?? c.specialty_hipe}>
                    <td className="c-name">{specialtyName(reference, c.specialty_hipe)}</td>
                    <td className="num c-dim">{c.clinic_code ?? '—'}</td>
                    <td className="c-n num">{fmt(c.slots_booked)}<span className="ov-of"> of {fmt(c.slots_total)}</span></td>
                    <td className="c-n num">
                      {slotsHold ? fmt(c.slots_available) : (
                        <SevChip sev={SEV_INTEGRITY}
                                 title={`${c.slots_booked} booked plus ${c.slots_available} free is not ${c.slots_total}`}>
                          {fmt(c.slots_available)}
                        </SevChip>
                      )}
                    </td>
                    <td className="c-bar">
                      <span className="ov-inline">
                        <Bar v={ratio} />
                        <span className="num ov-inline-n">{pct(ratio, 0)}</span>
                      </span>
                    </td>
                    <td><Sessions clinic={c} /></td>
                    <td className="c-n num">
                      {c.cited_session_date == null
                        ? <span className="ov-none">none cited</span>
                        : off
                          ? <SevChip sev={SEV_INTEGRITY} tone="quiet"
                                     title={`not ${longDate(date)}, the day selected`}>
                              {shortDate(c.cited_session_date)}
                            </SevChip>
                          : <span className="ov-cited-tag">{shortDate(c.cited_session_date)}</span>}
                    </td>
                    <td className="c-n num">
                      {empty ? (
                        // 1.0 here is "no clinic ran", not "full". It must not
                        // wear the same mark as a clinic with every slot taken.
                        <span className="ov-none">no clinic that day</span>
                      ) : (
                        <>
                          <SevChip sev={sevBooked(c.cited_pressure)}>{pct(c.cited_pressure, 0)}</SevChip>
                          {unresolved && (
                            <span className="ov-sub">full, or no slots at all: the cited
                            session is not in the series returned</span>
                          )}
                        </>
                      )}
                    </td>
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
 *  marked in clay, the single accent on this page. The series scrolls inside
 *  its own cell rather than pushing the table: 60 sessions at 11px each is
 *  660px inside a cell that may not wrap. */
function Sessions({ clinic }: { clinic: Clinic }) {
  const ss = clinic.sessions
  if (!ss.length) return <span className="ov-none">no sessions</span>
  const share = (x: Session) => (x.slots_total ? x.slots_booked / x.slots_total : 0)
  const shares = ss.map(share)
  const lo = Math.round(Math.min(...shares) * 100)
  const hi = Math.round(Math.max(...shares) * 100)
  const c = ss.find((x) => x.session_date === clinic.cited_session_date)
  // Bounded: a summary, not every session concatenated into one string.
  const label = `Booked share across ${ss.length} sessions, `
    + `${shortDate(ss[0].session_date)} to ${shortDate(ss[ss.length - 1].session_date)}, `
    + `${lo}% to ${hi}%.`
    + (c ? ` Cited session ${shortDate(c.session_date)}: ${Math.round(share(c) * 100)}%.` : '')
  return (
    <span className="ov-sess">
      <span className="ov-spark" role="img" aria-label={label}>
        {ss.map((x) => (
          <span key={x.session_date}
                className={'ov-spark-c' + (x.session_date === clinic.cited_session_date ? ' is-cited' : '')}>
            <i style={{ height: `${Math.max(4, share(x) * 100)}%` }} />
          </span>
        ))}
      </span>
      <span className="ov-spark-k num">
        {shortDate(ss[0].session_date)}–{shortDate(ss[ss.length - 1].session_date)}
      </span>
    </span>
  )
}

/* --- 8. ward pressure ------------------------------------------------------ */

function WardPanel({ ops, reference, date }: {
  ops: OpsQuery
  reference: Reference | undefined
  date: string
}) {
  const wards = ops.data?.wards ?? []
  const snapshots = wards.map((w) => w.snapshot)
  const snapDays = [...new Set(snapshots.map(dayOf))]
  const totals = wards.reduce((a, w) => ({
    occupied: a.occupied + (w.occupied ?? 0), free: a.free + (w.free ?? 0),
    outliers: a.outliers + w.outliers, dtoc: a.dtoc + w.dtoc, surge: a.surge + w.surge,
    over9: a.over9 + w.over_9h, over24: a.over24 + w.over_24h,
  }), { occupied: 0, free: 0, outliers: 0, dtoc: 0, surge: 0, over9: 0, over24: 0 })

  return (
    <Panel icon={BedDouble} title="Ward pressure"
           note={wards.length
             ? `${wards.length} wards · ${snapDays.length === 1 ? shortDate(snapDays[0]) : 'mixed snapshots'}`
             : undefined}
           cite={`${SAFE_OCCUPANCY}% safe-operating threshold: Bagust, Place & Posnett, BMJ 1999;319:155-8. One snapshot per ward, so there is no bed series behind α.`}>
      <PanelState q={ops}>
        <AsOf what="Ward figures" taken={snapshots} selected={date}
              source="core.bed_status is read latest-first with no date filter, so every hospital-day is served this same snapshot." />
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
              {wards.map((w) => <WardRow key={w.ward_id} w={w} reference={reference} date={date} />)}
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

function WardRow({ w, reference, date }: {
  w: Ward; reference: Reference | undefined; date: string
}) {
  // Absence of information is not Green. A ward that did not report an
  // escalation status used to be drawn with the routine swatch and the word
  // "Green", which is the same class of error as calling a 200-day-old normal
  // reading reassuring.
  const gar = w.gar_status as keyof typeof GAR_WORD | null
  const sev = sevOccupancy(w.occupancy_pct)
  const over = w.occupancy_pct >= SAFE_OCCUPANCY
  const line = `${over ? 'over' : 'under'} the ${SAFE_OCCUPANCY}% line`
  const also = w.specialties.filter((c) => !w.primary_for.includes(c))
  // occupied + free is the census occupancy_pct is computed against. When the
  // three disagree the percentage beside them is not describing this ward.
  const censusHolds = w.occupied == null || w.free == null || w.census == null
    || w.occupied + w.free === w.census
  const off = dayOf(w.snapshot) !== date
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
      {/* nowrap is inherited from .ov-t td, and one ward backing six
          specialties is ~600px on a single unbreakable line. It wraps. */}
      <td className="c-dim c-wrap">
        {also.length ? also.map((c) => specialtyName(reference, c)).join(', ') : <span className="ov-none">—</span>}
      </td>
      <td className="c-bar">
        <span className="ov-occ">
          <SevBar sev={sev} value={w.occupancy_pct / 100} of={SAFE_OCCUPANCY / 100} height={8}
                  label={`${w.occupancy_pct.toFixed(1)}% occupied, ${line}`} />
          <span className="ov-occ-n">
            <SevChip sev={sev}>
              <span className="num">{w.occupancy_pct.toFixed(1)}%</span>
              <span className="ov-occ-w">{line}</span>
            </SevChip>
          </span>
        </span>
      </td>
      <td className="c-n num">
        {censusHolds ? (w.free ?? '—') : (
          <SevChip sev={SEV_INTEGRITY}
                   title={`${w.occupied} occupied plus ${w.free} free is not the census of ${w.census}`}>
            {w.free ?? '—'}
          </SevChip>
        )}
      </td>
      <td className="c-n num">{w.occupied ?? '—'}</td>
      <td className="c-n num">{fmt(w.outliers)}</td>
      <td className="c-n num">{fmt(w.dtoc)}</td>
      <td className="c-n num">{fmt(w.surge)}</td>
      <td className="c-n num">{fmt(w.over_9h)}</td>
      <td className="c-n num">{fmt(w.over_24h)}</td>
      <td>
        {gar
          ? <span className={'ov-gar is-' + gar}><i aria-hidden />{GAR_WORD[gar]}</span>
          : <span className="ov-none">not reported</span>}
      </td>
      <td className="c-n num c-dim">
        {off ? (
          <SevChip sev={SEV_INTEGRITY} tone="quiet"
                   title={`not ${longDate(date)}, the day selected`}>
            {shortDate(w.snapshot)} {clockTime(w.snapshot)}
          </SevChip>
        ) : (
          <>{shortDate(w.snapshot)} {clockTime(w.snapshot)}</>
        )}
      </td>
    </tr>
  )
}
