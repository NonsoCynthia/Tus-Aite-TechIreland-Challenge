import { useQuery } from '@tanstack/react-query'
import { Check, TriangleAlert } from 'lucide-react'
import { api } from '../lib/api'
import { ruleStatement } from '../lib/ref'
import type { Decision, Overrides, Reference } from '../lib/types'
import './record.css'

const fmt = (n: number) => n.toLocaleString('en-IE')

/** Rules whose subject is the WHOLE list rather than one referral. They are
 *  checked once and hold or do not hold; a per-referral count would imply 305
 *  independent verdicts where there is one. */
const WHOLE_LIST = new Set(['RULE-ORDER', 'RULE-TIEBREAK'])

/** The decision as an auditable record.
 *
 *  README feature 10 promises "evidence-backed rule-violation output for
 *  review". The coordinator has always produced it — five rules, 776 checks —
 *  and none of it reached a screen, because the orchestrator served
 *  rank_cohort's raw output rather than the enriched rows that carry the checks.
 *
 *  Two things here refuse to be tidy on purpose. Every rule keeps its ID, so a
 *  reviewer can find it in core.ref_rules. And the four not-ranked buckets are
 *  never summed into one "excluded" figure: a whole specialty leaving the list
 *  is a coverage statement, a missing observation is a data-quality incident,
 *  and adding them together loses the difference.
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
  if (!dec.data) return <div className="pad"><p className="muted">Reading the decision…</p></div>
  const d = dec.data

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
  const union = new Set([...placedSet, ...paedSet, ...skipSet, ...excSet])
  const naiveSum = placedSet.size + paedSet.size + skipSet.size + excSet.size

  const buckets = [
    {
      k: 'Placed', n: placedSet.size,
      why: 'scored by both agents and given a position',
    },
    {
      k: 'Refused \u2014 paediatric', n: paedSet.size,
      why: 'NEWS2 is validated in adults, so the urgency agent refuses specialty 0601 rather than scoring a child on an adult scale',
      note: 'a coverage statement, not a low position',
    },
    {
      k: 'Skipped', n: skipSet.size,
      why: 'an adult referral the urgency agent could not score, usually a missing observation',
      note: 'a data-quality incident, and a different thing from a refusal',
    },
    {
      k: 'Excluded by the coordinator', n: excSet.size,
      why: 'no urgency score reached the ranking, so no position could be computed',
      note: bothPaedExc.length
        ? `${bothPaedExc.length} of these are the refusals above, seen a second time`
        : undefined,
    },
  ]

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
            core.ref_rules · {fmt([...tally.values()].reduce((a, b) => a + b.tested, 0))} checks
            across {fmt(d.rankings.length)} placements
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
              {rules.map((r) => {
                const whole = WHOLE_LIST.has(r.rule_id)
                const t = tally.get(r.rule_id)
                const passed = whole
                  ? (r.rule_id === 'RULE-ORDER' ? d.rule_order_passed : d.rule_tiebreak_passed)
                  : (t?.failed ?? 0) === 0
                return (
                  <tr key={r.rule_id} className={!passed ? 'is-breached' : ''}>
                    <td className="c-rid num">{r.rule_id}</td>
                    <td className="c-st">{ruleStatement(reference, r.rule_id)}</td>
                    <td className="c-n num">{r.threshold_days ? `${r.threshold_days}d` : '—'}</td>
                    <td className="c-n num">{whole ? 'whole list' : fmt(t?.tested ?? 0)}</td>
                    <td className="c-n num">
                      {whole ? '—' : t ? fmt(t.failed) : '—'}
                    </td>
                    <td className="c-v">
                      {passed
                        ? <span className="verdict is-ok"><Check size={13} strokeWidth={2.5} />holds</span>
                        : <span className="verdict is-bad">
                            <TriangleAlert size={13} strokeWidth={2.25} />
                            {whole ? 'violated' : `${fmt(t?.failed ?? 0)} past target`}
                          </span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="p-note measure">
          A breached timeframe rule is not a fault in the ranking. It records that a referral
          is already outside the window the health service set for its category — which is
          why the order places every breached referral in a band above every unbreached one,
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
              <div className="ledger-n num">{fmt(b.n)}</div>
              <div className="ledger-k">{b.k}</div>
              <div className="ledger-w">{b.why}{b.note && <em> — {b.note}</em>}</div>
            </div>
          ))}
        </div>
        {/* Reconciled on the UNION of the four, because they overlap. Summing
            them double-counts every referral that sits in two at once. */}
        <div className={'ledger-sum' + (union.size === total ? '' : ' is-off')}>
          <strong className="num">{fmt(union.size)}</strong> distinct referrals accounted
          for, of <strong className="num">{fmt(total)}</strong> on the list
          {union.size !== total && (
            <span className="ledger-gap"> · {fmt(Math.abs(total - union.size))} unexplained</span>
          )}
          {bothPaedExc.length > 0 && (
            <div className="ledger-overlap">
              The buckets overlap, which is why they are never summed:{' '}
              <strong className="num">{bothPaedExc.length}</strong> referrals sit in two at
              once — refused by the urgency agent, and therefore unplaceable by the
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
          Clinician actions
          <span className="sec-note">agent.overrides · every action, newest first</span>
        </h2>
        {ovr.data && ovr.data.overrides.length > 0 ? (
          <div className="scroll-x">
            <table className="rules ovr-log">
              <thead>
                <tr>
                  <th>When</th><th>Referral</th><th className="c-n">From</th>
                  <th className="c-n">To</th><th>Reason</th><th>Recorded as</th>
                </tr>
              </thead>
              <tbody>
                {ovr.data.overrides.map((o) => (
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
        ) : (
          <p className="muted">Nobody has confirmed or moved anyone on this hospital-day.</p>
        )}
        <p className="p-note measure">
          Attribution, not authentication: the record says who typed it, it does not verify
          them. Real identity is deployment work.
        </p>
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
