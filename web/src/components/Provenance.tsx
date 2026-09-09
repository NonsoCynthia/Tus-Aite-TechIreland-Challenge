import { lazy, Suspense, useMemo } from 'react'
import type { GraphNode, GraphEdge } from 'reagraph'

// reagraph carries three.js. It appears on one surface, so it is split out of
// the initial bundle rather than charged to every page load.
const GraphCanvas = lazy(() =>
  import('reagraph').then((m) => ({ default: m.GraphCanvas })))
import type { Decision, ScoresByPathway } from '../lib/types'

/** The provenance chain for one placement, assembled from REST rather than
 *  SPARQL.
 *
 *  Reading it from the graph store would lose most of it: retrieval's
 *  _resolve_iri writes each predicate into a plain dict, so a Score citing six
 *  observations reads back as ONE arbitrary citation. GET /runs/.../scores comes
 *  from Postgres and returns them as proper lists, so that is the source.
 *
 *  It shows what was cited. It does NOT show why one patient outranks another —
 *  that is the contribution bars' job, and this must never be read as the
 *  ordering argument.
 */
const PALETTE = {
  decision: '#122056',
  placement: '#7A5B4D',
  score: '#5A6172',
  observation: '#2F5D45',
  bed_status: '#8A5A12',
  clinic_session: '#8A5A12',
  condition: '#6B6257',
}

const VITALS: Record<string, string> = {
  rr: 'resp rate', spo2: 'SpO₂', sbp: 'systolic', hr: 'heart rate',
  avpu: 'consciousness', temp: 'temperature',
}

export function Provenance({ pathway, decision, scores, height = 380 }: {
  pathway: string
  decision: Decision
  scores: ScoresByPathway | undefined
  height?: number
}) {
  const { nodes, edges } = useMemo(() => {
    const n: GraphNode[] = []
    const e: GraphEdge[] = []
    const add = (id: string, label: string, kind: keyof typeof PALETTE, size = 8) => {
      if (!n.find((x) => x.id === id)) n.push({ id, label, fill: PALETTE[kind], size })
      return id
    }
    const link = (a: string, b: string, label: string) =>
      e.push({ id: `${a}->${b}`, source: a, target: b, label })

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
        const leaf = c.evidence_key.split('/')[1] ?? c.evidence_key
        link(c2, add(`cap-${c.evidence_key}`, `${c.evidence_type.replace('_', ' ')} ${leaf}`, kind, 7), 'cites')
      }
    }
    return { nodes: n, edges: e }
  }, [pathway, decision, scores])

  const citations = edges.filter((x) => x.label === 'cites').length

  return (
    <div className="prov" data-surface="dark">
      <div className="prov-canvas" style={{ height }}>
        <Suspense fallback={<div className="prov-load">drawing the chain…</div>}>
        <GraphCanvas
          nodes={nodes} edges={edges}
          layoutType="treeLr2d"
          labelType="all"
          edgeArrowPosition="none"
          animated
          theme={{
            canvas: { background: '#0B1436' },
            node: {
              fill: '#5A6172', activeFill: '#C4B6A6', opacity: 1, selectedOpacity: 1, inactiveOpacity: 0.5,
              label: { color: '#FAFAF8', stroke: '#0B1436', activeColor: '#C4B6A6' },
            },
            edge: {
              fill: '#3E4863', activeFill: '#C4B6A6', opacity: 1, selectedOpacity: 1, inactiveOpacity: 0.35,
              label: { color: '#8E93A8', stroke: '#0B1436', activeColor: '#C4B6A6' },
            },
            ring: { fill: '#3E4863', activeFill: '#C4B6A6' },
            arrow: { fill: '#3E4863', activeFill: '#C4B6A6' },
            lasso: { border: '1px solid #C4B6A6', background: 'rgba(196,182,166,0.1)' },
          }}
        />
        </Suspense>
      </div>
      <p className="prov-note">
        The chain the coordinator recorded: <strong className="num">{citations}</strong> cited
        records behind this position. It shows <em>what was cited</em>, never why one person
        is ahead of another — that is the arithmetic above.
      </p>
    </div>
  )
}
