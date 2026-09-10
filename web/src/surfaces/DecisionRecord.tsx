import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, Minus, TriangleAlert } from 'lucide-react'
import { api } from '../lib/api'
import { breachPhrase, ruleStatement } from '../lib/ref'
import { SEV_INTEGRITY, sevBreach, NONE } from '../lib/severity'
import { SevChip } from '../components/Severity'
import type { Decision, Overrides, Reference } from '../lib/types'
import './record.css'

const fmt = (n: number) => n.toLocaleString('en-IE')

type WholeListVerdict = (d: Decision) => boolean

/** Rules whose subject is the WHOLE list rather than one referral, each keyed
 *  to the decision field that carries its single verdict.
 *
 *  This was a Set of two IDs and a two-way branch:
 *
 *      id === 'RULE-ORDER' ? d.rule_order_passed : d.rule_tiebreak_passed
 *
 *  so a THIRD whole-list rule added to core.ref_rules would have silently taken
 *  RULE-TIEBREAK's verdict and reported it as its own, on the surface a
 *  reviewer trusts most. Keyed by rule ID there is no else-branch to fall into:
 *  a rule with no entry here is not a whole-list rule, and is tallied from its
 *  own per-referral checks like every other rule.
 *
 *  A per-referral count is deliberately not shown for these. RULE-ORDER and
 *  RULE-TIEBREAK do arrive on all 305 rows, but they are one verdict about one
 *  ordering; printing "305 tested" would imply 305 independent judgements.
 *
 *  The `| undefined` is load-bearing. Without it TS types every lookup as a
 *  function and calls the "is this a whole-list rule" test always-true, which
 *  is the same assumption this replaced. */
const WHOLE_LIST: Record<string, WholeListVerdict | undefined> = {
  'RULE-ORDER':    (d) => d.rule_order_passed,
  'RULE-TIEBREAK': (d) => d.rule_tiebreak_passed,
}

/** How many override rows to draw at once, and how many each click adds. */
const OVR_PAGE = 25

/** The decision as an auditable record.
 *
 *  README feature 10 promises "evidence-backed rule-violation output for
 *  review". The coordinator has always produced it and none of it reached a
 *  screen, because the orchestrator served rank_cohort's raw output rather than
 *  the enriched rows that carry the checks.
 *
 *  Nothing on this surface counts rules or checks for itself: the table is
 *  drawn from reference.rules and the totals are summed from what actually came
 *  back, so core.ref_rules can gain or lose rows without a line changing here.
 *  The one thing it cannot infer is a NEW WHOLE-LIST rule, which needs a
 *  verdict field on the decision payload and therefore an entry above; until it
 *  gets one such a rule reports "not tested" rather than borrowing a verdict.
 *
 *  Two things here refuse to be tidy on purpose. Every rule keeps its ID, so a
 *  reviewer can find it in core.ref_rules. And the not-ranked buckets are never
 *  summed into one "excluded" figure: a whole specialty leaving the list is a
 *  coverage statement, a missing observation is a data-quality incident, and
 *  adding them together loses the difference.
 */
export function DecisionRecord({ hospital, date, reference }: {
  hospital: string; date: string; reference: Reference | undefined
}) {
  const dec = useQuery<Decision>({
    queryKey: ['decision', hospital, date],
    queryFn: () => api.decision(hospital, date), retry: false,
  })
  const cohort = useQuery({
    queryKey: ['cohort', hospital, date], queryFn: () => api.cohort(hospital, date),
  })
  const ovr = useQuery<Overrides>({
    queryKey: ['overrides', hospital, date],
    queryFn: () => api.overrides(hospital, date), retry: false,
  })
  // The log is the full history and api.overrides takes no limit, so the cap is
  // held here. Declared before the early returns: hooks cannot be conditional.
  const [ovrShown, setOvrShown] = useState(OVR_PAGE)

  if (dec.isError) {
    return (
      <div className="pad">
        <div className="lede">
          <h1>No decision for this hospital-day</h1>
          <p className="lede-p measure">
            Nothing has been scored, so there is no record to audit. Run the agents from the
            top bar.
          </p>
        </div>
      </div>
    )
  }
  // BOTH, not just the decision. /api/decision returns in 9-22ms and
  // /api/cohort in 19-55ms, so the decision ALWAYS wins the race -- and for that
  // window `total` was 0 while the union held 308, which rendered
  // "308 distinct referrals accounted for, of 0 on the list · 308 unexplained"
  // under the loudest severity step the product owns, on the one surface whose
  // whole job is to say the counts close. One keystroke on the date picker was
  // enough to fire it.
  if (!dec.data || cohort.isPending) {
    return <div className="pad"><p className="muted">Reading the decision…</p></div>
  }
  const d = dec.data
  // A 404 from /api/overrides is normal: it means nobody has acted yet.
  const ovrRows = ovr.data?.overrides ?? []

  // Every rule the coordinator tested, tallied. RULE-ORDER and RULE-TIEBREAK
  // come from the decision's own whole-list booleans, not from counting rows.
  const tally = new Map<string, { tested: number; failed: number }>()
  for (const r of d.rankings) {
    for (const c of r.rule_checks ?? []) {
      const t = tally.get(c.rule_id) ?? { tested: 0, failed: 0 }
      t.tested += 1
      if (!c.passed) t.failed += 1
      tally.set(c.rule_id, t)
    }
  }
  const rules = reference?.rules ?? []
  // Both derived, never counted in the copy: the header used to read "plus 2
  // whole-list" as a literal.
  const wholeRules = rules.filter((r) => r.rule_id in WHOLE_LIST)
  const perReferralChecks = [...tally.entries()]
    .filter(([id]) => !(id in WHOLE_LIST))
    .reduce((a, [, b]) => a + b.tested, 0)

  // Reconciliation by SET UNION, never by sum.
  //
  // The three paediatric referrals appear in BOTH refused_paediatric and
  // excluded: the urgency agent refuses them deliberately, so the coordinator
  // then cannot place them and records them as "missing_urgency_score". Adding
  // the buckets gives 311 of 308. Worse, the coordinator's own reason loses the
  // point -- it reads as a data-quality gap when it is a coverage decision.
  const total = cohort.data?.referrals.length ?? 0
  const placedSet = new Set(d.rankings.map((r) => r.pathway_number))
  const paedSet = new Set(d.refused_paediatric)
  const skipSet = new Set(d.skipped)
  const excSet = new Set(d.excluded.map((e) => e.pathway_number))
  const bothPaedExc = [...paedSet].filter((p) => excSet.has(p))

  // Each bucket carries its MEMBERS, not a count, so the union and the naive sum
  // below are computed from this list rather than from four named variables. The
  // four are what the decision payload exposes; the arithmetic is N-ary, so a
  // fifth bucket is one entry here and nothing else.
  const buckets: Array<{ k: string; ids: Set<string>; why: string; note?: string }> = [
    {
      k: 'Placed', ids: placedSet,
      why: 'scored by both agents and given a position',
    },
    {
      k: 'Refused: paediatric', ids: paedSet,
      why: 'NEWS2 is validated in adults, so the urgency agent refuses specialty 0601 rather than scoring a child on an adult scale',
      note: 'a coverage statement, not a low position',
    },
    {
      k: 'Skipped', ids: skipSet,
      why: 'an adult referral the urgency agent could not score, usually a missing observation',
      note: 'a data-quality incident, and a different thing from a refusal',
    },
    {
      k: 'Excluded by the coordinator', ids: excSet,
      why: 'no urgency score reached the ranking, so no position could be computed',
      note: bothPaedExc.length
        ? `${bothPaedExc.length} of these are the refusals above, seen a second time`
        : undefined,
    },
  ]
  const union = new Set(buckets.flatMap((b) => [...b.ids]))
  const naiveSum = buckets.reduce((a, b) => a + b.ids.size, 0)
  const unexplained = Math.abs(total - union.size)

  return (
    <div className="pad rec">
      <div className="lede">
        <span className="lab">Decision record</span>
        <h1>What was decided, and against which rules</h1>
      </div>

      <section className="rec-meta">
        <Field k="decision" v={d.decision_id} mono />
        <Field k="run" v={d.run_id} mono />
        <Field k="as of" v={new Date(d.as_of_date).toLocaleDateString('en-IE',
          { day: 'numeric', month: 'long', year: 'numeric' })} />
        <Field k="α · weight on urgency" v={d.alpha.toFixed(3)} big />
        <Field k="scarcity" v={d.scarcity.toFixed(3)} big />
        <Field k="capacity read as" v={d.capacity_direction} note="ADR-007" />
        <Field k="built" v={new Date(d.built_at).toLocaleString('en-IE')} />
      </section>

      <section className="rec-sec">
        <h2 className="sec-h">
          Rules tested
          <span className="sec-note">
            core.ref_rules · {fmt(rules.length)} rules ·{' '}
            {fmt(perReferralChecks)} per-referral checks across{' '}
            {fmt(d.rankings.length)} placements
            {wholeRules.length > 0 && `, plus ${fmt(wholeRules.length)} whole-list`}
          </span>
        </h2>
        <div className="scroll-x">
          <table className="rules">
            <thead>
              <tr>
                <th>Rule</th><th>Statement</th><th className="c-n">Threshold</th>
                <th className="c-n">Tested</th><th className="c-n">Breached</th><th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {/* the table is drawn from core.ref_rules, so it has a state
                  where the reference has not arrived and there is nothing to
                  draw. It is not the same as a decision with no checks. */}
              {rules.length === 0 && (
                <tr><td className="c-st" colSpan={6}>Reading core.ref_rules…</td></tr>
              )}
              {rules.map((r) => {
                const wholeVerdict = WHOLE_LIST[r.rule_id]
                const t = tally.get(r.rule_id)
                // THREE states, not two. A rule that exists in core.ref_rules
                // but was never tested has no tally at all, and `(t?.failed ??
                // 0) === 0` read that absence as zero failures and drew a green
                // check against "0 tested". An untested rule reported as
                // passing, on the surface a reviewer trusts. `undefined` here
                // means "no verdict was reached", and says so.
                const verdict: boolean | undefined =
                  wholeVerdict ? wholeVerdict(d) : t ? t.failed === 0 : undefined
                const sev = verdict == null ? NONE : sevBreach(verdict)
                return (
                  <tr key={r.rule_id} className={verdict === false ? 'is-breached' : ''}>
                    <td className="c-rid num">{r.rule_id}</td>
                    <td className="c-st">{ruleStatement(reference, r.rule_id)}</td>
                    <td className="c-n num">{r.threshold_days ? `${r.threshold_days}d` : '—'}</td>
                    <td className="c-n num">
                      {wholeVerdict ? 'whole list' : t ? fmt(t.tested) : '—'}
                    </td>
                    <td className="c-n num">
                      {wholeVerdict || !t ? '—' : fmt(t.failed)}
                    </td>
                    <td className="c-v">
                      {verdict == null ? (
                        <span className="verdict is-none">
                          <Minus size={12} strokeWidth={2.5} aria-hidden />not tested
                        </span>
                      ) : verdict ? (
                        <span className="verdict is-ok">
                          <Check size={12} strokeWidth={2.5} aria-hidden />holds
                        </span>
                      ) : (
                        // sevBreach: a pass/fail rule has no magnitude, so it
                        // goes straight to the "high" step rather than pretending
                        // to a gradation it does not have. The count travels in
                        // the chip, so colour is never the only channel.
                        <SevChip sev={sev}>
                          <TriangleAlert size={12} strokeWidth={2.25} aria-hidden />
                          {wholeVerdict ? 'violated' : breachPhrase(r.rule_id, t?.failed ?? 0)}
                        </SevChip>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="p-note measure">
          A breached timeframe rule is not a fault in the ranking. It records that a referral
          is already outside the window the health service set for its category. That is why
          the order places every breached referral in a band above every unbreached one,
          before any score is compared.
        </p>
      </section>

      <section className="rec-sec">
        <h2 className="sec-h">
          Everyone accounted for
          <span className="sec-note">{fmt(total)} on the list, reconciled</span>
        </h2>
        <div className="ledger">
          {buckets.map((b) => (
            <div className="ledger-row" key={b.k}>
              <div className="ledger-n num">{fmt(b.ids.size)}</div>
              <div className="ledger-k">{b.k}</div>
              <div className="ledger-w">{b.why}{b.note && <em> ({b.note})</em>}</div>
            </div>
          ))}
        </div>
        {/* Reconciled on the UNION of the buckets, because they overlap. Summing
            them double-counts every referral that sits in two at once. */}
        <div className={'ledger-sum' + (union.size === total ? '' : ' is-off')}>
          <strong className="num">{fmt(union.size)}</strong> distinct referrals accounted
          for, of <strong className="num">{fmt(total)}</strong> on the list
          {union.size !== total && (
            <>
              {' '}
              {/* SEV_INTEGRITY, the loudest step the product has. A referral on
                  the list that no bucket accounts for means the reconciliation
                  itself cannot be trusted, which outranks any clinical state:
                  a clinician can act on a bad number. Its only signal before
                  this was a 3px --rule-firm left edge at 1.55:1. */}
              <SevChip sev={SEV_INTEGRITY}
                       title="on the list and in no bucket: the reconciliation does not close">
                {fmt(unexplained)} unexplained
              </SevChip>
            </>
          )}
          {bothPaedExc.length > 0 && (
            <div className="ledger-overlap">
              The buckets overlap, which is why they are never summed:{' '}
              <strong className="num">{bothPaedExc.length}</strong> referrals sit in two at
              once, refused by the urgency agent and therefore unplaceable by the
              coordinator, which records those same referrals as{' '}
              <span className="num">missing_urgency_score</span>. Added rather than unioned
              they read as <span className="num">{fmt(naiveSum)}</span> of{' '}
              <span className="num">{fmt(total)}</span>.
            </div>
          )}
        </div>
      </section>

      <section className="rec-sec">
        <h2 className="sec-h">
          Recorded actions
          <span className="sec-note">
            agent.overrides · {fmt(ovrRows.length)}{' '}
            {ovrRows.length === 1 ? 'action' : 'actions'}, newest first
          </span>
        </h2>
        {ovrRows.length > 0 ? (
          <>
            {/* The log is the FULL history and it was drawn in full: no slice,
                no cap. A Reason column at white-space: normal makes a row about
                55px, so 200 overrides is ~11,000px of table and a year of a busy
                list is ~110,000px. Capped, paged, and bounded by a viewport so
                the header has something to stick to. */}
            <div className="ovr-vp">
              <table className="rules ovr-log">
                <thead>
                  <tr>
                    <th>When</th><th>Referral</th><th className="c-n">From</th>
                    <th className="c-n">To</th><th>Reason</th><th>Recorded as</th>
                  </tr>
                </thead>
                <tbody>
                  {ovrRows.slice(0, ovrShown).map((o) => (
                    <tr key={o.override_id}>
                      <td className="num">{new Date(o.created_at).toLocaleString('en-IE')}</td>
                      <td className="num">{o.pathway_number}</td>
                      <td className="c-n num">{o.from_position ?? '—'}</td>
                      <td className="c-n num">
                        {o.to_position ?? '—'}
                        {o.from_position === o.to_position && <span className="muted"> · confirmed</span>}
                      </td>
                      <td>{o.reason}
                        {o.rule_warning_accepted && (
                          <span className="warn-chip">category boundary crossed, accepted</span>)}
                      </td>
                      <td className="num">{o.clinician_id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="ovr-foot">
              <span className="num">
                {fmt(Math.min(ovrShown, ovrRows.length))} of {fmt(ovrRows.length)} shown
              </span>
              {ovrShown < ovrRows.length && (
                <button className="ovr-more" onClick={() => setOvrShown((n) => n + OVR_PAGE)}>
                  Show {fmt(Math.min(OVR_PAGE, ovrRows.length - ovrShown))} more
                </button>
              )}
              {ovrShown > OVR_PAGE && (
                <button className="ovr-more" onClick={() => setOvrShown(OVR_PAGE)}>
                  Back to {fmt(OVR_PAGE)}
                </button>
              )}
            </div>
          </>
        ) : (
          <p className="muted">Nobody has confirmed or moved anyone on this hospital-day.</p>
        )}
      </section>
    </div>
  )
}

function Field({ k, v, mono, big, note }: {
  k: string; v: string; mono?: boolean; big?: boolean; note?: string
}) {
  return (
    <div className={'field' + (big ? ' is-big' : '')}>
      <div className="lab">{k}</div>
      <div className={'field-v' + (mono ? ' num' : '')}>{v}</div>
      {note && <div className="field-n">{note}</div>}
    </div>
  )
}
