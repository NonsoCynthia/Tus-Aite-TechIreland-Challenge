import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Maximize2, RotateCcw, TriangleAlert, ZoomIn, ZoomOut } from 'lucide-react'
import type { GraphCanvasRef, GraphEdge as RGEdge, GraphNode as RGNode } from 'reagraph'
import { api } from '../lib/api'
import type { CohortGraph, Decision } from '../lib/types'
import './cohortgraph.css'

// reagraph carries three.js. It is charged to the surfaces that use it, never
// to every page load.
const GraphCanvas = lazy(() => import('reagraph').then((m) => ({ default: m.GraphCanvas })))

/** The graph palette.
 *
 *  Deliberately outside the triage set: red, amber and green belong to CPC
 *  categories inside the product and nothing else may borrow them, so evidence
 *  classes are separated on the ink/clay/taupe axis instead. */
/** The graph palette: a lightness ramp on the brand axis, paper through taupe
 *  to clay and two ink steps.
 *
 *  An earlier version of this block claimed to be "deliberately outside the
 *  triage set" while shipping #D2A07E (amber), #B5765F (red-orange, adjacent in
 *  hue to --cat-urgent) and #7FA8A0 (green) — and a clinician reading an orange
 *  node beside a red node on an evidence graph reads severity. The documented
 *  "reagraph needs literals" exception covers where the values LIVE; it does not
 *  license which hues are allowed.
 *
 *  The three large classes (305 each) take the most separated values. The four
 *  small ones (6/6/2/1) are separated by SIZE, which the legend's count column
 *  disambiguates anyway. */
const KIND = {
  decision:       { fill: '#FAFAF8', label: 'Decision',           size: 20 },
  placement:      { fill: '#C4B6A6', label: 'Ranked placement',   size: 6 },
  score:          { fill: '#8C93AD', label: 'Urgency score',      size: 5 },
  referral_state: { fill: '#5B6480', label: 'Referral state',     size: 5 },
  bed_status:     { fill: '#7A5B4D', label: 'Ward bed status',    size: 15 },
  clinic_session: { fill: '#9C7C6B', label: 'Clinic session',     size: 15 },
  rule:           { fill: '#E4DED4', label: 'Rule',               size: 13 },
  obs:            { fill: '#8C93AD', label: 'Observation',        size: 5 },
  condition:      { fill: '#6E6559', label: 'Condition',          size: 5 },
  triage_event:   { fill: '#6E6559', label: 'Triage event',       size: 5 },
  evidence:       { fill: '#4A5470', label: 'Evidence',           size: 5 },
} as const

/* Edge roles, on the same axis. Nothing here may read as a severity. */
const ROLE = {
  hasPlacement: '#2E3757',
  urgency:      '#6E7796',
  capacity:     '#7A5B4D',
  timeframe:    '#57607C',
  multi_list:   '#4A5470',
} as const

const LAYOUTS = [
  { key: 'forceDirected2d', label: 'Force' },
  { key: 'radialOut2d', label: 'Radial' },
  { key: 'concentric2d', label: 'Concentric' },
  { key: 'treeLr2d', label: 'Tree' },
] as const

const SIZES = [
  { n: 60, label: 'Top 60' },
  { n: 150, label: 'Top 150' },
  { n: 0, label: 'All 305' },
] as const

/** The whole decision, drawn from the graph store.
 *
 *  Every graph this product has shown was rebuilt from Postgres, four levels
 *  deep, for one patient at a time, while the run graph held 11,839 triples that
 *  nothing had ever queried. This is one SPARQL query: 305 placements, their
 *  scores, their cited rows and the rules they were tested against.
 *
 *  What the shape says, before anyone reads a label: 305 placements fan out to
 *  305 individual urgency scores, and converge on six shared ward snapshots and
 *  six clinic sessions. That is not a drawing decision — it is what
 *  specialty-level capacity scoring looks like.
 */
export function CohortGraphSurface({ hospital, date, onOpenPatient }: {
  hospital: string; date: string; onOpenPatient: (pathway: string) => void
}) {
  const [layout, setLayout] = useState<(typeof LAYOUTS)[number]['key']>('forceDirected2d')
  const [limit, setLimit] = useState(150)
  const [sel, setSel] = useState<string | null>(null)

  const dec = useQuery<Decision>({
    queryKey: ['decision', hospital, date],
    queryFn: () => api.decision(hospital, date), retry: false,
  })
  const g = useQuery<CohortGraph>({
    queryKey: ['cohort-graph', dec.data?.run_id, limit],
    queryFn: () => api.cohortGraph(dec.data!.run_id, limit),
    enabled: !!dec.data?.run_id, retry: false, staleTime: 5 * 60_000,
  })

  const { nodes, edges, shares } = useMemo(() => {
    const src = g.data
    if (!src) return { nodes: [] as RGNode[], edges: [] as RGEdge[], shares: [] as Array<[string, number]> }
    const n: RGNode[] = src.nodes.map((x) => {
      const k = KIND[x.kind as keyof typeof KIND] ?? KIND.evidence
      return {
        id: x.id, label: x.label, fill: k.fill,
        // a placement that cites more grows; a shared row is already large
        size: x.kind === 'placement' ? k.size + Math.min(6, x.cites) : k.size,
        data: { kind: x.kind, pathway: x.pathway, position: x.position, cites: x.cites },
      }
    })
    const e: RGEdge[] = src.edges.map((x, i) => ({
      id: `e${i}`, source: x.source, target: x.target,
      label: x.label === 'hasPlacement' ? '' : x.label,
      fill: ROLE[x.label as keyof typeof ROLE] ?? ROLE.multi_list,
      size: x.label === 'hasPlacement' ? 1 : 1.4,
    }))
    const counts = new Map<string, number>()
    for (const x of src.nodes) counts.set(x.kind, (counts.get(x.kind) ?? 0) + 1)
    return {
      nodes: n, edges: e,
      shares: [...counts.entries()].sort((a, b) => b[1] - a[1]),
    }
  }, [g.data])

  const chosen = sel ? g.data?.nodes.find((x) => x.id === sel) : undefined

  if (dec.isError) return <NoRun />
  if (g.isError) return <NoRun graph />

  return (
    <div className="cg" data-surface="dark">
      <GraphStage nodes={nodes} edges={edges} layout={layout} selected={sel} onSelect={setSel} />

      {/* Panels float OVER the graph — the one place glass earns itself, since
          you have to be able to see the graph through them. */}
      <div className="cg-panel cg-tl glass">
        <span className="lab">Evidence</span>
        <h1>What the coordinator cited</h1>
        {g.data ? (
          <>
            <div className="cg-nums num">
              <span><strong>{g.data.placements}</strong> placements</span>
              <span><strong>{g.data.evidence_links.toLocaleString('en-IE')}</strong> evidence links</span>
              <span><strong>{g.data.nodes.length}</strong> nodes</span>
            </div>
            <div className="cg-src num">{g.data.run_id}</div>
          </>
        ) : <div className="cg-load">querying the graph store…</div>}
      </div>

      <div className="cg-panel cg-tr glass">
        <span className="lab">Node classes</span>
        <ul className="cg-legend">
          {shares.map(([kind, count]) => {
            const k = KIND[kind as keyof typeof KIND] ?? KIND.evidence
            return (
              <li key={kind}>
                <i style={{ background: k.fill }} aria-hidden />
                <span className="cg-lg-n">{k.label}</span>
                {/* no share bar: five of seven classes are 6, 6, 2 and 1, so
                    the bars rendered as 1px stubs and informed nobody */}
                <span className="cg-lg-c num">{count}</span>
              </li>
            )
          })}
        </ul>
        {/* the finding the picture makes, said once */}
        {g.data && (
          <p className="cg-note">
            An <strong>evidence link</strong> is one role-tagged edge from a
            placement. A placement's six cited vitals arrive as one link to its
            urgency score, so the recorded citation count is higher than the
            count of lines here.{' '}
          </p>
        )}
        {g.data && (
          <p className="cg-note">
            <strong className="num">{g.data.placements}</strong> placements and{' '}
            <strong className="num">{shares.find(([k]) => k === 'score')?.[1] ?? 0}</strong>{' '}
            urgency scores — converging on{' '}
            <strong className="num">{shares.find(([k]) => k === 'bed_status')?.[1] ?? 0}</strong>{' '}
            ward snapshots. Capacity is scored per specialty, so it sets one weight
            for the whole hospital-day and can move nobody.
          </p>
        )}
      </div>

      <div className="cg-panel cg-bl glass">
        <div className="cg-seg" role="group" aria-label="Layout">
          {LAYOUTS.map((l) => (
            <button key={l.key} className={layout === l.key ? 'is-on' : ''}
                    onClick={() => setLayout(l.key)}>{l.label}</button>
          ))}
        </div>
        <div className="cg-seg" role="group" aria-label="How many placements">
          {SIZES.map((s) => (
            <button key={s.n} className={limit === s.n ? 'is-on' : ''}
                    onClick={() => setLimit(s.n)}>{s.label}</button>
          ))}
        </div>
      </div>

      {chosen && (
        <div className="cg-panel cg-br glass">
          <span className="lab">{(KIND[chosen.kind as keyof typeof KIND] ?? KIND.evidence).label}</span>
          <div className="cg-sel num">{chosen.label}</div>
          {chosen.kind === 'placement' && chosen.pathway && (
            <>
              <div className="cg-sel-m num">
                position {chosen.position} · {chosen.cites} evidence links
              </div>
              <button className="cg-open" onClick={() => onOpenPatient(chosen.pathway!)}>
                Open {chosen.pathway} &rarr;
              </button>
            </>
          )}
          {chosen.kind !== 'placement' && !g.data?.inputs_graph_loaded && (
            <p className="cg-caveat">
              <TriangleAlert size={13} strokeWidth={2} aria-hidden />
              This node is cited, and its values are not in the graph store — the
              batch input layer is not loaded here. Its identity and its role are
              real; its readings live in the records, not in these triples.
            </p>
          )}
        </div>
      )}
    </div>
  )
}


/** The canvas, isolated so a lost WebGL context remounts it rather than leaving
 *  a black rectangle. It was observed being lost in this session simply by
 *  navigating away and back, which mid-demo would look like a broken product. */
function GraphStage({ nodes, edges, layout, selected, onSelect }: {
  nodes: RGNode[]; edges: RGEdge[]; layout: string
  selected: string | null
  onSelect: (id: string | null) => void
}) {
  // Selecting lights the chain and dims everything else. At 900 nodes a
  // highlight that does not suppress the rest reads as no highlight at all.
  const actives = useMemo(() => {
    if (!selected) return [] as string[]
    const near = new Set<string>([selected])
    for (const e of edges) {
      if (e.source === selected) near.add(e.target as string)
      if (e.target === selected) near.add(e.source as string)
    }
    return [...near]
  }, [selected, edges])
  const ref = useRef<GraphCanvasRef | null>(null)
  const host = useRef<HTMLDivElement | null>(null)
  const [gen, setGen] = useState(0)
  const [lost, setLost] = useState(false)

  useEffect(() => {
    const el = host.current?.querySelector('canvas')
    if (!el) return
    const onLost = (e: Event) => { e.preventDefault(); setLost(true) }
    const onRestored = () => { setLost(false); setGen((g) => g + 1) }
    el.addEventListener('webglcontextlost', onLost)
    el.addEventListener('webglcontextrestored', onRestored)
    return () => {
      el.removeEventListener('webglcontextlost', onLost)
      el.removeEventListener('webglcontextrestored', onRestored)
    }
  }, [gen, nodes.length])

  return (
    <div className="cg-stage" ref={host}>
      <Suspense fallback={<div className="cg-boot">drawing {nodes.length} nodes…</div>}>
        <GraphCanvas
          key={`${layout}-${gen}`}
          ref={ref as never}
          nodes={nodes} edges={edges}
          layoutType={layout as never}
          labelType="auto"
          edgeArrowPosition="none"
          edgeInterpolation="curved"
          draggable
          animated
          selections={selected ? [selected] : []}
          actives={actives}
          onNodeClick={(n) => onSelect(n.id)}
          onCanvasClick={() => onSelect(null)}
          theme={{
            canvas: { background: '#070F2A' },
            node: {
              fill: '#4A5470', activeFill: '#FAFAF8', opacity: 1,
              selectedOpacity: 1, inactiveOpacity: 0.22,
              label: { color: '#C9CEE0', stroke: '#070F2A', activeColor: '#FAFAF8' },
            },
            edge: {
              fill: '#2B3559', activeFill: '#C4B6A6', opacity: 0.9,
              selectedOpacity: 1, inactiveOpacity: 0.06,
              label: { color: '#7E86A3', stroke: '#070F2A', activeColor: '#C4B6A6' },
            },
            ring: { fill: '#3E4863', activeFill: '#C4B6A6' },
            arrow: { fill: '#2B3559', activeFill: '#C4B6A6' },
            lasso: { border: '1px solid #C4B6A6', background: 'rgba(196,182,166,0.1)' },
          }}
        />
      </Suspense>

      {lost && (
        <div className="cg-lost">
          The graphics context dropped. <button onClick={() => setGen((g) => g + 1)}>Redraw</button>
        </div>
      )}

      <div className="cg-ctrl glass">
        <button onClick={() => ref.current?.zoomIn()} aria-label="Zoom in"><ZoomIn size={15} /></button>
        <button onClick={() => ref.current?.zoomOut()} aria-label="Zoom out"><ZoomOut size={15} /></button>
        <button onClick={() => ref.current?.fitNodesInView()} aria-label="Fit to view"><Maximize2 size={15} /></button>
        <button onClick={() => ref.current?.resetControls(true)} aria-label="Reset"><RotateCcw size={15} /></button>
      </div>
    </div>
  )
}

function NoRun({ graph }: { graph?: boolean }) {
  return (
    <div className="pad">
      <div className="lede">
        <h1>Nothing has been cited for this hospital-day</h1>
        <p className="lede-p measure">
          {graph
            ? 'A decision exists but its run graph holds no triples. That happens when the decision was restored from a snapshot written by a run whose graph has since been cleared.'
            : 'No agent has scored this day, so there is no chain to draw. Run the agents from the top bar — evidence is date-blind, so only the newest day holding data can be scored.'}
        </p>
      </div>
    </div>
  )
}
