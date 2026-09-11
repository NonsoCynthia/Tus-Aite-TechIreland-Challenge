import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import type { GraphNode, GraphEdge } from 'reagraph'
import type { Decision, ReferralContext, ScoresByPathway } from '../lib/types'

// reagraph carries three.js. It appears on two surfaces, so it is split out of
// the initial bundle rather than charged to every page load.
const GraphCanvas = lazy(() =>
  import('reagraph').then((m) => ({ default: m.GraphCanvas })))

/** One referral's chain, in whichever of the two forms this day supports.
 *
 *  CITED — what the agents actually used. Assembled from REST rather than
 *  SPARQL: retrieval's `_resolve_iri` writes each predicate into a plain dict,
 *  so a Score citing six observations reads back as ONE arbitrary citation.
 *  `GET /runs/.../scores` comes from Postgres and returns proper lists.
 *  ON RECORD — what exists regardless of any run, on every hospital-day. Only
 *  the newest can be scored: evidence is date-blind, so ranking an older day
 *  would cite readings taken after it. Neither shows why one patient outranks
 *  another -- that is the contribution bars' job. */
/** The graph palette: the SAME ramp CohortGraph.tsx draws, value for value.
 *  reagraph needs literals, which is why these are not tokens -- that exception
 *  covers where the values LIVE, never which hues are allowed. Nothing here may
 *  collide with --cat-* or read as a severity: a reading in Routine green, or a
 *  ward in Semi-Urgent amber, contradicts the header chip on the same page.
 *
 *    #FAFAF8 paper   #C4B6A6 taupe   #9C7C6B clay-light   #7A5B4D clay
 *    #8C93AD ink-3   #6E6559 stone   #5B6480 ink-2  */
const PALETTE = {
  decision: '#FAFAF8',
  placement: '#C4B6A6',
  referral: '#C4B6A6',
  score: '#8C93AD',
  observation: '#8C93AD',
  bed_status: '#7A5B4D',
  ward: '#7A5B4D',
  clinic_session: '#9C7C6B',
  condition: '#6E6559',
  triage_event: '#6E6559',
  specialty: '#5B6480',
}

// three.js renders labels from a limited glyph set: U+2082 (the subscript 2 in
// SpO₂) came out as a tofu box on the canvas. Plain digits everywhere here.
const VITALS: Record<string, string> = {
  rr: 'resp rate', spo2: 'SpO2', sbp: 'systolic', hr: 'heart rate',
  avpu: 'consciousness', temp: 'temperature',
}

const THEME = {
  canvas: { background: '#0B1436' },
  node: {
    fill: '#4A5470', activeFill: '#C4B6A6', opacity: 1,
    selectedOpacity: 1, inactiveOpacity: 0.35,
    label: { color: '#FAFAF8', stroke: '#0B1436', activeColor: '#C4B6A6' },
  },
  edge: {
    fill: '#3E4863', activeFill: '#C4B6A6', opacity: 1,
    selectedOpacity: 1, inactiveOpacity: 0.2,
    label: { color: '#8E93A8', stroke: '#0B1436', activeColor: '#C4B6A6' },
  },
  ring: { fill: '#3E4863', activeFill: '#C4B6A6' },
  arrow: { fill: '#3E4863', activeFill: '#C4B6A6' },
  lasso: { border: '1px solid #C4B6A6', background: 'rgba(196,182,166,0.1)' },
}

export function Provenance({ pathway, decision, scores, context, height = 380 }: {
  pathway: string
  decision?: Decision
  scores?: ScoresByPathway
  /** Supplied for a day with no decision: the chain still exists on the record. */
  context?: ReferralContext
  height?: number
}) {
  const cited = !!decision

  const { nodes, edges, count } = useMemo(() => {
    const n: GraphNode[] = []
    const e: GraphEdge[] = []
    const add = (id: string, label: string, kind: keyof typeof PALETTE, size = 8) => {
      if (!n.find((x) => x.id === id)) n.push({ id, label, fill: PALETTE[kind], size })
      return id
    }
    const link = (a: string, b: string, label: string) =>
      e.push({ id: `${a}->${b}`, source: a, target: b, label })

    if (decision) {
      const d = add('decision', `decision · ${decision.rankings.length} placed`, 'decision', 16)
      const placed = decision.rankings.find((r) => r.pathway_number === pathway)
      const p = add('placement', placed ? `position ${placed.position}` : 'not placed', 'placement', 13)
      link(d, p, 'hasPlacement')

      const s = scores?.[pathway]
      if (s?.urgency) {
        const u = add('score-u', `urgency ${Number(s.urgency.score).toFixed(3)}`, 'score', 11)
        link(p, u, 'citesUrgencyEvidence')
        for (const c of s.urgency.citations) {
          const leaf = c.evidence_key.split('/').pop() ?? c.evidence_key
          link(u, add(`obs-${leaf}`, VITALS[leaf] ?? leaf, 'observation', 7), 'cites')
        }
      }
      if (s?.capacity) {
        const c2 = add('score-c', `capacity ${Number(s.capacity.score).toFixed(3)}`, 'score', 11)
        link(p, c2, 'citesCapacityEvidence')
        for (const c of s.capacity.citations) {
          const kind = c.evidence_type as keyof typeof PALETTE
          const leaf = decodeURIComponent(c.evidence_key.split('/')[1] ?? c.evidence_key)
          link(c2, add(`cap-${c.evidence_key}`,
                       `${c.evidence_type.replace('_', ' ')} ${leaf}`, kind, 7), 'cites')
        }
      }
      return { nodes: n, edges: e, count: e.filter((x) => x.label === 'cites').length }
    }

    // --- on record: no run, but the referral and everything hanging off it
    //     still exists, and does on every one of the 28 hospital-days
    if (context) {
      const r = add('referral', pathway, 'referral', 15)
      const spec = (context.referral as Record<string, unknown>)?.specialty_hipe
      if (typeof spec === 'string') link(r, add(`spec-${spec}`, `specialty ${spec}`, 'specialty', 9), 'forSpecialty')

      for (const o of context.observations ?? []) {
        const oid = add(`obs-${o.obs_datetime}`, `reading ${o.obs_datetime.slice(0, 10)}`, 'observation', 11)
        link(r, oid, 'hasObservationEvent')
        for (const k of ['rr', 'spo2', 'sbp', 'hr', 'avpu', 'temp'] as const) {
          const v = o[k]
          if (v == null) continue
          link(oid, add(`${oid}-${k}`, `${VITALS[k]} ${v}`, 'observation', 6), 'hasMember')
        }
      }
      for (const c of context.conditions ?? []) {
        link(r, add(`cond-${c.icd10am_code}`, c.icd10am_code, 'condition', 8), 'hasCondition')
      }
      for (const [i, t] of (context.triage_events ?? []).entries()) {
        const tid = add(`tri-${i}`, `triaged ${t.triage_date ?? '—'}`, 'triage_event', 9)
        link(r, tid, 'hasTriageEvent')
      }
      const cap = context.capacity as { wards?: Array<{ ward_id: string; is_primary?: boolean }>
                                        clinic_sessions?: Array<{ clinic_code: string; session_date: string }> } | undefined
      for (const w of cap?.wards ?? []) {
        link(r, add(`ward-${w.ward_id}`, `${w.ward_id}${w.is_primary ? ' · primary' : ''}`, 'ward', 9), 'inWard')
      }
      const s0 = cap?.clinic_sessions?.[0]
      if (s0) link(r, add(`cl-${s0.clinic_code}`, s0.clinic_code, 'clinic_session', 9), 'clinic')
      return { nodes: n, edges: e, count: n.length - 1 }
    }
    return { nodes: n, edges: e, count: 0 }
  }, [pathway, decision, scores, context])

  if (!nodes.length) return null

  return (
    <div className="prov" data-surface="dark">
      <Stage nodes={nodes} edges={edges} height={height} />
      <p className="prov-note">
        {cited ? (
          <>
            The chain the coordinator recorded: <strong className="num">{count}</strong> cited
            records behind this position. What was cited, never why one person is ahead of
            another, which is the arithmetic above.
          </>
        ) : (
          <>
            <strong>On record, not cited.</strong> No agent has scored this hospital-day, so
            nothing here was used to place anyone. This is what exists about this referral
            (<strong className="num">{count}</strong> linked records) and it exists on every
            day, which is why an older day can be read but not ranked.
          </>
        )}
      </p>
    </div>
  )
}


/** Isolated so a lost WebGL context remounts rather than leaving a black
 *  rectangle. It is lost here simply by navigating away and back. */
function Stage({ nodes, edges, height }: { nodes: GraphNode[]; edges: GraphEdge[]; height: number }) {
  const host = useRef<HTMLDivElement | null>(null)
  const [gen, setGen] = useState(0)
  const [lost, setLost] = useState(false)

  useEffect(() => {
    const el = host.current?.querySelector('canvas')
    if (!el) return
    // Same guard as CohortGraph's stage: react-three-fiber calls
    // forceContextLoss() on a canvas React has already discarded, 500ms after
    // unmount, dispatching webglcontextlost on a DEAD element.
    const onLost = (e: Event) => {
      if (!el.isConnected) return
      e.preventDefault(); setLost(true)
    }
    const onRestored = () => {
      if (!el.isConnected) return
      setLost(false); setGen((g) => g + 1)
    }
    el.addEventListener('webglcontextlost', onLost)
    el.addEventListener('webglcontextrestored', onRestored)
    return () => {
      el.removeEventListener('webglcontextlost', onLost)
      el.removeEventListener('webglcontextrestored', onRestored)
    }
  }, [gen, nodes.length])

  return (
    <div className="prov-canvas" style={{ height }} ref={host}>
      <Suspense fallback={<div className="prov-load">drawing the chain…</div>}>
        <GraphCanvas
          key={gen}
          nodes={nodes} edges={edges}
          layoutType="treeLr2d"
          labelType="all"
          edgeArrowPosition="none"
          animated
          theme={THEME}
        />
      </Suspense>
      {lost && (
        <div className="prov-lost">
          The graphics context dropped.{' '}
          {/* Clears the latch as well as remounting: webglcontextrestored can
              never fire on the canvas this replaces. */}
          <button onClick={() => { setLost(false); setGen((g) => g + 1) }}>Redraw</button>
        </div>
      )}
    </div>
  )
}
