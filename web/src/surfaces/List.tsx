import { Fragment, useEffect, useMemo, useState } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import { motion, useReducedMotion } from 'motion/react'
import { useQuery } from '@tanstack/react-query'
import {
  ArrowDown, ArrowUp, Check, ChevronDown, ChevronRight, PenLine, Search, TriangleAlert,
} from 'lucide-react'
import { api, bandOf, BANDS } from '../lib/api'
import { useNarrow } from '../lib/useNarrow'
import { crtDays, ruleStatement, specialtyName } from '../lib/ref'
import { plantedCase } from '../lib/planted'
import { Override } from '../components/Override'
import type {
  CohortReferral, Citation, Decision, Observation, OverrideRecord, Overrides,
  Ranking, Reference, RuleCheck,
} from '../lib/types'
import './list.css'

/** The ranked list.
 *
 *  The page used to open with a six-line paragraph explaining the sort order.
 *  A sort key is a structure, so it is drawn as one — six numbered steps, with
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
/** A date that will not parse prints as an em dash, never as "Invalid Date":
 *  evidence keys are strings from another service and may not be dates at all. */
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

/** A reading older than this is an absence of information rather than a
 *  reassurance, so it is marked as a caveat wherever it appears. */
const STALE_DAYS = 365

const UNPLACED = 1e9

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
   *  Nothing is interpolated — a row is either in a slot or it is not. */
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
   *  warning could stay silent for a move that visibly crosses a boundary —
   *  and rule_warning_accepted would then be stored false for a crossing that
   *  did happen. */
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
  const { rows, decision, ops, opsFailed, loading, error, displayedOrder } = useList(hospital, date)

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

  const refused = useMemo(() => new Set(decision?.refused_paediatric ?? []), [decision])

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
      {flash && <div className="flash" role="status" aria-live="polite" aria-atomic="true">{flash}</div>}

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
                No agent has scored this hospital-day. Rows sit in referral-date order —{' '}
                <em>a display order, not a ranking.</em>
              </>
            )}
          </p>
        </div>

        <div className="lst-figs">
          <Fig n={figures.onList} k="on the list" w="referrals open on this hospital-day" />
          <Fig n={figures.withTarget} k="have a target"
               w="a clinical timeframe applies to these, and only these" />
          <Fig n={figures.past} k="past target" accent
               w={`of the ${fmt(figures.withTarget)} with one — never of ${fmt(figures.onList)}`} />
          <Fig n={figures.noTarget} k="no target applies"
               w="Routine and Uncategorised. Nothing here can be late." />
        </div>
      </header>

      {!ranked && (
        <div className="lst-pre">
          <strong>No agent has scored this hospital-day yet.</strong>
          <span>
            Everything below is what a clinician recorded. Rows sit in referral-date order,
            which is a display order and carries no clinical claim. Run the agents from the
            top bar to see a suggested one.
          </span>
        </div>
      )}

      {opsFailed && (
        <div className="lst-warn">
          <TriangleAlert size={14} strokeWidth={2} />
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
        <SortKeyLadder alpha={alpha} ranked={ranked} reference={reference} />
      </details>

      {ranked && (
        <details className="lst-fold">
          <summary>
            <span className="lst-fold-t">Everyone accounted for</span>
            <span className="lst-fold-s">
              <span className="num">{decision!.rankings.length}</span> placed ·{' '}
              <span className="num">{decision!.refused_paediatric.length}</span> refused ·{' '}
              <span className="num">{decision!.skipped.length}</span> skipped ·{' '}
              <span className="num">{decision!.excluded.length}</span> excluded —
              reconciled by set union, never by sum
            </span>
          </summary>
          <Reconciliation decision={decision} total={figures.onList} />
        </details>
      )}

      <div className="lst-tools">
        <label className="lst-find">
          <Search size={15} strokeWidth={2} aria-hidden="true" />
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
            Sorted by {SORT_NAME[sort.key]} — <strong>not the suggested order</strong>. Reset
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

/* ----------------------------------------------------- the sort key, drawn -- */

/** The order used to be explained in a paragraph. A sort key is a structure, so
 *  it is drawn as one: six ordered steps, each naming the rule it comes from.
 *  Step 3 is the tier readers kept missing — everyone past target ranks above
 *  everyone within it, before any score is compared — so it takes the one clay
 *  accent this composition is allowed. */
function SortKeyLadder({ alpha, ranked, reference }: {
  alpha: number | null; ranked: boolean; reference: Reference | undefined
}) {
  const steps = [
    {
      k: 'Clinical category',
      w: 'Urgent, then Semi-Urgent, then Routine, then Uncategorised. No score moves anyone between them.',
      rule: 'RULE-ORDER',
    },
    {
      k: 'Severity rank',
      w: 'core.ref_codes.severity_rank, never the raw CPC code — CPC 3 outranks CPC 2.',
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
    },
    {
      k: 'Referral date',
      w: 'Oldest first, so two people the scores cannot separate are separated by their wait.',
      rule: 'RULE-TIEBREAK',
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
            {s.rule && (
              <span className="key-r num" title={ruleStatement(reference, s.rule.split(' · ')[0])}>
                {s.rule}
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
      k: 'Refused — paediatric', n: paed.size,
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
            <div className="recon-w">{b.w}{b.note && <em> — {b.note}</em>}</div>
          </div>
        ))}
      </div>
      <p className={'recon-sum' + (union.size === total ? '' : ' is-off')}>
        <strong className="num">{fmt(union.size)}</strong> distinct referrals accounted for, of{' '}
        <strong className="num">{fmt(total)}</strong> on the list.
        {overlap > 0 && (
          <> The buckets overlap by <span className="num">{overlap}</span>, which is why they are
          never summed — added rather than unioned they read as{' '}
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
}

function Band(p: BandProps) {
  const [page, setPage] = useState(0)
  // below 1440 the table drops Triage and Context rather than growing a
  // horizontal scrollbar that cuts 340px off the right on the rehearsal machine
  const narrow = useNarrow()
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
              <> They are counted here rather than in their clinical band —{' '}
                <strong>{
                  Object.entries(p.rows.reduce((a: Record<string, number>, r) => {
                    const b = bandOf(r.cpc); a[b] = (a[b] ?? 0) + 1; return a
                  }, {})).map(([b, n]) => `${n} ${b}`).join(' · ')
                }</strong> — so the tab counts above are of the ranking, while the
                Overview bands all 308 by category.</>
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

      <div className={'scroll-x lst-vp' + (p.tight ? ' is-tight' : '')}>
        <table className="lst-table">
          {/* Referral is the one elastic column: specialty names vary, and the
              rule chip must never wrap onto a second line inside a row. */}
          <colgroup>
            <col style={{ width: 76 }} />
            <col style={{ width: narrow ? 156 : 140 }} />
            <col />
            <col style={{ width: 200 }} />
            <col style={{ width: 240 }} />
            <col style={{ width: 180 }} />
            {/* Triage reads "triaged" on 307 of 308 and Context's subline was
                identical on every row, with both facts in full in the expander.
                They are the two columns to lose when the width will not take
                nine — never the balance, the wait or the rule. */}
            {!narrow && <col style={{ width: 144 }} />}
            {!narrow && <col style={{ width: 132 }} />}
            <col style={{ width: 42 }} />
          </colgroup>
          <thead>
            <tr>
              <Th k="order" sort={p.sort} onSort={p.onSort} align="right"
                  label={p.outside ? 'Not ranked' : p.ranked ? 'Order' : 'Display'}
                  sub={p.outside ? 'no position' : p.ranked ? 'position in the list' : 'referral date'} />
              <Th k="priority" sort={p.sort} onSort={p.onSort}
                  label="Balance" sub="unwell ← α → waited" />
              <Th k="specialty" sort={p.sort} onSort={p.onSort}
                  label="Referral" sub="specialty" k2="pathway" sub2="pathway" />
              <Th k="wait" sort={p.sort} onSort={p.onSort}
                  label="Waited" sub="days" k2="over" sub2="against target" />
              <th className="lst-th">
                <span className="lst-th-l">Rule</span>
                <span className="lst-th-s">the check that fired · core.ref_rules</span>
              </th>
              <Th k="news2" sort={p.sort} onSort={p.onSort}
                  label="How unwell" sub="NEWS2" k2="age" sub2="reading age" />
              {!narrow && <th className="lst-th">
                <span className="lst-th-l">Triage</span>
                <span className="lst-th-s">status on this pathway</span>
              </th>}
              {!narrow && <th className="lst-th">
                <span className="lst-th-l">Context</span>
                <span className="lst-th-s">recorded, not scored — ADR-004</span>
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
                        The sort places them there before any score is compared — step 3 of the
                        key, above priority. Below it, everyone is still within{' '}
                        {target != null ? `their ${target}-day target` : 'target'}.
                      </span>
                    </td>
                  </tr>
                )}
                <PatientRow
                  r={r} i={i} ranked={p.ranked} outside={p.outside}
                  reference={p.reference} tight={p.tight} narrow={narrow}
                  expanded={p.open === r.pathway_number}
                  onToggle={() => p.onToggleOpen(r.pathway_number)}
                  onOpen={p.onOpen} />
                {p.open === r.pathway_number && (
                  <tr className="ev-row">
                    <td colSpan={9}>
                      <Evidence
                        r={r} hospital={p.hospital} reference={p.reference}
                        ops={p.ops} decision={p.decision} onMove={p.onMove}
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
    ? <ArrowUp size={11} strokeWidth={2.5} aria-hidden="true" />
    : <ArrowDown size={11} strokeWidth={2.5} aria-hidden="true" />
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

function PatientRow({ r, i, ranked, outside, reference, tight, narrow, expanded, onToggle, onOpen }: {
  r: Row; i: number; ranked: boolean; outside: boolean; narrow: boolean
  reference: Reference | undefined; tight: boolean; expanded: boolean
  onToggle: () => void; onOpen: (pw: string) => void
}) {
  const still = useReducedMotion()
  const target = targetOf(r, reference)
  const wait = r.adjusted_wait_days ?? 0
  const ratio = ratioOf(r, reference)
  const over = ratio != null && ratio > 1
  const age = r.clin?.reading_age_days ?? null
  const stale = age != null && age > STALE_DAYS

  const moved = !!r.ovr && r.ovrLive && r.ovr.to_position !== r.ovr.from_position
  const shownPos = moved ? r.ovr!.to_position : r.rank?.position

  // The rule ID has never appeared in this product. It is the first thing a
  // reviewer looks for, and the coordinator has always computed it.
  const fired = (r.rank?.rule_checks ?? [])
    .filter((c) => !c.passed && !WHOLE_LIST.has(c.rule_id))

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
          {moved
            ? <span className="pos-was lab">system said {r.ovr!.from_position ?? '—'}</span>
            : r.ovr && r.ovrLive
              ? <span className="pos-was lab">confirmed</span>
              : null}
        </div>
      </td>

      {/* the spine: both terms, α-weighted */}
      <td className="c-spine">
        {r.rank
          ? <RankSpine urgency={r.rank.urgency_score} wait={r.rank.wait_normalised}
                       alpha={r.rank.alpha} priority={r.rank.priority} tight={tight} />
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
                planted · {plantedCase(r.pathway_number)!.what}
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
            <PenLine size={11} strokeWidth={2} aria-hidden="true" />
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
            <PenLine size={11} strokeWidth={2} aria-hidden="true" />
            <span className="ovbadge-t">
              edited by <b>{r.ovr.clinician_id}</b> · not applied
            </span>
          </span>
        )}
      </td>

      {/* waited, drawn against target */}
      <td className="c-wt">
        <div className="cell">
          <span className="wait-n num">{fmt(wait)}<span className="of"> days</span></span>
          <WaitBar ratio={ratio} />
          <span className={'sub' + (over ? ' is-over' : '')}>
            {target == null ? 'no target for this category'
              : over ? <><b className="num">{ratio! >= 10 ? Math.round(ratio!) : ratio!.toFixed(1)}×</b>{' '}
                over a {target}-day target</>
                : <>within a {target}-day target</>}
          </span>
        </div>
      </td>

      {/* the rule that fired */}
      <td className="c-rule">
        {fired.length > 0 ? (
          <div className="rulez">
            {fired.map((c) => (
              <span className="rule-chip" key={c.rule_id} title={ruleStatement(reference, c.rule_id)}>
                <TriangleAlert size={11} strokeWidth={2.25} aria-hidden="true" />
                <b className="num">{c.rule_id}</b>
                {c.detail && <span className="rule-d num">{c.detail}</span>}
              </span>
            ))}
          </div>
        ) : r.rank ? (
          <span className="rule-ok">
            <Check size={11} strokeWidth={2.5} aria-hidden="true" />
            every timeframe rule holds
          </span>
        ) : r.crt_breached === true ? (
          <span className="rule-pre">
            past target — no run has tested a rule against it yet
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
          <span className={'n2 num' + (outside ? ' is-na' : '')}>
            {outside
              ? <span className="n2-na">not applied<span className="of"> · adult scale</span></span>
              : <>{r.clin?.news2 ?? '—'}<span className="of"> of 17</span></>}
          </span>
          <span className={'sub' + (stale ? ' is-stale' : '')}>
            {r.clin?.obs_datetime == null ? 'no reading' : <>
              {dmy(r.clin.obs_datetime)}
              {age != null && <> · <b className="num">{fmt(age)}</b> days old</>}
            </>}
          </span>
        </div>
      </td>

      {/* triage status — carried by the cohort payload and never rendered before */}
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
            ? <ChevronDown size={15} strokeWidth={2} aria-hidden="true" />
            : <ChevronRight size={15} strokeWidth={2} aria-hidden="true" />}
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
 *  is a true comparison. */
function RankSpine({ urgency, wait, alpha, priority, tight }: {
  urgency: number; wait: number; alpha: number; priority: number; tight: boolean
}) {
  const u = clamp01(urgency) * alpha
  const w = clamp01(wait) * (1 - alpha)
  const title = `priority ${priority.toFixed(3)} = ${u.toFixed(3)} unwell `
    + `(α ${alpha.toFixed(2)} × ${urgency.toFixed(2)}) + ${w.toFixed(3)} waited `
    + `(1−α ${(1 - alpha).toFixed(2)} × ${wait.toFixed(2)})`
  return (
    <span className={'spn' + (tight ? ' is-tight' : '')} title={title}>
      <span className="spn-g">
        <i className="spn-stem" />
        <i className="spn-u" style={{ width: `${u * 50}%` }} />
        <i className="spn-w" style={{ width: `${w * 50}%` }} />
      </span>
      <span className="spn-n num">{priority.toFixed(2)}</span>
    </span>
  )
}

/** Waiting time against target, drawn. The target sits at a fixed mark; the
 *  overflow past it is compressed, because a 31× overrun and a 1.2× one have to
 *  share an axis without either becoming invisible. The numeral beside the bar
 *  always carries the true value. A missing target is an open tick, not a zero. */
function WaitBar({ ratio }: { ratio: number | null }) {
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
    <span className="wb" aria-hidden="true">
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
 *  click away on the row itself — this is the quick look, not a replacement. */
function Evidence({ r, hospital, reference, ops, decision, onMove, onOpen }: {
  r: Row; hospital: string; reference: Reference | undefined
  ops: ReturnType<typeof useList>['ops']
  decision: Decision | undefined
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
  const clinicKey = capCites.find((c) => c.evidence_type === 'clinic_session')
  const ward = wardKey ? ops?.wards.find((w) => w.ward_id === keyParts(wardKey.evidence_key)[1]) : undefined
  const clinic = clinicKey
    ? ops?.clinics.find((c) => c.clinic_code === keyParts(clinicKey.evidence_key)[1])
    : undefined

  const checks: RuleCheck[] = r.rank?.rule_checks ?? []
  const age = r.clin?.reading_age_days ?? null
  const stale = age != null && age > STALE_DAYS

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
                numbers above — no model wrote this sentence. The capacity score
                it names belongs to the whole specialty and set{' '}
                <span className="num">α</span>; it did not move this referral.
              </p>
              <dl className="ev-terms">
                <div><dt>how unwell</dt>
                  <dd className="num">{r.rank.urgency_score.toFixed(3)} × α {r.rank.alpha.toFixed(3)}
                    {' = '}<b>{(r.rank.urgency_score * r.rank.alpha).toFixed(3)}</b></dd></div>
                <div><dt>how long waited</dt>
                  <dd className="num">{r.rank.wait_normalised.toFixed(3)} × {(1 - r.rank.alpha).toFixed(3)}
                    {' = '}<b>{(r.rank.wait_normalised * (1 - r.rank.alpha)).toFixed(3)}</b></dd></div>
                <div className="ev-tsum"><dt>priority</dt>
                  <dd className="num"><b>{r.rank.priority.toFixed(3)}</b></dd></div>
              </dl>
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
                  <span className={'ev-vd ' + (c.passed ? 'is-ok' : 'is-bad')}>
                    {c.passed
                      ? <Check size={12} strokeWidth={2.5} aria-hidden="true" />
                      : <TriangleAlert size={12} strokeWidth={2.25} aria-hidden="true" />}
                    {c.passed ? 'holds' : 'breached'}
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
                : 'no citations — nothing has scored this referral'}
              {citedAt && <> · {dmyt(citedAt)}{age != null && <> · <b className="num">{fmt(age)}</b> days old</>}</>}
            </span>
          </h3>
          {stale && (
            <p className="ev-stale">
              This reading has never been repeated. Its date is also how long this person has
              gone unmeasured.
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
          <p className="ev-cav">
            {obsCites.length
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
              {capCites.length ? `${capCites.length} rows · specialty-level` : 'no citations'}
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
                  <div className="ev-cap-r">
                    <span className="lab">clinic session</span>
                    <span className="ev-cap-k num">{clinic.clinic_code}</span>
                    <span className="ev-cap-v">
                      <b className="num">{clinic.slots_booked}</b> of{' '}
                      <span className="num">{clinic.slots_total}</span> slots booked ·{' '}
                      <span className="num">{clinic.slots_available}</span> free · pressure{' '}
                      <span className="num">{clinic.cited_pressure.toFixed(3)}</span>
                    </span>
                    <span className="ev-cap-d">
                      the one session cited: {clinic.cited_session_date ?? keyParts(clinicKey.evidence_key)[2]}
                    </span>
                  </div>
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
            scored — ADR-004. The condition code is a weighted random draw over the specialty's
            mix, independent of acuity: a record field, never a finding.
          </p>
        </section>

        {/* what a clinician did, and what they can do */}
        <section className="ev-b">
          <h3 className="ev-h">
            Clinician action
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
                <div className="ev-warn">category boundary crossed, attested</div>
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
          <p className="ev-cav">
            Attribution, not authentication: the record says who typed it, it does not verify them.
          </p>
        </section>
      </div>
    </div>
  )
}
