import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Maximize2, RotateCcw, TriangleAlert, ZoomIn, ZoomOut } from 'lucide-react'
import type { GraphCanvasRef, GraphEdge as RGEdge, GraphNode as RGNode } from 'reagraph'
import { Aside } from '../components/Aside'
import { api } from '../lib/api'
import type { CohortGraph, Decision } from '../lib/types'
import './cohortgraph.css'

// reagraph carries three.js. It is charged to the surfaces that use it, never
// to every page load.
const GraphCanvas = lazy(() => import('reagraph').then((m) => ({ default: m.GraphCanvas })))

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
 *  The three large classes -- one node per DRAWN placement, so they are as many
 *  as the size control asks for -- take the most separated values. The small
 *  ones (six wards, six clinic sessions, the rules) are separated by SIZE, which
 *  the legend's count column disambiguates anyway. */
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

/** How many placements to draw. `n: 0` is no limit.
 *
 *  The label for that last one used to be the literal string "All 305", which
 *  is a claim about the data written into the chrome. 305 is one hospital-day's
 *  ranking count and nothing else's: 9002 carries 301 referrals on the same
 *  date (/api/cohort/9002/2026-08-30), and a day whose run places fewer would
 *  still have read "All 305". It is derived from the decision now, and says only
 *  "All" until the decision has arrived. The Top-N labels stay literal because
 *  they are a REQUEST, not a claim: asking for the top 150 of a 62-row day is
 *  not wrong, it just returns 62. */
const SIZES = [{ n: 60 }, { n: 150 }, { n: 0 }] as const

const sizeLabel = (n: number, placements: number | undefined | null): string =>
  n ? `Top ${n}` : placements != null ? `All ${placements}` : 'All'

const fmtN = (n: number) => n.toLocaleString('en-IE')

/** What the three headline figures are counts OF.
 *
 *  Three states, and none of them claims more than is known:
 *    - a subset of a known whole  -> says both numbers and names the control
 *    - the whole run              -> says so
 *    - a draw with no decision to compare against -> says only what it drew */
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

/** The whole decision, drawn from the graph store.
 *
 *  Every graph this product has shown was rebuilt from Postgres, four levels
 *  deep, for one patient at a time, while the run graph held 11,839 triples that
 *  nothing had ever queried. This is one SPARQL query: the run's placements,
 *  their scores, their cited rows and the rules they were tested against.
 *
 *  What the shape says, before anyone reads a label: every placement fans out to
 *  an urgency score of its own, and they all converge on a handful of shared
 *  ward snapshots and clinic sessions. That is not a drawing decision — it is
 *  what specialty-level capacity scoring looks like. Measured on the one
 *  hospital-day that holds a decision here (9001, 2026-08-30, run
 *  run-20260910-134205-48ec): 305 placements, 305 scores, six ward snapshots.
 *
 *  It draws a SUBSET by default. Every figure this surface prints is a figure of
 *  that subset, and the panel says so rather than leaving "what the coordinator
 *  cited" to be read as all of it.
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

  /* The three headline figures count the DRAWN SUBSET, and always did: at the
     default limit of 150 this panel read "150 placements · 750 evidence links ·
     465 nodes" under a heading that sounds like the whole decision, while the
     run holds 305 / 1,386 / 931. Verified against the live API on
     run-20260910-134205-48ec: ?limit=150 -> 150 / 750 / 465, ?limit=0 -> 305 /
     1,386 / 931.

     The whole is the decision's own ranking count, which is already loaded, is
     free, and is exactly what the graph returns unlimited (305 = 305 there).
     It is never assumed: if the decision has not arrived, the panel says what
     it is drawing and claims nothing about the rest. */
  const total = dec.data?.rankings.length ?? null
  const drawn = g.data?.placements ?? null
  const partial = total != null && drawn != null && drawn < total

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
                {/* no share bar: five of seven classes are 6, 6, 2 and 1, so
                    the bars rendered as 1px stubs and informed nobody */}
                <span className="cg-lg-c num">{count}</span>
              </li>
            )
          })}
        </ul>
        {/* TWO paragraphs of 201 and 205 characters, under a legend that has
            already printed every count they cite. Both were DEFINITIONS -- what
            an edge is, and what the shape of a specialty-scored graph looks like
            -- true on every run, read once and re-read on every visit after
            that. They are one disclosure now, and one toggle rather than two,
            because a 296px panel floating over a graph cannot afford two.

            WHAT STAYS VISIBLE IS THE CLAIM, and it is invariant 3's: capacity is
            resource pressure, it sets alpha for the hospital-day, and it never
            appears to move an individual. The picture puts that question on the
            screen -- every placement running into a handful of ward nodes -- so
            the answer cannot be behind a click. The counts that are the ARGUMENT
            for it can: they are in the legend column directly above, with their
            numbers, which is invariant 8 satisfied without this paragraph.

            NOT the scope note. "150 of 305" and what the three headline figures
            are counts OF stay where they are, in the panel on the left, in plain
            text: that line is this run's state, not a definition, and it is the
            only thing on the surface that says the figures are of the drawn
            subset. */}
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


/** The canvas, isolated so a lost WebGL context remounts it rather than leaving
 *  a black rectangle. It was observed being lost in this session simply by
 *  navigating away and back, which mid-demo would look like a broken product.
 *
 *  The reported "switching between options dropped the graphics context" was
 *  four faults compounding, none of them an actual context loss:
 *
 *    1. `key` carried `layout`, so every layout click unmounted the canvas and
 *       mounted a new one. `layout` was missing from the listener effect's
 *       deps, so the effect never re-ran and the listener stayed bound to the
 *       DETACHED element.
 *    2. react-three-fiber calls gl.forceContextLoss() on that dead canvas in a
 *       setTimeout(500) on unmount. That dispatches webglcontextlost on it, the
 *       stale listener fired, and the banner appeared over a perfectly healthy
 *       graph half a second after the click. That delay is why it read as a
 *       spontaneous crash rather than as a consequence of the click.
 *    3. Redraw bumped `gen` but never cleared `lost`, and webglcontextrestored
 *       can never fire on a detached canvas, so the banner was a ONE-WAY LATCH
 *       for the rest of the session.
 *    4. The scrim had no z-index while the panels and camera controls have 5,
 *       so the controls painted ABOVE it and the user kept clicking through a
 *       permanent veil (fixed in cohortgraph.css).
 *
 *  The remount is gone as well: reagraph takes `layoutType` as a live prop and
 *  re-runs the layout on it (useGraph's own effect keyed on layoutType), so
 *  switching layout no longer creates a WebGL context. It used to leave the old
 *  one alive for those 500ms, and browsers cap live contexts around 16, so
 *  clicking through four layouts and three sizes quickly could force a GENUINE
 *  loss. `gen` is now the only thing that remounts, and it is only ever bumped
 *  by a real loss or by Redraw. */
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

  // These deps must name EVERYTHING that can swap the canvas element, or the
  // listener is left on the old one. `layout` is here even though it no longer
  // remounts the canvas, so that putting it back into `key` cannot silently
  // unbind this again.
  useEffect(() => {
    const el = host.current?.querySelector('canvas')
    if (!el) return
    // A canvas React has already discarded still gets forceContextLoss() called
    // on it. Its loss is not this surface's loss: ignore anything dispatched on
    // an element that is no longer in the document.
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

  // reagraph fits the camera once, on mount, behind a `mounted` ref. The canvas
  // used to be remounted on every layout change so that fit came free; it is
  // not remounted now, and a tree layout drawn under a force-directed camera
  // lands mostly off-screen. Re-fit once the new layout has settled.
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
          {/* clears the latch as well as remounting: without setLost(false) the
              banner outlived every redraw for the rest of the session */}
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
