import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Maximize2, RotateCcw, TriangleAlert, ZoomIn, ZoomOut } from 'lucide-react'
import type { GraphCanvasRef, GraphEdge as RGEdge, GraphNode as RGNode } from 'reagraph'
import { Aside } from '../components/Aside'
import { api } from '../lib/api'
import type { CohortGraph, Decision } from '../lib/types'
import './cohortgraph.css'

// reagraph carries three.js: charged to this surface, never to every page load.
const GraphCanvas = lazy(() => import('reagraph').then((m) => ({ default: m.GraphCanvas })))

/** The graph palette: a lightness ramp on the brand axis, paper through taupe to
 *  clay and two ink steps. TRAP: no amber, red-orange or green -- an orange node
 *  beside a red one on an evidence graph reads as severity. The "reagraph needs
 *  literals" exception covers where these values LIVE, not which hues are
 *  allowed. Small classes are separated by SIZE rather than by value. */
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

/** How many placements to draw. `n: 0` is no limit. The "All N" label is DERIVED
 *  from the decision and reads plain "All" until it arrives -- a literal there
 *  claims a ranking count that differs per hospital-day. Top-N stays literal
 *  because it is a REQUEST, not a claim. */
const SIZES = [{ n: 60 }, { n: 150 }, { n: 0 }] as const

const sizeLabel = (n: number, placements: number | undefined | null): string =>
  n ? `Top ${n}` : placements != null ? `All ${placements}` : 'All'

const fmtN = (n: number) => n.toLocaleString('en-IE')

/** What the three headline figures are counts OF. Three states, none claiming
 *  more than is known: a subset names both numbers and the control; the whole
 *  run says so; a draw with no decision says only what it drew. */
function scopeNote(drawn: number | null, total: number | null, limit: number): string {
  const tail = 'All three follow the size control below.'
  if (drawn == null) return ''
  if (total != null && drawn < total) {
    return `Counts of what is drawn, not of the run: the top ${fmtN(drawn)} placements by rank`
      + ` and the evidence they cite. ${tail} “${sizeLabel(0, total)}” draws the whole run.`
  }
  if (limit === 0 || (total != null && drawn >= total)) {
    return `Counts of what is drawn, which at this setting is every placement in the run. ${tail}`
  }
  return `Counts of what is drawn: the top ${fmtN(drawn)} placements by rank and the evidence`
    + ` they cite. ${tail}`
}

/** The whole decision, from the graph store in one SPARQL query. The shape is the
 *  point: placements fanning out to their own urgency scores and converging on a
 *  handful of shared ward snapshots is what specialty-level capacity scoring looks
 *  like. It draws a SUBSET by default, so every figure here is of that subset. */
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

  /* The three headline figures count the DRAWN SUBSET under a heading that sounds
     like the whole decision, so the whole travels with them. Never assumed. */
  const total = dec.data?.rankings.length ?? null
  const drawn = g.data?.placements ?? null
  const partial = total != null && drawn != null && drawn < total

  if (dec.isError) return <NoRun />
  if (g.isError) return <NoRun graph />

  return (
    <div className="cg" data-surface="dark">
      <GraphStage nodes={nodes} edges={edges} layout={layout} selected={sel} onSelect={setSel} />

      {/* Panels float OVER the graph: the one place glass earns itself. */}
      <div className="cg-panel cg-tl glass">
        <span className="lab">Evidence</span>
        <h1>What the coordinator cited</h1>
        {g.data ? (
          <>
            <div className="cg-nums num">
              <span>
                <strong>{fmtN(g.data.placements)}</strong>
                {partial && <> of {fmtN(total!)}</>} placements
              </span>
              <span><strong>{fmtN(g.data.evidence_links)}</strong> evidence links</span>
              <span><strong>{fmtN(g.data.nodes.length)}</strong> nodes</span>
            </div>
            {/* what those three are counts OF, said before they are believed */}
            <p className="cg-scope">{scopeNote(drawn, total, limit)}</p>
            <div className="cg-src num">{g.data.run_id}</div>
          </>
        ) : <div className="cg-load">querying the graph store…</div>}
      </div>

      <div className="cg-panel cg-tr glass">
        <span className="lab">Node classes drawn</span>
        <ul className="cg-legend">
          {shares.map(([kind, count]) => {
            const k = KIND[kind as keyof typeof KIND] ?? KIND.evidence
            return (
              <li key={kind}>
                <i style={{ background: k.fill }} aria-hidden />
                <span className="cg-lg-n">{k.label}</span>
                {/* no share bar: most classes count in single digits, so the
                    bars render as 1px stubs */}
                <span className="cg-lg-c num">{count}</span>
              </li>
            )
          })}
        </ul>
        {/* The CLAIM stays on the summary -- capacity sets alpha for the
            hospital-day and moves nobody -- because the picture puts that
            question on screen. NOT the scope note: that is this run's state,
            and the only thing saying the figures are of the drawn subset. */}
        {g.data && (
          <Aside
            className="cg-note"
            label="how these counts are built"
            summary="Placements share a handful of ward snapshots: capacity is scored per specialty, one weight for the hospital-day that can move nobody.">
            <p>
              An <strong>evidence link</strong> is one role-tagged edge from a
              placement. A placement's six cited vitals arrive as one link to its
              urgency score, so the recorded citation count is higher than the
              count of lines here.
            </p>
            <p>
              The <strong className="num">{fmtN(g.data.placements)}</strong> placements drawn here
              carry <strong className="num">{shares.find(([k]) => k === 'score')?.[1] ?? 0}</strong>{' '}
              urgency scores of their own and share{' '}
              <strong className="num">{shares.find(([k]) => k === 'bed_status')?.[1] ?? 0}</strong>{' '}
              ward snapshots between them.
            </p>
          </Aside>
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
                    onClick={() => setLimit(s.n)}>
              {sizeLabel(s.n, dec.data?.rankings.length)}
            </button>
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
              <TriangleAlert size={14} strokeWidth={2} aria-hidden />
              This node is cited, and its values are not in the graph store: the
              batch input layer is not loaded here. Its identity and its role are
              real; its readings live in the records, not in these triples.
            </p>
          )}
        </div>
      )}
    </div>
  )
}


/** The canvas, isolated so a lost WebGL context remounts it. Four live traps,
 *  each a way to fake a context loss. `layout` must NOT go back into `key`:
 *  reagraph takes `layoutType` live, and a remount per click leaves the old
 *  context alive 500ms against a browser cap of ~16. react-three-fiber calls
 *  forceContextLoss() on a discarded canvas in a setTimeout(500), so the
 *  listeners below ignore anything not isConnected. Redraw must clear `lost` as
 *  well as bump `gen`, or the banner latches: webglcontextrestored cannot fire on
 *  a detached canvas. And the scrim needs its z-index (cohortgraph.css), or the
 *  controls at z-index 5 paint above it. See BUILD_LEDGER.md. */
function GraphStage({ nodes, edges, layout, selected, onSelect }: {
  nodes: RGNode[]; edges: RGEdge[]; layout: string
  selected: string | null
  onSelect: (id: string | null) => void
}) {
  // Selecting lights the chain and dims the rest: at this node count a highlight
  // that suppresses nothing reads as no highlight at all.
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

  // These deps must name EVERYTHING that can swap the canvas element, or the
  // listener stays bound to the old one. `layout` is here even though it no
  // longer remounts, so restoring it to `key` cannot silently unbind this.
  useEffect(() => {
    const el = host.current?.querySelector('canvas')
    if (!el) return
    // A canvas React has already discarded still gets forceContextLoss() called
    // on it. That loss is not this surface's: ignore events on a detached node.
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
  }, [gen, layout, nodes.length])

  // reagraph fits the camera on mount only, and with no remount per layout a tree
  // drawn under a force-directed camera lands off-screen. Re-fit once settled.
  const settled = useRef(false)
  useEffect(() => {
    if (!settled.current) { settled.current = true; return }
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const t = window.setTimeout(
      () => ref.current?.fitNodesInView([], { animated: !still }), 600)
    return () => window.clearTimeout(t)
  }, [layout])

  return (
    <div className="cg-stage" ref={host}>
      <Suspense fallback={<div className="cg-boot">drawing {nodes.length} nodes…</div>}>
        <GraphCanvas
          key={gen}
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
          The graphics context dropped.{' '}
          {/* must clear the latch as well as remount: webglcontextrestored
              cannot fire on the detached canvas */}
          <button onClick={() => { setLost(false); setGen((g) => g + 1) }}>Redraw</button>
        </div>
      )}

      <div className="cg-ctrl glass">
        <button onClick={() => ref.current?.zoomIn()} aria-label="Zoom in">
          <ZoomIn size={16} strokeWidth={1.75} aria-hidden /></button>
        <button onClick={() => ref.current?.zoomOut()} aria-label="Zoom out">
          <ZoomOut size={16} strokeWidth={1.75} aria-hidden /></button>
        <button onClick={() => ref.current?.fitNodesInView()} aria-label="Fit to view">
          <Maximize2 size={16} strokeWidth={1.75} aria-hidden /></button>
        <button onClick={() => ref.current?.resetControls(true)} aria-label="Reset">
          <RotateCcw size={16} strokeWidth={1.75} aria-hidden /></button>
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
            : 'No agent has scored this day, so there is no chain to draw. Run the agents from the top bar. Evidence is date-blind, so only the newest day holding data can be scored.'}
        </p>
      </div>
    </div>
  )
}
