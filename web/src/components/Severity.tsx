import type { ReactNode } from 'react'
import type { Sev } from '../lib/severity'
import './severity.css'

/** The one severity primitive. Every attention state in the product renders
 *  through this, so a reader learns the scale once.
 *
 *  Three shapes, one scale:
 *    <SevChip>   a filled block carrying a value. The distance channel.
 *    <SevBar>    a magnitude drawn against a track, with the same four steps.
 *    <SevLegend> the four steps named, once, above the thing they mark.
 *
 *  The value is ALWAYS rendered. Colour is never the only channel, both because
 *  WCAG 2.2 SC 1.4.1 requires it and because a filled block with no number
 *  tells a clinician nothing they can act on.
 */

/** The four steps in order. Step 0 is not a step: it is the absence of a mark. */
export const SEV_STEPS: Exclude<Sev, 0>[] = [1, 2, 3, 4]

/** What each step is CALLED.
 *
 *  These words were written in tokens.css beside each step and rendered
 *  nowhere. A scale whose steps have no names cannot be explained, cannot be
 *  spoken by a screen reader and cannot be argued with, so the words are a
 *  module export now and there is exactly one set of them: the legend prints
 *  them, and every mark hands its own to assistive technology.
 */
export const SEV_WORD: Record<Sev, string> = {
  0: '',
  1: 'noted',
  2: 'attention',
  3: 'high',
  4: 'severe',
}

/** What a mark adds to its own accessible name.
 *
 *  "marked high (3 of 4)". The ordinal travels with the word because a screen
 *  reader user can land on a mark in the middle of a 595-mark table without
 *  ever having passed the legend, and "high" on its own does not say how many
 *  steps there are or where this one sits. Step 0 contributes nothing, because
 *  the absence of a mark is not a quiet mark.
 */
export function sevAria(sev: Sev): string {
  return sev === 0 ? '' : `marked ${SEV_WORD[sev]} (${sev} of 4)`
}

/** One class string, so the legend paints the REAL mark rather than a copy of
 *  it that can drift. If a step ever looks different in the table than in the
 *  legend, it is because someone changed this in two places. */
function blockClass(sev: Sev, tone: 'fill' | 'quiet'): string {
  return `sev sev-${sev} sev-${tone}`
}

export function SevChip({ sev, children, title, tone = 'fill' }: {
  sev: Sev
  children: ReactNode
  title?: string
  /** `fill` escalates to a solid block at 3 and 4 -- the default, and what
   *  makes the scale readable across a room. `quiet` keeps the hairline at
   *  every step, for places where a solid block would be the loudest thing on a
   *  surface that has something louder to say. */
  tone?: 'fill' | 'quiet'
}) {
  if (sev === 0) return <>{children}</>
  return (
    <span className={blockClass(sev, tone)} title={title} data-sev={sev}>
      {children}
      {/* The step, for assistive technology. 26 of the 30 call sites pass no
          `title`, so until this existed the scale did not reach a screen reader
          at all: the fill is the only thing that carried the step, and a fill
          is not announced. Rendered inside the chip so every call site gets it
          without changing, and positioned out of flow so it takes no width, no
          flex gap and no line height. */}
      <span className="sev-sr">, {sevAria(sev)}</span>
    </span>
  )
}

/** A magnitude against a track. `of` is where the reference line sits, as a
 *  fraction, so the eye reads "past this point" rather than a bare length. */
export function SevBar({ sev, value, of, label, height = 6 }: {
  sev: Sev
  /** 0..1 of the track, already clamped by the caller. */
  value: number
  /** 0..1, where the threshold line is drawn. Omit for no line. */
  of?: number
  label?: string
  height?: number
}) {
  /* The step is appended here rather than at the call site because it was
     missing at EVERY call site: each one passed a factual description
     ("92.4% occupied, over the 85% line") and none of them named the step, so a
     bar's severity was visible and inaudible. Doing it in the component is what
     makes that true of all of them at once. */
  const name = [label, sevAria(sev)].filter(Boolean).join(', ')
  return (
    <span className="sevbar" style={{ height }} data-sev={sev}
          /* an unlabelled bar at step 0 says nothing a screen reader can use,
             and an unnamed role="img" announces itself as an image with no
             name. Better silent than noise. */
          role={name ? 'img' : undefined}
          aria-label={name || undefined}
          aria-hidden={name ? undefined : true}>
      <i className="sevbar-f" style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }} />
      {of != null && (
        <i className="sevbar-m" style={{ left: `${Math.max(0, Math.min(100, of * 100))}%` }} />
      )}
    </span>
  )
}

/** The scale, named. Place it above the thing it marks.
 *
 *  Why it exists: the scale spans five axes and seven idioms, and was explained
 *  only in code comments and in tooltips that most call sites never passed. A
 *  reader met 62 filled blocks on the first screen with no way to learn what
 *  two shades of brown meant.
 *
 *  Why the word "severity" is not on screen, in any form:
 *    - it grades measurements and waits, never people, and "severity" beside a
 *      patient's name reads as a claim about the patient;
 *    - the ranked list already prints "Severity rank"
 *      (core.ref_codes.severity_rank), which is the CPC ordering field and a
 *      completely different quantity. Two things called severity on one screen
 *      means the product answers the judge's question with the wrong one.
 *  So the strip is titled by what the scale is OF. Every axis it drives --
 *  wait against target, reading age past 90 days, a NEWS2 sub-score above 0,
 *  occupancy past 85%, a clinic past 75% booked -- is literally "how far past a
 *  line", which is why that phrase covers all five without stretching.
 *
 *  It is deliberately not a panel: no ground of its own and no border, so the
 *  four swatches sit on whatever surface the caller sits on and therefore look
 *  exactly like the marks below them. A legend that flatters its own swatches
 *  teaches the wrong scale.
 */
export function SevLegend({ className }: { className?: string }) {
  return (
    <div className={className ? `sevleg ${className}` : 'sevleg'}>
      <span className="sevleg-t lab">how far past a line</span>
      {/* an ordered list, so the ordering is in the markup and not only in the
          left-to-right of the ink */}
      <ol className="sevleg-steps">
        {SEV_STEPS.map((s) => (
          <li key={s}>
            {/* the real chip classes, and the word is the visible label -- so
                no sev-sr copy here, which would make a screen reader read
                "noted, marked noted (1 of 4)" */}
            <span className={blockClass(s, 'fill')} data-sev={s}>{SEV_WORD[s]}</span>
          </li>
        ))}
      </ol>
      <p className="sevleg-n">
        A mark grades a measurement, never a person: how far a wait is past its target, how old a
        reading is, how far a ward is past its safe line. Every mark carries its own value; an
        unmarked number is inside the line, and a missing one says so in words.
      </p>
    </div>
  )
}
