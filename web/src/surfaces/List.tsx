import { Fragment, useEffect, useMemo, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import { motion, useReducedMotion } from 'motion/react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowDown, ArrowUp, Check, ChevronDown, ChevronRight, PenLine, Search, TriangleAlert,
} from 'lucide-react'
import { api, bandOf, BANDS } from '../lib/api'
import { useNarrow } from '../lib/useNarrow'
import { crtDays, isRefusedPaediatric, ruleStatement, specialtyName } from '../lib/ref'
import { plantedCase } from '../lib/planted'
import { sevBreach, sevReadingAge, sevWaitRatio } from '../lib/severity'
import type { Sev } from '../lib/severity'
/** Median wait. ONE home, lib/stats.ts, shared with Overview.tsx: two copies drift. */
import { median } from '../lib/stats'
import { Aside } from '../components/Aside'
import { SevChip, SevLegend } from '../components/Severity'
import { Override } from '../components/Override'
import type {
  CohortReferral, Citation, Decision, Observation, OverrideRecord, Overrides,
  Ranking, Reference, RuleCheck,
} from '../lib/types'
import './list.css'

/** The ranked list. The sort key is drawn as a structure (SortKeyLadder); step 3,
 *  past target before any score, carries the one clay accent. */

const fmt = (n: number) => n.toLocaleString('en-IE')
const pct = (n: number) => `${Math.round(n * 100)}%`
const clamp01 = (n: number) => Math.max(0, Math.min(1, n))
/** Never "Invalid Date": evidence keys may not be dates at all. */
const dmy = (s: string | null | undefined) => {
  const d = s ? new Date(s) : null
  return d && !Number.isNaN(d.getTime())
    ? d.toLocaleDateString('en-IE', { day: 'numeric', month: 'short', year: 'numeric' })
    : '\u2014'
}
const dmyt = (s: string | null | undefined) => {
  const d = s ? new Date(s) : null
  return d && !Number.isNaN(d.getTime())
    ? d.toLocaleString('en-IE', {
      day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    })
    : '\u2014'
}

/** Rules whose subject is the whole list, not one referral. A per-row chip for
 *  these would imply 305 independent verdicts where the coordinator made one. */
const WHOLE_LIST = new Set(['RULE-ORDER', 'RULE-TIEBREAK'])

/** The numeral always carries the true value, whatever the bar does with it. */
const ratioText = (r: number) => (r >= 10 ? String(Math.round(r)) : r.toFixed(1))

/** NEWS2 typeset so a 7 does not look like a 0: weight and size, no colour. The
 *  total is outside the severity scale by design, so a threshold here would be
 *  invented. A magnitude channel, not a claim. */
const n2Type = (n: number | null): CSSProperties => {
  if (n == null) return {}
  const t = clamp01(n / 17)
  return { fontWeight: 400 + Math.round(t * 300), fontSize: `${(14 + t * 7).toFixed(1)}px` }
}

const UNPLACED = 1e9

/* ------------------------------------------------------------- geometry -- */

/** The table's column widths, in ONE place: min-width is derived from them.
 *
 *  TRAP: `table-layout: fixed` gives the elastic Referral column what is left
 *  after every specified width, and td overflow is `visible` -- so a min-width
 *  below the fixed sum plus COL_REF allots it a negative width and its contents
 *  paint over the Waited column. Never write min-width down as a literal. */
const COL = {
  pos: 76, spine: 140, wait: 200, rule: 240, news: 180,
  triage: 144, ctx: 132, exp: 42,
} as const

/** Referral's floor: a specialty name, a pathway number and a chip on one line. */
const COL_REF = 260

/** The viewport at which the ninth column first fits. THREE chrome terms, and
 *  the third gets forgotten: the table gets what is inside .lst-vp, which has a
 *  1px border of its own on each side (list.css). The rail's border-right is not
 *  a fourth -- `box-sizing: border-box` keeps it inside the 236px grid track.
 *
 *    9 cols  76+140+200+240+180+144+132+42 = 1154 + 260 Referral = 1414
 *    7 cols  76+140+200+240+180+42         =  878 + 260 Referral = 1138
 *    chrome  rail 236 + .pad 2x32 + .lst-vp 2x1 = 302  ->  1414 + 302 = 1716
 *            rail  64 + .pad 2x16 + .lst-vp 2x1 =  98  (app.css @1439)
 *
 *  One pixel low and .lst-vp grows a sideways scrollbar at the very width that
 *  adds the column. Classic (non-overlay) scrollbars are not modelled: a vertical
 *  bar takes ~15px more of the inner width. Triage and Context are the two to
 *  drop below it, both nearly constant down the column and both in the expander. */
const NINE_COL_PX = 1716

const tableMin = (narrow: boolean): number =>
  COL.pos + COL.spine + COL.wait + COL.rule + COL.news
  + (narrow ? 0 : COL.triage + COL.ctx) + COL.exp + COL_REF

type Clin = {
  news2: number | null
  obs_datetime: string | null
  reading_age_days: number | null
  pain: number | null
  mts_category: string | null
  icd10am_code: string | null
}

type Row = CohortReferral & {
  /** The full ranking row, when one exists: rule_checks, citations, α, priority. */
  rank?: Ranking
  clin?: Clin
  /** The override that stands for this pathway, if any. */
  ovr?: OverrideRecord
  /** True only for an override recorded against the decision on screen: an older
   *  one names a position in a list that no longer exists, so it never moves a row. */
  ovrLive: boolean
  exclusion?: string
  /** Index in the displayed order: the system's, with live overrides applied. */
  seq: number
}

type SortKey = 'order' | 'wait' | 'over' | 'news2' | 'age' | 'specialty' | 'pathway' | 'priority'

/** Which way a column reads first. A wait sorts longest-first; a name sorts A–Z. */
const FIRST_DIR: Record<SortKey, 1 | -1> = {
  order: 1, wait: -1, over: -1, news2: -1, age: -1, specialty: 1, pathway: 1, priority: -1,
}
const SORT_NAME: Record<SortKey, string> = {
  order: 'the suggested order', wait: 'days waited', over: 'wait against target',
  news2: 'NEWS2', age: 'reading age', specialty: 'specialty', pathway: 'pathway number',
  priority: 'priority',
}

const TABS = [...BANDS.map((b) => b.key), 'Outside'] as string[]
const TAB_TOKEN: Record<string, string> = {
  Urgent: 'urgent', 'Semi-Urgent': 'semiurgent', Routine: 'routine',
  Uncategorised: 'uncategorised', Outside: 'outside',
}

/* ------------------------------------------------------------------ data -- */

function useList(hospital: string, date: string) {
  const cohort = useQuery({
    queryKey: ['cohort', hospital, date], queryFn: () => api.cohort(hospital, date),
  })
  const ops = useQuery({
    queryKey: ['operations', hospital, date], queryFn: () => api.operations(hospital, date),
    staleTime: Infinity,
  })
  // 404 until a run has produced one: a normal state, not an error.
  const decision = useQuery<Decision>({
    queryKey: ['decision', hospital, date], queryFn: () => api.decision(hospital, date),
    retry: false, staleTime: 5_000,
  })
  const overrides = useQuery<Overrides>({
    queryKey: ['overrides', hospital, date], queryFn: () => api.overrides(hospital, date),
    retry: false,
  })

  /** The coordinator's positions, then this decision's overrides applied oldest
   *  first so the newest wins. Nothing interpolated: a row is in a slot or not. */
  const seqOf = useMemo(() => {
    const m = new Map<string, number>()
    const d = decision.data
    if (!d) return m
    const order = [...d.rankings].sort((a, b) => a.position - b.position)
      .map((r) => r.pathway_number)
    const live = Object.values(overrides.data?.current ?? {})
      .filter((o) => o.decision_id === d.decision_id
        && o.to_position != null && o.to_position !== o.from_position)
      .sort((a, b) => a.created_at.localeCompare(b.created_at))
    for (const o of live) {
      const i = order.indexOf(o.pathway_number)
      if (i < 0) continue
      order.splice(i, 1)
      order.splice(Math.max(0, Math.min(order.length, (o.to_position as number) - 1)), 0,
        o.pathway_number)
    }
    order.forEach((p, i) => m.set(p, i))
    return m
  }, [decision.data, overrides.data])

  /** So the override dialog judges a boundary crossing IN THE LIST THE CLINICIAN
   *  SEES: after one override decision.rankings is a different list, and stores
   *  rule_warning_accepted false for a crossing that did happen. */
  const displayedOrder = useMemo(() => {
    const arr: string[] = []
    for (const [pw, i] of seqOf) arr[i] = pw
    return arr.filter(Boolean)
  }, [seqOf])

  const rows = useMemo<Row[]>(() => {
    if (!cohort.data) return []
    const clinical = ops.data?.clinical ?? {}
    const placed = new Map(decision.data?.rankings.map((r) => [r.pathway_number, r]) ?? [])
    const exc = new Map(decision.data?.excluded.map((e) => [e.pathway_number, e.exclusion_reason]) ?? [])
    const cur = overrides.data?.current ?? {}
    const decId = decision.data?.decision_id
    return cohort.data.referrals.map((r) => {
      const o = cur[r.pathway_number]
      return {
        ...r,
        rank: placed.get(r.pathway_number),
        clin: clinical[r.pathway_number],
        ovr: o,
        ovrLive: !!o && !!decId && o.decision_id === decId,
        exclusion: exc.get(r.pathway_number),
        seq: seqOf.get(r.pathway_number) ?? UNPLACED,
      }
    })
  }, [cohort.data, ops.data, decision.data, overrides.data, seqOf])

  return {
    rows,
    decision: decision.data,
    ops: ops.data,
    opsFailed: ops.isError,
    opsPending: ops.isPending,
    loading: cohort.isPending,
    error: cohort.error,
    displayedOrder,
  }
}

/* --------------------------------------------------------------- helpers -- */

/** The authoritative target, from core.ref_codes, with the cohort's own value
 *  as a fallback for the first paint. 28 and 91 are never written down here. */
const targetOf = (r: Row, ref: Reference | undefined): number | null =>
  crtDays(ref, r.cpc) ?? r.crt_threshold_days

const ratioOf = (r: Row, ref: Reference | undefined): number | null => {
  const t = targetOf(r, ref)
  return t != null && t > 0 ? (r.adjusted_wait_days ?? 0) / t : null
}

function metric(r: Row, key: SortKey, ref: Reference | undefined): number | null {
  switch (key) {
    case 'wait': return r.adjusted_wait_days
    case 'over': return ratioOf(r, ref)
    // The NEWS2 header sorts in every tab, so a score returned in Outside would
    // rank children by the adult scale just refused.
    case 'news2': return isRefusedPaediatric(r.specialty_hipe) ? null : (r.clin?.news2 ?? null)
    case 'age': return r.clin?.reading_age_days ?? null
    case 'priority': return r.rank?.priority ?? null
    default: return null
  }
}

function comparator(sort: { key: SortKey; dir: 1 | -1 }, ranked: boolean, ref: Reference | undefined) {
  return (a: Row, b: Row): number => {
    let d = 0
    if (sort.key === 'order') {
      d = ranked && (a.seq < UNPLACED || b.seq < UNPLACED)
        ? a.seq - b.seq
        : a.referral_date.localeCompare(b.referral_date)
    } else if (sort.key === 'specialty') {
      d = specialtyName(ref, a.specialty_hipe).localeCompare(specialtyName(ref, b.specialty_hipe))
    } else if (sort.key === 'pathway') {
      d = a.pathway_number.localeCompare(b.pathway_number)
    } else {
      const va = metric(a, sort.key, ref)
      const vb = metric(b, sort.key, ref)
      // a missing value is not a zero, and never sorts to the top of a column
      if (va == null && vb == null) d = 0
      else if (va == null) return 1
      else if (vb == null) return -1
      else d = va - vb
    }
    if (d !== 0) return d * sort.dir
    return a.pathway_number.localeCompare(b.pathway_number)
  }
}

/* ------------------------------------------------------------ tied priority -- */

/** Two rows, adjacent in the suggested order, whose priorities print the same. At
 *  three decimals a pair separated from the fourth decimal looks like one equal to
 *  the last bit, and the surface then claims priority decided an order referral
 *  date decided. Both term differences travel with the margin: they pull opposite
 *  ways and the margin is their residue, so a winner alone is a half truth. */
type Tie = {
  hi: string; lo: string
  hiPos: number; loPos: number
  hiP: number; loP: number
  /** hiP less loP. Exactly zero when the two are equal at every decimal. */
  delta: number
  /** alpha x urgency, hi less lo. */
  du: number
  /** (1 - alpha) x wait_normalised, hi less lo. */
  dw: number
  exact: boolean
  /** The term that resolved the pair. Null when referral date had to. */
  carries: 'urgency' | 'wait' | null
}

const term = (t: Tie['carries']) => (t === 'urgency' ? 'how unwell' : 'how long waited')

/** Every such pair, keyed by both pathway numbers, from the coordinator's own
 *  positions so it survives a filter, a page or a sort. Same breach tier only. */
function findTies(rankings: Ranking[]): Map<string, Tie> {
  const m = new Map<string, Tie>()
  const byBand: Record<string, Ranking[]> = {}
  for (const r of [...rankings].sort((a, b) => a.position - b.position)) {
    (byBand[bandOf(r.cpc)] ??= []).push(r)
  }
  for (const list of Object.values(byBand)) {
    for (let i = 1; i < list.length; i++) {
      const a = list[i - 1]
      const b = list[i]
      if ((a.crt_breached === true) !== (b.crt_breached === true)) continue
      if (a.priority.toFixed(3) !== b.priority.toFixed(3)) continue
      const [hi, lo] = a.priority >= b.priority ? [a, b] : [b, a]
      const du = hi.urgency_score * hi.alpha - lo.urgency_score * lo.alpha
      const dw = hi.wait_normalised * (1 - hi.alpha) - lo.wait_normalised * (1 - lo.alpha)
      const delta = hi.priority - lo.priority
      const t: Tie = {
        hi: hi.pathway_number, lo: lo.pathway_number,
        hiPos: hi.position, loPos: lo.position,
        hiP: hi.priority, loP: lo.priority,
        delta, du, dw,
        exact: delta === 0,
        // delta is positive by construction, so the larger difference carried it.
        carries: delta === 0 ? null : du > dw ? 'urgency' : 'wait',
      }
      if (!m.has(a.pathway_number)) m.set(a.pathway_number, t)
      if (!m.has(b.pathway_number)) m.set(b.pathway_number, t)
    }
  }
  return m
}

/** Evidence keys are slash-joined and percent-encoded:
 *  9001/PW-9001-000191/2026-03-31%2009%3A08%3A00/avpu */
const keyParts = (k: string): string[] =>
  k.split('/').map((s) => { try { return decodeURIComponent(s) } catch { return s } })

const sameMoment = (a: string | null | undefined, b: string | null | undefined) =>
  !!a && !!b && a.replace(' ', 'T').slice(0, 16) === b.replace(' ', 'T').slice(0, 16)

const VITAL: Record<string, { k: string; u?: string }> = {
  hr: { k: 'Heart rate', u: 'bpm' },
  sbp: { k: 'Systolic BP', u: 'mmHg' },
  dbp: { k: 'Diastolic BP', u: 'mmHg' },
  rr: { k: 'Respiratory rate', u: '/min' },
  spo2: { k: 'Oxygen saturation', u: '%' },
  temp: { k: 'Temperature', u: '°C' },
  avpu: { k: 'Consciousness', u: 'AVPU' },
  pain: { k: 'Pain', u: '0–10' },
}

function vitalValue(o: Observation | undefined, k: string): string {
  if (!o) return '—'
  const v = (o as unknown as Record<string, unknown>)[k]
  return v == null ? '—' : String(v)
}

/* ------------------------------------------------------------------ page -- */

export function List({ hospital, date, reference, onOpen }: {
  hospital: string; date: string
  reference: Reference | undefined
  onOpen: (pw: string) => void
}) {
  const { rows, decision, ops, opsFailed, opsPending, loading, error, displayedOrder } = useList(hospital, date)

  const [tab, setTab] = useState('Urgent')
  const [q, setQ] = useState('')
  const [tight, setTight] = useState(false)
  const [size, setSize] = useState(20)
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'order', dir: 1 })
  const [open, setOpen] = useState<string | null>(null)
  const [moving, setMoving] = useState<Ranking | null>(null)
  const [flash, setFlash] = useState<string | null>(null)

  const ranked = decision != null
  const needle = q.trim().toLowerCase()

  const visible = useMemo(() => {
    if (!needle) return rows
    return rows.filter((r) =>
      r.pathway_number.toLowerCase().includes(needle)
      || r.specialty_hipe.toLowerCase().includes(needle)
      || specialtyName(reference, r.specialty_hipe).toLowerCase().includes(needle))
  }, [rows, needle, reference])

  // Union of what the decision refused and what the SPECIALTY refuses: ADR-007
  // refuses 0601 unconditionally, and this must hold on days with no decision.
  const refused = useMemo(() => {
    const set = new Set(decision?.refused_paediatric ?? [])
    for (const r of rows) if (isRefusedPaediatric(r.specialty_hipe)) set.add(r.pathway_number)
    return set
  }, [decision, rows])

  const groups = useMemo(() => {
    const g: Record<string, Row[]> = {
      Urgent: [], 'Semi-Urgent': [], Routine: [], Uncategorised: [], Outside: [],
    }
    for (const r of visible) (refused.has(r.pathway_number) ? g.Outside : g[bandOf(r.cpc)]).push(r)
    const cmp = comparator(sort, ranked, reference)
    for (const k of Object.keys(g)) g[k].sort(cmp)
    return g
  }, [visible, refused, sort, ranked, reference])

  // A breach is always of the referrals that HAVE a target, never of the list.
  const figures = useMemo(() => {
    const withTarget = rows.filter((r) => targetOf(r, reference) != null)
    return {
      onList: rows.length,
      withTarget: withTarget.length,
      past: withTarget.filter((r) => r.crt_breached === true).length,
      noTarget: rows.length - withTarget.length,
    }
  }, [rows, reference])

  /** The state before ranking, counted from the cohort, so it holds on a day
   *  nothing has scored. WORDING TRAP: every figure counts ROWS and must say
   *  referrals, never people -- pathway numbers deliberately collide across
   *  hospitals here. Not a hedge: no qualifier, no synthetic-data label. */
  const pre = useMemo(() => {
    if (ranked || !rows.length) return null
    const waits = rows.map((r) => r.adjusted_wait_days ?? 0).sort((a, b) => a - b)
    const n = waits.length
    const ratios = rows.map((r) => ratioOf(r, reference)).filter((x): x is number => x != null)
    const steps = rows.map((r) => sevReadingAge(r.clin?.reading_age_days ?? null))
    const n2 = rows.map((r) => r.clin?.news2).filter((x): x is number => x != null)
    return {
      // lib/stats.ts, the same call Overview.tsx makes; median() sorts its own copy.
      median: median(waits), min: waits[0], max: waits[n - 1],
      worst: ratios.length ? Math.max(...ratios) : null,
      // graded by the frozen scale, never a threshold invented here
      year: steps.filter((x) => x >= sevReadingAge(365)).length,
      twoYear: steps.filter((x) => x >= sevReadingAge(730)).length,
      noReading: rows.filter((r) => r.clin?.obs_datetime == null).length,
      n2n: n2.length,
      n2zero: n2.filter((x) => x === 0).length,
      n2max: n2.length ? Math.max(...n2) : null,
      awaiting: rows.filter((r) => r.triage_status === 'awaiting_triage').length,
    }
  }, [rows, ranked, reference])

  /** From the decision's own positions, so it holds under any filter or sort. */
  const ties = useMemo(
    () => (decision ? findTies(decision.rankings) : new Map<string, Tie>()),
    [decision])
  const tieCount = useMemo(() => {
    const seen = new Set<Tie>(ties.values())
    let near = 0
    let exact = 0
    for (const t of seen) if (t.exact) exact++; else near++
    return { near, exact }
  }, [ties])

  function toggleSort(key: SortKey) {
    setOpen(null)
    setSort((s) => (s.key === key
      ? { key, dir: (s.dir === 1 ? -1 : 1) as 1 | -1 }
      : { key, dir: FIRST_DIR[key] }))
  }

  if (loading) {
    return (
      <div className="pad">
        <div className="lst-load"><span className="lab">Reading the cohort…</span></div>
      </div>
    )
  }
  if (error) {
    return (
      <div className="pad">
        <div className="err">{String(error)}</div>
        <p className="lst-p measure">
          The cohort could not be read, so there is nothing to rank. Nothing below would be
          true, so nothing below is drawn.
        </p>
      </div>
    )
  }

  const alpha = decision?.alpha ?? null

  return (
    <div className="pad lst">
      {/* mounted unconditionally: a polite region must be observed BEFORE its
          text changes, or the first announcement is dropped */}
      <div className="flash" role="status" aria-live="polite" aria-atomic="true"
           hidden={!flash}>{flash}</div>

      <header className="lst-top">
        <div className="lst-title">
          <span className="lab">Ranked order</span>
          <h1>{ranked ? 'Suggested order' : 'The list, before any ranking'}</h1>
          <p className="lst-sub">
            {ranked ? (
              <>
                <strong className="num">{fmt(decision.rankings.length)}</strong> placed of{' '}
                <strong className="num">{fmt(figures.onList)}</strong> on the list ·{' '}
                <span className="num">{decision.run_id}</span> · built{' '}
                {dmyt(decision.built_at)}
              </>
            ) : (
              <>
                No agent has scored this hospital-day. The list below is what a clinician
                recorded, in referral-date order: <em>a display order, not a ranking.</em>
              </>
            )}
          </p>
        </div>

        <div className="lst-figs">
          <Fig n={figures.onList} k="on the list" w="referrals open on this hospital-day" />
          <Fig n={figures.withTarget} k="have a target"
               w="a clinical timeframe applies to these, and only these" />
          <Fig n={figures.past} k="past target" accent
               w={`of the ${fmt(figures.withTarget)} with one, never of ${fmt(figures.onList)}`} />
          <Fig n={figures.noTarget} k="no target applies"
               w="Routine and Uncategorised. Nothing here can be late." />
        </div>
      </header>

      {!ranked && pre && (
        <section className="lst-pre" aria-label="The list before any ranking">
          <h2 className="pre-h">
            <strong className="num">{fmt(figures.onList)}</strong> referrals are on this list,
            and nothing has scored them yet.
          </h2>
          <div className="pre-figs">
            <PreFig k={`already past their target, of the ${fmt(figures.withTarget)} that have one. `
              + `${fmt(figures.noTarget)} have no target at all and nothing in that group can be late.`}>
              <b className="num">{fmt(figures.past)}</b>
            </PreFig>
            <PreFig k={`days waited, median. The spread is ${fmt(pre.min)} to ${fmt(pre.max)} days.`}>
              <b className="num">{fmt(pre.median)}</b>
            </PreFig>
            <PreFig k="the furthest past target any referral here is">
              {pre.worst != null && pre.worst > 1
                ? (
                  <SevChip sev={sevWaitRatio(pre.worst)}
                           title="the largest wait-against-target on this hospital-day">
                    <b className="num">{ratioText(pre.worst)}×</b>
                  </SevChip>
                )
                : <span className="muted">no referral here is past a target</span>}
            </PreFig>
            <PreFig k={'readings older than a year. A stale normal reading is an absence of '
              + 'information, not reassurance, so the age is graded on its own.'}>
              <SevChip sev={sevReadingAge(365)} title="at least a year since the reading">
                <b className="num">{fmt(pre.year)}</b>
              </SevChip>
              {pre.twoYear > 0 && (
                <SevChip sev={sevReadingAge(730)} title="at least two years since the reading">
                  <b className="num">{fmt(pre.twoYear)}</b> past two years
                </SevChip>
              )}
            </PreFig>
            {/* TRAP: /api/operations takes ~3s cold, so until it lands `pre` is
                computed from nulls and this asserts an absolute for that long. */}
            <PreFig k={opsPending
              ? 'carry a NEWS2. Reading the observations…'
              : pre.n2max == null
              ? 'carry a NEWS2. No observation has been read on this hospital-day.'
              : `carry a NEWS2. ${fmt(pre.n2zero)} of those are 0 and the highest is `
                + `${pre.n2max} of 17, which is why NEWS2 total is never the thing that ranks.`}>
              <b className="num">{fmt(pre.n2n)}</b>
            </PreFig>
          </div>
          {/* STATE, so it stays visible. .lst-sub above already says "a display
              order, not a ranking", so this must not. */}
          <p className="pre-p">
            Referral-date order carries no clinical claim: nothing below has been scored,
            placed or tested against a rule.{' '}
            <strong>Run the agents from the top bar</strong> and these same{' '}
            <span className="num">{fmt(figures.onList)}</span> rows come back in a suggested
            order, each with its score, its cited evidence and every rule tested against it.
          </p>
        </section>
      )}

      {opsFailed && (
        <div className="lst-warn">
          <TriangleAlert className="ico-sig" strokeWidth={1.75} />
          <span>
            Operational context could not be read, so NEWS2, the reading dates and the cited
            capacity rows are unavailable. Every other column is from the cohort itself.
          </span>
        </div>
      )}

      {/* Reference material: left open it pushes the list below the fold. */}
      <details className="lst-fold">
        <summary>
          <span className="lst-fold-t">The sort key</span>
          <span className="lst-fold-s">
            category → severity → past target first → priority → referral date → pathway number
          </span>
        </summary>
        <SortKeyLadder alpha={alpha} ranked={ranked} reference={reference} ties={tieCount} />
      </details>

      {ranked && (
        <details className="lst-fold">
          <summary>
            <span className="lst-fold-t">Everyone accounted for</span>
            <span className="lst-fold-s">
              <span className="num">{decision!.rankings.length}</span> placed ·{' '}
              <span className="num">{decision!.refused_paediatric.length}</span> refused ·{' '}
              <span className="num">{decision!.skipped.length}</span> skipped ·{' '}
              <span className="num">{decision!.excluded.length}</span> excluded ·
              reconciled by set union, never by sum
            </span>
          </summary>
          <Reconciliation decision={decision} total={figures.onList} />
        </details>
      )}

      <div className="lst-tools">
        <label className="lst-find">
          <Search className="ico-chr" strokeWidth={1.75} aria-hidden="true" />
          <input
            type="search" value={q} onChange={(e) => { setQ(e.target.value); setOpen(null) }}
            placeholder="Find a pathway number or a specialty"
            aria-label="Filter by pathway number or specialty" />
          {needle && (
            <span className="lst-find-n num">
              {fmt(visible.length)} of {fmt(rows.length)}
            </span>
          )}
        </label>

        <div className="lst-seg" role="group" aria-label="Row density">
          <button type="button" className={'seg' + (tight ? '' : ' is-on')}
                  aria-pressed={!tight} onClick={() => setTight(false)}>Comfortable</button>
          <button type="button" className={'seg' + (tight ? ' is-on' : '')}
                  aria-pressed={tight} onClick={() => setTight(true)}>Compact</button>
        </div>

        <label className="lst-pick">
          <span className="lab">Rows</span>
          <select className="lst-select" value={size}
                  onChange={(e) => setSize(Number(e.target.value))}>
            <option value={20}>20</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
            <option value={100000}>All</option>
          </select>
        </label>

        {sort.key !== 'order' && (
          <button type="button" className="lst-reset" onClick={() => setSort({ key: 'order', dir: 1 })}>
            Sorted by {SORT_NAME[sort.key]}, <strong>not the suggested order</strong>. Reset
          </button>
        )}
      </div>

      <Tabs.Root value={tab} onValueChange={(v) => { setTab(v); setOpen(null) }}>
        <Tabs.List className="lst-tabs" aria-label="Clinical category">
          {TABS.map((k) => {
            const g = groups[k] ?? []
            const t = k === 'Outside' ? null : bandTarget(k, reference)
            const past = g.filter((r) => r.crt_breached === true).length
            return (
              <Tabs.Trigger key={k} value={k} className="tb">
                <span className="tb-top">
                  <span className={'tb-sw cat-' + TAB_TOKEN[k]} aria-hidden="true" />
                  <span className="tb-k">{k === 'Outside' ? 'Outside the ranking' : k}</span>
                  <span className="tb-n num">{fmt(g.length)}</span>
                </span>
                <span className="tb-x num">
                  {k === 'Outside' ? 'not scored, not placed'
                    : t == null ? 'no target applies'
                      : <>{fmt(past)} past a {t}-day target</>}
                </span>
              </Tabs.Trigger>
            )
          })}
        </Tabs.List>

        {TABS.map((k) => (
          <Tabs.Content key={k} value={k} className="lst-panel">
            <Band
              rows={groups[k] ?? []}
              onList={figures.onList}
              bandKey={k}
              ranked={ranked}
              outside={k === 'Outside'}
              reference={reference}
              decision={decision}
              ops={ops}
              hospital={hospital}
              sort={sort}
              onSort={toggleSort}
              tight={tight}
              size={size}
              filtered={!!needle}
              elsewhere={TABS.filter((t) => t !== k)
                .map((t) => [t, (groups[t] ?? []).length] as [string, number])}
              onGoTab={setTab}
              open={open}
              onToggleOpen={(pw) => setOpen((c) => (c === pw ? null : pw))}
              onOpen={onOpen}
              onMove={setMoving}
              ties={ties}
            />
          </Tabs.Content>
        ))}
      </Tabs.Root>

      {moving && decision && (
        <Override
          patient={moving} decision={decision}
          onClose={() => setMoving(null)}
          onDone={(m) => { setFlash(m); setMoving(null) }}
          displayedOrder={displayedOrder} />
      )}
    </div>
  )
}

const bandTarget = (k: string, ref: Reference | undefined): number | null => {
  const b = BANDS.find((x) => x.key === k)
  if (!b) return null
  return crtDays(ref, b.cpc) ?? b.target
}

function Fig({ n, k, w, accent }: { n: number; k: string; w: string; accent?: boolean }) {
  return (
    <div className={'fig' + (accent ? ' is-accent' : '')}>
      <div className="fig-n num">{fmt(n)}</div>
      <div className="fig-k">{k}</div>
      <div className="fig-w">{w}</div>
    </div>
  )
}

/** The value is a node, not a number: some arrive as a severity chip. */
function PreFig({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="pre-f">
      <div className="pre-f-v">{children}</div>
      <div className="pre-f-k">{k}</div>
    </div>
  )
}

/* ----------------------------------------------------- the sort key, drawn -- */

/** Six ordered steps, each naming its rule; step 3 takes the one clay accent.
 *  Steps 4 and 5 count the pairs priority cannot separate as printed. */
function SortKeyLadder({ alpha, ranked, reference, ties }: {
  alpha: number | null; ranked: boolean; reference: Reference | undefined
  ties: { near: number; exact: number }
}) {
  const steps = [
    {
      k: 'Clinical category',
      w: 'Urgent, then Semi-Urgent, then Routine, then Uncategorised. No score moves anyone between them.',
      rule: 'RULE-ORDER',
    },
    {
      k: 'Severity rank',
      w: 'core.ref_codes.severity_rank, never the raw CPC code: CPC 3 outranks CPC 2.',
    },
    {
      k: 'Past target first',
      w: 'A hard tier. Everyone already past their target ranks above everyone within it, before any score is compared.',
      rule: 'RULE-CRT-URGENT · RULE-CRT-SEMI',
      tier: true,
    },
    {
      k: 'Priority',
      w: alpha == null
        ? 'α × how unwell, plus (1 − α) × how long waited. A run sets α from capacity pressure.'
        : `${pct(alpha)} how unwell, ${pct(1 - alpha)} how long waited. Capacity sets that one α for the whole hospital-day and never moves an individual.`,
      note: ties.near > 0
        ? `${ties.near} adjacent pairs here print the same priority at three decimals and are `
          + 'still separated by it. Those rows show the margin at the precision that carries '
          + 'it, and name which of the two terms carried it.'
        : undefined,
    },
    {
      k: 'Referral date',
      w: 'Oldest first, so two referrals the scores cannot separate are separated by their wait.',
      rule: 'RULE-TIEBREAK',
      note: ties.exact > 0
        ? `${ties.exact} pairs here are equal at every decimal place, so priority genuinely `
          + 'cannot separate them and this step is what places them.'
        : undefined,
    },
    {
      k: 'Pathway number',
      w: 'The last resort, so the same inputs always produce the same order.',
    },
  ]

  return (
    <section className="lst-key-sec" aria-label="How the order is decided">
      <h2 className="sec-h">
        The sort key
        <span className="sec-note">
          read top to bottom · a step is only reached when every step above it ties
        </span>
      </h2>
      <ol className="key">
        {steps.map((s, i) => (
          <li key={s.k} className={'key-s' + (s.tier ? ' is-tier' : '') + (ranked ? '' : ' is-off')}>
            <span className="key-n num">{i + 1}</span>
            <span className="key-k">{s.k}</span>
            <span className="key-w">{s.w}</span>
            {s.note && <span className="key-note">{s.note}</span>}
            {/* The rule a step comes from, and what it SAYS: in a `title` alone
                the ladder names an ID and hides the sentence under a pointer. */}
            {s.rule && (
              <span className="key-r">
                {s.rule.split(' · ').map((id) => {
                  // ruleStatement falls back to the ID while core.ref_rules loads
                  const st = ruleStatement(reference, id)
                  return (
                    <span className="key-r-1" key={id}>
                      <span className="key-r-id num">{id}</span>
                      {st !== id && <span className="key-r-w">{st}</span>}
                    </span>
                  )
                })}
              </span>
            )}
          </li>
        ))}
      </ol>
      {!ranked && (
        <p className="lst-p">
          No run has been made, so steps 2 to 6 have not been applied to anyone. Rows below sit
          in referral-date order.
        </p>
      )}
    </section>
  )
}

/* ------------------------------------------------------- reconciliation D4 -- */

/** The four not-ranked buckets, reconciled by set union. They OVERLAP -- a refused
 *  referral is also unplaceable -- so a sum over-counts and loses what each means. */
function Reconciliation({ decision, total }: { decision: Decision; total: number }) {
  const placed = new Set(decision.rankings.map((r) => r.pathway_number))
  const paed = new Set(decision.refused_paediatric)
  const skip = new Set(decision.skipped)
  const exc = new Set(decision.excluded.map((e) => e.pathway_number))
  const overlap = [...paed].filter((p) => exc.has(p)).length
  const union = new Set([...placed, ...paed, ...skip, ...exc])
  const naive = placed.size + paed.size + skip.size + exc.size

  const buckets = [
    { k: 'Placed', n: placed.size, w: 'scored by both agents and given a position' },
    {
      k: 'Refused, paediatric', n: paed.size,
      w: 'NEWS2 is validated in adults, so specialty 0601 is refused rather than scored on an adult scale',
      note: 'a coverage statement, not a low position',
    },
    {
      k: 'Skipped', n: skip.size,
      w: 'an adult referral the urgency agent could not score, usually a missing observation',
      note: 'a data-quality incident, and a different thing from a refusal',
    },
    {
      k: 'Excluded by the coordinator', n: exc.size,
      w: 'no valid adult NEWS2 urgency score reached the ranking, so no position could be computed',
      note: overlap ? `${overlap} of these are the refusals above, seen a second time` : undefined,
    },
  ]

  return (
    <section className="lst-recon" aria-label="Everyone accounted for">
      <h2 className="sec-h">
        Everyone accounted for
        <span className="sec-note">
          {fmt(total)} on the list · reconciled by set union, never by sum
        </span>
      </h2>
      <div className="recon">
        {buckets.map((b) => (
          <div className="recon-c" key={b.k}>
            <div className="recon-n num">{fmt(b.n)}</div>
            <div className="recon-k">{b.k}</div>
            <div className="recon-w">{b.w}{b.note && <em> ({b.note})</em>}</div>
          </div>
        ))}
      </div>
      <p className={'recon-sum' + (union.size === total ? '' : ' is-off')}>
        <strong className="num">{fmt(union.size)}</strong> distinct referrals accounted for, of{' '}
        <strong className="num">{fmt(total)}</strong> on the list.
        {overlap > 0 && (
          <> The buckets overlap by <span className="num">{overlap}</span>, which is why they are
          never summed: added rather than unioned they read as{' '}
          <span className="num">{fmt(naive)}</span> of <span className="num">{fmt(total)}</span>.</>
        )}
        {union.size !== total && (
          <strong className="recon-gap"> · {fmt(Math.abs(total - union.size))} unexplained</strong>
        )}
      </p>
    </section>
  )
}

/* ------------------------------------------------------------- one band -- */

type BandProps = {
  rows: Row[]
  /** The whole cohort, so the Outside tab reconciles against the Overview's
   *  without a hardcoded number that is wrong at another hospital. */
  onList: number
  bandKey: string
  ranked: boolean
  outside: boolean
  reference: Reference | undefined
  decision: Decision | undefined
  ops: ReturnType<typeof useList>['ops']
  hospital: string
  sort: { key: SortKey; dir: 1 | -1 }
  onSort: (k: SortKey) => void
  tight: boolean
  size: number
  filtered: boolean
  /** Match counts in the OTHER categories, so an empty tab is not a dead end. */
  elsewhere?: Array<[string, number]>
  onGoTab: (k: string) => void
  open: string | null
  onToggleOpen: (pw: string) => void
  onOpen: (pw: string) => void
  onMove: (r: Ranking) => void
  ties: Map<string, Tie>
}

function Band(p: BandProps) {
  const [page, setPage] = useState(0)
  // Below this, Triage and Context go rather than the Referral cell paint over
  // the Waited column. See COL and NINE_COL_PX above.
  const narrow = useNarrow(NINE_COL_PX)
  // a new sort, filter or category starts at the top, never mid-list
  useEffect(() => { setPage(0) }, [p.rows, p.size])

  const target = p.outside ? null : bandTarget(p.bandKey, p.reference)
  const past = p.rows.filter((r) => r.crt_breached === true).length
  const moved = p.rows.filter((r) => r.ovr && r.ovrLive
    && r.ovr.to_position !== r.ovr.from_position).length

  if (!p.rows.length) {
    // A filter matching only in another category otherwise reads "nothing
    // matches" while a tab two inches away shows a count. Name where they are.
    const elsewhere = (p.elsewhere ?? []).filter(([, n]) => n > 0)
    return (
      <p className="muted lst-empty">
        {p.filtered ? 'Nothing in this category matches that filter.' : 'Nobody in this group.'}
        {p.filtered && elsewhere.length > 0 && (
          <>
            {' '}Matches are in{' '}
            {elsewhere.map(([k, n], i) => (
              <Fragment key={k}>
                {i > 0 && (i === elsewhere.length - 1 ? ' and ' : ', ')}
                <button className="lst-jump" onClick={() => p.onGoTab(k)}>
                  {k === 'Outside' ? 'Outside the ranking' : k}{' '}
                  <span className="num">{n}</span>
                </button>
              </Fragment>
            ))}.
          </>
        )}
      </p>
    )
  }

  const pages = Math.max(1, Math.ceil(p.rows.length / p.size))
  const from = Math.min(page, pages - 1) * p.size
  const slice = p.rows.slice(from, from + p.size)

  // The breach tier is a step in the sort key, so it is only a real boundary
  // while the list is IN that order. Under any other sort it is not drawn.
  const edgeAt = p.ranked && !p.outside && p.sort.key === 'order'
    ? slice.findIndex((r, i) => i > 0
      && slice[i - 1].crt_breached === true && r.crt_breached !== true)
    : -1

  /* Hoisted out of the <p>: the Outside tab's note is an <Aside> whose root is a
     <div>, and a <div> inside a <p> is invalid. A STATE, so it stays visible. */
  const movedNote = moved > 0 ? (
    <> · <strong className="num">{moved}</strong> row{moved > 1 ? 's' : ''} here sit
    where a clinician placed {moved > 1 ? 'them' : 'it'}, not where the system did.</>
  ) : null

  return (
    <>
      {/* The only <Aside> here. Both halves of the summary change how a number
          already on screen reads -- "not a low position", and why this tab's
          counts differ from the Overview's -- so both stay on the line, and only
          the argument goes inside. It sits OUTSIDE .lst-table: Aside bars itself
          from that table, whose own disclosure is the row expander. */}
      {p.outside ? (
        <Aside
          className="lst-note"
          label="why these are not scored"
          summary={(
            <>
              Not scored, not placed. <strong>This is not a low position.</strong> Counted
              here, not in their clinical band, so the tab counts differ from the Overview's.
              {movedNote}
            </>
          )}>
          <p>
            NEWS2 is validated in adults, so the urgency agent refuses paediatric specialties
            rather than scoring a child on an adult scale. Category and waiting time are shown
            in full, because a clinician recorded those: the refusal is about the instrument,
            not about the record.
          </p>
          {p.rows.length > 0 && (
            <p>
              In their clinical band these rows would read{' '}
              <strong>{
                Object.entries(p.rows.reduce((a: Record<string, number>, r) => {
                  const b = bandOf(r.cpc); a[b] = (a[b] ?? 0) + 1; return a
                }, {})).map(([b, n]) => `${n} ${b}`).join(' · ')
              }</strong>. The tab counts above are of the ranking; the Overview bands all{' '}
              {fmt(p.onList)} by category.
            </p>
          )}
        </Aside>
      ) : (
        <p className="lst-note">
          {target == null ? (
            <>No clinical timeframe applies to this category, so nothing here can be “late”, and
            nothing here is drawn against a target.</>
          ) : (
            <>
              Target: seen within <strong className="num">{target}</strong> days ·{' '}
              <strong className="num">{fmt(past)}</strong> of{' '}
              <strong className="num">{fmt(p.rows.length)}</strong> already past it, and all of
              them rank above everyone within it.
            </>
          )}
          {movedNote}
        </p>
      )}

      {/* The scale, once, above the rows it grades. It belongs to
          components/Severity.tsx: placed here, never redrawn. */}
      <SevLegend className="lst-legend" />

      <div className={'scroll-x lst-vp' + (p.tight ? ' is-tight' : '')}>
        {/* min-width is DERIVED, never written down: the specified widths plus
            Referral's reserved minimum. See COL. */}
        <table className="lst-table" style={{ minWidth: tableMin(narrow) }}>
          {/* Referral is the one elastic column -- the <col> with no width -- and
              tableMin never lets what is left fall below COL_REF. */}
          <colgroup>
            <col style={{ width: COL.pos }} />
            <col style={{ width: COL.spine }} />
            <col />
            <col style={{ width: COL.wait }} />
            <col style={{ width: COL.rule }} />
            <col style={{ width: COL.news }} />
            {/* The two to lose when the width will not take nine: both nearly
                constant, both in the expander. Never balance, wait or rule. */}
            {!narrow && <col style={{ width: COL.triage }} />}
            {!narrow && <col style={{ width: COL.ctx }} />}
            <col style={{ width: COL.exp }} />
          </colgroup>
          <thead>
            <tr>
              <Th k="order" sort={p.sort} onSort={p.onSort} align="right"
                  label={p.outside ? 'Not ranked' : p.ranked ? 'Order' : 'Display'}
                  sub={p.outside ? 'no position' : p.ranked ? 'position in the list' : 'referral date'} />
              <Th k="priority" sort={p.sort} onSort={p.onSort}
                  label="Balance" sub="unwell when measured ← α → waited" />
              <Th k="specialty" sort={p.sort} onSort={p.onSort}
                  label="Referral" sub="specialty" k2="pathway" sub2="pathway" />
              <Th k="wait" sort={p.sort} onSort={p.onSort}
                  label="Waited" sub="days" k2="over" sub2="against target" />
              <th className="lst-th">
                <span className="lst-th-l">Rule</span>
                <span className="lst-th-s">the check that fired · core.ref_rules</span>
              </th>
              <Th k="news2" sort={p.sort} onSort={p.onSort}
                  label="How unwell" sub="NEWS2 when measured" k2="age" sub2="reading age" />
              {!narrow && <th className="lst-th">
                <span className="lst-th-l">Triage</span>
                <span className="lst-th-s">status on this pathway</span>
              </th>}
              {!narrow && <th className="lst-th">
                <span className="lst-th-l">Context</span>
                <span className="lst-th-s">recorded, not scored · ADR-004</span>
              </th>}
              <th className="lst-th"><span className="vh">Evidence</span></th>
            </tr>
          </thead>
          <tbody>
            {slice.map((r, i) => (
              <Fragment key={r.pathway_number}>
                {i === edgeAt && (
                  <tr className="tier">
                    <td colSpan={9}>
                      <span className="tier-t">
                        <strong>Everyone above this line is already past their target.</strong>{' '}
                        The sort places them there before any score is compared: step 3 of the
                        key, above priority. Below it, everyone is still within{' '}
                        {target != null ? `their ${target}-day target` : 'target'}.
                      </span>
                    </td>
                  </tr>
                )}
                <PatientRow
                  r={r} i={i} ranked={p.ranked} outside={p.outside}
                  reference={p.reference} tight={p.tight} narrow={narrow}
                  tie={p.ties.get(r.pathway_number)}
                  expanded={p.open === r.pathway_number}
                  onToggle={() => p.onToggleOpen(r.pathway_number)}
                  onOpen={p.onOpen} />
                {p.open === r.pathway_number && (
                  <tr className="ev-row">
                    <td colSpan={9}>
                      <Evidence
                        r={r} hospital={p.hospital} reference={p.reference}
                        ops={p.ops} decision={p.decision} onMove={p.onMove}
                        tie={p.ties.get(r.pathway_number)}
                        onOpen={p.onOpen} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <nav className="lst-pager" aria-label="Pages within this category">
        <span className="lst-pager-of num">
          {fmt(from + 1)}–{fmt(Math.min(from + p.size, p.rows.length))} of {fmt(p.rows.length)}
          <span className="muted">
            {' · '}
            {p.sort.key === 'order'
              ? (p.ranked && !p.outside ? 'in suggested order' : 'in referral-date order')
              : `sorted by ${SORT_NAME[p.sort.key]}, ${p.sort.dir === 1 ? 'lowest' : 'highest'} first`}
          </span>
        </span>
        {pages > 1 && (
          <span className="lst-pager-b">
            <button className="pg" onClick={() => setPage((x) => Math.max(0, x - 1))}
                    disabled={page === 0}>Previous</button>
            {pageWindow(page, pages).map((n, idx) => (n < 0
              ? <span key={`gap${idx}`} className="lst-gap">…</span>
              : <button key={n} className={'pg pg-n num' + (n === page ? ' is-on' : '')}
                        onClick={() => setPage(n)} aria-current={n === page}>{n + 1}</button>))}
            <button className="pg" onClick={() => setPage((x) => Math.min(pages - 1, x + 1))}
                    disabled={page >= pages - 1}>Next</button>
          </span>
        )}
      </nav>
    </>
  )
}

/** Ends, neighbours and an ellipsis for the rest. -1 is the ellipsis. */
function pageWindow(page: number, pages: number): number[] {
  if (pages <= 9) return Array.from({ length: pages }, (_, i) => i)
  const out = new Set<number>([0, pages - 1, page, page - 1, page + 1])
  const keep = [...out].filter((n) => n >= 0 && n < pages).sort((a, b) => a - b)
  const withGaps: number[] = []
  keep.forEach((n, i) => {
    if (i > 0 && n - keep[i - 1] > 1) withGaps.push(-1)
    withGaps.push(n)
  })
  return withGaps
}

/** Two sorts per header, the column's value and the qualifier under it: a
 *  reading's age is as sortable as the reading. */
function Th({ k, label, sub, sort, onSort, align, k2, sub2 }: {
  k: SortKey; label: string; sub: string
  sort: { key: SortKey; dir: 1 | -1 }; onSort: (k: SortKey) => void
  align?: 'right'
  k2?: SortKey; sub2?: string
}) {
  const on = sort.key === k
  const on2 = !!k2 && sort.key === k2
  const arrow = sort.dir === 1
    ? <ArrowUp className="ico-chr" strokeWidth={1.75} aria-hidden="true" />
    : <ArrowDown className="ico-chr" strokeWidth={1.75} aria-hidden="true" />
  return (
    <th className={'lst-th' + (align === 'right' ? ' is-r' : '') + (on || on2 ? ' is-on' : '')}
        aria-sort={on || on2 ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="lst-sortb" onClick={() => onSort(k)}
              aria-label={`Sort by ${SORT_NAME[k]}`}>
        <span className={'lst-th-l' + (on ? ' is-key' : '')}>{label}{on && arrow}</span>
        {!k2 && <span className="lst-th-s">{sub}</span>}
      </button>
      {k2 && sub2 && (
        <span className="lst-th-two">
          <button type="button" className="subb" onClick={() => onSort(k)}
                  aria-label={`Sort by ${SORT_NAME[k]}`}>
            <span className={'lst-th-s' + (on ? ' is-key' : '')}>{sub}{on && arrow}</span>
          </button>
          <span className="lst-th-dot" aria-hidden="true">·</span>
          <button type="button" className="subb" onClick={() => onSort(k2)}
                  aria-label={`Sort by ${SORT_NAME[k2]}`}>
            <span className={'lst-th-s' + (on2 ? ' is-key' : '')}>{sub2}{on2 && arrow}</span>
          </button>
        </span>
      )}
    </th>
  )
}

/* --------------------------------------------------------------- one row -- */

/* `outside` is a TAB fact; whether NEWS2 may be shown as acuity is a SPECIALTY
   fact. They coincide only because the grouping tests refusal before band, so
   the NEWS2 cell derives its own answer. */
function PatientRow({ r, i, ranked, outside, reference, tight, narrow, tie, expanded, onToggle, onOpen }: {
  r: Row; i: number; ranked: boolean; outside: boolean; narrow: boolean
  reference: Reference | undefined; tight: boolean; expanded: boolean
  tie: Tie | undefined
  onToggle: () => void; onOpen: (pw: string) => void
}) {
  const still = useReducedMotion()
  const target = targetOf(r, reference)
  const wait = r.adjusted_wait_days ?? 0
  const ratio = ratioOf(r, reference)
  const over = ratio != null && ratio > 1
  const age = r.clin?.reading_age_days ?? null

  // Two graded states, both from lib/severity.ts and neither invented here.
  const waitSev = sevWaitRatio(ratio)
  const ageSev = sevReadingAge(age)

  // NEWS2 may not be shown as acuity for a refused specialty. Same derivation as
  // the refused set and the patient page, so the cell is right in any tab.
  const naNews2 = outside || isRefusedPaediatric(r.specialty_hipe)

  const moved = !!r.ovr && r.ovrLive && r.ovr.to_position !== r.ovr.from_position
  // The ORDINAL is the row's place in the DISPLAYED order: print the stored
  // position and the column stops enumerating the moment anyone is moved.
  const shownPos = r.seq < UNPLACED ? r.seq + 1 : r.rank?.position
  // the system's own number is kept whenever it differs from where the row now sits
  const systemPos = r.rank?.position
  const displaced = systemPos != null && shownPos != null && systemPos !== shownPos

  // The rule ID is the first thing a reviewer looks for.
  const fired = (r.rank?.rule_checks ?? [])
    .filter((c) => !c.passed && !WHOLE_LIST.has(c.rule_id))
  // A row can fire a CRT rule AND RULE-TRIAGE-TURNAROUND. Compact has room for
  // one, so the rest are counted out loud rather than clipped silently.
  const shownRules = tight && fired.length > 1 ? fired.slice(0, 1) : fired
  const hiddenRules = fired.length - shownRules.length

  return (
    <motion.tr
      className={'lst-row is-clickable'
        + (expanded ? ' is-open' : '')
        + (r.ovr && r.ovrLive ? ' is-overridden' : '')}
      // TRAP: never role="button" here -- ARIA makes a button's children
      // presentational, stripping every <td>, the reading's age included.
      initial={still ? false : { opacity: 0, y: 3 }}
      animate={{ opacity: 1, y: 0 }}
      transition={still ? { duration: 0 } : {
        // a stagger across one page only, or the list reads as slow
        delay: Math.min(i, 18) * 0.012, duration: 0.22, ease: [0.2, 0, 0, 1],
      }}
      onClick={() => onOpen(r.pathway_number)}>

      {/* order */}
      <td className="c-pos">
        <div className="cell is-r">
          <span className={'pos num' + (moved ? ' is-moved' : '')}>
            {outside ? '—' : shownPos != null ? shownPos : '·'}
          </span>
          {/* the clinician's position is shown; the system's stays beside it */}
          {/* COL.pos leaves ~56px of content, so the phrase is in the tooltip,
              where the expander repeats it in full. */}
          {displaced
            ? <span className="pos-was lab"
                    title={`the system placed this referral at ${systemPos}`}>
                was {systemPos}
              </span>
            : r.ovr && r.ovrLive
              ? <span className="pos-was lab"
                      title="recorded as confirmed at this position">confirmed</span>
              : null}
        </div>
      </td>

      {/* both terms, α-weighted. Half of a pair the printed priority cannot
          separate goes to six decimals, with the term that carried it named. */}
      <td className="c-spine">
        {r.rank
          ? (
            <>
              <RankSpine urgency={r.rank.urgency_score} wait={r.rank.wait_normalised}
                         alpha={r.rank.alpha} priority={r.rank.priority} tight={tight}
                         precise={!!tie} />
              {tie && <TieLine tie={tie} self={r.pathway_number} />}
            </>
          )
          : <span className="muted lst-dash">not scored</span>}
      </td>

      {/* referral */}
      <td className="c-ref">
        {/* TRAP: .cell and .ovbadge are SIBLINGS that compact lays on one line.
            Without this flex wrapper they are unshrinkable inline boxes and the
            badge paints over the wait bar; list.css's two min-width:0 rules
            decide which gives way. */}
        <div className="ref-wrap">
        <div className="cell">
          <span className="pw-line">
            <button type="button" className="pw num pw-open"
                    onClick={(e) => { e.stopPropagation(); onOpen(r.pathway_number) }}>
              {r.pathway_number}
            </button>
            {/* Planted fixtures the dataset track keeps at fixed pathway numbers.
                Unlabelled they read as leftover test data in a clinical list. */}
            {plantedCase(r.pathway_number) && (
              <span className="planted" title={plantedCase(r.pathway_number)!.why}>
                demo fixture · {plantedCase(r.pathway_number)!.what}
              </span>
            )}
          </span>
          <span className="sub" title={specialtyName(reference, r.specialty_hipe)}>
            {specialtyName(reference, r.specialty_hipe)}
            <span className="sub-code num"> · {r.specialty_hipe}</span>
          </span>
        </div>
        {r.ovr && r.ovrLive && (
          // One flex item, not four: a bare text node inside an inline-flex
          // becomes an anonymous item of its own and wraps separately.
          <span className="ovbadge" title={`${r.ovr.clinician_id}: ${r.ovr.reason}`}>
            <PenLine className="ico-chr" strokeWidth={1.75} aria-hidden="true" />
            <span className="ovbadge-t">
              {moved
                ? <>moved to {r.ovr.to_position} by <b>{r.ovr.clinician_id}</b></>
                : <>confirmed by <b>{r.ovr.clinician_id}</b></>}
            </span>
          </span>
        )}
        {r.ovr && !r.ovrLive && (
          <span className="ovbadge is-stale"
                title={`${r.ovr.clinician_id} edited an earlier decision (${r.ovr.decision_id}). Its positions name a list this run replaced, so it is recorded but not applied.`}>
            <PenLine className="ico-chr" strokeWidth={1.75} aria-hidden="true" />
            <span className="ovbadge-t">
              edited by <b>{r.ovr.clinician_id}</b> · not applied
            </span>
          </span>
        )}
        </div>
      </td>

      {/* The multiple past target is the graded state: .sub.is-over must differ. */}
      <td className="c-wt">
        <div className="cell">
          <span className="wait-n num">{fmt(wait)}<span className="of"> days</span></span>
          <WaitBar ratio={ratio} sev={waitSev} />
          <span className="sub is-split">
            {target == null ? 'no target for this category'
              : over ? (
                <>
                  {/* No chip: the bar above carries the graded channel for this
                      exact fact. The numeral stays, so it is never colour-only. */}
                  <b className="num wait-x"
                     title={`${fmt(wait)} days against a ${target}-day target`}>
                    {ratioText(ratio!)}×
                  </b>
                  <span className="sub-t">over a {target}-day target</span>
                </>
              )
                : <span className="sub-t">within a {target}-day target</span>}
          </span>
        </div>
      </td>

      {/* Drawn QUIET: sevBreach has two values, so a solid chip is the same block
          on most rows that can breach -- a field, not an accent. */}
      <td className="c-rule">
        {fired.length > 0 ? (
          <div className="rulez">
            {shownRules.map((c) => (
              <span className="rule-chip" key={c.rule_id}>
                {/* The rule ID is a CONTROL: a `title` on a non-focusable span is
                    unreachable by keyboard and touch. The statement is this
                    control's accessible name, visible text first. */}
                <button
                  type="button" className="rule-open"
                  aria-expanded={expanded}
                  title={ruleStatement(reference, c.rule_id)}
                  aria-label={`${c.rule_id}: ${ruleStatement(reference, c.rule_id)}. `
                    + (expanded
                      ? 'Hide the evidence for this referral'
                      : 'Show the evidence for this referral, where this rule is stated in full')}
                  onClick={(e) => { e.stopPropagation(); onToggle() }}
                  onKeyDown={(e) => e.stopPropagation()}>
                  <SevChip sev={sevBreach(c.passed)} tone="quiet">
                    <TriangleAlert className="ico-sig" strokeWidth={1.75} aria-hidden="true" />
                    <b className="num">{c.rule_id}</b>
                  </SevChip>
                </button>
                {/* ellipsises rather than wrapping, so it carries its full text */}
                {c.detail && <span className="rule-d num" title={c.detail}>{c.detail}</span>}
              </span>
            ))}
            {hiddenRules > 0 && (
              // Same reason as the chip above: a `title` alone is unreachable.
              <button
                type="button" className="rule-more num"
                aria-expanded={expanded}
                title={fired.slice(shownRules.length)
                  .map((c) => `${c.rule_id}: ${ruleStatement(reference, c.rule_id)}`)
                  .join(' · ') + ' · open the row for every rule tested'}
                aria-label={`${hiddenRules} more rule${hiddenRules > 1 ? 's' : ''} fired: `
                  + fired.slice(shownRules.length)
                    .map((c) => `${c.rule_id}, ${ruleStatement(reference, c.rule_id)}`)
                    .join('; ')
                  + '. Show the evidence for this referral, where every rule tested is listed'}
                onClick={(e) => { e.stopPropagation(); onToggle() }}
                onKeyDown={(e) => e.stopPropagation()}>
                +{hiddenRules} more
              </button>
            )}
          </div>
        ) : r.rank ? (
          <span className="rule-ok">
            <Check className="ico-sig" strokeWidth={1.75} aria-hidden="true" />
            every timeframe rule holds
          </span>
        ) : r.crt_breached === true ? (
          <span className="rule-pre">
            past target, and no run has tested a rule against it yet
          </span>
        ) : (
          <span className="muted lst-dash">{ranked ? '—' : 'not tested yet'}</span>
        )}
      </td>

      {/* NEWS2 and the reading's age, always together. On a refused row the total
          is NOT acuity, but reading and age still travel. Cf. Vitals.tsx. */}
      <td className="c-news">
        <div className="cell">
          <span className={'n2 num' + (naNews2 ? ' is-na' : '')}>
            {naNews2
              ? <span className="n2-na">not applied<span className="of"> · adult scale</span></span>
              : (
                <>
                  <span className="n2-v" style={n2Type(r.clin?.news2 ?? null)}>
                    {r.clin?.news2 ?? '—'}
                  </span>
                  <span className="of"> of 17</span>
                </>
              )}
          </span>
          {/* The age is the flex item that never shrinks: it travels with the
              reading for every reader, and the date truncates before it does. */}
          <span className="sub is-split">
            {r.clin?.obs_datetime == null ? 'no reading' : (
              <>
                <span className="sub-t">{dmy(r.clin.obs_datetime)}</span>
                {/* one flex item, always: at sev 0 SevChip renders children bare,
                    and a loose text node cannot truncate. */}
                {age != null && (
                  <span className="sub-age">
                    <SevChip sev={ageSev}
                             title={`the only reading on this pathway, ${fmt(age)} days old`}>
                      <b className="num">{fmt(age)}</b> days old
                    </SevChip>
                  </span>
                )}
              </>
            )}
          </span>
        </div>
      </td>

      {/* triage status: carried by the cohort payload and never rendered before */}
      {!narrow && <td className="c-triage">
        <div className="cell">
          <span className="tri">
            {r.triage_status === 'awaiting_triage' ? 'awaiting triage' : r.triage_status}
          </span>
          <span className="sub">
            {r.days_awaiting_triage != null
              ? <><b className="num">{fmt(r.days_awaiting_triage)}</b> days awaiting triage</>
              : <>referred {dmy(r.referral_date)}</>}
            {r.currently_suspended && <span className="susp"> · suspended</span>}
          </span>
        </div>
      </td>}

      {/* recorded but not scored. MTS keeps its own colour vocabulary, which is
          why it is shown here in a neutral register and never in triage hues. */}
      {!narrow && <td className="c-ctx">
        <div className="cell">
          <span className="ctx-v">
            {r.clin?.mts_category
              ? <>MTS <b>{r.clin.mts_category}</b></>
              : <span className="muted">no MTS</span>}
          </span>
          {/* Only pain varies; the header above already says "not scored". */}
          {r.clin?.pain != null && (
            <span className="sub">pain <span className="num">{r.clin.pain}</span>/10</span>
          )}
        </div>
      </td>}

      <td className="c-exp">
        <button
          type="button" className="expb"
          aria-expanded={expanded}
          aria-label={expanded ? 'Hide the evidence for this referral' : 'Show the evidence for this referral'}
          onClick={(e) => { e.stopPropagation(); onToggle() }}
          onKeyDown={(e) => e.stopPropagation()}>
          {expanded
            ? <ChevronDown className="ico-ctl" strokeWidth={1.75} aria-hidden="true" />
            : <ChevronRight className="ico-ctl" strokeWidth={1.75} aria-hidden="true" />}
        </button>
      </td>
    </motion.tr>
  )
}

/** The mark's geometry, carrying the two terms that decide the order. BOTH bars
 *  are α-weighted: raw urgency against a raw wait percentile overstates waiting
 *  time several times over. Weighted, they sum to the priority the coordinator
 *  used, so comparing them by eye is true. `precise` prints six decimals. */
function RankSpine({ urgency, wait, alpha, priority, tight, precise }: {
  urgency: number; wait: number; alpha: number; priority: number; tight: boolean
  precise?: boolean
}) {
  const u = clamp01(urgency) * alpha
  const w = clamp01(wait) * (1 - alpha)
  const title = `priority ${priority.toFixed(6)} = ${u.toFixed(6)} unwell `
    + `(α ${alpha.toFixed(3)} × ${urgency.toFixed(3)}) + ${w.toFixed(6)} waited `
    + `(1−α ${(1 - alpha).toFixed(3)} × ${wait.toFixed(3)})`
  return (
    <span className={'spn' + (tight ? ' is-tight' : '') + (precise ? ' is-precise' : '')}
          title={title}>
      <span className="spn-g">
        <i className="spn-stem" />
        <i className="spn-u" style={{ width: `${u * 50}%` }} />
        <i className="spn-w" style={{ width: `${w * 50}%` }} />
      </span>
      <span className="spn-n num">{precise ? priority.toFixed(6) : priority.toFixed(2)}</span>
    </span>
  )
}

/** What the priority column cannot say: this row and a neighbour print the same
 *  number. Both halves of the pair carry the line, so the difference is seen. */
function TieLine({ tie, self }: { tie: Tie; self: string }) {
  const other = self === tie.hi ? tie.loPos : tie.hiPos
  const word = tie.exact
    ? 'exact tie · referral date'
    : `${tie.carries === 'urgency' ? 'unwell' : 'waited'} decides`
  const title = tie.exact
    ? `Position ${tie.hiPos} and position ${tie.loPos} carry the same priority to every `
      + `decimal place (${tie.hiP.toFixed(6)}). Priority cannot separate them, so the order `
      + 'falls through to referral date, step 5 of the key.'
    : `Position ${tie.hiPos} is ${tie.hiP.toFixed(6)} and position ${tie.loPos} is `
      + `${tie.loP.toFixed(6)}, a margin of ${tie.delta.toFixed(6)}. `
      + `α × urgency differs by ${tie.du.toFixed(6)} and (1 − α) × wait_normalised by `
      + `${tie.dw.toFixed(6)}, so ${term(tie.carries)} carries it.`
  return (
    <span className={'tie' + (tie.exact ? ' is-exact' : '')} title={title}>
      <span className="tie-w" aria-hidden="true">{word}</span>
      <span className="vh">
        {tie.exact
          ? `equal at every decimal place to position ${other}, so referral date places them`
          : `printed priority ties with position ${other}; ${term(tie.carries)} separates them `
            + `by ${tie.delta.toFixed(6)}`}
      </span>
    </span>
  )
}

/** Waiting time against target. The target sits at a fixed mark and the overflow
 *  past it is compressed, so a 31× and a 1.2× overrun share one axis; the numeral
 *  beside the bar always carries the true value. A missing target is an open tick,
 *  never a zero. */
function WaitBar({ ratio, sev }: { ratio: number | null; sev: Sev }) {
  if (ratio == null) {
    return (
      <span className="wb is-none" aria-hidden="true">
        <i className="wb-tick" />
      </span>
    )
  }
  const within = Math.min(1, ratio) * 62
  const overflow = ratio > 1 ? Math.sqrt(Math.min((ratio - 1) / 9, 1)) * 38 : 0
  return (
    <span className="wb" data-sev={sev} aria-hidden="true">
      <i className="wb-in" style={{ width: `${within}%` }} />
      {overflow > 0 && <i className="wb-over" style={{ left: '62%', width: `${overflow}%` }} />}
      <i className="wb-mark" />
    </span>
  )
}

/* -------------------------------------------------- the inline expander D3 -- */

/** Evidence in place, one interaction away. NFR5: no score is rendered without
 *  its cited evidence attached, which is what this panel is. */
function Evidence({ r, hospital, reference, ops, decision, tie, onMove, onOpen }: {
  r: Row; hospital: string; reference: Reference | undefined
  ops: ReturnType<typeof useList>['ops']
  decision: Decision | undefined
  tie: Tie | undefined
  onMove: (r: Ranking) => void
  onOpen: (pw: string) => void
}) {
  const ctx = useQuery({
    queryKey: ['context', hospital, r.pathway_number],
    queryFn: () => api.context(hospital, r.pathway_number),
    staleTime: Infinity, retry: false,
  })

  const obsCites: Citation[] = (r.rank?.urgency_citations ?? [])
    .filter((c) => c.evidence_type === 'observation')
  const capCites: Citation[] = r.rank?.capacity_citations ?? []

  const citedAt = obsCites.length ? keyParts(obsCites[0].evidence_key)[2] : r.clin?.obs_datetime
  const obs: Observation | undefined =
    ctx.data?.observations.find((o) => sameMoment(o.obs_datetime, citedAt))
    ?? ctx.data?.observations[0]

  const wardKey = capCites.find((c) => c.evidence_type === 'bed_status')
  // Same derivation as List's `refused` set and Patient's: the SPECIALTY, never
  // a decision -- /api/decision 404s on most days.
  const evRefused = isRefusedPaediatric(r.specialty_hipe)
  const clinicKey = capCites.find((c) => c.evidence_type === 'clinic_session')
  const ward = wardKey ? ops?.wards.find((w) => w.ward_id === keyParts(wardKey.evidence_key)[1]) : undefined
  const clinic = clinicKey
    ? ops?.clinics.find((c) => c.clinic_code === keyParts(clinicKey.evidence_key)[1])
    : undefined
  /** TRAP: `slots_booked / slots_total / slots_available` are SERIES totals, while
   *  `cited_pressure` is booked / total for the ONE session the agent read. On one
   *  line they refute each other ("15 free · pressure 1.000"), so the cited session
   *  is resolved here. Same resolution as Overview.tsx citedSession(). */
  const citedSess = clinic && clinic.cited_session_date
    ? clinic.sessions.find((s) => s.session_date === clinic.cited_session_date)
    : undefined

  const checks: RuleCheck[] = r.rank?.rule_checks ?? []
  const age = r.clin?.reading_age_days ?? null
  const ageSev = sevReadingAge(age)

  return (
    <div className="ev">
      <div className="ev-grid">

        {/* why this position */}
        <section className="ev-b">
          <h3 className="ev-h">
            Why this position
            <span className="ev-hn">the coordinator's own note</span>
          </h3>
          {r.rank ? (
            <>
              <p className="ev-p">{r.rank.rationale_summary ?? 'No rationale was recorded.'}</p>
              {/* The rationale names a capacity score, which reads as if it
                  placed this person; it did not, and the text is template output,
                  not a model's opinion. Both said here, beside it.

                  A DEFINITION printing once per expanded row, so it belongs behind
                  an <Aside> -- but Aside bars itself from inside .lst-table by
                  contract, since this expander IS the table's disclosure. Kept
                  short in place instead. */}
              <p className="ev-p ev-p-meta">
                Deterministic template text from the coordinator: no model wrote this
                sentence. The capacity score it names belongs to the whole specialty and
                set <span className="num">α</span>; it did not move this referral.
              </p>
              {/* Six decimals: at three, adjacent pairs become indistinguishable
                  and the two terms stop reconciling with their own sum. */}
              <dl className="ev-terms">
                <div><dt>how unwell</dt>
                  <dd className="num">{r.rank.urgency_score.toFixed(3)} × α {r.rank.alpha.toFixed(3)}
                    {' = '}<b>{(r.rank.urgency_score * r.rank.alpha).toFixed(6)}</b></dd></div>
                <div><dt>how long waited</dt>
                  <dd className="num">{r.rank.wait_normalised.toFixed(3)} × {(1 - r.rank.alpha).toFixed(3)}
                    {' = '}<b>{(r.rank.wait_normalised * (1 - r.rank.alpha)).toFixed(6)}</b></dd></div>
                <div className="ev-tsum"><dt>priority</dt>
                  <dd className="num"><b>{r.rank.priority.toFixed(6)}</b></dd></div>
              </dl>
              {tie && (
                <p className={'ev-tie' + (tie.exact ? ' is-exact' : '')}>
                  <strong>
                    Position <span className="num">{tie.hiPos}</span> and position{' '}
                    <span className="num">{tie.loPos}</span> print the same priority at three
                    decimals.
                  </strong>{' '}
                  {tie.exact ? (
                    <>They are equal at every decimal place, so priority genuinely cannot
                    separate them and the order falls through to referral date, step 5 of the
                    key. Nothing about this pair was decided by a score.</>
                  ) : (
                    <>
                      They are not equal: <span className="num">{tie.hiP.toFixed(6)}</span>{' '}
                      against <span className="num">{tie.loP.toFixed(6)}</span>, a margin of{' '}
                      <span className="num">{tie.delta.toFixed(6)}</span>. The two terms pull
                      opposite ways, so the margin is what is left of them:{' '}
                      <span className="num">α × urgency</span> differs by{' '}
                      <span className="num">{tie.du.toFixed(6)}</span> and{' '}
                      <span className="num">(1 − α) × wait_normalised</span> by{' '}
                      <span className="num">{tie.dw.toFixed(6)}</span>, so{' '}
                      <b>{term(tie.carries)}</b> is what carries it.
                    </>
                  )}
                </p>
              )}
              <p className="ev-cav">
                Priority is compared only after category, severity and the past-target tier have
                tied. It cannot move anyone between categories.
              </p>
            </>
          ) : (
            <p className="ev-p">
              {r.exclusion
                ? <>The coordinator recorded <span className="num">{r.exclusion}</span>: no
                  urgency score reached the ranking, so no position could be computed. This is
                  not a low position.</>
                : 'No run has scored this referral, so there is no position and no rationale.'}
            </p>
          )}
        </section>

        {/* rules */}
        <section className="ev-b">
          <h3 className="ev-h">
            Rules tested
            <span className="ev-hn">{checks.length ? `${checks.length} checks · core.ref_rules` : 'core.ref_rules'}</span>
          </h3>
          {checks.length ? (
            <ul className="ev-rules">
              {checks.map((c) => (
                <li key={c.rule_id} className={c.passed ? '' : 'is-bad'}>
                  {/* A breach is a solid block; "holds" is not an attention state
                      and keeps the neutral pill. */}
                  <span className="ev-vd">
                    {c.passed ? (
                      <span className="ev-ok">
                        <Check className="ico-sig" strokeWidth={1.75} aria-hidden="true" />
                        holds
                      </span>
                    ) : (
                      <SevChip sev={sevBreach(c.passed)}>
                        <TriangleAlert className="ico-sig" strokeWidth={1.75} aria-hidden="true" />
                        breached
                      </SevChip>
                    )}
                  </span>
                  <span className="ev-rid num">{c.rule_id}</span>
                  <span className="ev-rst">{ruleStatement(reference, c.rule_id)}</span>
                  {c.detail && <span className="ev-rd num">{c.detail}</span>}
                  {WHOLE_LIST.has(c.rule_id) && (
                    <span className="ev-rw">tested against the whole list, not this row</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="ev-p muted">
              No run has tested a rule against this referral.
              {r.crt_breached === true && ' The cohort still records it as past its target.'}
            </p>
          )}
        </section>

        {/* the cited vitals */}
        <section className="ev-b ev-wide">
          <h3 className="ev-h">
            Cited vitals
            <span className="ev-hn">
              {obsCites.length
                ? `${obsCites.length} citations from one reading`
                : 'no citations · nothing has scored this referral'}
              {citedAt && <> · {dmyt(citedAt)}</>}
            </span>
            {age != null && (
              <span className="ev-age">
                <SevChip sev={ageSev} title={`the reading is ${fmt(age)} days old`}>
                  <b className="num">{fmt(age)}</b> days old
                </SevChip>
              </span>
            )}
          </h3>
          {ageSev > 0 && (
            <p className="ev-stale">
              This reading has never been repeated. Its date is also how long this person has
              gone unmeasured, so a normal number here is an absence of information rather
              than a reassurance.
            </p>
          )}
          {ctx.isPending && <p className="ev-p muted">Reading the observation…</p>}
          {ctx.isError && (
            <p className="ev-p muted">
              The observation could not be read. The citation keys below are still what the
              agent recorded.
            </p>
          )}
          <div className="ev-vitals">
            {(obsCites.length
              ? obsCites.map((c) => keyParts(c.evidence_key)[3])
              : ['hr', 'sbp', 'rr', 'spo2', 'temp', 'avpu']
            ).map((k) => (
              <div className={'ev-v' + (obsCites.length ? ' is-cited' : '')} key={k}>
                <div className="ev-vk">{VITAL[k]?.k ?? k}</div>
                <div className="ev-vv">{vitalValue(obs, k)}</div>
                <div className="ev-vu">{VITAL[k]?.u ?? ''}</div>
              </div>
            ))}
          </div>
          {/* Derived HERE from the specialty, not taken from a prop: Evidence is
              reachable from every tab, and the NEWS2 column's gate is per-TAB and
              only correct while the grouping puts refusal before band. The vitals
              stay -- a clinician recorded them, and a refusal is about the
              INSTRUMENT, not the record. */}
          <p className="ev-cav">
            {evRefused
              ? <>These are the vitals a NEWS2 would be built from. NEWS2 is validated in
                adults, so specialty 0601 is refused rather than scored, and no total was
                formed from them.</>
              : obsCites.length
              ? <>A clay underline marks a vital the urgency agent actually cited. NEWS2{' '}
                <span className="num">{r.clin?.news2 ?? obs?.news2 ?? '—'}</span> of 17 is the
                sum of these, zeros included.</>
              : <>These are the vitals NEWS2 is built from. Nothing has cited them on this
                hospital-day.</>}
          </p>
        </section>

        {/* the cited capacity rows */}
        <section className="ev-b ev-wide">
          <h3 className="ev-h">
            Cited capacity
            <span className="ev-hn">
              {/* "citations", not "rows": the clinic citation takes two lines on
                  screen, so a line count would be a different number. */}
              {capCites.length
                ? `${capCites.length} citation${capCites.length === 1 ? '' : 's'} · specialty-level`
                : 'no citations'}
            </span>
          </h3>
          {capCites.length ? (
            <>
              <div className="ev-cap">
                {ward && wardKey && (
                  <div className="ev-cap-r">
                    <span className="lab">bed status</span>
                    <span className="ev-cap-k num">{ward.ward_id}</span>
                    {/* occupancy_pct is against the CENSUS, not the nominal
                        allocation, so the two are never divided into one another.
                        TrolleyGAR's green/amber/red is the HSE's vocabulary, not
                        the triage palette. */}
                    <span className="ev-cap-v">
                      <b className="num">{ward.occupancy_pct.toFixed(1)}%</b> occupied ·{' '}
                      <span className="num">{ward.occupied ?? '—'}</span> of{' '}
                      <span className="num">{ward.census ?? '—'}</span> recorded ·{' '}
                      <span className="num">{ward.free ?? '—'}</span> free · TrolleyGAR{' '}
                      <span className="num">{ward.gar_status ?? '—'}</span>
                    </span>
                    <span className="ev-cap-d">
                      nominal <span className="num">{ward.nominal_beds ?? '—'}</span> beds ·
                      snapshot {dmyt(keyParts(wardKey.evidence_key)[2])}
                    </span>
                  </div>
                )}
                {clinic && clinicKey && (
                  <>
                    {/* The cited session and nothing else on the line carrying the
                        cited pressure: booked / total here must divide into it. */}
                    <div className="ev-cap-r">
                      <span className="lab">clinic session</span>
                      <span className="ev-cap-k num">{clinic.clinic_code ?? '\u2014'}</span>
                      <span className="ev-cap-v">
                        {citedSess == null ? (
                          /* The cited date is not among the sessions returned, so
                             its pressure cannot be checked here. Absence, stated. */
                          <>slots for that session were not returned · pressure{' '}
                            <span className="num">{clinic.cited_pressure.toFixed(3)}</span>{' '}
                            cannot be reconciled on this screen</>
                        ) : citedSess.slots_total === 0 ? (
                          /* scoring.py returns exactly 1.0 when slots_total is 0,
                             so "every slot taken" and "no clinic sat" are one
                             number; only the session tells them apart. */
                          <>no clinic sat that day · <span className="num">0</span> slots offered ·
                            pressure <span className="num">{clinic.cited_pressure.toFixed(3)}</span>{' '}
                            is the value the agent uses when there is no session to divide into</>
                        ) : (
                          <><b className="num">{citedSess.slots_booked}</b> of{' '}
                            <span className="num">{citedSess.slots_total}</span> slots booked ·{' '}
                            <span className="num">{citedSess.slots_available}</span> free · pressure{' '}
                            <span className="num">{clinic.cited_pressure.toFixed(3)}</span></>
                        )}
                      </span>
                      <span className="ev-cap-d">
                        the one session cited: {clinic.cited_session_date ?? keyParts(clinicKey.evidence_key)[2]}
                      </span>
                    </div>
                    {/* Context around the cited row, never the arithmetic behind
                        its pressure, so it gets its own line and says so. */}
                    <div className="ev-cap-r">
                      <span className="lab">clinic series</span>
                      <span className="ev-cap-k num">
                        {clinic.sessions.length
                          ? `${clinic.sessions.length} sessions`
                          : '\u2014'}
                      </span>
                      <span className="ev-cap-v">
                        {clinic.sessions.length
                          ? `across ${clinic.sessions.length} session${clinic.sessions.length === 1 ? '' : 's'}: `
                          : 'series total, no sessions returned: '}
                        <span className="num">{clinic.slots_booked}</span> of{' '}
                        <span className="num">{clinic.slots_total}</span> booked ·{' '}
                        <span className="num">{clinic.slots_available}</span> free
                      </span>
                      <span className="ev-cap-d">
                        context, not the arithmetic behind the pressure above
                      </span>
                    </div>
                  </>
                )}
                {!ward && !clinic && (
                  <div className="ev-cap-r">
                    <span className="lab">cited</span>
                    <span className="ev-cap-v num">
                      {capCites.map((c) => keyParts(c.evidence_key)[1]).join(' · ')}
                    </span>
                    <span className="ev-cap-d">operational context is not loaded</span>
                  </div>
                )}
              </div>
              {r.rank?.capacity_detail && (
                <div className="ev-cap-sum num">
                  ward pressure {r.rank.capacity_detail.ward_pressure?.toFixed(3) ?? '—'} ·
                  clinic pressure {r.rank.capacity_detail.clinic_pressure?.toFixed(3) ?? '—'} ·
                  capacity score {r.rank.capacity_score.toFixed(3)}
                </div>
              )}
              <p className="ev-cav">
                Capacity is specialty-level and identical for everyone in this specialty. It sets
                α for the whole hospital-day and can never move one person above another.
              </p>
            </>
          ) : (
            <p className="ev-p muted">No capacity row has been cited for this referral.</p>
          )}
        </section>

        {/* record fields, explicitly not evidence */}
        <section className="ev-b">
          <h3 className="ev-h">
            Recorded, not scored
            <span className="ev-hn">record fields</span>
          </h3>
          <dl className="ev-terms">
            <div><dt>MTS category</dt>
              <dd>{r.clin?.mts_category ?? '—'}</dd></div>
            <div><dt>Condition code</dt>
              <dd className="num">{r.clin?.icd10am_code ?? '—'}</dd></div>
            <div><dt>Pain</dt>
              <dd className="num">{r.clin?.pain ?? '—'}</dd></div>
          </dl>
          {/* A DEFINITION (ADR-004) that would belong behind an <Aside>, which
              bars itself from inside .lst-table. Kept short in place instead. */}
          <p className="ev-cav">
            MTS keeps its own red/orange/yellow/green/blue vocabulary, so it is shown as a
            word and never in triage hues (ADR-004). The condition code is a weighted random
            draw over the specialty's mix, independent of acuity: never a finding.
          </p>
        </section>

        {/* what a clinician did, and what they can do */}
        <section className="ev-b">
          <h3 className="ev-h">
            Recorded action
            <span className="ev-hn">agent.overrides</span>
          </h3>
          {r.ovr ? (
            <div className="ev-ovr">
              <div className="ev-ovr-l">
                {r.ovr.to_position === r.ovr.from_position
                  ? <>Position <span className="num">{r.ovr.from_position ?? '—'}</span> confirmed</>
                  : <>Moved from <span className="num">{r.ovr.from_position ?? '—'}</span> to{' '}
                    <span className="num">{r.ovr.to_position ?? '—'}</span></>}
                {' by '}<b>{r.ovr.clinician_id}</b>, {dmyt(r.ovr.created_at)}
              </div>
              <div className="ev-ovr-r">{r.ovr.reason}</div>
              {r.ovr.rule_warning_accepted && (
                <div className="ev-warn">category boundary crossed, accepted on the record</div>
              )}
              {!r.ovrLive && (
                <div className="ev-ovr-n">
                  Recorded against decision <span className="num">{r.ovr.decision_id}</span>, not
                  the one on screen. Its position refers to a list that no longer exists, so the
                  row has not been moved.
                </div>
              )}
            </div>
          ) : (
            <p className="ev-p muted">Nobody has confirmed or moved this referral.</p>
          )}
          <div className="ev-acts">
            {r.rank && decision && (
              <button type="button" className="pg" onClick={() => onMove(r.rank as Ranking)}>
                Move or confirm this position
              </button>
            )}
            <button type="button" className="pg" onClick={() => onOpen(r.pathway_number)}>
              Open the full record
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}
