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
/** Median wait. ONE home, lib/stats.ts, shared with Overview.tsx -- the two
 *  surfaces used to hold a copy each and printed 141 against 142 on 2026-08-21. */
import { median } from '../lib/stats'
import { SevChip, SevLegend } from '../components/Severity'
import { Override } from '../components/Override'
import type {
  CohortReferral, Citation, Decision, Observation, OverrideRecord, Overrides,
  Ranking, Reference, RuleCheck,
} from '../lib/types'
import './list.css'

/** The ranked list.
 *
 *  The page used to open with a six-line paragraph explaining the sort order.
 *  A sort key is a structure, so it is drawn as one: six numbered steps, with
 *  the hidden third tier (past target first, before any score is compared)
 *  carrying the composition's one clay accent, because that tier is the thing
 *  readers kept missing and the thing that makes adjacent rows look wrong.
 *
 *  Everything the cohort payload carries is now on screen. triage_status,
 *  days_awaiting_triage and currently_suspended had never been rendered
 *  anywhere; neither had a rule ID, though the coordinator has produced 776
 *  rule checks since the first run.
 */

const fmt = (n: number) => n.toLocaleString('en-IE')
const pct = (n: number) => `${Math.round(n * 100)}%`
const clamp01 = (n: number) => Math.max(0, Math.min(1, n))
/** A date that will not parse prints as the no-value placeholder, never as
 *  "Invalid Date": evidence keys are strings from another service and may not
 *  be dates at all. */
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

/** How far past target, as a numeral. 31x rounds, 1.2x keeps its decimal, and
 *  the numeral always carries the true value whatever the bar does with it. */
const ratioText = (r: number) => (r >= 10 ? String(Math.round(r)) : r.toFixed(1))

/** NEWS2 typeset so that a 7 does not look like a 0.
 *
 *  Weight and size, no band and no colour. NEWS2 TOTAL is deliberately outside
 *  the severity scale (lib/severity.ts: 148 of 308 tie at exactly 0, so a
 *  graded scale on it would be flat across half the list), and any threshold
 *  drawn here would be an invented one. This is a continuous map from the value
 *  to its weight: a magnitude channel, not a claim. */
const n2Type = (n: number | null): CSSProperties => {
  if (n == null) return {}
  const t = clamp01(n / 17)
  return { fontWeight: 400 + Math.round(t * 300), fontSize: `${(14 + t * 7).toFixed(1)}px` }
}

const UNPLACED = 1e9

/* ------------------------------------------------------------- geometry -- */

/** The table's column widths, in ONE place, because the table's own min-width
 *  has to be derived from them.
 *
 *  `table-layout: fixed` gives the elastic column whatever is left after every
 *  specified width is honoured. The specified widths summed to 1154px while the
 *  table's min-width was 1120px, so the one auto column (Referral) was allotted
 *  -34px, which is to say 0. td overflow is `visible`, so the pathway number,
 *  the planted chip and the override badge painted straight over the Waited
 *  column at every width from 1440 up. That is the "compact version overlaps"
 *  report, and 1440x900 and 1536x864 are both inside it.
 *
 *  min-width is now the fixed sum PLUS a reserved minimum for Referral, so the
 *  elastic column can never be squeezed to nothing again. The worst case is
 *  that .lst-vp scrolls sideways, which is what .lst-vp is for. */
const COL = {
  pos: 76, spine: 140, wait: 200, rule: 240, news: 180,
  triage: 144, ctx: 132, exp: 42,
} as const

/** Referral's floor. "Otolaryngology (ENT) · 0600" beside a pathway number and
 *  a planted chip does not fit in less. */
const COL_REF = 260

/** Nine columns need 1414px of table, seven need 1138:
 *
 *    9 cols  76+140+200+240+180+144+132+42 = 1154 + 260 Referral = 1414
 *    7 cols  76+140+200+240+180+42         =  878 + 260 Referral = 1138
 *
 *  The chrome between the viewport and the table is THREE terms, and this
 *  comment used to count two. It stopped at "300px at 1440 and above (rail 236
 *  + 2x32)", which is the content column -- but the table does not get the
 *  content column, it gets what is inside .lst-vp, and .lst-vp has a 1px border
 *  on each side (list.css). That third term is where 1714 came from:
 *
 *    >= 1440   rail 236 + .pad 2x32 + .lst-vp 2x1 = 302px
 *    <  1440   rail  64 + .pad 2x16 + .lst-vp 2x1 =  98px   (app.css @1439)
 *
 *  The rail's own border-right is NOT a fourth term: `* { box-sizing:
 *  border-box }` (tokens.css) keeps it inside the 236px grid track. Measured in
 *  the running app at a 1716px viewport, .main starts at x=236 and is 1480 wide,
 *  not 1479.
 *
 *  Measured at each width -- .lst-vp clientWidth, and whether it actually grew a
 *  horizontal scrollbar:
 *
 *    viewport  rail  .pad  chrome  .lst-vp inner  cols  needs  result
 *      1280      64  2x16      98           1182     7   1138  44px spare
 *      1440     236  2x32     302           1138     7   1138  fits exactly
 *      1715     236  2x32     302           1413     9   1414  1px SHORT
 *      1716     236  2x32     302           1414     9   1414  fits exactly
 *      1920     236  2x32     302           1618     9   1414  204px spare
 *
 *  So the ninth column first fits at 1716 and the old 1714 switched it on two
 *  pixels early: at 1714 and 1715 the table was 1414px inside a 1412/1413px box,
 *  and .lst-vp grew a sideways scrollbar at the exact width that added the
 *  column. Confirmed on the running build at 1715: scrollWidth 1414 against
 *  clientWidth 1413.
 *
 *  One thing this constant cannot model: on a platform with classic rather than
 *  overlay scrollbars, .lst-vp's own VERTICAL scrollbar takes ~15px more of that
 *  inner width, and the fit moves with it. The measurements above are macOS
 *  overlay scrollbars, where it takes none.
 *
 *  Triage and Context are the two that go below the breakpoint: Triage reads
 *  "triaged" on 307 of 308, Context's subline was identical on every row, and
 *  both are in the expander in full. */
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
  /** True only when that override was recorded against the decision on screen.
   *  An override from an earlier decision names a position in a list that no
   *  longer exists, so it is shown but never allowed to move a row. */
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
  // 404 until a run has produced one. That is a normal state, not an error.
  const decision = useQuery<Decision>({
    queryKey: ['decision', hospital, date], queryFn: () => api.decision(hospital, date),
    retry: false, staleTime: 5_000,
  })
  const overrides = useQuery<Overrides>({
    queryKey: ['overrides', hospital, date], queryFn: () => api.overrides(hospital, date),
    retry: false,
  })

  /** The displayed order: the coordinator's positions, then every override that
   *  belongs to THIS decision applied oldest first, so the newest one wins.
   *  Nothing is interpolated: a row is either in a slot or it is not. */
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

  /** The displayed order as a list, so the override dialog can decide whether a
   *  move crosses a category boundary IN THE LIST THE CLINICIAN IS LOOKING AT.
   *  Computed against decision.rankings it was answering about a different list:
   *  after one override, displayed position N is a different person, so the
   *  warning could stay silent for a move that visibly crosses a boundary, and
   *  rule_warning_accepted would then be stored false for a crossing that did
   *  happen. */
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
    case 'news2': return r.clin?.news2 ?? null
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

/** Two rows, adjacent in the suggested order, whose priorities print the same.
 *
 *  On 9001/2026-08-30 twelve adjacent in-band pairs differ only from the fourth
 *  decimal: positions 18 and 19 are 0.282693 and 0.282539, and both print
 *  0.283. Sixteen further pairs are equal to the last bit and correctly fall
 *  through to referral date. At three decimals the two kinds are indis-
 *  tinguishable, and the surface then says priority decided the order. So the
 *  pair is named, the margin is printed at the precision that carries it, and
 *  the term that carries it is named as well.
 *
 *  In every near-tie in this decision the two terms pull in OPPOSITE
 *  directions: alpha x urgency puts one row ahead by ~0.061 while
 *  (1 - alpha) x wait_normalised puts the other ahead by ~0.061, and the
 *  residue is the margin. Naming the winner without naming that is a half
 *  truth, so both differences travel. */
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
  /** The term pulling in the direction the pair actually resolved. Null when
   *  nothing resolved it and referral date had to. */
  carries: 'urgency' | 'wait' | null
}

const term = (t: Tie['carries']) => (t === 'urgency' ? 'how unwell' : 'how long waited')

/** Every such pair in a decision, keyed by both of its pathway numbers.
 *
 *  Computed from the coordinator's own positions rather than from what is on
 *  screen, so the fact survives a filter, a page and a different sort: it is a
 *  property of the decision, not of the view. Only pairs in the same breach
 *  tier are compared, because priority is only reached once that tier has tied
 *  (step 3 of the key), so two rows either side of the boundary were never
 *  separated by a score at all. */
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
        // delta is positive by construction, so the larger of the two
        // differences is the positive one and is the term that carried it.
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

  // Union of what the decision refused and what the SPECIALTY refuses. ADR-007
  // refuses 0601 unconditionally (urgency-agent scoring.py:88), so this must hold
  // on the 13 days that have no decision at all -- otherwise the Outside tab is
  // empty and a child's adult NEWS2 renders under "How unwell" on every one of
  // them, which is exactly the pre-ranking view this round built.
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

  // Breaches are always of the referrals that HAVE a target. 143 of 308 have
  // none at all, so "130 of 308" would be a different and untrue statement.
  const figures = useMemo(() => {
    const withTarget = rows.filter((r) => targetOf(r, reference) != null)
    return {
      onList: rows.length,
      withTarget: withTarget.length,
      past: withTarget.filter((r) => r.crt_breached === true).length,
      noTarget: rows.length - withTarget.length,
    }
  }, [rows, reference])

  /** The state before ranking, which the client asked for by name: how many
   *  are waiting, and with what, so that running the agents is a step the
   *  reader chooses rather than a screen they arrive at. Everything here is
   *  counted from the cohort, so it is true of a day nothing has scored.
   *
   *  WORDING. Every figure in this panel is counted off `rows`, which is the
   *  cohort's referrals -- so the headline counts ROWS and says referrals.
   *  Landing.tsx made the same change first and argues it at length: this
   *  screen can see a list, not a population, and the dataset plants
   *  PW-DEMO-06/07 (one pair of referrals across two hospitals) and
   *  PW-COLLIDE-01 (the same pathway number at two hospitals) precisely so
   *  that a list holding more rows than it holds people is representable.
   *  This is NOT a hedge and must not become one: the numeral is as large and
   *  as immediate as it was, nothing qualifies it, and the synthetic-data
   *  label the client had removed does not come back. The fix is in the noun,
   *  and it costs the screen nothing. */
  const pre = useMemo(() => {
    if (ranked || !rows.length) return null
    const waits = rows.map((r) => r.adjusted_wait_days ?? 0).sort((a, b) => a - b)
    const n = waits.length
    const ratios = rows.map((r) => ratioOf(r, reference)).filter((x): x is number => x != null)
    const steps = rows.map((r) => sevReadingAge(r.clin?.reading_age_days ?? null))
    const n2 = rows.map((r) => r.clin?.news2).filter((x): x is number => x != null)
    return {
      // lib/stats.ts, the same call Overview.tsx makes. Sorted here already for
      // min/max; median() sorts its own copy, so the two cannot drift.
      median: median(waits), min: waits[0], max: waits[n - 1],
      worst: ratios.length ? Math.max(...ratios) : null,
      // graded by the frozen scale rather than by a threshold invented here:
      // sevReadingAge answers what a year-old and a two-year-old reading are.
      year: steps.filter((x) => x >= sevReadingAge(365)).length,
      twoYear: steps.filter((x) => x >= sevReadingAge(730)).length,
      noReading: rows.filter((r) => r.clin?.obs_datetime == null).length,
      n2n: n2.length,
      n2zero: n2.filter((x) => x === 0).length,
      n2max: n2.length ? Math.max(...n2) : null,
      awaiting: rows.filter((r) => r.triage_status === 'awaiting_triage').length,
    }
  }, [rows, ranked, reference])

  /** Adjacent pairs the printed priority cannot separate. Computed from the
   *  decision's own positions, so the fact holds under any filter or sort. */
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
      {/* mounted unconditionally: a polite region has to be observed BEFORE its
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
            {/* /api/operations takes 3.255s cold and 0.003s warm. Until it
                lands, r.clin is undefined on all 308 rows and `pre` is computed
                from nulls -- so this panel used to assert "No observation has
                been read on this hospital-day", an absolute, for three seconds,
                on the panel the client asked for by name. It is 308 of 308 on
                the real data. */}
            <PreFig k={opsPending
              ? 'carry a NEWS2. Reading the observations…'
              : pre.n2max == null
              ? 'carry a NEWS2. No observation has been read on this hospital-day.'
              : `carry a NEWS2. ${fmt(pre.n2zero)} of those are 0 and the highest is `
                + `${pre.n2max} of 17, which is why NEWS2 total is never the thing that ranks.`}>
              <b className="num">{fmt(pre.n2n)}</b>
            </PreFig>
          </div>
          <p className="pre-p">
            Rows sit in referral-date order, which is a display order and carries no clinical
            claim: nothing below has been scored, placed or tested against a rule yet.{' '}
            <strong>Run the agents from the top bar</strong> and these same{' '}
            <span className="num">{fmt(figures.onList)}</span> rows come back in a suggested
            order, each one carrying its score, the evidence cited for it and every rule
            tested against it.
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

      {/* Both of these are reference material: true, worth having, and read
          once. Left open they pushed the actual list below the fold on a
          1080-tall screen, which is the opposite of what a working surface
          should do. They open on demand and remember nothing, because the
          answer does not change. */}
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

/** One figure in the before-ranking summary. The value is a node rather than a
 *  number because some of these are graded and arrive as a severity chip. */
function PreFig({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="pre-f">
      <div className="pre-f-v">{children}</div>
      <div className="pre-f-k">{k}</div>
    </div>
  )
}

/* ----------------------------------------------------- the sort key, drawn -- */

/** The order used to be explained in a paragraph. A sort key is a structure, so
 *  it is drawn as one: six ordered steps, each naming the rule it comes from.
 *  Step 3 is the tier readers kept missing (everyone past target ranks above
 *  everyone within it, before any score is compared), so it takes the one clay
 *  accent this composition is allowed.
 *
 *  Steps 4 and 5 carry what the printed order cannot show on its own: how many
 *  pairs the priority column cannot separate at the precision it prints, and
 *  how many are genuinely equal and reach step 5. */
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
            {/* The rule a step comes from, and what it SAYS. The statement
                was a `title` on this span and nowhere else, so the ladder --
                the surface whose whole job is explaining the order -- named
                RULE-CRT-URGENT and left the sentence under a pointer. Step 3
                cites two rules and only the first one's statement was even on
                the tooltip. */}
            {s.rule && (
              <span className="key-r">
                {s.rule.split(' · ').map((id) => {
                  // ruleStatement falls back to the ID itself while
                  // core.ref_rules is still loading, and printing the ID twice
                  // says nothing: the step shows the ID alone on the first
                  // paint, as it always did, and gains the sentence when the
                  // reference lands.
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

/** The four not-ranked buckets, separately labelled and reconciled by set
 *  union. They overlap: the three paediatric referrals are refused by the
 *  urgency agent AND recorded by the coordinator as missing_urgency_score, so
 *  adding them reads as 311 of 308 and loses what each bucket means. */
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
      w: 'no urgency score reached the ranking, so no position could be computed',
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
  /** The whole cohort, so the Outside tab can reconcile its counts against
   *  the Overview's without hardcoding a number that is wrong on 9002. */
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
  // Nine columns need 1414px of table and only have it from a 1716px viewport
  // up (rail 236 + .pad 2x32 + .lst-vp's own 2x1 border = 302px of chrome), so
  // below that the table drops Triage and Context rather than paint the Referral
  // cell over the Waited column. See COL and NINE_COL_PX above.
  const narrow = useNarrow(NINE_COL_PX)
  // a new sort, a new filter or a new category always starts at the top of the
  // category, never mid-list
  useEffect(() => { setPage(0) }, [p.rows, p.size])

  const target = p.outside ? null : bandTarget(p.bandKey, p.reference)
  const past = p.rows.filter((r) => r.crt_breached === true).length
  const moved = p.rows.filter((r) => r.ovr && r.ovrLive
    && r.ovr.to_position !== r.ovr.from_position).length

  if (!p.rows.length) {
    // A filter that matches only in another category left the reader looking at
    // "nothing matches" while a tab two inches away showed a count. The counts
    // were right; the dead end was the problem. Name where the matches are and
    // offer to go there.
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

  return (
    <>
      <p className="lst-note">
        {p.outside ? (
          <>
            Not scored, not placed. <strong>This is not a low position.</strong> NEWS2 is
            validated in adults, so the urgency agent refuses paediatric specialties rather
            than scoring a child on an adult scale. Category and waiting time are shown in
            full, because a clinician recorded those.
            {/* These rows are counted HERE and not in their clinical band, so
                the tab counts above are the ranking's counts and differ from the
                Overview's, which bands all 308 by CPC. Two correct numbers that
                would otherwise change by 2 when you click between surfaces. */}
            {p.rows.length > 0 && (
              <> They are counted here rather than in their clinical band ({' '}
                <strong>{
                  Object.entries(p.rows.reduce((a: Record<string, number>, r) => {
                    const b = bandOf(r.cpc); a[b] = (a[b] ?? 0) + 1; return a
                  }, {})).map(([b, n]) => `${n} ${b}`).join(' · ')
                }</strong> ), so the tab counts above are of the ranking, while the
                Overview bands all {fmt(p.onList)} by category.</>
            )}
          </>
        ) : target == null ? (
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
        {moved > 0 && (
          <> · <strong className="num">{moved}</strong> row{moved > 1 ? 's' : ''} here sit
          where a clinician placed {moved > 1 ? 'them' : 'it'}, not where the system did.</>
        )}
      </p>

      {/* The scale, once, immediately above the rows it grades. Every graded
          mark in the table below -- the wait bar, the wait-against-target step,
          the reading's age, the rule that fired -- is drawn from this one
          four-step ladder, and the ladder had never been stated anywhere on the
          surface that spends it. It belongs to components/Severity.tsx; this
          surface places it and does not redraw it. */}
      <SevLegend className="lst-legend" />

      <div className={'scroll-x lst-vp' + (p.tight ? ' is-tight' : '')}>
        {/* min-width is DERIVED, never written down: the specified widths plus
            Referral's reserved minimum. Written down it was 1120 against a
            1154 sum, and `table-layout: fixed` handed the elastic column its
            remainder of -34px. */}
        <table className="lst-table" style={{ minWidth: tableMin(narrow) }}>
          {/* Referral is the one elastic column: specialty names vary, and the
              rule chip must never wrap onto a second line inside a row. It is
              the column with no width here, so it takes what is left, and the
              table is never allowed to be narrower than COL_REF past the rest. */}
          <colgroup>
            <col style={{ width: COL.pos }} />
            <col style={{ width: COL.spine }} />
            <col />
            <col style={{ width: COL.wait }} />
            <col style={{ width: COL.rule }} />
            <col style={{ width: COL.news }} />
            {/* Triage reads "triaged" on 307 of 308 and Context's subline was
                identical on every row, with both facts in full in the expander.
                They are the two columns to lose when the width will not take
                nine, and never the balance, the wait or the rule. */}
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

/** 16 numbered buttons for 308 rows is a wall, so the pager keeps the ends, the
 *  neighbours and an ellipsis for the rest. -1 is the ellipsis. */
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

/** A header with two sorts: the column's value, and the qualifier underneath it.
 *  A reading's age is as sortable as the reading, and a wait against its target
 *  is a different question from a wait in days. Putting both in one header keeps
 *  every sort key reachable without a second row of controls. */
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

/* `outside` is a TAB fact (this row is not in the ranking). Whether NEWS2 may be
   shown as acuity is a SPECIALTY fact. They coincide today only because the
   grouping at :483 checks refusal before band, which a reviewer flagged as the
   one line standing between this and a third escape of the same leak. So the
   NEWS2 cell reads its own derivation and the coincidence stops being load-bearing. */
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
  // The wait is the one number on this row with a real spread (0.036x to
  // 31.1x); the reading's age is the one that says a number cannot be trusted.
  const waitSev = sevWaitRatio(ratio)
  const ageSev = sevReadingAge(age)

  // NEWS2 may not be shown as acuity for a refused specialty. `outside` alone
  // would be enough only while refusal is grouped before band; this is the same
  // derivation the refused set and the patient page use, so the cell is right
  // whatever tab it is drawn in.
  const naNews2 = outside || isRefusedPaediatric(r.specialty_hipe)

  const moved = !!r.ovr && r.ovrLive && r.ovr.to_position !== r.ovr.from_position
  // The ORDINAL is the row's place in the displayed order, not the coordinator's
  // stored position. Printing the stored position meant that the moment a
  // clinician moved anyone, the column stopped enumerating: with one override
  // the Urgent tab read 1, 1, 2, 3 ... 20, 22, 23 -- position 1 printed twice
  // and 21 absent, with every row between the old and new slot one place away
  // from the number beside it. `seq` is the index in the spliced order, so it is
  // always a true 1..n enumeration of what is on screen.
  const shownPos = r.seq < UNPLACED ? r.seq + 1 : r.rank?.position
  // the system's own number is kept whenever it differs from where the row now sits
  const systemPos = r.rank?.position
  const displaced = systemPos != null && shownPos != null && systemPos !== shownPos

  // The rule ID has never appeared in this product. It is the first thing a
  // reviewer looks for, and the coordinator has always computed it.
  const fired = (r.rank?.rule_checks ?? [])
    .filter((c) => !c.passed && !WHOLE_LIST.has(c.rule_id))
  // A row can fire a CRT rule AND RULE-TRIAGE-TURNAROUND. Compact used to clip
  // the second one with `overflow: hidden` and no ellipsis, which is silent
  // loss; it is now counted out loud instead.
  const shownRules = tight && fired.length > 1 ? fired.slice(0, 1) : fired
  const hiddenRules = fired.length - shownRules.length

  return (
    <motion.tr
      className={'lst-row is-clickable'
        + (expanded ? ' is-open' : '')
        + (r.ovr && r.ovrLive ? ' is-overridden' : '')}
      // NOT role="button". ARIA gives button "children presentational", so
      // every <td> was stripped from the accessibility tree -- position, days
      // waited, ratio to target, NEWS2 and CRITICALLY the reading's age were
      // all unreachable, and a screen-reader user heard only the pathway
      // number. Age must travel with the reading for every reader. The row
      // stays a row; the pathway link in the first cell is the named control,
      // and the click handler is a convenience on top of it.
      initial={still ? false : { opacity: 0, y: 3 }}
      animate={{ opacity: 1, y: 0 }}
      transition={still ? { duration: 0 } : {
        // a stagger across one page only. 305 rows arriving in sequence reads
        // as slow, not as considered.
        delay: Math.min(i, 18) * 0.012, duration: 0.22, ease: [0.2, 0, 0, 1],
      }}
      onClick={() => onOpen(r.pathway_number)}>

      {/* order */}
      <td className="c-pos">
        <div className="cell is-r">
          <span className={'pos num' + (moved ? ' is-moved' : '')}>
            {outside ? '—' : shownPos != null ? shownPos : '·'}
          </span>
          {/* the clinician's position is the one shown; the system's stays beside it */}
          {/* 76px of column is 56px of content, and "system said 12" wrapped to
              three lines in it. The phrase moves to the tooltip, where the
              expander repeats it in full. */}
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

      {/* the spine: both terms, α-weighted. When the row is one half of a pair
          the printed priority cannot separate, the numeral goes to six decimals
          and the term that carried the margin is named underneath. */}
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
        <div className="cell">
          <span className="pw-line">
            <button type="button" className="pw num pw-open"
                    onClick={(e) => { e.stopPropagation(); onOpen(r.pathway_number) }}>
              {r.pathway_number}
            </button>
            {/* Eight of the 308 are planted fixtures the dataset track keeps at
                fixed pathway numbers because the demo depends on them. Unlabelled
                they read as leftover test data in a clinical list. */}
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
          // One flex item, not four. Bare text nodes inside an inline-flex each
          // become an anonymous flex item, so in a narrow column the phrase, the
          // name and the reason wrapped into three stacked fragments. The reason
          // moves to the tooltip and the expander, where there is room for it.
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
      </td>

      {/* Waited, drawn against target. The multiple past target is the graded
          state: .sub.is-over used to restate the base class verbatim, so a
          referral 31x past its target was typeset exactly like one at 1.04x. */}
      <td className="c-wt">
        <div className="cell">
          <span className="wait-n num">{fmt(wait)}<span className="of"> days</span></span>
          <WaitBar ratio={ratio} sev={waitSev} />
          <span className="sub is-split">
            {target == null ? 'no target for this category'
              : over ? (
                <>
                  {/* No chip here. The bar immediately above carries the graded
                      channel for this exact fact, and drawing it twice 2mm apart
                      was 20 of the 77 severity marks on the first screen. The
                      numeral stays, so the value is never colour-only. */}
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

      {/* The rule that fired. sevBreach has only two values, so every chip here
          would be the SAME solid block -- on 130 of the 165 rows that can breach.
          That is a field, not an accent, and it was the largest single
          contributor to the table's saturation. Quiet keeps the escalation in
          hue and withholds the fill; the wait bar beside it still carries the
          graded channel, because THAT one varies row to row. */}
      <td className="c-rule">
        {fired.length > 0 ? (
          <div className="rulez">
            {shownRules.map((c) => (
              <span className="rule-chip" key={c.rule_id}>
                {/* The rule ID is a CONTROL, not a label with a tooltip.
                    What the rule SAYS -- ruleStatement, from core.ref_rules --
                    used to exist only as a `title` on a non-focusable span, so
                    a mouse could read it and nothing else could: on a keyboard
                    and on every touch screen the cell was an opaque
                    RULE-CRT-URGENT. The expander one row below already carries
                    every statement in full (.ev-rst), so the ID opens it, and
                    the statement is the control's accessible name. The visible
                    text is the first thing in that name, which is what SC 2.5.3
                    asks for. */}
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
                {/* the detail ellipsises rather than wrapping the row onto a
                    second line, so it carries its own full text */}
                {c.detail && <span className="rule-d num" title={c.detail}>{c.detail}</span>}
              </span>
            ))}
            {hiddenRules > 0 && (
              // Same fault, same fix: this named the rules it stands in for in a
              // `title` and nowhere else. It opens the expander, which lists all
              // of them with their statements.
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

      {/* NEWS2, and the reading's age, always together.

          On a refused row the number is NOT shown as acuity. NEWS2 is validated
          in adults; the urgency agent refuses specialty 0601 rather than score a
          child on an adult scale, and printing the observation's stored total
          under a column headed "how unwell" would contradict that two inches
          below the panel note that states it. The reading and its age still
          travel, because a clinician recorded those. This mirrors what the
          patient page already does (Vitals.tsx, applied={false}). */}
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
              reading for every reader, and the date truncates before it does.
              The stale marker used to be a 1px dashed underline at 1.75:1. */}
          <span className="sub is-split">
            {r.clin?.obs_datetime == null ? 'no reading' : (
              <>
                <span className="sub-t">{dmy(r.clin.obs_datetime)}</span>
                {/* one flex item, always: at sev 0 SevChip renders its children
                    bare, and a loose text node in a flex row becomes an
                    anonymous item of its own that cannot truncate. */}
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
          {/* "not scored" was on every one of 305 rows AND in the column
              header directly above, so the subline said nothing and truncated
              while doing it. Only pain varies. */}
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

/** The mark's geometry, carrying the two terms that decide the order.
 *
 *  A 5-wide stem with a bar high on one side and a bar low on the other, which
 *  is the mark's own alternation. BOTH bars are α-weighted: drawing the raw
 *  urgency score against the raw wait percentile overstates waiting time by up
 *  to six times, because α is 0.81 here. The two lengths sum to the priority
 *  the coordinator actually used, and share one scale, so comparing them by eye
 *  is a true comparison.
 *
 *  `precise` prints six decimals instead of two. Two decimals is the right
 *  density for a column of 305, and exactly the wrong one for the pairs it
 *  cannot separate. */
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

/** What the priority column cannot say on its own: this row and one of its
 *  neighbours print the same number, and here is what actually separates them.
 *
 *  Both halves of the pair carry the line, each showing its own value, so the
 *  two six-decimal numerals sit one above the other and the difference is
 *  visible rather than asserted. */
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

/** Waiting time against target, drawn. The target sits at a fixed mark; the
 *  overflow past it is compressed, because a 31× overrun and a 1.2× one have to
 *  share an axis without either becoming invisible. The numeral beside the bar
 *  always carries the true value. A missing target is an open tick, not a zero.
 *
 *  The overflow segment takes its colour from the same severity step as the
 *  chip beside it, so the bar and the numeral cannot disagree. */
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

/** Evidence in place, one interaction away.
 *
 *  NFR5: no score is ever rendered without its cited evidence attached. The row
 *  above renders NEWS2 and the two weighted terms; this is where the six cited
 *  vitals, the one or two cited capacity rows, every rule the coordinator
 *  tested and its own rationale line live. The full patient page is still one
 *  click away on the row itself: this is the quick look, not a replacement. */
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
  // Same derivation as List's `refused` set (:475) and Patient's (:87): the
  // SPECIALTY, never a decision -- /api/decision 404s on 13 of 14 days.
  const evRefused = isRefusedPaediatric(r.specialty_hipe)
  const clinicKey = capCites.find((c) => c.evidence_type === 'clinic_session')
  const ward = wardKey ? ops?.wards.find((w) => w.ward_id === keyParts(wardKey.evidence_key)[1]) : undefined
  const clinic = clinicKey
    ? ops?.clinics.find((c) => c.clinic_code === keyParts(clinicKey.evidence_key)[1])
    : undefined
  /** `slots_booked / slots_total / slots_available` on the clinic row are the
   *  FIVE-SESSION SERIES totals. `cited_pressure` is booked / total for the ONE
   *  session the agent actually read. Printing both on one line made this
   *  surface refute itself: General Surgery read "15 free - pressure 1.000"
   *  while the session cited was 11 of 11 with nothing free. Resolve the cited
   *  row so its own numbers can stand beside its own pressure.
   *  Same resolution as Overview.tsx:569 citedSession(); kept local because
   *  Overview.tsx is another agent's file this week. */
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
              {/* The sentence names a capacity score, which pairs it with the
                  urgency score as if both placed this person. They did not:
                  capacity is specialty-level and sets alpha only. And the
                  patient page states this text is template output while this
                  panel did not, so a reader could take it for a model's
                  opinion. Both said here, next to it. */}
              <p className="ev-p ev-p-meta">
                Deterministic template text, written by the coordinator from the
                numbers above. No model wrote this sentence. The capacity score
                it names belongs to the whole specialty and set{' '}
                <span className="num">α</span>; it did not move this referral.
              </p>
              {/* Six decimals, not three. Three is where twelve adjacent pairs
                  in this decision become indistinguishable, and it is also
                  where the two terms stop reconciling with their own sum. */}
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
                  {/* A pass and a breach used to share one background, separated
                      by a text step and a 1.55:1 ring. A breach is a solid
                      block now; "holds" is not an attention state and keeps the
                      neutral pill it always had. */}
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
          {/* The refusal is derived HERE from the specialty rather than taken from
              a prop. Evidence is reachable from every tab, and the NEWS2 column's
              own gate is per-TAB (`outside={k === 'Outside'}`), correct only while
              the grouping at :483 puts refusal before band. Deriving it at the
              point of use means reordering that ternary can never re-open this
              sentence. The vitals themselves stay: a clinician recorded them, and
              a refusal is a statement about the INSTRUMENT, not about the record. */}
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
              {/* "rows" counted citations and read as lines on screen; the
                  clinic citation now needs two lines to stop contradicting
                  itself, so the count names what it actually counts. */}
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
                    {/* occupancy_pct is measured against the CENSUS, not the
                        nominal allocation, so the two are never divided into
                        one another here. TrolleyGAR keeps its letter and its
                        word; its green/amber/red is the HSE's own vocabulary
                        and stays out of the triage palette. */}
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
                    {/* The cited session, and nothing else, on the line that
                        carries the cited pressure. booked / total here divides
                        into the pressure printed beside it, every clinic, every
                        day. */}
                    <div className="ev-cap-r">
                      <span className="lab">clinic session</span>
                      <span className="ev-cap-k num">{clinic.clinic_code ?? '\u2014'}</span>
                      <span className="ev-cap-v">
                        {citedSess == null ? (
                          /* The cited date is not among the sessions returned,
                             so its slots cannot be shown and its pressure
                             cannot be checked here. Absence, stated. */
                          <>slots for that session were not returned · pressure{' '}
                            <span className="num">{clinic.cited_pressure.toFixed(3)}</span>{' '}
                            cannot be reconciled on this screen</>
                        ) : citedSess.slots_total === 0 ? (
                          /* scoring.py returns exactly 1.0 when slots_total is
                             0, so "every slot taken" and "no clinic sat" are
                             the same number. Only the session tells them apart,
                             and this one says no clinic sat. */
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
                    {/* The series totals are worth keeping and were the whole
                        of this line before. They are context around the cited
                        row, never the arithmetic behind its pressure, so they
                        get their own line and say so. */}
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
          <p className="ev-cav">
            MTS carries its own red/orange/yellow/green/blue vocabulary, which would collide with
            the triage categories, so it is shown as a word in a neutral register and is not
            scored (ADR-004). The condition code is a weighted random draw over the specialty's
            mix, independent of acuity: a record field, never a finding.
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
