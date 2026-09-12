import { useEffect, useRef, type ReactNode } from 'react'
import { SEV_INTEGRITY, sevBreach, type Sev } from '../lib/severity'
import { Aside } from './Aside'
import './severity.css'

/** The one severity primitive: every attention state renders through this, so a
 *  reader learns the scale once. SevChip is a filled block, SevBar a magnitude
 *  against a track, SevQuiet a step drawn without its fill, SevLegend the key.
 *  The value is ALWAYS rendered: colour is never the only channel (SC 1.4.1). */

/** The four steps in order. Step 0 is not a step: it is the absence of a mark. */
export const SEV_STEPS: Exclude<Sev, 0>[] = [1, 2, 3, 4]

/** What each step is CALLED. Exactly one set of words: the legend prints them,
 *  and every mark hands its own to assistive technology. */
export const SEV_WORD: Record<Sev, string> = {
  0: '',
  1: 'noted',
  2: 'attention',
  3: 'high',
  4: 'severe',
}

/** What a mark adds to its accessible name: "marked high (3 of 4)". The ordinal
 *  travels with the word because a reader can land on a mark deep in a table
 *  without ever having passed the legend. */
export function sevAria(sev: Sev): string {
  return sev === 0 ? '' : `marked ${SEV_WORD[sev]} (${sev} of 4)`
}

/** One class string, so the legend paints the REAL mark rather than a copy that
 *  can drift. BOTH TONES go through here: a legend that keys only `fill` leaves
 *  most of the table unexplained. See BUILD_LEDGER.md. */
function blockClass(sev: Sev, tone: 'fill' | 'quiet'): string {
  return `sev sev-${sev} sev-${tone}`
}

/** The step a fired rule takes -- read from the scale, never typed here as a 3,
 *  so the legend follows that step if it ever moves. */
const RULE_SEV = sevBreach(false)

/** WHAT A QUIET MARK MEANS, as a value rather than as a comment.
 *
 *  Not a fifth step: one of the four steps drawn without its fill. WHICH step,
 *  and what it means, belongs to the SURFACE rather than to the scale.
 *
 *    List      step 3, the breach step     a rule that fired, one per breaching row
 *    Overview  step 4, the integrity step  a date that is not the day selected
 *
 *  As a value the legend and SevQuiet draw from one object, so a surface cannot
 *  key one step and draw another. */
export type QuietMark = {
  /** The step drawn without its fill. Taken from the scale at the constants
   *  below, never typed as a number, so a mark follows its step if it moves. */
  sev: Exclude<Sev, 0>
  /** What the mark means ON THE SURFACE THAT DRAWS IT, printed beside the chip. */
  label: string
  /** Why that step is drawn quiet HERE rather than solid, joined into the note
   *  under the strip. KEEP IT SHORT: it is the last clause of the aside, which
   *  is the surface the wordiness complaint was about. */
  why: string
}

/** Narrows a step to a DRAWABLE one. Step 0 is the absence of a mark, so a
 *  QuietMark at 0 would key a chip that is not on screen. Asserts NON-ZERO-NESS
 *  and never the number, so a mark still follows its step if that step moves. */
const drawable = (sev: Sev) => sev as Exclude<Sev, 0>

/** List's, and the default -- see SevLegend for why there is a default at all.
 *  One per breaching row in the rule column. */
export const QUIET_RULE_FIRED: QuietMark = {
  sev: drawable(RULE_SEV),
  label: 'a rule that fired',
  why: 'a rule fires on most breaching rows, and solid blocks would outshout the table',
}

/** Overview's three quiet marks all make the same claim: this date is not the
 *  day selected. Quiet, not solid, because the evidence is date-blind -- on 12
 *  of the 14 hospital-days all fourteen fire at once, and fourteen solid blocks
 *  at the loudest step would drown the one thing that step is for: a figure that
 *  does not reconcile. See BUILD_LEDGER.md. */
export const QUIET_OFF_DAY: QuietMark = {
  sev: drawable(SEV_INTEGRITY),
  label: 'a date that is not the day selected',
  why: 'on most days all fourteen of these dates are marked at once, and the solid block here is kept for a figure that does not reconcile',
}

/* --- the contract, checked rather than trusted -----------------------------
   A quiet chip registers itself while on screen; the legend compares what is
   mounted against what it was told to print, in BOTH directions. Runtime rather
   than a required prop because List.tsx already places this strip with no prop,
   so `quiet` keeps a default -- and a default is what a third surface would
   inherit in silence. DEV only, dead in the built bundle. */
const AUDIT = (import.meta as unknown as { env?: { DEV?: boolean } }).env?.DEV === true

/** What a mounted quiet chip registers: the mark itself when it has one, and
 *  its step either way. Exported because it names quietMismatch's input. */
export type QuietKey = Exclude<Sev, 0> | QuietMark
const quietDrawn = new Map<QuietKey, number>()
const quietWatchers = new Set<() => void>()
let quietQueued = false

/** Counted, not flagged: the same mark is drawn 7 times on one Overview table,
   and StrictMode mounts every effect twice. */
function quietBump(what: QuietKey, by: number) {
  const n = (quietDrawn.get(what) ?? 0) + by
  if (n > 0) quietDrawn.set(what, n)
  else quietDrawn.delete(what)
  /* Coalesced to one pass per commit: the legend mounts BEFORE the marks it
     explains, so it subscribes and re-checks rather than looking once. */
  if (quietQueued) return
  quietQueued = true
  queueMicrotask(() => {
    quietQueued = false
    for (const w of quietWatchers) w()
  })
}

/** The audit's whole rule: a surface's key must show the quiet marks that
 *  surface draws, and no others. Pure, so it can be exercised without a browser;
 *  Rollup drops it. Named marks compare by identity, so two sharing a step but
 *  not their words are told apart; an unnamed chip registers only its step. */
export function quietMismatch(quiet: QuietMark[], drawn: Iterable<QuietKey>): string[] {
  const wrong: string[] = []
  const seen = new Set<QuietKey>([...drawn])
  /* A SevQuiet registers BOTH its mark and its step, so a step is reported only
     when nothing named claims it -- otherwise one chip is reported twice. */
  const named = new Set<Sev>()
  for (const k of seen) if (typeof k !== 'number') named.add(k.sev)
  for (const k of seen) {
    if (typeof k === 'number') {
      if (!quiet.some((m) => m.sev === k) && !named.has(k)) {
        wrong.push(`drawn here but not in this key: a quiet mark at step ${k} (${SEV_WORD[k]})`)
      }
    } else if (!quiet.includes(k)) {
      wrong.push(`drawn here but not in this key: "${k.label}"`)
    }
  }
  for (const m of quiet) {
    if (!seen.has(m) && !seen.has(m.sev)) {
      wrong.push(`in this key but drawn nowhere: "${m.label}" at step ${m.sev} (${SEV_WORD[m.sev]})`)
    }
  }
  return wrong
}

/** Renders nothing. It holds the effect that says "this mark is on screen", so
 *  it can sit inside a chip without taking a flex gap or a table cell. */
function QuietAudit({ what }: { what: QuietKey }) {
  useEffect(() => {
    quietBump(what, 1)
    return () => quietBump(what, -1)
  }, [what])
  return null
}

export function SevChip({ sev, children, title, tone = 'fill' }: {
  sev: Sev
  children: ReactNode
  title?: string
  /** `fill` escalates to a solid block at 3 and 4 -- the default. `quiet` keeps
   *  the hairline at every step, where a solid block would be the loudest thing
   *  on a surface that has something louder to say. */
  tone?: 'fill' | 'quiet'
}) {
  if (sev === 0) return <>{children}</>
  return (
    <span className={blockClass(sev, tone)} title={title} data-sev={sev}>
      {children}
      {/* The step, for assistive technology: a fill is not announced, and most
          call sites pass no `title`. Inside the chip so every call site gets it,
          and out of flow so it takes no width, flex gap or line height. */}
      <span className="sev-sr">, {sevAria(sev)}</span>
      {/* Renders no node. A quiet chip with no QuietMark is still counted, by
          step, so the audit can check that surface's legend. */}
      {AUDIT && tone === 'quiet' && <QuietAudit what={sev} />}
    </span>
  )
}

/** A quiet mark, drawn FROM the object the legend prints. Prefer this to
 *  <SevChip tone="quiet"> everywhere: the step comes from the mark, so key and
 *  mark cannot name different steps. */
export function SevQuiet({ mark, children, title }: {
  mark: QuietMark
  children: ReactNode
  title?: string
}) {
  return (
    <>
      <SevChip sev={mark.sev} tone="quiet" title={title}>{children}</SevChip>
      {AUDIT && <QuietAudit what={mark} />}
    </>
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
  /* The step is appended here, not at the call site: call sites pass a factual
     description ("92.4% occupied, over the 85% line") and never the step, so a
     bar's severity would be visible and inaudible. */
  const name = [label, sevAria(sev)].filter(Boolean).join(', ')
  /* Clamped once, and BEFORE the comparison below, so what is compared is what
     is drawn rather than what was passed. */
  const v = clamp01(value)
  const m = of == null ? null : clamp01(of)
  return (
    <span className="sevbar" style={{ height }} data-sev={sev}
          /* An unnamed role="img" announces an image with no name, so an
             unlabelled bar is hidden rather than made noise. */
          role={name ? 'img' : undefined}
          aria-label={name || undefined}
          aria-hidden={name ? undefined : true}>
      <i className="sevbar-f" style={{ width: `${v * 100}%` }} />
      {m != null && (
        /* The marker must be legible on whatever is behind it, and that is the
           fill only where the fill has REACHED it -- which the step does not
           settle, since the staleness meter grades against a cohort MEDIAN. The
           side is stated, not inferred, and severity.css colours from it. */
        <i className="sevbar-m" data-on={m <= v ? 'fill' : 'track'}
           data-at={m >= 1 ? 'end' : undefined}
           style={{ left: `${m * 100}%` }} />
      )}
    </span>
  )
}

/** A module constant, not an inline default: a fresh `[QUIET_RULE_FIRED]` on
 *  every render would re-subscribe the audit on every render. */
const DEFAULT_QUIET: QuietMark[] = [QUIET_RULE_FIRED]

/** The scale, named. Place it above the thing it marks.
 *
 *  The word "severity" is never on screen: it grades measurements and waits,
 *  never people, and the ranked list already prints "Severity rank"
 *  (core.ref_codes.severity_rank), a different quantity.
 *
 *  WHICH quiet marks is the CALLER'S to say: exactly the set that surface draws,
 *  and an empty array is a valid answer. The default exists only because List.tsx
 *  places this strip with no prop; if List ever passes `quiet` itself, delete the
 *  default and make the prop required. See BUILD_LEDGER.md. */
export function SevLegend({ className, quiet = DEFAULT_QUIET }: {
  className?: string
  /** The quiet marks THIS surface draws -- all of them, and nothing else. */
  quiet?: QuietMark[]
}) {
  /* DEV only. Does this surface draw exactly the marks this strip prints? Both
     directions -- see "the contract, checked rather than trusted" above. */
  const said = useRef('')
  useEffect(() => {
    if (!AUDIT) return
    const check = () => {
      const now = quietMismatch(quiet, quietDrawn.keys()).join(' | ')
      if (now === said.current) return
      said.current = now
      if (now) {
        console.error(
          `SevLegend: the key does not match the quiet marks this surface draws -- ${now}. ` +
          'Pass `quiet` to <SevLegend>, naming every quiet mark this surface draws and no ' +
          'others (components/Severity.tsx).',
        )
      }
    }
    quietWatchers.add(check)
    check()
    return () => { quietWatchers.delete(check) }
  }, [quiet])

  return (
    <div className={className ? `sevleg ${className}` : 'sevleg'}>
      <span className="sevleg-t lab">how far past a line</span>
      {/* an ordered list, so the order is in the markup and not only in the ink */}
      <ol className="sevleg-steps">
        {SEV_STEPS.map((s) => (
          <li key={s}>
            {/* The real chip classes. The word IS the visible label here, so no
                sev-sr copy: it would read "noted, marked noted (1 of 4)". */}
            <span className={blockClass(s, 'fill')} data-sev={s}>{SEV_WORD[s]}</span>
          </li>
        ))}
      </ol>
      {/* Not a fifth step, so not inside the <ol> above: one group per quiet
          mark this surface draws, each with the sentence saying what the tone
          means there. The step is read off the mark, so this cannot show a step
          the caller's own chips do not draw. No triangle icon, though List's
          real chip carries one: that icon is List's composition, not the tone's,
          and copying it here is exactly the drift blockClass prevents. */}
      {quiet.map((m) => (
        <span className="sevleg-g" key={m.label}>
          <span className="sevleg-t lab">{m.label}</span>
          <span className={blockClass(m.sev, 'quiet')} data-sev={m.sev}>{SEV_WORD[m.sev]}</span>
        </span>
      ))}
      {/* Copy rules for this legend, the one place on screen that teaches the
          scale. THREE STATES, NOT TWO: an unmarked number is inside its line OR
          has no line at all -- sevWaitRatio returns 0 for a null ratio
          (severity.ts:27), so Routine and Uncategorised rows are unmarked for
          want of a target, not for being inside one. NO EM DASH: in this product
          the em dash is the GLYPH a cell prints when it has no value, so one
          inside the sentence that explains absence sets the product's symbol for
          "nothing here" in the middle of the definition of it. And the summary is
          the half a reader cannot decline, so both of its clauses stay there and
          nothing else does. See BUILD_LEDGER.md. */}
      <Aside
        className="sevleg-n"
        label="how to read a mark"
        summary="A mark grades a measurement, never a person. Every mark carries its own value.">
        What a mark grades: how far a wait is past its target, how old a reading is, how far a
        ward is past its safe line. An unmarked number is inside its line, or has no line at
        all: no target applies to Routine or Uncategorised. A missing measurement says so in
        words.
        {/* No sentence about pale chips on a surface that draws none. */}
        {quiet.length > 0 && ' A pale chip is one of those four steps drawn without its fill, ' +
          `bounded by the colour that fill uses: ${quiet.map((m) => m.why).join('; ')}.`}
      </Aside>
    </div>
  )
}
