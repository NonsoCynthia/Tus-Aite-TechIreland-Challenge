import type { ReactNode } from 'react'
import { sevBreach, type Sev } from '../lib/severity'
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
 *  legend, it is because someone changed this in two places.
 *
 *  That was true of the STEP and false of the TONE. The legend painted all four
 *  steps in `fill` and the table draws two tones, so on the List's first screen
 *  -- the only surface that places the legend -- the legend showed 4 chips
 *  while the table below it drew 37, of which 20 were the rule that fired: the
 *  same step, in a tone the legend never showed. 54% of the marks on screen
 *  were a shape the reader had no key for, and the two objects are not subtly
 *  different: a solid block at 8.67:1 against the page and a tint at 1.42:1.
 *  Both tones go through this function now, and both are drawn. */
function blockClass(sev: Sev, tone: 'fill' | 'quiet'): string {
  return `sev sev-${sev} sev-${tone}`
}

/** The step a fired rule takes -- read from the scale, not typed here as a 3.
 *
 *  It is the one mark the table draws in `quiet` on the surface that places the
 *  legend (List's rule column, one per breaching row). Taking it from sevBreach
 *  means the legend follows the scale if that step ever moves, which is the
 *  same contract blockClass has for the classes. */
const RULE_SEV = sevBreach(false)

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

const clamp01 = (n: number) => Math.max(0, Math.min(1, n))

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
  /* Clamped once, and BEFORE the comparison below, so what is compared is what
     is drawn rather than what was passed. */
  const v = clamp01(value)
  const m = of == null ? null : clamp01(of)
  return (
    <span className="sevbar" style={{ height }} data-sev={sev}
          /* an unlabelled bar at step 0 says nothing a screen reader can use,
             and an unnamed role="img" announces itself as an image with no
             name. Better silent than noise. */
          role={name ? 'img' : undefined}
          aria-label={name || undefined}
          aria-hidden={name ? undefined : true}>
      <i className="sevbar-f" style={{ width: `${v * 100}%` }} />
      {m != null && (
        /* The marker has to be legible on whatever is behind it, and what is
           behind it is the fill only where the fill has REACHED it. The step
           does not settle that: occupancy and wait ratio both score 0 until
           their line is passed, so for those the fill is always under the
           marker by the time the step climbs -- but the staleness meter grades
           this reading's age against a line that is the cohort MEDIAN, and a
           reading over a year old can still sit left of a median older than it.
           Today it cannot (the median runs 139-146 days across all 14
           hospital-days), which is exactly the kind of accident that put six
           inversions of this ramp into the product. So the side is stated, not
           inferred, and severity.css colours the marker from it. */
        <i className="sevbar-m" data-on={m <= v ? 'fill' : 'track'}
           style={{ left: `${m * 100}%` }} />
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
 *
 *  It also draws BOTH TONES, because the table does. Four fill chips explained
 *  4 of the 37 marks on the List's first screen and left 20 -- the rule that
 *  fired, one on every breaching row -- looking like a different object
 *  entirely: solid at 8.67:1 beside a tint at 1.42:1, both meaning the same
 *  step, on the same screen. The quiet chip is shown as what it is rather than
 *  the row chip being made solid, because the table was deliberately cut from
 *  62 solid marks to 8 to answer a saturation complaint, and teaching the
 *  reader a mark costs nothing while re-adding 20 solid blocks would spend
 *  that fix.
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
      {/* The second tone, which is 54% of the marks on the first screen below
          this strip and had no key at all.

          Not a fifth step, so not inside the <ol> above: it is one of those
          four steps drawn in the other tone, and the markup says that by
          keeping the ladder to itself and labelling this separately.

          Only the step sevBreach gives, and only one chip: the tone also
          carries the integrity mark at step 4, but that is drawn on Overview,
          which does not place this legend -- and a legend that shows a mark its
          surface never draws is the same fault as one that flatters its own
          swatches. If this strip is ever placed on Overview, this group grows.

          No triangle icon, though the real chip carries one: the icon is List's
          composition, not the tone's, and copying it here would be exactly the
          drift blockClass exists to prevent. What identifies the tone is the
          pale fill inside a solid edge, and that IS the real thing. */}
      <span className="sevleg-g">
        <span className="sevleg-t lab">a rule that fired</span>
        <span className={blockClass(RULE_SEV, 'quiet')} data-sev={RULE_SEV}>{SEV_WORD[RULE_SEV]}</span>
      </span>
      {/* THREE STATES, NOT TWO.

          This note used to say "an unmarked number is inside the line". On the
          wait axis that was false for every referral with NO TARGET:
          sevWaitRatio returns 0 for a null ratio (severity.ts:27), so a Routine
          or Uncategorised row is unmarked because there is no line -- not
          because it is inside one. That is 143 of the 308 open at
          9001/2026-08-30 (88 Routine, 55 Uncategorised, counted from
          /api/cohort), against 35 that do have a target and sit inside it. The
          legend is the one place on screen that teaches the scale, so a false
          sentence here is worse than no sentence.

          Stated in words and not as a figure, because the figure is of the
          hospital-day: 133 of 293 on 2026-08-25, 134 of 295 on 08-27. The
          header above already prints the day's own count under "no target
          applies", and this strip is placed once per band tab beneath it, so
          the wording borrows that surface's phrase rather than inventing a
          second name for the same thing.

          The other four axes the scale drives always have a line -- 90 days,
          a sub-score above 0, 85% occupied, 75% booked -- so the third state is
          written as the exception it is, and named by the only thing that
          causes it. The missing-reading clause is untouched: an absent
          measurement is an absence of information, never reassurance, and it
          is the one state that is never carried by a mark at all.

          No em dash in the aside, though the sentence wants one. In this
          product the em dash is a GLYPH, not punctuation: it is what a cell
          prints when it has no value (List, Overview, DecisionRecord). Setting
          one inside the sentence that explains absence would put the
          product's own symbol for "nothing here" in the middle of the
          legend's definition of it. A colon and a full stop cost nothing. */}
      <p className="sevleg-n">
        A mark grades a measurement, never a person: how far a wait is past its target, how old a
        reading is, how far a ward is past its safe line. Every mark carries its own value. An
        unmarked number is inside its line, or has no line at all: no target applies to Routine
        or Uncategorised. A missing one says so in words. The pale chip is one of those
        four steps drawn without its fill, bounded by the colour that fill uses: a rule fires on
        most rows that breach, and a field of solid blocks would outshout the table.
      </p>
    </div>
  )
}
