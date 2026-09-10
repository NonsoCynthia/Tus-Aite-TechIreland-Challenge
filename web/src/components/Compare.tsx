import type { ReactNode } from 'react'
import { bandOf } from '../lib/api'
import { sevBreach, type Sev } from '../lib/severity'
import { SevChip } from './Severity'
import type { Decision, Ranking } from '../lib/types'

/** Why A is ahead of B, resolved step by step.
 *
 *  This is the only surface that answers the question the whole project is
 *  built on: among two people a clinician marked equally urgent, why is this
 *  one first? The ladder is the coordinator's real sort key, in order:
 *
 *      1  clinical category      a hard boundary; no score crosses it
 *      2  past target or not     a tier, decided before any score
 *      3  priority               alpha*urgency + (1-alpha)*wait-percentile
 *      4  referral date          oldest first, when priority ties
 *
 *  It stops at the first step that separates them and says which one did it.
 */
const n3 = (x: number) => x.toFixed(3)
const fmt = (x: number) => x.toLocaleString('en-IE')

/** The two priority terms, by the names the rest of the product gives them. */
const TERM = {
  urgency: 'how unwell',
  wait: 'how long waited',
  both: 'both terms together',
} as const

/** First decimal place at which two numbers stop printing the same string. */
function firstDifferingDp(x: number, y: number): number {
  for (let d = 3; d <= 9; d++) if (x.toFixed(d) !== y.toFixed(d)) return d
  return 9
}

/** Decimals needed to carry two significant figures of a gap this small. */
function gapDp(gap: number): number {
  const g = Math.abs(gap)
  if (g === 0) return 3
  return Math.min(9, Math.max(3, Math.ceil(-Math.log10(g)) + 1))
}

export interface Margin {
  /** priority(a) - priority(b). The coordinator sorts descending inside a tier,
   *  so for two adjacent rows this is zero or positive. */
  gap: number
  /** Decimals at which the gap is visible AND the two priorities print
   *  differently, so the two figures and the gap between them agree on screen. */
  dp: number
  /** Signed alpha * urgency difference, a minus b. */
  du: number
  /** Signed (1-alpha) * wait-percentile difference, a minus b. */
  dw: number
  /** The term whose sign matches the gap: the one left standing. */
  carrier: 'urgency' | 'wait' | 'both'
  /** The two terms pull opposite ways, so the margin is only what did not
   *  cancel. Twelve of the adjacent in-band pairs in this hospital-day are of
   *  this shape, and it is the whole reason two "identical" numbers are not. */
  offsetting: boolean
  /** These two print the SAME string at 3 d.p. Only then may the copy say so:
   *  a gap of 0.0012 also needs a fourth decimal to carry two significant
   *  figures, and those two priorities were never identical on screen. */
  tiedAtDisplay: boolean
}

/** Where a priority difference actually comes from.
 *
 *  The ladder used to print both priorities at 3 d.p. and then label one of them
 *  "decides it". On this hospital-day that puts two IDENTICAL numbers under that
 *  label on 12 adjacent in-band pairs: positions 18 and 19 are 0.282693 and
 *  0.282539, and both print 0.283. The reader is shown a = b and told a > b,
 *  which is the client's point 12 word for word.
 *
 *  The cause is worth stating rather than hiding behind more decimals. On those
 *  pairs the two terms pull in OPPOSITE directions and very nearly cancel: at
 *  18/19 one is 0.061 more unwell and the other waited 0.061 longer, and the
 *  0.00015 left over is the whole margin. So the precision is widened only where
 *  the values really differ, and the term that survives the cancellation is
 *  named. Sixteen further pairs tie EXACTLY and fall through to referral date;
 *  those are untouched and still read as identical.
 */
export function margin(a: Ranking, b: Ranking, alpha: number): Margin {
  const du = alpha * (a.urgency_score - b.urgency_score)
  const dw = (1 - alpha) * (a.wait_normalised - b.wait_normalised)
  const gap = a.priority - b.priority
  const s = Math.sign(gap)
  const carrier = Math.sign(du) === s && Math.sign(dw) === s ? 'both'
    : Math.sign(du) === s ? 'urgency' : 'wait'
  const differsAt = firstDifferingDp(a.priority, b.priority)
  return {
    gap,
    dp: Math.max(differsAt, gapDp(gap)),
    du,
    dw,
    carrier,
    offsetting: du !== 0 && dw !== 0 && Math.sign(du) !== Math.sign(dw),
    tiedAtDisplay: differsAt > 3,
  }
}

type Cell = { text: string; sev?: Sev }
type Step = { rule: string; a: Cell; b: Cell; decided: boolean; note?: string }

function ladder(a: Ranking, b: Ranking, alpha: number): Step[] {
  const out: Step[] = []
  const ba = bandOf(a.cpc), bb = bandOf(b.cpc)
  out.push({
    rule: 'Clinical category', a: { text: ba }, b: { text: bb }, decided: ba !== bb,
    note: ba !== bb ? 'A hard boundary. No score moves anyone across it.' : 'Both in the same category, so this decides nothing.',
  })
  if (out[0].decided) return out

  // Past target is a breach of the category's own target, so the two cells wear
  // the severity register a breach gets everywhere else in the product.
  const ta = a.crt_breached === true, tb = b.crt_breached === true
  const tier = (r: Ranking, past: boolean): Cell =>
    r.crt_threshold_days == null
      ? { text: 'no target' }
      : { text: past ? 'past target' : 'within target', sev: sevBreach(!past) }
  out.push({
    rule: 'Past their target',
    a: tier(a, ta),
    b: tier(b, tb),
    decided: ta !== tb,
    note: ta !== tb
      ? 'Everyone past target is placed above everyone within it, whatever their score.'
      : 'Both on the same side of their target.',
  })
  if (out[1].decided) return out

  const differ = a.priority !== b.priority
  const m = differ ? margin(a, b, alpha) : null
  out.push({
    rule: 'Priority',
    a: { text: m ? a.priority.toFixed(m.dp) : n3(a.priority) },
    b: { text: m ? b.priority.toFixed(m.dp) : n3(b.priority) },
    decided: differ,
    note: m ? priorityNote(m) : 'Identical, so the older referral goes first.',
  })
  if (out[2].decided) return out

  out.push({
    rule: 'Referral date', a: { text: a.referral_date }, b: { text: b.referral_date },
    decided: a.referral_date !== b.referral_date, note: 'Oldest first.',
  })
  return out
}

/** Says what the widened precision is FOR, so the extra decimals do not read as
 *  false accuracy. */
function priorityNote(m: Margin): string {
  const gap = Math.abs(m.gap).toFixed(m.dp)
  const same = m.tiedAtDisplay
    ? `These print the same figure at 3 decimal places; shown to ${m.dp}, which is where they differ. `
    : ''
  if (m.offsetting) {
    const hi = m.carrier === 'wait' ? TERM.wait : TERM.urgency
    const lo = m.carrier === 'wait' ? TERM.urgency : TERM.wait
    return `${same}The two terms pull opposite ways and nearly cancel: ${gap} of ${hi} is what is left after ${lo} is taken off.`
  }
  return `${same}The margin is ${gap}, carried by ${TERM[m.carrier]}.`
}

/** What separates two adjacent people, stated ON the page.
 *
 *  The client's point 12: "your why on single view of patient just doesn't carry
 *  any explanation. It just says both are the same, but why is the other top
 *  then or below? What key differences?" That was true for two reasons. The
 *  explanation lived behind a "why?" click on a neighbour row, so the page as
 *  read said nothing at all; and when it was opened it printed two numbers
 *  rounded to the same 3 d.p. and called one of them the decider.
 *
 *  This is the one-line answer, inline, between the two rows it is about. The
 *  full ladder stays behind the click.
 */
export function WhatSeparates({ a, b, alpha }: { a: Ranking; b: Ranking; alpha: number }) {
  const steps = ladder(a, b, alpha)
  const by = steps.find((s) => s.decided)

  let body: ReactNode
  if (!by) {
    body = <>Nothing on the ladder separates them: same category, same side of target, identical
      priority and the same referral date.</>
  } else if (by.rule === 'Clinical category') {
    body = <><strong>the clinical category</strong>: {by.a.text} against {by.b.text}. A hard
      boundary, decided before any score.</>
  } else if (by.rule === 'Past their target') {
    const past = by.a.text === 'yes' ? a : b
    const within = by.a.text === 'yes' ? b : a
    body = <><strong>the target</strong>: <span className="num">{past.pathway_number}</span> is
      past its target and <span className="num">{within.pathway_number}</span> is not. That tier is
      decided before any score, whatever either of them scores.</>
  } else if (by.rule === 'Priority') {
    const m = margin(a, b, alpha)
    const hi = m.carrier === 'wait' ? TERM.wait : TERM.urgency
    const lo = m.carrier === 'wait' ? TERM.urgency : TERM.wait
    const hiBy = Math.abs(m.carrier === 'wait' ? m.dw : m.du)
    const loBy = Math.abs(m.carrier === 'wait' ? m.du : m.dw)
    body = m.offsetting ? (
      <>
        <strong>{hi}</strong>, by <span className="num">{Math.abs(m.gap).toFixed(m.dp)}</span> of
        priority. <span className="num">{a.pathway_number}</span> is{' '}
        <span className="num">{n3(hiBy)}</span> ahead on {hi} and{' '}
        <span className="num">{n3(loBy)}</span> behind on {lo}: the two almost cancel, and that
        margin is all that is left of them.
      </>
    ) : (
      <>
        <strong>{TERM[m.carrier]}</strong>, by <span className="num">{Math.abs(m.gap).toFixed(m.dp)}</span>{' '}
        of priority: <span className="num">{n3(Math.abs(m.du))}</span> of it from {TERM.urgency} and{' '}
        <span className="num">{n3(Math.abs(m.dw))}</span> from {TERM.wait}.
      </>
    )
  } else {
    body = <><strong>the referral date</strong>. Priority is identical to the last decimal, so the
      older letter goes first: {a.referral_date} against {b.referral_date}.</>
  }

  return (
    <div className="nb-sep">
      <span className="nb-sep-k">separated by</span>
      <span className="nb-sep-v">{body}</span>
    </div>
  )
}

export function Compare({ a, b, decision, ages, onClose }: {
  a: Ranking; b: Ranking; decision: Decision
  /** Each side's reading age in days, keyed by pathway.
   *
   *  Without it this panel presented "how unwell: 0.812 vs 0.406" in the present
   *  tense for two people whose single readings can be 12 and 800 days old, and
   *  concluded "NEWS2 separates them". Ages in this cohort run to 871 days, so
   *  equal-looking evidence is routinely nothing of the kind. */
  ages?: Record<string, number | null>
  onClose: () => void
}) {
  const al = decision.alpha
  const steps = ladder(a, b, al)
  const decidedBy = steps.find((s) => s.decided)
  const terms = (r: Ranking) => ({ u: al * r.urgency_score, w: (1 - al) * r.wait_normalised })
  const ta = terms(a), tb = terms(b)
  const urgencyGap = Math.abs(ta.u - tb.u)
  const waitGap = Math.abs(ta.w - tb.w)
  const m = a.priority !== b.priority ? margin(a, b, al) : null

  return (
    <div className="cmp">
      <div className="cmp-head">
        <h3>Why {a.pathway_number} is ahead of {b.pathway_number}</h3>
        <button className="pg" onClick={onClose}>Close</button>
      </div>

      <div className="cmp-cols">
        <span />
        <span className="cmp-who num">#{a.position} {a.pathway_number}</span>
        <span className="cmp-who num">#{b.position} {b.pathway_number}</span>
      </div>

      {steps.map((s) => (
        <div key={s.rule} className={'cmp-step' + (s.decided ? ' is-decider' : '')}>
          <div className="cmp-rule">
            {s.rule}
            {s.decided && <span className="cmp-tag">decides it</span>}
          </div>
          <div className="cmp-v num"><SevChip sev={s.a.sev ?? 0}>{s.a.text}</SevChip></div>
          <div className="cmp-v num"><SevChip sev={s.b.sev ?? 0}>{s.b.text}</SevChip></div>
          {s.note && <div className="cmp-note">{s.note}</div>}
        </div>
      ))}

      {decidedBy?.rule === 'Priority' && m && (
        <div className="cmp-terms">
          <div className="cmp-terms-h">Where that priority came from</div>
          <div className="cmp-trow">
            <span className="cmp-tk">
              how unwell
              <span className="cmp-tk-s">when measured</span>
            </span>
            <span className="cmp-tv num">
              {n3(ta.u)}
              {ages?.[a.pathway_number] != null && (
                <span className="cmp-age">{fmt(ages[a.pathway_number]!)}d old</span>)}
            </span>
            <span className="cmp-tv num">
              {n3(tb.u)}
              {ages?.[b.pathway_number] != null && (
                <span className="cmp-age">{fmt(ages[b.pathway_number]!)}d old</span>)}
            </span>
            <span className="cmp-td num">{urgencyGap < 0.0005 ? 'no difference' : `${n3(urgencyGap)} apart`}</span>
          </div>
          <div className="cmp-trow">
            <span className="cmp-tk">how long waited</span>
            <span className="cmp-tv num">{n3(ta.w)}</span>
            <span className="cmp-tv num">{n3(tb.w)}</span>
            <span className="cmp-td num">{waitGap < 0.0005 ? 'no difference' : `${n3(waitGap)} apart`}</span>
          </div>
          {/* The net, at the precision the net actually needs. Without this row
              the two rows above can each read "0.061 apart" and leave a reader
              with no idea which way the sum went. */}
          <div className="cmp-trow is-net">
            <span className="cmp-tk">priority</span>
            <span className="cmp-tv num">{a.priority.toFixed(m.dp)}</span>
            <span className="cmp-tv num">{b.priority.toFixed(m.dp)}</span>
            <span className="cmp-td num">{Math.abs(m.gap).toFixed(m.dp)} apart</span>
          </div>
          <p className="cmp-verdict">
            {m.offsetting ? (
              <>The two terms pull <strong>opposite ways</strong> here and all but cancel.{' '}
                {a.pathway_number} is <span className="num">{n3(Math.abs(m.du))}</span>{' '}
                {m.du > 0 ? 'ahead' : 'behind'} on how unwell and{' '}
                <span className="num">{n3(Math.abs(m.dw))}</span>{' '}
                {m.dw > 0 ? 'ahead' : 'behind'} on how long waited, so the margin that decides the
                order is <span className="num">{Math.abs(m.gap).toFixed(m.dp)}</span>: what is left
                of <strong>{m.carrier === 'wait' ? 'waiting time' : 'how unwell they were when measured'}</strong>{' '}
                after the other term is taken off.
                {m.tiedAtDisplay && (
                  <>{' '}Both figures round to <span className="num">{n3(a.priority)}</span> at
                    three decimal places, which is why this reads as a tie until it is opened.</>
                )}</>
            ) : waitGap > urgencyGap ? (
              <>The whole gap between these two is <strong>waiting time</strong>.{' '}
                {fmt(a.adjusted_wait_days ?? 0)} days against {fmt(b.adjusted_wait_days ?? 0)}.
                {urgencyGap < 0.0005 && ' Their vital signs contribute nothing at all: both score the same.'}</>
            ) : (
              <>The gap here is <strong>how unwell they were when measured</strong>. NEWS2
                separates them where waiting time does not. Each score is a single reading,
                and the two readings are not the same age.</>
            )}
          </p>
        </div>
      )}
    </div>
  )
}
