import { isValidElement, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import './aside.css'

/** The one disclosure primitive: a line that STAYS, and the rest on demand.
 *
 *  WHAT THIS IS INSTEAD OF. The client asked for "neat tooltips ... dynamic as
 *  need per each section", and the pack they signed off bans exactly that:
 *  DESIGN_PACK.md:2705-2708, "No information is EVER carried by a tooltip, a
 *  title attribute or a hover-only state -- tooltips fail keyboard, touch and
 *  fast scanning alike." That is not a style preference. BUILD_LEDGER.md:298
 *  records the bill already paid for ignoring it: rule statements lived only in
 *  `title` on non-focusable spans, so a mouse could read them and a keyboard and
 *  every touch screen could not, and they had to be moved onto real buttons.
 *
 *  So this is the neat on-demand thing they want, built as the one control that
 *  works on all three inputs: a real button that shows and hides text which is
 *  in the DOM either way.
 *
 *  WHY NOT role="tooltip" + aria-describedby, which is the shape the word
 *  "tooltip" names in the APG:
 *    - the APG tooltip needs a FOCUSABLE trigger anyway, so it is this
 *      disclosure plus an overlay on top: all of the cost, and an overlay this
 *      product has nowhere to put (see the containing-block note below);
 *    - aria-describedby fires the WHOLE description on every focus with no way
 *      for the reader to decline it. The legend's detail is 444-496 characters.
 *      A description that long, announced on arrival, is the wordiness complaint
 *      moved from the eye to the ear.
 *  aria-expanded on a button says "there is more, here is how to get it" and
 *  lets the reader choose. That is the whole difference.
 *
 *  WHY NOT the <aside> element, whose name this shares. <aside> is a
 *  complementary LANDMARK: ten of them floods the rotor with ten entries that
 *  all say "complementary", which is worse than none. It is also flow content,
 *  so <aside> inside the <p> this often sits in is invalid. The word is the
 *  product's own for this object already (Severity.tsx:490, Overview.tsx:661
 *  both call it an aside in prose), so the name is kept and the element is not.
 *
 *  WHY NO `title` ON THE TOGGLE, even as a mouse shortcut. A `title` that
 *  differs from the aria-label double-announces, and a `title` that matches it
 *  is a second copy to drift. More to the point, re-introducing the mouse-only
 *  channel as the FAST path is precisely how `title` became load-bearing on 42
 *  elements here in the first place. There is one channel and everything can
 *  reach it.
 *
 *  IN NORMAL FLOW. NO POPOVER, NO PORTAL. This product has no reliable
 *  containing block and has been bitten twice: an outline on a chip was
 *  silently clipped by `.lst-table .sub { overflow: hidden }`, and an absolutely
 *  positioned span with no positioned ancestor took the VIEWPORT as its
 *  containing block and gave the page 189px of real sideways scroll from inside
 *  a table scrolled to x=1776. An overlay would be a third instance of the same
 *  bug. The body expands inline, pushes what follows down, and is bounded by
 *  `max-width` so it can never widen its own parent (aside.css).
 *
 *  NEVER PLACE THIS INSIDE `.lst-table`. A row-level disclosure has to span the
 *  <tr>, which needs a second row and a colSpan cell, not a <div> inside a <td>
 *  -- and the row expander (List.tsx `.expb`, `<td className="c-exp">`) already
 *  IS that disclosure. Two disclosure idioms in one table teaches two things.
 */

/** The visible line's budget, and the only figure here that is an opinion.
 *
 *  It is the threshold the client's own complaint is measured against: an Aside
 *  whose visible half is itself over-long has MOVED the wordiness, not solved
 *  it. 140 is the point past which the summary stops being a line and starts
 *  being the paragraph it was supposed to replace. The legend's old note, the
 *  worst offender on the product, was 508 characters on the List and 603 on the
 *  Overview; its summary is now 78. */
export const ASIDE_SUMMARY_MAX = 140

/** Labels that name nothing. A toggle's job is to say WHAT opens, so a reader
 *  can decide whether to spend the click; "more" and "info" say only that
 *  something does, which is the tooltip's own failure written as a word. */
const LAZY_LABEL = /^(more|info|details?|\?|learn more)$/i

const norm = (s: string) => s.replace(/\s+/g, ' ').trim()

/** THE AUDIT'S WHOLE RULE, as one pure function, in the same idiom as
 *  quietMismatch (Severity.tsx:204-228) and for the same reason: lifted out of
 *  the component so it can be exercised WITHOUT A BROWSER, which is the only way
 *  the check itself ever gets checked. Rollup drops it from the built bundle --
 *  nothing calls it outside the DEV branch below.
 *
 *  Takes flattened text, not ReactNode, so it stays pure and testable; the
 *  component does the flattening, in DEV only.
 *
 *  Returns one sentence per fault. Three faults, all of them ways of shipping a
 *  disclosure that discloses nothing:
 *    - a summary over the budget: the wordiness moved, it did not go;
 *    - a label from LAZY_LABEL: the control names nothing;
 *    - a body that is empty, or that repeats the line already on screen: a
 *      toggle whose reward is text the reader has already read. */
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

/* Development only, and dead in the built bundle -- the same constant, spelled
   the same way, as Severity.tsx:166. A clinician must never be shown a
   developer's error, and the demo is served from `vite build` output. The next
   author to place an Aside is by definition running the dev server. */
const AUDIT = (import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV === true

/** ReactNode to text, for the audit only. Never called in the built bundle.
 *  Elements are walked into rather than skipped, because the load-bearing case
 *  is a summary or body assembled from <b>, <span> and interpolated strings. */
function flatten(node: ReactNode): string {
  if (node == null || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(flatten).join('')
  if (isValidElement(node)) return flatten((node.props as { children?: ReactNode }).children)
  return ''
}

export function Aside({ summary, children, label, className }: {
  /** The one line that STAYS VISIBLE, open or shut. Load-bearing facts live
   *  here: a reader who never touches the toggle must still be told the thing
   *  they cannot act without. */
  summary: ReactNode
  /** The rest. Revealed by the toggle, and in the DOM either way -- hidden with
   *  the `hidden` attribute, so browser find-in-page and every assistive
   *  technology treat it as the app does, and nothing has to be re-rendered to
   *  exist. */
  children: ReactNode
  /** The toggle's VISIBLE text: a noun phrase naming what opens. Never "more",
   *  never "info", never a bare "?" -- see LAZY_LABEL, which says so out loud in
   *  development. */
  label: string
  /** Merged onto the root, the way SevLegend merges onto .sevleg: the caller
   *  places this object, this file does not decide where it sits. */
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const id = useId()

  /* Development only, and dead in the built bundle: is this actually a
     disclosure, or a paragraph with a button on it? See asideMismatch above for
     the three ways it is neither. The ref holds what was last said, so a body
     whose element identity changes every render (which is every body) does not
     print the same sentence on every render. */
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
             asks that speech input can say what it can see, so "how to read a
             mark" has to start the name and cannot be paraphrased inside it.
             aria-expanded already carries the state to a screen reader; the verb
             is here because the name is also what a voice user hears back, and
             "show" against "hide" is the difference between the two things this
             one control does. No `title` -- see the docblock. */
          aria-label={`${label}, ${open ? 'hide' : 'show'}`}
          /* Click only. A button fires click on Enter and on Space natively, so
             keyboard is covered without a keydown handler; hover and focus are
             deliberately NOT triggers, which is the entire point of not building
             a tooltip. */
          onClick={() => setOpen((v) => !v)}>
          {label}
          {/* The state as a SHAPE, not as a colour, and the same two glyphs the
              row expander uses (List.tsx:1699-1700) so the product has one sign
              for "there is more below this". aria-hidden: the state is already
              on aria-expanded, and an announced icon would say it twice. */}
          {open
            ? <ChevronDown className="aside-i" strokeWidth={1.75} aria-hidden="true" />
            : <ChevronRight className="aside-i" strokeWidth={1.75} aria-hidden="true" />}
        </button>
      </p>
      {/* Always rendered, hidden with the attribute. `hidden` is what removes it
          from the accessibility tree, from find-in-page and from the tab order
          in one move; a conditional render would do the same but would also
          throw away any state inside the body, and would make the reader wait
          for a mount on a control that is meant to feel like nothing more than
          text arriving. */}
      <div className="aside-b" id={id} hidden={!open}>{children}</div>
    </div>
  )
}
