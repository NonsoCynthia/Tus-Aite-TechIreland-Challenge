import { useQuery } from '@tanstack/react-query'
import {
  Activity, BedDouble, Building2, CalendarCheck, CalendarDays, Check, Clock, Gauge,
  Layers, ListOrdered, Lock, Minus, Play, Scale, Stethoscope, TrendingUp, TriangleAlert,
  Users,
} from 'lucide-react'
import { api, BANDS, bandOf } from '../lib/api'
import {
  breachPhrase, crtDays, failed, isRefusedPaediatric, rule, ruleStatement, specialtyFull,
  specialtyName,
} from '../lib/ref'
import { Aside } from '../components/Aside'
import { QUIET_OFF_DAY, SevBar, SevChip, SevLegend, SevQuiet } from '../components/Severity'
import {
  SAFE_OCCUPANCY, SEV_INTEGRITY, sevBooked, sevBreach, sevOccupancy, sevReadingAge, type Sev,
} from '../lib/severity'
/** Median wait. ONE home, lib/stats.ts, shared with List.tsx: two copies drift. */
import { median } from '../lib/stats'
import type { CohortReferral, Decision, Reference } from '../lib/types'
import './overview.css'

/* --- constants that are CITED. Everything else is counted from a payload. --- */

/* Safe-operating occupancy -- Bagust, Place & Posnett, BMJ 1999;319:155-8 -- is
   imported from lib/severity, beside the bands that grade against it. ONE
   declaration, or the drawn line drifts from the edge grading the same number. */

/** Colour is never the only channel: the GAR letter always resolves to a word. */
const GAR_WORD = { G: 'Green', A: 'Amber', R: 'Red' } as const

/** --icon-sm: the token floor for an icon that carries meaning. */
const ICON = 14

/** THE QUIET MARKS THIS SURFACE DRAWS, and the only ones its key may show: one,
 *  at SEV_INTEGRITY, for a date that is not the day selected. NOT List's quiet
 *  rule mark -- a rule that fired is drawn SOLID here, so it has no referent.
 *  A module constant, not an inline array: a fresh array re-subscribes the
 *  legend's audit on every render. */
const QUIET_HERE = [QUIET_OFF_DAY]

/** NTPF Outpatient Waiting List by Speciality, OpenData_OPNational02_2026.csv,
 *  snapshot 30/07/2026, in this repo at dataset/generator/calibration/_raw/.
 *  Counted over EVERY row, nothing excluded: a citation is the one thing here a
 *  judge can reproduce. TWO totals, because the file carries two that disagree --
 *  its Total column and its four band columns; the shares are of the band sum,
 *  and the Total is cited beside it rather than reconciled away. 183/365/548 are
 *  the day boundaries every wait in this dataset was cut on. */
const NTPF_SNAPSHOT = '2026-07-30'
/** The Total column, summed over the snapshot. */
const NTPF_TOTAL = 683_553
const NTPF_SPECIALTIES = 58
const NTPF_ROWS = 77
const NTPF_BAND_ROWS = [
  { key: '0–6 months', lo: 0, hi: 183, n: 407_839 },
  { key: '6–12 months', lo: 183, hi: 365, n: 154_166 },
  { key: '12–18 months', lo: 365, hi: 548, n: 71_212 },
  { key: '18 months +', lo: 548, hi: Infinity, n: 50_340 },
] as const
/** DERIVED, never written beside the four counts that are it; so are the shares. */
const NTPF_BAND_TOTAL = NTPF_BAND_ROWS.reduce((a, b) => a + b.n, 0)
const NTPF_BANDS = NTPF_BAND_ROWS.map((b) => ({ ...b, share: b.n / NTPF_BAND_TOTAL }))

/* No referral-day row count is written down: the generator's output file is not
   what gets loaded, so the figure comes from /api/hospital-days. */

/** Day-columns before the chart scrolls: past this, a count label centred on its
 *  track overlaps its neighbours. */
const INTAKE_COLUMNS = 30

/** Bucketed on observation_age's own boundaries. Severity comes from
 *  sevReadingAge, never from these edges. */
const AGE_BUCKETS = [
  { key: 'under 3 months', lo: 0, hi: 90 },
  { key: '3–6 months', lo: 90, hi: 180 },
  { key: '6–12 months', lo: 180, hi: 365 },
  { key: '1–2 years', lo: 365, hi: 730 },
  { key: 'over 2 years', lo: 730, hi: Infinity },
] as const

/** Rules whose subject is the whole list, and where each verdict lives on the
 *  decision. A lookup, not a two-way branch: a new one with no entry here has no
 *  verdict to show, rather than rendering another rule's under its name. */
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

/* --- Aggregation. A breach is always of the referrals that HAVE a target. --- */

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

/** What /api/decision returns in `excluded`: the whole banded cohort row, of
 *  which types.ts declares only the two fields the rest of the app reads. Every
 *  field here is optional and checked, so a payload that drops them degrades to
 *  "not scored", never to a wrong number. */
type ExcludedRow = Decision['excluded'][number] & Partial<{
  specialty_hipe: string
  capacity_score: number | null
}>

/** What the capacity agent computed, per SPECIALTY. These three are identical for
 *  every referral in a specialty, so none may be drawn against a person or called
 *  the hospital's figure.
 *
 *  BOTH LISTS, not just `rankings`: a refused specialty produces no ranking, yet
 *  ranking.py:147-155 builds the distinct-capacity dict from every banded
 *  referral, so its score is one of those whose mean IS scarcity. `placed` says
 *  which list a row came from; an excluded one carries no ward/clinic split. */
function agentCapacity(d: Decision | undefined) {
  const m = new Map<string, {
    ward: number | null; clinic: number | null; score: number; placed: boolean
  }>()
  for (const r of d?.rankings ?? []) {
    if (m.has(r.specialty_hipe)) continue
    m.set(r.specialty_hipe, {
      ward: r.capacity_detail?.ward_pressure ?? null,
      clinic: r.capacity_detail?.clinic_pressure ?? null,
      score: r.capacity_score,
      placed: true,
    })
  }
  for (const e of (d?.excluded ?? []) as ExcludedRow[]) {
    const code = e.specialty_hipe
    if (code == null || m.has(code) || typeof e.capacity_score !== 'number') continue
    // No capacity_detail on an excluded row: null is "not carried", said in words.
    m.set(code, { ward: null, clinic: null, score: e.capacity_score, placed: false })
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

/* --- Reconciliation. A gap outranks any clinical state: SEV_INTEGRITY. --- */

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

/** The hospital overview as an instrument panel. Five rules hold on every panel:
 *  a breach is of the referrals that have a target; a reading's age travels with
 *  the reading; every colour carries a word; capacity is one number for the whole
 *  hospital-day (priority.py guarantees it cannot reorder two people); and every
 *  panel says the day its figures were taken on, which is not always the day
 *  selected above. */
export function Overview({ hospital, date, name, reference, onOpenList }: {
  hospital: string; date: string; name: string
  reference: Reference | undefined
  onOpenList: () => void
}) {
  const cohort = useQuery({
    queryKey: ['cohort', hospital, date],
    queryFn: () => api.cohort(hospital, date),
  })
  // ~3.3s uncached: every ward, every clinic series, one context per referral.
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
  // A 404 is the ordinary "nothing has run yet" state; anything else is a failed
  // read of a decision that may exist. isError alone cannot tell them apart.
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

      {/* ONE key strip for the whole surface, and the same component the marks
          are built from so the two cannot drift. BELOW the reconciliation band:
          a strip between the header and that role="alert" pushes the one thing
          that outranks everything else down the screen.

          THE QUIET GROUP MUST BE PASSED. The strip's default is List's mark,
          which this surface never draws, so with no prop the key teaches the
          wrong step and omits the only quiet mark on the page. */}
      <div className="ov-key">
        <SevLegend quiet={QUIET_HERE} />
        <ReadoutBand s={s} d={d} decNote={decNote} reference={reference} />
      </div>

      <div className="ov-cols">
        <SpecialtyPanel specs={specs} s={s} reference={reference} ops={ops} d={d}
                        noRun={noRun} date={date} />
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

/** The loudest thing here: quiet while the counts agree, solid when they do not. */
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

/** With no decision this surface is the whole product: the list, unranked. */
function BeforeRanking({ date, runnable }: { date: string; runnable: string | null | undefined }) {
  const here = runnable == null || runnable === date
  return (
    <section className="ov-before" aria-label="Before ranking">
      <h2 className="ov-before-h">
        <ListOrdered size={ICON} strokeWidth={1.9} aria-hidden />
        Nothing has been ranked for this day
      </h2>
      {/* Only what the table below cannot say: who put those numbers there, and
          what the agent columns do when nothing has run. */}
      <p>
        Everything here was recorded by a clinician, not computed by an agent. With no run,
        α, scarcity, placement and rule verdict read "no run" rather than zero.
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

/** `core.bed_status` and `core.clinic_sessions` are read latest-first with no
 *  date predicate, so every hospital-day is served the same rows. The payload
 *  carries the true date; this panel shows it and says when it is not the day
 *  selected. `source` is a DEFINITION on three panels, so it goes behind the
 *  disclosure; the span and the fact that it differs stay visible. */
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
      <Aside label="where this date comes from"
             summary={<>{what} are as of {span}, not {longDate(selected)}, the day selected above.</>}>
        {source}
      </Aside>
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
      {/* A pass/fail with no magnitude at hospital level -- some referral is past
          its target or none is -- which is exactly what sevBreach grades. */}
      <Readout icon={TriangleAlert} k="past target" v={fmt(s.breached)}
               sev={sevBreach(s.breached === 0)}
               n={`${pct(s.withTarget ? s.breached / s.withTarget : 0, 0)} of the ${fmt(s.withTarget)} that have one`} />
      <Readout icon={Layers} k="no target at all" v={fmt(s.noTarget)}
               n="Routine and Uncategorised carry no timeframe, so nothing here can be late" />
      <Readout icon={Clock} k="median wait" v={fmt(s.median)} unit="days"
               n={`longest ${fmt(s.longest)} days`} />
      {/* One alpha for the whole hospital-day, so it cannot reorder anyone. */}
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

/** `cite` STAYS on the caption -- the claim and its source -- and `citeMore` is
 *  the argument for it, behind the toggle. A one-line caption passes `cite`
 *  alone: a disclosure over one sentence is more chrome than the sentence. */
function Panel({ icon: Icon, title, note, cite, citeLabel, citeMore, children }: {
  icon: typeof Gauge; title: string; note?: string; cite?: string
  /** The toggle's visible text: a noun phrase naming what opens. */
  citeLabel?: string
  /** The half of the caption that is a definition. Omit it and `cite` is plain. */
  citeMore?: React.ReactNode
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
      {cite && (
        <div className="ov-cite">
          {citeMore
            ? (
              <Aside label={citeLabel ?? 'where this figure comes from'} summary={cite}>
                {citeMore}
              </Aside>
            )
            : cite}
        </div>
      )}
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

/** A bar with no severity: a magnitude that is context, not a state. */
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

/** A 0–1 pressure carrying no severity: the agent's own working, neutral because
 *  a busy ward is not an Urgent referral. `title` is an aside on the word standing
 *  in for a missing number, never the only place it is explained. */
function Meter({ v, empty, title }: { v: number | null; empty: string; title?: string }) {
  if (v == null) return <span className="ov-none" title={title}>{empty}</span>
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

function SpecialtyPanel({ specs, s, reference, ops, d, noRun, date }: {
  specs: SpecRow[]
  s: ReturnType<typeof summarise>
  reference: Reference | undefined
  ops: OpsQuery
  d: Decision | undefined
  noRun: boolean
  date: string
}) {
  const maxN = Math.max(...specs.map((x) => x.n), 1)
  const cap = agentCapacity(d)
  const scored = [...cap.values()]
  const unplaced = scored.filter((c) => !c.placed).length
  /* Scarcity is the mean of the distinct specialty capacity scores, refused ones
     included (ranking.py:147-155). CHECKED, not claimed: reproduced from the
     scores this table prints, and the footer says nothing unless it comes back to
     the decision's own scarcity. ADR-007 fixes the sign convention. */
  const capMean = scored.length ? scored.reduce((a, c) => a + c.score, 0) / scored.length : null
  const scarcityIsMean = d != null && capMean != null
    && d.capacity_direction === 'pressure' && Math.abs(capMean - d.scarcity) < 1e-6
  /* Rows that will draw a clinic figure nothing computed for this day: the cited
     session's own number. Collected so the panel can date them all at once. */
  const citedFallback = specs
    .filter((x) => cap.get(x.code)?.clinic == null && !noSlots(x.clinic)
      && x.clinic?.cited_pressure != null && x.clinic?.cited_session_date != null)
    .map((x) => x.clinic!.cited_session_date!)

  return (
    <Panel icon={Stethoscope} title="By specialty"
           note={`${specs.length} specialties · core.ref_specialties`}>
      {/* A clinic pressure drawn undated in a table whose header names the
          selected day claims that day. The cited session can be in the FUTURE
          for most hospital-days, so it is dated in the cell and here. */}
      {citedFallback.length > 0 && (
        <AsOf what="Clinic sessions cited with no agent figure"
              taken={citedFallback} selected={date}
              source="core.clinic_sessions is read latest-first with no date filter, so every hospital-day is served this same series. Those cells carry that date and are not graded: nothing computed a clinic pressure for the day selected." />
      )}
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
              <th className="c-bar">Clinic pressure<span className="ov-th-sub">agent's figure · else the cited session, dated</span></th>
              <th className="c-n">Capacity score<span className="ov-th-sub">agent · identical within a specialty</span></th>
            </tr>
          </thead>
          <tbody>
            {specs.map((x) => {
              const a = cap.get(x.code)
              // What the capacity agent produced FOR THIS HOSPITAL-DAY and only
              // that. The cited session's own figure is a different claim, below.
              const agentClinic = a?.clinic ?? null
              const citedP = noSlots(x.clinic) ? null : x.clinic?.cited_pressure ?? null
              const citedDay = x.clinic?.cited_session_date
                ? dayOf(x.clinic.cited_session_date) : null
              // A standing property of the SPECIALTY, not of a run: 0601 is
              // refused unconditionally and /api/decision 404s on most days. NOT
              // "produced no ranking", a different fact that answers "not ranked"
              // in columns the capacity agent has filled.
              const refused = isRefusedPaediatric(x.code)
              // THREE absences, and not the same claim: nothing ran; this
              // specialty is in no decision list; or the working is not carried.
              const empty = !d ? (noRun ? 'no run' : '—') : a ? 'not carried' : 'not scored'
              const notCarried = a && !a.placed
                ? 'the capacity agent scored this specialty; the decision carries the score for'
                  + ' a referral it did not place, without the ward and clinic halves behind it'
                : 'the decision carries this specialty’s capacity score but not the ward and'
                  + ' clinic halves behind it'
              return (
                <tr key={x.code}>
                  <td className="c-name">
                    {specialtyFull(reference, x.code)}
                    {refused && (
                      <span className="ov-sub">
                        no urgency score: the agent refuses this specialty, NEWS2 is validated
                        in adults
                      </span>
                    )}
                  </td>
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
                  {/* ward_pressure is 0.6 x occupancy + 0.4 x an escalation flag,
                      not an occupancy, so the safe line and sevOccupancy do not
                      apply to it. Occupancy itself is graded on the ward table. */}
                  <td className="c-bar">
                    <Meter v={a?.ward ?? null} empty={empty}
                           title={a && a.ward == null ? notCarried : undefined} />
                  </td>
                  <td className="c-bar">
                    {noSlots(x.clinic)
                      ? <span className="ov-none">no clinic that day</span>
                      : agentClinic != null
                        // Graded: the day it grades is the day at the top.
                        ? <SevMeter v={agentClinic} sev={sevBooked(agentClinic)} empty="—"
                                    label={`clinic ${pct(agentClinic, 0)} booked on the cited session`} />
                        : citedP != null && citedDay != null
                          // The cited session's own number, with its own date.
                          // NOT graded: a step means "how far past a line THIS
                          // day is", and the same figure is graded one panel down
                          // under a column that names the session, not the day.
                          ? (
                            <>
                              <Meter v={citedP} empty="—" />
                              <span className="ov-cited-on">
                                cited session{' '}
                                {citedDay === date
                                  ? <span className="num">{shortDate(citedDay)}</span>
                                  : (
                                    <SevQuiet mark={QUIET_OFF_DAY}
                                              title={`not ${longDate(date)}, the day selected`}>
                                      {shortDate(citedDay)}
                                    </SevQuiet>
                                  )}
                              </span>
                            </>
                          )
                          // Withheld rather than drawn undated.
                          : <span className="ov-none">{citedP != null ? 'no session cited' : empty}</span>}
                  </td>
                  <td className="c-n num">
                    {/* The urgency agent refuses this specialty; the capacity
                        agent does not. What is absent is a PLACEMENT, so that is
                        what the cell says, and the score is shown. */}
                    {a ? (
                      <>
                        {a.score.toFixed(3)}
                        {!a.placed && <span className="ov-sub">scored, not placed</span>}
                      </>
                    ) : <span className="ov-none">{empty}</span>}
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
              <td colSpan={3} className="ov-of ov-foot-wrap">
                {d ? (
                  <>
                    α {d.alpha.toFixed(3)} · scarcity {d.scarcity.toFixed(3)}: one pair of
                    numbers for the whole hospital-day.
                    {scarcityIsMean && (
                      <>
                        {' '}Scarcity is the mean of the {fmt(scored.length)} specialty capacity
                        scores in this table
                        {unplaced > 0 && (
                          <>, the {fmt(unplaced)} scored but not placed included</>
                        )}.
                      </>
                    )}
                  </>
                ) : 'no decision for this hospital-day'}
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

/* --- 3. against the national picture -------------------------------------- */

function NationalPanel({ s }: { s: ReturnType<typeof summarise> }) {
  const maxShare = Math.max(
    ...s.waitBands.map((b) => Math.max(b.share, s.total ? b.here / s.total : 0)),
  )
  return (
    <Panel icon={Layers} title="Against the national picture"
           note="adjusted wait, NTPF bands"
           cite={`NTPF Outpatient Waiting List by Speciality · OpenData_OPNational02_2026.csv · snapshot ${NTPF_SNAPSHOT}.`}
           citeLabel="how this file was counted"
           citeMore={`Every row of it: ${fmt(NTPF_SPECIALTIES)} specialty labels over ${fmt(NTPF_ROWS)} adult and child rows, ${fmt(NTPF_TOTAL)} people by the file's Total column. Its four band columns sum to ${fmt(NTPF_BAND_TOTAL)}, ${NTPF_BAND_TOTAL - NTPF_TOTAL} more; that difference is inside the published file, and the national shares here are of the band sum they are counted from. Both sides are cut on the same day boundaries: 183 / 365 / 548.`}>
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

  // Evidence for the claim above the chart. Null means the read failed, which is
  // not the finding "none were removed", so the line is dropped, not zeroed.
  const rowsHeld = days.data?.referral_days
  const removed = days.data?.removed
  const intakeEvidence = rowsHeld == null || removed == null
    ? undefined
    : removed === 0
      ? `${fmt(rowsHeld)} referral-days are recorded for this hospital, and not one of them carries a removal date.`
      : `${fmt(rowsHeld)} referral-days are recorded for this hospital, and ${fmt(removed)} carry a removal date, so a rise in the counts above is not intake on its own.`

  // The claim follows its own evidence: written unconditionally, "nothing has
  // ever left this list" goes false the day a removal appears.
  const intakeClaim = removed == null
    ? 'Net change per day. Whether anything has left this list could not be read.'
    : removed === 0
      ? 'Net change per day is intake: nothing has ever left this list.'
      : 'Net change per day is arrivals minus departures: some referrals have left this list.'

  return (
    <Panel icon={TrendingUp} title="Intake" note={note}
           cite={intakeClaim}
           citeLabel={intakeEvidence ? 'how intake is counted' : undefined}
           citeMore={intakeEvidence}>
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
            {/* One label per column, not the whole series in one string. */}
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
           cite="A normal reading this old is an absence of information, not reassurance."
           citeLabel="where these readings come from"
           citeMore="One set of vitals per person, taken when the referral letter arrived and never revisited.">
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
                  // Where the rule is drawn and where the ramp steps are one
                  // fact, so both read sevReadingAge; 365 is only its argument.
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
  // split out: only a CRT breach is what the readout band counts as past target
  const crtBreached = d.rankings.filter((r) =>
    failed(r.rule_checks).some((c) => c.rule_id.startsWith('RULE-CRT-'))).length
  // EVERY rule in core.ref_rules, tested or not: filtering to the ones a referral
  // carried a check for drops untested rules while DecisionRecord.tsx still
  // reports them, and makes the "not tested" branch below unreachable.
  const ids = (reference?.rules ?? []).map((r) => r.rule_id)
  // Still a union: a rule tested but absent from core.ref_rules keeps its place.
  for (const id of tally.keys()) if (!ids.includes(id)) ids.push(id)
  const untested = ids.filter((id) => !isWholeList(reference, id) && !tally.has(id)).length
  const perReferral = [...tally.entries()]
    .filter(([id]) => !isWholeList(reference, id))
    .reduce((a, [, b]) => a + b.tested, 0)

  return (
    <Panel icon={Activity} title="Rules"
           note={`${fmt(ids.length)} rules · ${fmt(perReferral)} per-referral checks`}>
      {/* "The rules have not arrived" is a state, and not "tested nothing". */}
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
                  // TWO ways to reach "no verdict", and different claims. Wording
                  // matches DecisionRecord.tsx so the audit surfaces read alike.
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
        {/* This count and the readout band's "past target" differ for a real
            reason -- an untriaged referral can be past the turnaround window with
            no category and so no target -- so it is said, not left to be found. */}
        <span className="num">{fmt(carrying)}</span> of{' '}
        <span className="num">{fmt(d.rankings.length)}</span> placed referrals carry at least
        one breached rule: <span className="num">{fmt(crtBreached)}</span> past a CRT target
        {carrying > crtBreached && (
          <>, and <span className="num">{fmt(carrying - crtBreached)}</span> past the triage
          turnaround window with no category to be late against</>
        )}.
        {/* An untested rule is not a passing rule. Counted here so a reader is
            told the board holds one, rather than having to scan for it. */}
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
           cite="The agent read one session per clinic. Every other session in the series is context and was not scored."
           citeLabel="why the clinic is the constraint"
           citeMore={'DATASET_README.md:625: "most outpatient referrals need a clinic appointment, not a bed, so this is where the real constraint usually sits".'}>
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
                // booked + available must account for every slot; when it does
                // not, the pressure drawn from the row cannot be trusted.
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
                          ? <SevQuiet mark={QUIET_OFF_DAY}
                                      title={`not ${longDate(date)}, the day selected`}>
                              {shortDate(c.cited_session_date)}
                            </SevQuiet>
                          : <span className="ov-cited-tag">{shortDate(c.cited_session_date)}</span>}
                    </td>
                    <td className="c-n num">
                      {empty ? (
                        // 1.0 here is "no clinic ran", not "full", and must not
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
                      {/* Same three absences the By-specialty table draws: a
                          specialty scored but not placed carries no clinic half,
                          and "not scored" over a real capacity score is wrong. */}
                      {cap.get(c.specialty_hipe)?.clinic?.toFixed(3)
                        ?? (
                          <span className="ov-none"
                                title={cap.has(c.specialty_hipe)
                                  ? 'the decision carries this specialty’s capacity score but not the clinic half behind it'
                                  : undefined}>
                            {!d ? 'no run' : cap.has(c.specialty_hipe) ? 'not carried' : 'not scored'}
                          </span>
                        )}
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

/** The session series as columns, the cited one in clay. It scrolls inside its
 *  own cell rather than push the table wider. */
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
  // Absence of information is not Green: a ward that reported no escalation
  // status gets "not reported", never the routine swatch.
  const gar = w.gar_status as keyof typeof GAR_WORD | null
  const sev = sevOccupancy(w.occupancy_pct)
  const over = w.occupancy_pct >= SAFE_OCCUPANCY
  const line = `${over ? 'over' : 'under'} the ${SAFE_OCCUPANCY}% line`
  const also = w.specialties.filter((c) => !w.primary_for.includes(c))
  // occupied + free is the census occupancy_pct is computed against; when the
  // three disagree the percentage is not describing this ward.
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
      {/* nowrap is inherited from .ov-t td, and a ward backing six specialties
          is one unbreakable ~600px line. This cell wraps. */}
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
          <SevQuiet mark={QUIET_OFF_DAY}
                    title={`not ${longDate(date)}, the day selected`}>
            {shortDate(w.snapshot)} {clockTime(w.snapshot)}
          </SevQuiet>
        ) : (
          <>{shortDate(w.snapshot)} {clockTime(w.snapshot)}</>
        )}
      </td>
    </tr>
  )
}
