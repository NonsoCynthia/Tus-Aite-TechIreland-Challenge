import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Check, Info, TriangleAlert } from 'lucide-react'
import { api, bandOf } from '../lib/api'
import { checkLabel, crtDays, failed, ruleStatement, specialtyFull } from '../lib/ref'
import { plantedCase } from '../lib/planted'
import { sevBreach, sevWaitRatio } from '../lib/severity'
import { SevBar, SevChip } from '../components/Severity'
import { Journey, type Event } from '../components/Journey'
import { Provenance } from '../components/Provenance'
import { Override } from '../components/Override'
import { Compare, WhatSeparates } from '../components/Compare'
import { AgentInputs, type CapacityContext } from '../components/AgentInputs'
import type { AgeStats } from '../components/Vitals'
import type { Decision, Overrides, Ranking, Reference, RuleCheck } from '../lib/types'
import './patient.css'

/** One referral, answering one question: why is this person here?
 *
 *  The page used to answer it in prose. Three notes did the real work ("add the
 *  six by hand and you get the same number", "it does not mean this person is
 *  near normal now", "the condition code is a weighted random draw") and every
 *  one of them was a sentence standing in for an instrument that had not been
 *  built. This is a system, not a notebook, so each of the three is now a thing
 *  on screen: the NEWS2 sub-scores drawn against their bands, a staleness meter
 *  on the reading, and a limits panel whose chips carry their provenance.
 *
 *  The order follows the question. Where this person sits, then why, then what
 *  each agent actually read, then the shape of the wait, then the recorded
 *  citation chain, and last what the instrument never looked at.
 */

/** --icon-sm from tokens.css, and lucide's stroke passed rather than inherited:
 *  the default of 2 renders heavier than the 1.75 hairline chrome beside it.
 *  V_ICON is the verdict register, matched to the three others in the product. */
const ICON_SM_PX = 14
const STROKE = 1.75
const V_ICON = 12

const fmt = (n: number) => n.toLocaleString('en-IE')
const n3 = (x: number) => x.toFixed(3)
const dateLong = (s: string) =>
  new Date(s).toLocaleDateString('en-IE', { day: 'numeric', month: 'long', year: 'numeric' })
const chipClass = (band: string) => 'chip cat-' + band.toLowerCase().replace('-', '')
/** "9001/W-9001-06/2026-08-30%2020%3A00%3A00" -> the segment asked for. */
const seg = (key: string, i: number) => {
  const parts = key.split('/')
  return parts[i] ? decodeURIComponent(parts[i]) : null
}

export function Patient({ hospital, date, pathway, reference, onBack }: {
  hospital: string; date: string; pathway: string
  reference: Reference | undefined
  onBack: () => void
}) {
  const [ovr, setOvr] = useState(false)
  const [cmp, setCmp] = useState<'above' | 'below' | null>(null)
  const [flash, setFlash] = useState<string | null>(null)

  const ops = useQuery({
    queryKey: ['operations', hospital, date],
    queryFn: () => api.operations(hospital, date), staleTime: Infinity,
  })
  const ctx = useQuery({
    queryKey: ['context', hospital, pathway], queryFn: () => api.context(hospital, pathway),
  })
  const dec = useQuery<Decision>({
    queryKey: ['decision', hospital, date], queryFn: () => api.decision(hospital, date), retry: false,
  })
  const cohort = useQuery({
    queryKey: ['cohort', hospital, date], queryFn: () => api.cohort(hospital, date),
  })
  const overrides = useQuery<Overrides>({
    queryKey: ['overrides', hospital, date],
    queryFn: () => api.overrides(hospital, date), retry: false,
  })

  const c = ops.data?.clinical?.[pathway]
  const row = cohort.data?.referrals.find((r) => r.pathway_number === pathway)
  const placed = dec.data?.rankings.find((r) => r.pathway_number === pathway)
  const refused = dec.data?.refused_paediatric.includes(pathway) ?? false
  const skipped = dec.data?.skipped.includes(pathway) ?? false

  const scores = useQuery({
    queryKey: ['scores', dec.data?.run_id, hospital], enabled: !!dec.data?.run_id,
    queryFn: () => api.scores(dec.data!.run_id, hospital),
  })

  if (cohort.isLoading || ops.isLoading) {
    return (
      <div className="pad">
        <button className="back" onClick={onBack}><ArrowLeft size={ICON_SM_PX} strokeWidth={STROKE} aria-hidden /> the list</button>
        <p className="muted">Reading the referral…</p>
      </div>
    )
  }
  if (!row) {
    return (
      <div className="pad">
        <button className="back" onClick={onBack}><ArrowLeft size={ICON_SM_PX} strokeWidth={STROKE} aria-hidden /> the list</button>
        <div className="notyet">
          <strong>{pathway} is not in this hospital-day.</strong>
          <p>The cohort for {dateLong(date)} does not contain this referral. Nothing below would
             be about the right person, so nothing is drawn.</p>
        </div>
      </div>
    )
  }

  const obs = ctx.data?.observations?.[0]
  const capacity = ctx.data?.capacity as CapacityContext | undefined
  const band = bandOf(row.cpc)
  // Reading age per pathway, for the neighbour comparison. Ages in this cohort
  // run from days to 871 days, so two equal-looking NEWS2 scores are routinely
  // not equal evidence.
  const ages: Record<string, number | null> = Object.fromEntries(
    Object.entries(ops.data?.clinical ?? {}).map(([pw, c]) => [pw, c.reading_age_days]))
  const wait = row.adjusted_wait_days ?? 0
  // Never 28 or 91 by hand: core.ref_codes is authoritative and the cohort's own
  // copy is only the fallback if the reference has not loaded yet.
  const target = crtDays(reference, row.cpc) ?? row.crt_threshold_days
  const overdueBy = target != null ? wait - target : null
  // How far past target, as a multiple. This bar used not to change colour AT
  // ALL when the wait went past the target: only the words underneath changed,
  // which on a referral 31x past its target is the least of the three channels
  // doing the work. 143 of the 308 have no target at all and score nothing.
  const waitRatio = target != null && target > 0 ? wait / target : null
  const waitSev = sevWaitRatio(waitRatio)

  // One citation per NEWS2 parameter, zeros included. The ranking row carries
  // them; GET /scores is the fallback for a decision served without them.
  const urgencyCites = placed?.urgency_citations
    ?? scores.data?.scores?.[pathway]?.urgency?.citations ?? []
  const cited = new Set(urgencyCites.map((x) => seg(x.evidence_key, 3) ?? ''))
  const capCites = placed?.capacity_citations
    ?? scores.data?.scores?.[pathway]?.capacity?.citations ?? []
  const citedWard = capCites.find((x) => x.evidence_type === 'bed_status')
    ? seg(capCites.find((x) => x.evidence_type === 'bed_status')!.evidence_key, 1) : null
  const citedSession = capCites.find((x) => x.evidence_type === 'clinic_session')
    ? seg(capCites.find((x) => x.evidence_type === 'clinic_session')!.evidence_key, 2) : null

  // The capacity score is a property of the specialty. Counted here, not claimed.
  const inSpecialty = dec.data?.rankings.filter((r) => r.specialty_hipe === row.specialty_hipe) ?? []
  const peers = placed
    ? {
        inSpecialty: inSpecialty.length,
        same: inSpecialty.filter((r) => r.capacity_score === placed.capacity_score).length,
      }
    : null

  const ovrRec = overrides.data?.current?.[pathway]
  const ageStats = (ops.data?.observation_age ?? undefined) as AgeStats | undefined

  const events: Event[] = [
    c?.referral_date ? { key: 'ref', date: c.referral_date, label: 'referred', detail: 'GP letter written' } : null,
    c?.referral_received_date ? { key: 'rec', date: c.referral_received_date, label: 'received by the hospital' } : null,
    c?.obs_datetime ? {
      key: 'obs', date: c.obs_datetime.slice(0, 10), label: 'vital signs taken', clinical: true,
      detail: `NEWS2 ${c.news2 ?? '—'} of 17${c.reading_age_days != null ? ` · ${fmt(c.reading_age_days)} days ago` : ''}`,
    } : null,
    c?.sent_for_triage_date ? { key: 'snt', date: c.sent_for_triage_date, label: 'sent for triage' } : null,
    c?.triage_date ? {
      key: 'tri', date: c.triage_date, label: `triaged ${band}`,
      detail: c.turnaround_days != null ? `${c.turnaround_days}-day turnaround` : undefined,
    } : null,
    // The target falls `target` days into the WAIT, and the wait is measured
    // from the date the referral was received -- not from the triage date. Built
    // from triage_date it landed days later than the header and the rule chip
    // said, and on five referrals it put the target in the future while the
    // header said the referral was already past it.
    c?.referral_received_date && target ? {
      key: 'tgt',
      date: new Date(new Date(c.referral_received_date).getTime() + target * 86_400_000)
        .toISOString().slice(0, 10),
      label: `${target}-day target`, target: true,
    } : null,
  ].filter(Boolean) as Event[]

  return (
    <div className="pad pt">
      <button className="back" onClick={onBack}><ArrowLeft size={ICON_SM_PX} strokeWidth={STROKE} aria-hidden /> the list</button>

      {/* 1: where this person is */}
      <header className="pt-head">
        <div className="pt-head-l">
          <span className="lab">Referral</span>
          <h1 className="num">{pathway}</h1>
          <div className="pt-head-facts">
            <span className={chipClass(band)}>{band}</span>
            <span className="pt-spec">{specialtyFull(reference, row.specialty_hipe)}</span>
            {placed && dec.data && (
              <span>position <strong className="num">{placed.position}</strong> of{' '}
                <span className="num">{fmt(dec.data.rankings.length)}</span></span>
            )}
            {refused && <span className="pt-flag">outside the ranking: paediatric</span>}
            {skipped && <span className="pt-flag">outside the ranking: no observation</span>}
            {ovrRec && (
              <span className="pt-ovr">
                overridden{ovrRec.from_position != null && ovrRec.to_position != null
                  ? <> · <span className="num">{ovrRec.from_position} → {ovrRec.to_position}</span></>
                  : null} · {ovrRec.clinician_id}
              </span>
            )}
          </div>
        </div>

        <div className="pt-head-r">
          <div className="pt-wait">
            <div className="pt-wait-n num">{fmt(wait)}</div>
            <div className="pt-wait-l">
              days waiting
              {target != null
                ? <> against a <span className="num">{target}</span>-day target</>
                : ', no target applies to this category'}
            </div>
            {target != null && (
              <>
                <div className="pt-wait-bar">
                  <SevBar sev={waitSev} height={7}
                          value={wait / Math.max(1, wait, target)}
                          of={target / Math.max(1, wait, target)}
                          label={`${fmt(wait)} days waited against a ${target} day target`} />
                </div>
                <div className="pt-wait-x num">
                  {overdueBy != null && overdueBy > 0
                    ? (
                      <SevChip sev={waitSev}>
                        past target by {fmt(overdueBy)} days
                        {/* The multiple only once it says something the day
                            count does not: under 2x it rounds to "1.0x" and
                            reads as "exactly at target", which is the opposite
                            of what the words beside it mean. */}
                        {waitRatio != null && waitSev >= 2 && <> · {waitRatio.toFixed(1)}&times; the target</>}
                      </SevChip>
                    )
                    : `${fmt(Math.abs(overdueBy ?? 0))} days of target left`}
                </div>
              </>
            )}
          </div>
          {placed && dec.data && (
            <button className="pg pt-act" onClick={() => setOvr(true)}>Accept or move…</button>
          )}
        </div>
      </header>

      {flash && <div className="flash" role="status" aria-live="polite" aria-atomic="true">{flash}</div>}

      {/* Eight of the 308 are fixtures the dataset track plants at fixed pathway
          numbers because the demo depends on them existing. Saying what each one
          is for turns the most obvious challenge ("why is there test data in
          your clinical list?") into the answer: each is a claim the system can
          be tested against, and the test that plants it is named. */}
      {plantedCase(pathway) && (
        <aside className="pt-planted">
          <span className="lab">Planted case · {plantedCase(pathway)!.what}</span>
          <p>{plantedCase(pathway)!.why}</p>
          <code className="num">{plantedCase(pathway)!.source}</code>
        </aside>
      )}

      {ovr && placed && dec.data && (
        <Override patient={placed} decision={dec.data}
                  onClose={() => setOvr(false)}
                  onDone={(m) => { setFlash(m); setOvr(false) }} />
      )}

      {ovrRec && (
        <div className="pt-ovr-note">
          <Info size={ICON_SM_PX} strokeWidth={STROKE} aria-hidden />
          <span>
            A clinician moved this referral on{' '}
            <span className="num">{new Date(ovrRec.created_at).toLocaleString('en-IE')}</span>:{' '}
            <strong>{ovrRec.reason}</strong>
            {ovrRec.rule_warning_accepted && ' (a category-boundary warning was accepted on the record)'}
            {'. '}The position below is the system's; the override is what stands.
          </span>
        </div>
      )}

      {/* 2: why that position */}
      {placed && dec.data
        ? <WhyHere placed={placed} decision={dec.data} reference={reference} ages={ages} compare={cmp}
                   onCompare={setCmp} onCloseCompare={() => setCmp(null)} />
        : <NotScoredYet refused={refused} skipped={skipped} error={dec.isError} />}

      {/* 3: what reached each agent */}
      <section className="p-sec">
        <h2 className="sec-h">What informed the agents
          <span className="sec-note">
            two agents, two worlds: six readings about this person, one ward and one clinic about
            the specialty
          </span>
        </h2>
        <AgentInputs
          obs={obs}
          recordedTotal={c?.news2 ?? obs?.news2 ?? null}
          agentTotal={dec.data?.news2?.[pathway] ?? null}
          when={c?.obs_datetime ?? obs?.obs_datetime ?? null}
          ageDays={c?.reading_age_days ?? null}
          stats={ageStats}
          cited={cited}
          applied={!refused}
          urgencyScore={placed?.urgency_score ?? null}
          capacityScore={placed?.capacity_score ?? null}
          capacityDetail={placed?.capacity_detail ?? null}
          capacity={capacity}
          citedWard={citedWard}
          citedSession={citedSession}
          specialty={specialtyFull(reference, row.specialty_hipe)}
          alpha={placed?.alpha ?? dec.data?.alpha ?? null}
          peers={peers}
        />
      </section>

      {/* 4: the shape of the wait */}
      {events.length > 0 && (
        <section className="p-sec">
          <h2 className="sec-h">The journey
            <span className="sec-note">recorded dates only, nothing here is computed</span></h2>
          {/* The axis's overdue span is the same fact as the header's bar, so
              it reads the same scale. Journey draws the span; the step comes
              down as a class on its root because the span's magnitude is the
              header's ratio, not something the axis can compute for itself. */}
          <Journey events={events} today={date}
                   className={'pt-journey' + (waitSev ? ` is-sev-${waitSev}` : '')}
                   waitDays={wait} targetDays={target} />
        </section>
      )}

      {/* 5: the chain. Cited where a run exists; on-record everywhere else.
             A view-only day used to render nothing here at all, which read as a
             missing feature rather than as the deliberate limit it is: evidence
             is date-blind, so only the newest day can honestly be ranked, but
             the referral and everything hanging off it exists on all 28. */}
      {dec.data && placed ? (
        <section className="p-sec">
          <h2 className="sec-h">The chain behind this position
            <span className="sec-note">assembled from the recorded citations</span></h2>
          <Provenance pathway={pathway} decision={dec.data} scores={scores.data?.scores} />
        </section>
      ) : ctx.data ? (
        <section className="p-sec">
          <h2 className="sec-h">What is on record
            <span className="sec-note">no agent has scored this day, so nothing here was cited</span></h2>
          <Provenance pathway={pathway} context={ctx.data} />
        </section>
      ) : null}

      {/* 6: the edge of the instrument */}
      <Limits pathway={pathway} clinical={c ?? null}
              news2={ops.data?.clinical} cohort={cohort.data?.referrals} />
    </div>
  )
}


/** Three fields that were on the record and did not enter the score, each
 *  carrying where it came from, and the one statistic that explains why the
 *  instrument cannot do the discriminating on its own. */
function Limits({ pathway, clinical, news2, cohort }: {
  pathway: string
  clinical: { pain: number | null; mts_category: string | null; icd10am_code: string | null } | null
  news2: Record<string, { news2: number | null }> | undefined
  cohort: Array<{ pathway_number: string; cpc: number | null }> | undefined
}) {
  // Counted from this hospital-day, never typed in as a sentence.
  const vals = Object.values(news2 ?? {}).map((x) => x.news2).filter((x): x is number => x != null)
  const low = vals.filter((v) => v <= 2).length
  const urgent = (cohort ?? []).filter((r) => r.cpc === 1)
  const urgentZero = urgent.filter((r) => news2?.[r.pathway_number]?.news2 === 0).length
  const mine = news2?.[pathway]?.news2 ?? null
  const buckets: number[] = []
  for (const v of vals) buckets[v] = (buckets[v] ?? 0) + 1
  const top = Math.max(1, ...buckets.filter((x) => x != null))
  const width = Math.max(buckets.length, 4)

  return (
    <section className="p-sec">
      <h2 className="sec-h">What the instrument could not see
        <span className="sec-note">on the record, and outside the score</span></h2>

      <div className="pt-chips">
        <LimitChip k="Pain" v={clinical?.pain != null ? `${clinical.pain} / 10` : null}
                   tag="not scored · ADR-004"
                   note="a patient-reported number NEWS2 has no parameter for" />
        <LimitChip k="Manchester triage" v={clinical?.mts_category ?? null}
                   tag="read but not scored · ADR-004"
                   note="MTS carries its own red/orange/yellow/green/blue vocabulary. Those are not this product's triage hues, so the category is shown as a word and nothing else." />
        <LimitChip k="Condition" v={clinical?.icd10am_code ?? null}
                   tag="record field · not evidence"
                   note="in this dataset the code is a weighted random draw over the specialty's case mix, statistically independent of acuity. It is never styled as a finding, and no code dictionary ships with this page." />
      </div>

      {vals.length > 0 && (
        <div className="pt-dist">
          <div className="pt-dist-h">
            <span className="lab">Every NEWS2 in this hospital-day</span>
            <span className="pt-dist-n num">{fmt(vals.length)} referrals</span>
          </div>
          <div className="pt-hist" role="img"
               aria-label={`NEWS2 distribution: ${low} of ${vals.length} referrals score 2 or below`}>
            {Array.from({ length: width }, (_, v) => {
              const n = buckets[v] ?? 0
              return (
                <div key={v} className={'pt-bar' + (v <= 2 ? ' is-low' : '') + (v === mine ? ' is-mine' : '')}>
                  <span className="pt-bar-n num">{n || ''}</span>
                  <span className="pt-bar-box"><i style={{ height: `${(n / top) * 100}%` }} /></span>
                  <span className="pt-bar-v num">{v}</span>
                </div>
              )
            })}
          </div>
          <div className="pt-dist-facts">
            <span className="pt-stat">
              <strong className="num">{fmt(low)}</strong> of <span className="num">{fmt(vals.length)}</span>
              {' '}<span className="pt-stat-pct num">({Math.round((low / vals.length) * 100)}%)</span>
              {' '}score 2 or below
            </span>
            <span className="pt-stat">
              <strong className="num">{fmt(urgentZero)}</strong> of the{' '}
              <span className="num">{fmt(urgent.length)}</span> marked Urgent score{' '}
              <span className="num">0</span>
            </span>
            {mine != null && (
              <span className="pt-stat is-mine">
                this referral scores <strong className="num">{mine}</strong>
              </span>
            )}
          </div>
          <p className="p-note">
            Six parameters cannot separate a cohort sitting almost entirely at the bottom of the
            scale, so waiting time does the discriminating.
          </p>
        </div>
      )}
    </section>
  )
}

function LimitChip({ k, v, tag, note }: { k: string; v: string | null; tag: string; note: string }) {
  return (
    <div className="pt-chip">
      <div className="pt-chip-h">
        <span className="lab">{k}</span>
        <span className="pt-chip-tag">{tag}</span>
      </div>
      <div className="pt-chip-v">{v ?? <span className="pt-flag">not recorded</span>}</div>
      <p className="pt-mini">{note}</p>
    </div>
  )
}


/** Why this person sits here, as arithmetic rather than assertion.
 *
 *  The order inside a band is (past target first, then priority), and priority
 *  is alpha*urgency + (1-alpha)*wait-percentile. Both facts are shown, because
 *  showing only the blend contradicts the rows either side of a tier boundary.
 *
 *  The rule checks the coordinator recorded now travel with it: every one keeps
 *  its ID so it can be found in core.ref_rules, and its statement comes from the
 *  reference layer rather than from a string in this file.
 */
function WhyHere({ placed, decision, reference, ages, compare, onCompare, onCloseCompare }: {
  placed: Ranking; decision: Decision; reference: Reference | undefined
  /** Reading age per pathway, so a neighbour comparison cannot present two
   *  single readings of very different ages as equivalent evidence. */
  ages?: Record<string, number | null>
  compare: 'above' | 'below' | null
  onCompare: (w: 'above' | 'below') => void
  onCloseCompare: () => void
}) {
  const a = placed.alpha
  const uTerm = a * placed.urgency_score
  const wTerm = (1 - a) * placed.wait_normalised
  const band = bandOf(placed.cpc)
  const inBand = decision.rankings.filter((r) => bandOf(r.cpc) === band)
  const idx = inBand.findIndex((r) => r.pathway_number === placed.pathway_number)
  const above = idx > 0 ? inBand[idx - 1] : undefined
  const below = idx >= 0 && idx < inBand.length - 1 ? inBand[idx + 1] : undefined
  const checks: RuleCheck[] = placed.rule_checks ?? []
  const breaches = failed(checks)

  return (
    <section className="p-sec">
      <h2 className="sec-h">Why this position
        <span className="sec-note">the same arithmetic the coordinator used</span></h2>

      <div className="why-tier">
        {placed.crt_breached === true
          ? <><strong>Already past target.</strong> Inside {band}, everyone past their target is
              placed before everyone still within it. That tier is decided before any score.</>
          : placed.crt_threshold_days == null
            ? <><strong>No target applies</strong> to {band}, so only the score below orders this group.</>
            : <><strong>Still within target.</strong> Inside {band}, everyone already past their
              target is placed above this point, whatever their score.</>}
      </div>

      <div className="why-sum">
        <div className="why-row">
          <span className="why-k">how unwell</span>
          <span className="why-b"><i style={{ width: `${uTerm * 100}%` }} /></span>
          <span className="why-v num">{n3(a)} &times; {n3(placed.urgency_score)} = {n3(uTerm)}</span>
        </div>
        <div className="why-row">
          <span className="why-k">how long waited</span>
          <span className="why-b"><i className="is-wait" style={{ width: `${wTerm * 100}%` }} /></span>
          <span className="why-v num">{n3(1 - a)} &times; {n3(placed.wait_normalised)} = {n3(wTerm)}</span>
        </div>
        <div className="why-row is-total">
          <span className="why-k">priority</span>
          <span className="why-b" />
          <span className="why-v num">{n3(placed.priority)}
            {/* The two terms above are each rounded to 3 d.p., so on 38 of 305
                rows they do not visibly add to this figure -- always by 0.001.
                Priority is the ranking key and is shown exactly; the note says
                which of the three is the rounded one rather than leaving a
                reader to find an arithmetic error that is not there. */}
            {Math.abs(Math.round(uTerm * 1000) / 1000 + Math.round(wTerm * 1000) / 1000
                      - Math.round(placed.priority * 1000) / 1000) > 1e-9 && (
              <span className="why-round">the two terms are rounded; this is exact</span>
            )}</span>
        </div>
      </div>

      <p className="p-note">
        Waiting time is a percentile <em>within this category</em>, not a raw day count, so one
        very long waiter cannot flatten everyone else. The {Math.round(a * 100)}/{Math.round((1 - a) * 100)}{' '}
        split is set once for the whole hospital-day from how pressured its specialties are. It
        is the same number for all {fmt(decision.rankings.length)} people here and cannot move
        anyone between categories.
      </p>

      {checks.length > 0 && (
        <div className="pt-checks">
          <div className="pt-checks-h">
            <span className="lab">Rules tested on this referral</span>
            <span className="pt-checks-n num">
              {checks.length} checked · {breaches.length} breached
            </span>
          </div>
          {checks.map((ch) => (
            <div key={ch.rule_id} className="pt-check" data-passed={ch.passed ? 'yes' : 'no'}
                 aria-label={checkLabel(ch)}>
              <span className="pt-check-id num">{ch.rule_id}</span>
              <span className="pt-check-st">{ruleStatement(reference, ch.rule_id)}</span>
              <span className="pt-check-d num">{ch.detail ?? '—'}</span>
              {/* The only one of four verdict registers in the product with no
                  icon, and a breach carried by a 1px inset hairline. Now the
                  same word, the same icon and the severity a breach gets
                  everywhere else. */}
              <span className={'pt-verdict' + (ch.passed ? ' is-ok' : '')}>
                {ch.passed
                  ? <><Check size={V_ICON} strokeWidth={2.5} aria-hidden />holds</>
                  : (
                    <SevChip sev={sevBreach(false)}>
                      <TriangleAlert size={V_ICON} strokeWidth={2.25} aria-hidden />breached
                    </SevChip>
                  )}
              </span>
            </div>
          ))}
        </div>
      )}

      {placed.rationale_summary && (
        <div className="pt-rationale">
          <span className="lab">Coordinator's note</span>
          <p>{placed.rationale_summary}</p>
          <span className="pt-mini">
            Written by <code>coordinator</code> from the numbers above. Deterministic: no model
            wrote this sentence.
          </span>
        </div>
      )}

      {(above || below) && (
        <div className="why-neighbours">
          {above && <NeighbourRow r={above} label="above" onCompare={() => onCompare('above')} />}
          {above && <WhatSeparates a={above} b={placed} alpha={decision.alpha} />}
          <NeighbourRow r={placed} label="this patient" self />
          {below && <WhatSeparates a={placed} b={below} alpha={decision.alpha} />}
          {below && <NeighbourRow r={below} label="below" onCompare={() => onCompare('below')} />}
        </div>
      )}

      {compare === 'above' && above && (
        <Compare a={above} b={placed} decision={decision} ages={ages} onClose={onCloseCompare} />
      )}
      {compare === 'below' && below && (
        <Compare a={placed} b={below} decision={decision} ages={ages} onClose={onCloseCompare} />
      )}
    </section>
  )
}

function NeighbourRow({ r, label, self, onCompare }: {
  r: Ranking; label: string; self?: boolean; onCompare?: () => void
}) {
  return (
    <div className={'nb' + (self ? ' is-self' : '')}>
      <span className="nb-l">{label}</span>
      <span className="nb-p num">{r.position}</span>
      <span className="nb-id num">{r.pathway_number}</span>
      <span className="nb-w num">{fmt(r.adjusted_wait_days ?? 0)}d</span>
      <span className="nb-t">{r.crt_breached === true ? 'past target' : r.crt_threshold_days == null ? 'no target' : 'within target'}</span>
      <span className="nb-s num">priority {n3(r.priority)}</span>
      {onCompare
        ? <button className="nb-cmp" onClick={onCompare}>why?</button>
        : <span />}
    </div>
  )
}


/** The honest empty states. Three of them, and they are different things.
 *
 *  A paediatric refusal is a coverage statement. A skip is a data-quality
 *  incident. No decision at all is a day nobody has run. Collapsing them into
 *  one "unavailable" loses the difference that matters most to a reviewer.
 */
function NotScoredYet({ refused, skipped, error }: {
  refused: boolean; skipped: boolean; error: boolean
}) {
  return (
    <section className="p-sec">
      <div className="notyet">
        <strong>
          {refused ? 'Not scored, and not placed: paediatric.'
            : skipped ? 'Not scored: no observation to read.'
              : error ? 'No agent has scored this hospital-day.'
                : 'No position yet.'}
        </strong>
        <p>
          {refused
            ? 'NEWS2 is validated in adults, so the urgency agent refuses paediatric specialties rather than scoring a child on an adult scale. That is a statement about what this system covers, not a low position. Everything else on this page was recorded by a clinician and is unaffected.'
            : skipped
              ? 'The urgency agent found no observation on this referral. NEWS2 needs six readings and there were none, so nothing was scored. A missing measurement is a data-quality incident and is never shown as a low score.'
              : 'Everything else here was recorded by a clinician and is unaffected. There is no position, no priority arithmetic and no citation chain, because nothing has been computed for this day. Runs happen on the newest day holding data.'}
        </p>
      </div>
    </section>
  )
}
