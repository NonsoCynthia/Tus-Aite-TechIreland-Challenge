import { isValidElement, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import './aside.css'

/** The one disclosure primitive: a line that STAYS, and the rest on demand.
 *  A disclosure, not a tooltip: DESIGN_PACK.md:2705-2708 bans tooltips, `title`
 *  and hover-only state, which fail keyboard, touch and fast scanning alike.
 *  Not the <aside> ELEMENT either -- a landmark, and flow content, so invalid
 *  inside the <p> this usually sits in. See BUILD_LEDGER.md.
 *
 *  Two traps. It renders IN NORMAL FLOW, never a popover or portal, because
 *  nothing here is a reliable containing block. And it must NEVER sit inside
 *  `.lst-table`, where a disclosure has to span the <tr> and List's row
 *  expander (`.expb`) already is one. */

/** The visible line's budget: past this the summary is the paragraph it was
 *  meant to replace. An opinion, not a measurement. */
export const ASIDE_SUMMARY_MAX = 140

/** Labels that name nothing: a toggle must say WHAT opens, so a reader can
 *  decide whether to spend the click. */
const LAZY_LABEL = /^(more|info|details?|\?|learn more)$/i

const norm = (s: string) => s.replace(/\s+/g, ' ').trim()

/** The audit's whole rule. Pure, so it can be exercised without a browser;
 *  Rollup drops it. Takes flattened text rather than ReactNode to stay pure;
 *  the component does the flattening, in DEV only. */
export function asideMismatch(summary: string, label: string, detail: string): string[] {
  const wrong: string[] = []
  const s = norm(summary)
  const l = norm(label)
  const d = norm(detail)
  if (s.length > ASIDE_SUMMARY_MAX) {
    wrong.push(
      `the visible line is ${s.length} characters, over ${ASIDE_SUMMARY_MAX}: an Aside whose `
      + 'visible half is itself over-long has moved the problem, not solved it',
    )
  }
  if (LAZY_LABEL.test(l)) {
    wrong.push(`the toggle is labelled "${l}", which names nothing that opens`)
  }
  if (!d) {
    wrong.push('nothing behind the toggle: a disclosure with an empty body is a control that lies')
  } else if (s.length > 0 && d.includes(s)) {
    wrong.push('behind the toggle repeats the visible line, so the toggle rewards a click with text already on screen')
  }
  return wrong
}

/* DEV only: a clinician must never be shown a developer's error, and the demo
   is served from `vite build` output, where this is dead. */
const AUDIT = (import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV === true

/** ReactNode to text, for the audit only. Walks into elements rather than
 *  skipping them: summaries are routinely assembled from <b> and <span>. */
function flatten(node: ReactNode): string {
  if (node == null || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(flatten).join('')
  if (isValidElement(node)) return flatten((node.props as { children?: ReactNode }).children)
  return ''
}

export function Aside({ summary, children, label, className }: {
  /** The one line that STAYS VISIBLE, open or shut. Anything a reader cannot
   *  act without belongs here, never behind the toggle. */
  summary: ReactNode
  /** The rest. In the DOM either way, hidden with the `hidden` attribute. */
  children: ReactNode
  /** The toggle's VISIBLE text: a noun phrase naming what opens, never "more"
   *  or "info" (see LAZY_LABEL). */
  label: string
  /** Merged onto the root: the caller places this object, not this file. */
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const id = useId()

  /* DEV only. The ref holds what was last said: `children` changes element
     identity on every render, so without it the same sentence prints forever. */
  const said = useRef('')
  useEffect(() => {
    if (!AUDIT) return
    const now = asideMismatch(flatten(summary), label, flatten(children)).join(' | ')
    if (now === said.current) return
    said.current = now
    if (now) {
      console.error(
        `Aside ("${label}"): ${now}. See the disclosure contract in components/Aside.tsx.`,
      )
    }
  }, [summary, label, children])

  return (
    <div className={className ? `aside ${className}` : 'aside'}>
      <p className="aside-s">
        {summary}{' '}
        <button
          type="button" className="aside-t"
          aria-expanded={open}
          aria-controls={id}
          /* The visible text FIRST, then the state verb: SC 2.5.3 Label in Name
             means speech input must be able to say what it can see, so `label`
             starts the name and is never paraphrased inside it. */
          aria-label={`${label}, ${open ? 'hide' : 'show'}`}
          /* Click only: a button fires it on Enter and Space natively. Hover and
             focus are deliberately not triggers. */
          onClick={() => setOpen((v) => !v)}>
          {label}
          {/* State as a SHAPE, not a colour, and the same two glyphs List's row
              expander uses. aria-hidden: aria-expanded already says it. */}
          {open
            ? <ChevronDown className="aside-i" strokeWidth={1.75} aria-hidden="true" />
            : <ChevronRight className="aside-i" strokeWidth={1.75} aria-hidden="true" />}
        </button>
      </p>
      {/* Always rendered, hidden with the attribute: `hidden` removes it from
          the accessibility tree, find-in-page and the tab order in one move,
          and unlike a conditional render it keeps any state inside the body. */}
      <div className="aside-b" id={id} hidden={!open}>{children}</div>
    </div>
  )
}
