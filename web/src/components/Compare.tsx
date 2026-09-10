import { bandOf } from '../lib/api'
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

type Step = { rule: string; a: string; b: string; decided: boolean; note?: string }

function ladder(a: Ranking, b: Ranking): Step[] {
  const out: Step[] = []
  const ba = bandOf(a.cpc), bb = bandOf(b.cpc)
  out.push({
    rule: 'Clinical category', a: ba, b: bb, decided: ba !== bb,
    note: ba !== bb ? 'A hard boundary. No score moves anyone across it.' : 'Both in the same category, so this decides nothing.',
  })
  if (out[0].decided) return out

  const ta = a.crt_breached === true, tb = b.crt_breached === true
  out.push({
    rule: 'Past their target',
    a: a.crt_threshold_days == null ? 'no target' : ta ? 'yes' : 'no',
    b: b.crt_threshold_days == null ? 'no target' : tb ? 'yes' : 'no',
    decided: ta !== tb,
    note: ta !== tb
      ? 'Everyone past target is placed above everyone within it, whatever their score.'
      : 'Both on the same side of their target.',
  })
  if (out[1].decided) return out

  out.push({
    rule: 'Priority', a: n3(a.priority), b: n3(b.priority),
    decided: a.priority !== b.priority,
    note: a.priority !== b.priority ? undefined : 'Identical, so the older referral goes first.',
  })
  if (out[2].decided) return out

  out.push({
    rule: 'Referral date', a: a.referral_date, b: b.referral_date,
    decided: a.referral_date !== b.referral_date, note: 'Oldest first.',
  })
  return out
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
  const steps = ladder(a, b)
  const decidedBy = steps.find((s) => s.decided)
  const al = decision.alpha
  const terms = (r: Ranking) => ({ u: al * r.urgency_score, w: (1 - al) * r.wait_normalised })
  const ta = terms(a), tb = terms(b)
  const urgencyGap = Math.abs(ta.u - tb.u)
  const waitGap = Math.abs(ta.w - tb.w)

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
          <div className="cmp-v num">{s.a}</div>
          <div className="cmp-v num">{s.b}</div>
          {s.note && <div className="cmp-note">{s.note}</div>}
        </div>
      ))}

      {decidedBy?.rule === 'Priority' && (
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
          <p className="cmp-verdict">
            {waitGap > urgencyGap ? (
              <>The whole gap between these two is <strong>waiting time</strong>.{' '}
                {fmt(a.adjusted_wait_days ?? 0)} days against {fmt(b.adjusted_wait_days ?? 0)}.
                {urgencyGap < 0.0005 && ' Their vital signs contribute nothing at all: both score the same.'}</>
            ) : (
              <>The gap here is <strong>how unwell they were when measured</strong> — NEWS2
                separates them where waiting time does not. Each score is a single reading,
                and the two readings are not the same age.</>
            )}
          </p>
        </div>
      )}
    </div>
  )
}
