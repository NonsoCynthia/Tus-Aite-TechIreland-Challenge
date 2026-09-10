import { useEffect, useRef, type ReactNode } from 'react'
import { SEV_INTEGRITY, sevBreach, type Sev } from '../lib/severity'
import './severity.css'

/** The one severity primitive. Every attention state in the product renders
 *  through this, so a reader learns the scale once.
 *
 *  Four shapes, one scale:
 *    <SevChip>   a filled block carrying a value. The distance channel.
 *    <SevBar>    a magnitude drawn against a track, with the same four steps.
 *    <SevQuiet>  one of those steps drawn without its fill, from a QuietMark
 *                that says what it means on the surface drawing it.
 *    <SevLegend> the steps named, once, above the thing they mark -- the four
 *                solid ones always, plus the quiet marks THAT SURFACE draws.
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
 *  different: a solid block at 8.67:1 against the page, and a tint at 1.36:1
 *  against that same page (1.42 on --surface, where the ranked table sits).
 *  Both grounds are named on purpose: an unnamed ground is how four wrong
 *  figures got published in this family of files.
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

/** WHAT A QUIET MARK MEANS, as a value rather than as a comment.
 *
 *  The quiet tone is not a fifth step. It is one of the four steps drawn
 *  without its fill, and which step it is -- and what it means -- belongs to
 *  the SURFACE, not to the scale:
 *
 *    List      step 3, the breach step     a rule that fired, one per breaching row
 *    Overview  step 4, the integrity step  a date that is not the day selected
 *
 *  That contract used to be a sentence in this file telling the next author
 *  what to do, which is exactly how it broke: the strip was placed on Overview
 *  and went on printing List's mark -- a step Overview never draws -- while the
 *  mark Overview does draw had no key at all. A comment cannot be read by the
 *  file that violates it.
 *
 *  So a quiet mark is a VALUE now. The legend prints these, and SevQuiet draws
 *  from the same object, so one declaration feeds both and a surface cannot key
 *  one step and draw another. The half a shared object cannot check -- whether
 *  the WORDS still fit, and whether a surface declared a mark it never draws --
 *  is what the audit below checks, out loud, in the browser. */
export type QuietMark = {
  /** The step drawn without its fill. Taken from the scale at the constants
   *  below, never typed as a number here, so a mark follows its step if that
   *  step ever moves -- the same contract blockClass has for the classes. */
  sev: Exclude<Sev, 0>
  /** What the mark means ON THE SURFACE THAT DRAWS IT, printed beside the chip
   *  in the same voice as the ladder's own words. */
  label: string
  /** Why that step is drawn quiet here rather than solid. Joined into the note
   *  under the strip, so the reason is on screen and not only in a comment. */
  why: string
}

/** Narrows a step to a DRAWABLE one, in one place rather than at each mark.
 *
 *  Step 0 is not a step, it is the absence of a mark: SevChip renders bare
 *  children for it, so a QuietMark that arrived at 0 would key a chip that is
 *  not on the screen. Neither source below can be 0 -- sevBreach(false) is the
 *  breach step by that function's own definition, and SEV_INTEGRITY is the top
 *  of the scale -- so this asserts NON-ZERO-NESS and never the number, which is
 *  what keeps a mark following its step if that step ever moves. */
const drawable = (sev: Sev) => sev as Exclude<Sev, 0>

/** List's, and the default -- see SevLegend for why there is a default at all.
 *  One per breaching row in the rule column. */
export const QUIET_RULE_FIRED: QuietMark = {
  sev: drawable(RULE_SEV),
  label: 'a rule that fired',
  why: 'a rule fires on most rows that breach, and a field of solid blocks would outshout the table',
}

/** Overview's. Its three quiet marks -- the cited session in the specialty
 *  panel, the cited session in Clinic capacity, the ward snapshot -- all make
 *  the same claim: this date is not the day selected above.
 *
 *  Quiet rather than solid at a step whose SOLID form that surface keeps for a
 *  figure that does not reconcile. Counted from /api/operations/9001 over all
 *  14 hospital-days: all 7 wards carry 2026-08-30 and all 7 clinics carry
 *  2026-08-28 on every one of them, so on the 12 days that are neither, all 14
 *  of these dates are marked at the same time. Fourteen solid blocks at the
 *  loudest step the product has, on most days, saying only that the evidence is
 *  date-blind -- and drowning the one thing that step is for. */
export const QUIET_OFF_DAY: QuietMark = {
  sev: drawable(SEV_INTEGRITY),
  label: 'a date that is not the day selected',
  why: 'every ward and clinic here carries the same snapshot, so on most days all fourteen dates are marked at once, and the solid block at this step is kept for a figure that does not reconcile',
}

/* --- the contract, checked rather than trusted -----------------------------
   A quiet chip registers itself while it is on screen; the legend compares what
   is mounted against what it was told to print, and says so when the two
   disagree -- in BOTH directions, because this fault had both: a mark shown
   that the surface never draws, and a mark drawn that the key never shows.

   Why a runtime check and not a required prop, which the type checker would
   enforce for free: List.tsx already places this strip with no prop and is not
   this change's file to edit, so `quiet` has to keep a default, and a default
   is precisely what a third surface would inherit in silence. The check is what
   makes the default safe. It is the first thing the console says on a surface
   that got it wrong.

   Development only. A clinician must never be shown a developer's error, and
   the demo is served from `vite build` output where this is dead. The next
   author to place the strip is by definition running the dev server.

   Named marks are compared by identity and unnamed ones (List's own
   <SevChip tone="quiet">) by step, so the older call site is covered too. */
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
  /* Coalesced to one pass per commit. The legend sits ABOVE the marks it
     explains, so its own mount effect runs before theirs and would see an empty
     map; and half these tables arrive with a later query. So the legend
     subscribes and re-checks instead of looking once. */
  if (quietQueued) return
  quietQueued = true
  queueMicrotask(() => {
    quietQueued = false
    for (const w of quietWatchers) w()
  })
}

/** THE AUDIT'S WHOLE RULE, as one pure function: a surface's key must show the
 *  quiet marks that surface draws, and no others.
 *
 *  Lifted out of the component so it can be exercised without a browser, which
 *  is the only way this check itself gets checked. Rollup drops it from the
 *  built bundle -- nothing in the app calls it outside the DEV branch below.
 *
 *  Returns one sentence per disagreement, in both directions. Named marks are
 *  compared by identity, so two marks that share a step but not their words are
 *  still told apart; an unnamed quiet chip (List's <SevChip tone="quiet">)
 *  registers only its step, so it satisfies any declared mark at that step. */
export function quietMismatch(quiet: QuietMark[], drawn: Iterable<QuietKey>): string[] {
  const wrong: string[] = []
  const seen = new Set<QuietKey>([...drawn])
  /* A SevQuiet registers BOTH its mark and its step, so an undeclared named
     mark would otherwise be reported twice for one chip -- once by name and
     once as a bare step. The name is the more useful of the two, so a step is
     only reported when nothing named claims it. */
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

/** Renders nothing. It exists to hold the effect that says "this mark is on
 *  screen", which is why it can sit inside a chip without taking a flex gap or
 *  a table cell. */
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
      {/* Renders no node. A quiet chip drawn here without a QuietMark -- which
          today is List's rule column only -- is still counted, by step, so the
          audit can tell that surface's legend it is keying a real mark. */}
      {AUDIT && tone === 'quiet' && <QuietAudit what={sev} />}
    </span>
  )
}

/** A quiet mark, drawn FROM the object the legend prints.
 *
 *  Prefer this to <SevChip tone="quiet"> at every call site: the step comes
 *  from the mark, so the key and the mark cannot name different steps, and the
 *  mark registers itself by identity so the audit can check the words too. */
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
 *  entirely: solid at 8.67:1 beside a tint at 1.36:1 on the page, both the same
 *  step, on the same screen. The quiet chip is shown as what it is rather than
 *  the row chip being made solid, because the table was deliberately cut from
 *  62 solid marks to 8 to answer a saturation complaint, and teaching the
 *  reader a mark costs nothing while re-adding 20 solid blocks would spend
 *  that fix.
 *
 *  WHICH quiet marks is the CALLER'S to say, because it is the caller's fact.
 *  `quiet` is the marks this surface actually draws, and the only right answer
 *  is that set exactly: a key that shows a mark its surface never draws is the
 *  same fault as one that flatters its own swatches, and a key that omits one
 *  leaves the reader without the loudest signal on the page. An empty array is
 *  a legitimate answer -- a surface that draws no quiet mark shows no quiet
 *  group and no sentence about one -- and it is an answer the old comment could
 *  not even express.
 *
 *  There is a DEFAULT, and it is a compromise, not a convenience. Making
 *  `quiet` required would have the type checker catch every future call site
 *  for nothing, but List.tsx:1163 already places this strip with no prop and is
 *  not this change's file to touch. So the default is List's mark, and the
 *  audit above is what stops a third surface from inheriting it in silence.
 *  If List ever passes `quiet={[QUIET_RULE_FIRED]}` itself, delete the default
 *  and make the prop required: that is strictly better than a checked default.
 */
export function SevLegend({ className, quiet = DEFAULT_QUIET }: {
  className?: string
  /** The quiet marks THIS surface draws -- all of them, and nothing else. */
  quiet?: QuietMark[]
}) {
  /* Development only and dead in the built bundle: does this surface draw
     exactly the quiet marks this strip is printing? Both directions, because
     the fault this exists to catch had both. See "the contract, checked rather
     than trusted" above for why it is checked here and not by the type. */
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
      {/* The second tone, which on List is 54% of the marks on the first screen
          below this strip and had no key at all.

          Not a fifth step, so not inside the <ol> above: each of these is one
          of those four steps drawn in the other tone, and the markup says so by
          keeping the ladder to itself and labelling these separately.

          ONE GROUP PER MARK THIS SURFACE DRAWS -- List's rule at step 3,
          Overview's off-day date at step 4 -- each with the sentence that says
          what the tone means there. The step is read off the mark, so this
          cannot show a step the caller's own chips do not draw.

          No triangle icon, though List's real chip carries one: the icon is
          List's composition, not the tone's, and copying it here would be
          exactly the drift blockClass exists to prevent. What identifies the
          tone is the pale fill inside a solid edge, and that IS the real
          thing. */}
      {quiet.map((m) => (
        <span className="sevleg-g" key={m.label}>
          <span className="sevleg-t lab">{m.label}</span>
          <span className={blockClass(m.sev, 'quiet')} data-sev={m.sev}>{SEV_WORD[m.sev]}</span>
        </span>
      ))}
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
        or Uncategorised. A missing one says so in words.
        {/* The pale chip's sentence is the CALLER'S, and there is none at all when the
            caller draws no quiet mark: on a surface with no pale chip on it, a sentence
            explaining pale chips is one more mark with no referent. */}
        {quiet.length > 0 && ' A pale chip is one of those four steps drawn without its fill, ' +
          `bounded by the colour that fill uses: ${quiet.map((m) => m.why).join('; ')}.`}
      </p>
    </div>
  )
}
