import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, Minus, TriangleAlert } from 'lucide-react'
import { api } from '../lib/api'
import { breachPhrase, ruleStatement } from '../lib/ref'
import { SEV_INTEGRITY, sevBreach, NONE } from '../lib/severity'
import { SevChip } from '../components/Severity'
import { Aside } from '../components/Aside'
import type { Decision, Overrides, Reference } from '../lib/types'
import './record.css'

const fmt = (n: number) => n.toLocaleString('en-IE')

type WholeListVerdict = (d: Decision) => boolean

/** Rules whose subject is the WHOLE list, keyed to the decision field carrying
 *  each one's verdict -- keyed, so a new one has no else-branch to borrow another
 *  rule's verdict from. The `| undefined` is load-bearing: without it TS types
 *  every lookup as a function and the whole-list test is always true. */
const WHOLE_LIST: Record<string, WholeListVerdict | undefined> = {
  'RULE-ORDER':    (d) => d.rule_order_passed,
  'RULE-TIEBREAK': (d) => d.rule_tiebreak_passed,
}

/** How many override rows to draw at once, and how many each click adds. */
const OVR_PAGE = 25

/** `dec-40afec5c-a8d5-4af1-ab39-c198d24458e3` -> `dec-40afec5c`, for the log's
 *  provenance column only. The full id stays on the cell's title. */
const shortDec = (id: string) => (id.length > 12 ? id.slice(0, 12) : id)

/** The decision as an auditable record.
 *
 *  Nothing here counts rules for itself: the table is drawn from reference.rules
 *  and totalled from what came back. It cannot infer a NEW WHOLE-LIST rule --
 *  that needs a verdict field and an entry in WHOLE_LIST above.
 *
 *  THE OVERRIDE LOG NAMES ITS DECISION, ROW BY ROW: /api/overrides is scoped to a
 *  hospital-DAY, which holds one decision per run, so most rows can belong to
 *  earlier ones and their From/To name positions in another ordering. Kept, never
 *  allowed to pass as this decision's. See BUILD_LEDGER.md. */
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
  // api.overrides takes no limit, so the cap is here -- before the early
  // returns, because hooks cannot be conditional.
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
  // TRAP: gate on BOTH. /api/decision always wins the race against /api/cohort,
  // and in that window `total` is 0 while the union is full, which fires the
  // "N unexplained" integrity alarm.
  if (!dec.data || cohort.isPending) {
    return <div className="pad"><p className="muted">Reading the decision…</p></div>
  }
  const d = dec.data
  // A 404 from /api/overrides is normal: it means nobody has acted yet.
  const ovrRows = ovr.data?.overrides ?? []
  // Three groups: a row with no decision_id is not a row from another decision.
  const ovrOwn = ovrRows.filter((o) => o.decision_id === d.decision_id).length
  const ovrNone = ovrRows.filter((o) => !o.decision_id).length
  const ovrElsewhere = ovrRows.length - ovrOwn - ovrNone
  const ovrOtherDecisions = new Set(
    ovrRows.filter((o) => o.decision_id && o.decision_id !== d.decision_id)
      .map((o) => o.decision_id),
  ).size

  // Whole-list rules come from the decision's own booleans, never from rows.
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
  // Both derived, never written as literals in the header copy.
  const wholeRules = rules.filter((r) => r.rule_id in WHOLE_LIST)
  const perReferralChecks = [...tally.entries()]
    .filter(([id]) => !(id in WHOLE_LIST))
    .reduce((a, [, b]) => a + b.tested, 0)

  // SET UNION, never a sum: a refused referral is also unplaceable, so it is in
  // BOTH refused_paediatric and excluded.
  const total = cohort.data?.referrals.length ?? 0
  const placedSet = new Set(d.rankings.map((r) => r.pathway_number))
  const paedSet = new Set(d.refused_paediatric)
  const skipSet = new Set(d.skipped)
  const excSet = new Set(d.excluded.map((e) => e.pathway_number))
  const bothPaedExc = [...paedSet].filter((p) => excSet.has(p))

  // Members, not counts: the arithmetic below is N-ary, so a fifth bucket is one
  // entry here and nothing else.
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
              {/* drawn from core.ref_rules, so "the reference has not arrived"
                  is a state, and not the same as a decision with no checks */}
              {rules.length === 0 && (
                <tr><td className="c-st" colSpan={6}>Reading core.ref_rules…</td></tr>
              )}
              {rules.map((r) => {
                const wholeVerdict = WHOLE_LIST[r.rule_id]
                const t = tally.get(r.rule_id)
                // THREE states, not two: `(t?.failed ?? 0) === 0` reads an untested
                // rule's absent tally as zero failures and draws a green check
                // against "0 tested". `undefined` is "no verdict reached".
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
                        // No magnitude in a pass/fail rule, so sevBreach goes
                        // straight to "high"; the count travels in the chip.
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
        {/* The claim a reader must not get wrong stays visible -- a breach is not
            a fault in the ranking -- and the definition goes inside. */}
        <Aside className="p-note measure" label="how a breach changes the order"
               summary="A breached timeframe rule is not a fault in the ranking: it records a referral already outside its category's window.">
          The window is the one the health service set for that category. The order places every
          breached referral in a band above every unbreached one, before any score is compared.
        </Aside>
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
        {/* UNION, because the buckets overlap: a sum double-counts. */}
        <div className={'ledger-sum' + (union.size === total ? '' : ' is-off')}>
          <strong className="num">{fmt(union.size)}</strong> distinct referrals accounted
          for, of <strong className="num">{fmt(total)}</strong> on the list
          {union.size !== total && (
            <>
              {' '}
              {/* SEV_INTEGRITY, the loudest step there is: a referral no bucket
                  accounts for means the reconciliation cannot be trusted. */}
              <SevChip sev={SEV_INTEGRITY}
                       title="on the list and in no bucket: the reconciliation does not close">
                {fmt(unexplained)} unexplained
              </SevChip>
            </>
          )}
          {bothPaedExc.length > 0 && (
            <div className="ledger-overlap">
              The buckets overlap and are never summed:{' '}
              <strong className="num">{bothPaedExc.length}</strong> referrals sit in two at once,
              refused by the urgency agent and therefore unplaceable, which the coordinator
              records as <span className="num">paediatric_news2_not_applicable</span>. Summed rather than
              unioned they read as <span className="num">{fmt(naiveSum)}</span> of{' '}
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
            {ovrRows.length === 1 ? 'action' : 'actions'} on this hospital-day, newest first
            {ovrRows.length > 0 && <> · {fmt(ovrOwn)} against this decision</>}
          </span>
        </h2>
        {ovrRows.length > 0 ? (
          <>
            {/* BEFORE the table: From and To are unreadable until a reader knows
                which ordering each row counts in. */}
            <p className="p-note measure">
              The log is scoped to this hospital-day, and a hospital-day holds one decision per
              run.{' '}
              <strong className="num">{fmt(ovrOwn)}</strong> of these{' '}
              <strong className="num">{fmt(ovrRows.length)}</strong>{' '}
              {ovrRows.length === 1 ? 'action' : 'actions'}{' '}
              {ovrOwn === 1 ? 'was' : 'were'} recorded against{' '}
              <span className="num">{d.decision_id}</span>, the decision on this page.
              {ovrElsewhere > 0 && (
                <> <strong className="num">{fmt(ovrElsewhere)}</strong>{' '}
                  {ovrElsewhere === 1 ? 'was' : 'were'} recorded against{' '}
                  <span className="num">{fmt(ovrOtherDecisions)}</span> earlier{' '}
                  {ovrOtherDecisions === 1 ? 'decision' : 'decisions'} for this same hospital-day.
                  A From and a To are positions in the ordering their own decision produced, so on
                  those rows the two numbers name places in a list this run never built, and the
                  rules table and the ledger say nothing about them. They are kept, and marked,
                  because the log is the record of what people did.</>
              )}
              {ovrNone > 0 && (
                <> <strong className="num">{fmt(ovrNone)}</strong>{' '}
                  {ovrNone === 1 ? 'carries' : 'carry'} no decision id at all, so which ordering{' '}
                  {ovrNone === 1 ? 'its' : 'their'} positions belong to is not on the record.</>
              )}
            </p>
            {/* Capped, paged, and in a viewport the header can stick to. */}
            <div className="ovr-vp">
              <table className="rules ovr-log">
                <thead>
                  {/* TRAP: Decision sits AFTER Reason. record.css wraps and
                      width-caps Reason BY POSITION (.ovr-log td:nth-child(5)),
                      so a column inserted ahead of it hands those rules to the
                      wrong column and leaves the reasons nowrap. */}
                  <tr>
                    <th>When</th><th>Referral</th><th className="c-n">From</th>
                    <th className="c-n">To</th><th>Reason</th><th>Decision</th>
                    <th>Recorded as</th>
                  </tr>
                </thead>
                <tbody>
                  {ovrRows.slice(0, ovrShown).map((o) => {
                    // The one comparison the log turns on. It dims the From/To
                    // ink, but the Decision column's word carries it, not tone.
                    const own = !!o.decision_id && o.decision_id === d.decision_id
                    const pos = 'c-n num' + (own ? '' : ' muted')
                    return (
                      <tr key={o.override_id}>
                        <td className="num">{new Date(o.created_at).toLocaleString('en-IE')}</td>
                        <td className="num">{o.pathway_number}</td>
                        <td className={pos}>{o.from_position ?? '—'}</td>
                        <td className={pos}>
                          {o.to_position ?? '—'}
                          {o.from_position === o.to_position && <span className="muted"> · confirmed</span>}
                        </td>
                        <td>{o.reason}
                          {o.rule_warning_accepted && (
                            <span className="warn-chip">category boundary crossed, accepted</span>)}
                        </td>
                        <td className="num">
                          {!o.decision_id ? (
                            <span className="muted">not recorded</span>
                          ) : own ? (
                            <span title={o.decision_id}>this decision</span>
                          ) : (
                            <span className="muted" title={o.decision_id}>
                              {shortDec(o.decision_id)} · an earlier decision
                            </span>
                          )}
                        </td>
                        <td className="num">{o.clinician_id}</td>
                      </tr>
                    )
                  })}
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
