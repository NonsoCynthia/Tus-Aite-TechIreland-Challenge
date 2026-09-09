import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api, bandOf } from '../lib/api'
import { Journey, type Event } from '../components/Journey'
import { Provenance } from '../components/Provenance'
import { Override } from '../components/Override'
import { Compare } from '../components/Compare'
import type { Decision, Ranking } from '../lib/types'

const fmt = (n: number) => n.toLocaleString('en-IE')
const VITAL = {
  rr: 'Respiratory rate', spo2: 'Oxygen saturation', sbp: 'Systolic BP',
  hr: 'Heart rate', avpu: 'Consciousness', temp: 'Temperature',
} as const
const UNIT: Record<string, string> = { rr: '/min', spo2: '%', sbp: ' mmHg', hr: ' bpm', temp: '°C' }
/** ICD-10-AM is not in the data as prose: core.conditions.condition_label holds
 *  the placeholder "Condition C43.9". Anything readable is a UI-side lookup and
 *  is labelled as one. */
const ICD: Record<string, string> = {
  'C43.9': 'Malignant melanoma of skin, unspecified',
}

export function Patient({ hospital, date, pathway, onBack }: {
  hospital: string; date: string; pathway: string; onBack: () => void
}) {
  const [ovr, setOvr] = useState(false)
  const [cmp, setCmp] = useState<'above' | 'below' | null>(null)
  const [flash, setFlash] = useState<string | null>(null)
  const ops = useQuery({ queryKey: ['operations', hospital, date], queryFn: () => api.operations(hospital, date), staleTime: Infinity })
  const ctx = useQuery({ queryKey: ['context', hospital, pathway], queryFn: () => api.context(hospital, pathway) })
  const dec = useQuery<Decision>({ queryKey: ['decision', hospital, date], queryFn: () => api.decision(hospital, date), retry: false })
  const cohort = useQuery({ queryKey: ['cohort', hospital, date], queryFn: () => api.cohort(hospital, date) })

  const c = ops.data?.clinical?.[pathway]
  const row = cohort.data?.referrals.find((r) => r.pathway_number === pathway)
  const placed = dec.data?.rankings.find((r) => r.pathway_number === pathway)
  const refused = dec.data?.refused_paediatric.includes(pathway)
  const scores = useQuery({
    queryKey: ['scores', dec.data?.run_id, hospital], enabled: !!dec.data?.run_id,
    queryFn: () => api.scores(dec.data!.run_id, hospital),
  })
  const cited = new Set(
    (scores.data?.scores?.[pathway]?.urgency?.citations ?? [])
      .map((x) => x.evidence_key.split('/').pop() ?? ''))

  if (!c || !row) return <div className="pad"><p className="muted">Loading…</p></div>

  const obs = ctx.data?.observations?.[0]
  const band = bandOf(row.cpc)
  const wait = row.adjusted_wait_days ?? 0
  const target = row.crt_threshold_days

  const events: Event[] = [
    { key: 'ref', date: c.referral_date!, label: 'referred', detail: 'GP letter written' },
    { key: 'rec', date: c.referral_received_date!, label: 'received by the hospital' },
    c.obs_datetime ? { key: 'obs', date: c.obs_datetime.slice(0, 10), label: 'vital signs taken', clinical: true, detail: `NEWS2 ${c.news2 ?? '—'}` } : null,
    c.sent_for_triage_date ? { key: 'snt', date: c.sent_for_triage_date, label: 'sent for triage' } : null,
    c.triage_date ? { key: 'tri', date: c.triage_date, label: `triaged ${band}`, detail: c.turnaround_days != null ? `${c.turnaround_days}-day turnaround` : undefined } : null,
    c.triage_date && target ? {
      key: 'tgt',
      date: new Date(new Date(c.triage_date).getTime() + target * 86_400_000).toISOString().slice(0, 10),
      label: `${target}-day target`, target: true,
    } : null,
  ].filter(Boolean) as Event[]

  return (
    <div className="pad">
      <button className="back" onClick={onBack}>&larr; the list</button>

      <div className="p-head">
        <div>
          <h1 className="num">{pathway}</h1>
          <div className="p-sub">
            <span className={'chip cat-' + band.toLowerCase().replace('-', '')}>{band}</span>
            <span className="muted">specialty {row.specialty_hipe}</span>
            {placed && <span className="muted">position <strong className="num">{placed.position}</strong> of {dec.data!.rankings.length}</span>}
            {refused && <span className="muted">outside the ranking &mdash; paediatric</span>}
          </div>
        </div>
        <div className="p-actions">
          {placed && dec.data && (
            <button className="pg" onClick={() => setOvr(true)}>Accept or move&hellip;</button>
          )}
        </div>
        <div className="p-wait">
          <div className="p-wait-n num">{fmt(wait)}</div>
          <div className="p-wait-l">
            days waiting{target ? <> against a <span className="num">{target}</span>-day target</> : ', no target applies'}
          </div>
        </div>
      </div>

      {flash && <div className="flash">{flash}</div>}

      {ovr && placed && dec.data && (
        <Override patient={placed} decision={dec.data}
                  onClose={() => setOvr(false)}
                  onDone={(m) => { setFlash(m); setOvr(false) }} />
      )}

      <Journey events={events} today={date} />

      {placed && dec.data
        ? <WhyHere placed={placed} decision={dec.data} compare={cmp}
                   onCompare={setCmp} onCloseCompare={() => setCmp(null)} />
        : <NotScoredYet refused={!!refused} />}

      <section className="p-sec">
        <h2 className="sec-h">What the score read
          <span className="sec-note">six vital signs, measured once</span></h2>
        <div className="vitals">
          {(Object.keys(VITAL) as Array<keyof typeof VITAL>).map((k) => {
            const v = obs?.[k as keyof typeof obs]
            return (
              <div key={k} className={'vital' + (cited.has(k) ? ' is-cited' : '')}>
                <div className="vital-k">{VITAL[k]}</div>
                <div className="vital-v num">{v ?? '—'}{v != null && UNIT[k] ? UNIT[k] : ''}</div>
              </div>
            )
          })}
        </div>
        <p className="p-note">
          NEWS2 <strong className="num">{c.news2 ?? '—'} of 17</strong>. Add the six by hand and
          you get the same number. {cited.size > 0 && <>All {cited.size} were cited by the agent.</>}
        </p>
      </section>

      {dec.data && placed && (
        <section className="p-sec">
          <h2 className="sec-h">The chain behind this position
            <span className="sec-note">assembled from the recorded citations</span></h2>
          <Provenance pathway={pathway} decision={dec.data} scores={scores.data?.scores} />
        </section>
      )}

      <section className="p-sec">
        <h2 className="sec-h">What it did not read</h2>
        <div className="notread">
          {c.pain != null && <span className="chip-x">Pain <strong className="num">{c.pain}</strong>/10</span>}
          {c.mts_category && <span className="chip-x">Manchester triage <strong>{c.mts_category}</strong></span>}
          {c.icd10am_code && <span className="chip-x">Condition <strong className="num">{c.icd10am_code}</strong></span>}
        </div>
        <div className="warn">
          A score of <strong className="num">{c.news2 ?? '—'}</strong> means those six vital signs
          were near normal on {new Date(c.obs_datetime!).toLocaleDateString('en-IE', { day: 'numeric', month: 'long', year: 'numeric' })}.
          It does not mean this person is near normal now.
        </div>
        {c.icd10am_code && (
          <p className="p-note">
            {ICD[c.icd10am_code] && <><strong>{c.icd10am_code}</strong> is {ICD[c.icd10am_code]} —{' '}
            <em>a UI-side lookup, not data.</em> </>}
            In this dataset the condition code is a weighted random draw over the specialty's
            case mix, statistically independent of how unwell someone is. It is a record field,
            never evidence.
          </p>
        )}
      </section>
    </div>
  )
}


/** Why this person sits here, as arithmetic rather than assertion.
 *
 *  The order inside a band is (past target first, then priority), and priority
 *  is alpha*urgency + (1-alpha)*wait-percentile. Both facts are shown, because
 *  showing only the blend contradicts the rows either side of a tier boundary.
 */
function WhyHere({ placed, decision, compare, onCompare, onCloseCompare }: {
  placed: Ranking; decision: Decision
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
  const n = (x: number) => x.toFixed(3)

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
          <span className="why-v num">{n(a)} &times; {n(placed.urgency_score)} = {n(uTerm)}</span>
        </div>
        <div className="why-row">
          <span className="why-k">how long waited</span>
          <span className="why-b"><i className="is-wait" style={{ width: `${wTerm * 100}%` }} /></span>
          <span className="why-v num">{n(1 - a)} &times; {n(placed.wait_normalised)} = {n(wTerm)}</span>
        </div>
        <div className="why-row is-total">
          <span className="why-k">priority</span>
          <span className="why-b" />
          <span className="why-v num">{n(placed.priority)}</span>
        </div>
      </div>

      <p className="p-note">
        Waiting time is a percentile <em>within this category</em>, not a raw day count, so one
        very long waiter cannot flatten everyone else. The {Math.round(a * 100)}/{Math.round((1 - a) * 100)}{' '}
        split is set once for the whole hospital-day from how pressured its specialties are —
        it is the same number for all {decision.rankings.length} people here and cannot move
        anyone between categories.
      </p>

      {(above || below) && (
        <div className="why-neighbours">
          {above && <NeighbourRow r={above} label="above" onCompare={() => onCompare('above')} />}
          <NeighbourRow r={placed} label="this patient" self />
          {below && <NeighbourRow r={below} label="below" onCompare={() => onCompare('below')} />}
        </div>
      )}

      {compare === 'above' && above && (
        <Compare a={above} b={placed} decision={decision} onClose={onCloseCompare} />
      )}
      {compare === 'below' && below && (
        <Compare a={placed} b={below} decision={decision} onClose={onCloseCompare} />
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
      <span className="nb-w num">{(r.adjusted_wait_days ?? 0).toLocaleString('en-IE')}d</span>
      <span className="nb-t">{r.crt_breached === true ? 'past target' : r.crt_threshold_days == null ? 'no target' : 'within target'}</span>
      <span className="nb-s num">priority {r.priority.toFixed(3)}</span>
      {onCompare
        ? <button className="nb-cmp" onClick={onCompare}>why?</button>
        : <span />}
    </div>
  )
}


/** The honest empty state for a day no agent has scored.
 *
 *  Three sections disappear without it -- position, arithmetic, provenance --
 *  and a page that silently shrinks reads as broken rather than as "nothing has
 *  happened here yet". The clinician-recorded facts above are still true and
 *  still shown; only the computed layer is absent.
 */
function NotScoredYet({ refused }: { refused: boolean }) {
  return (
    <section className="p-sec">
      <div className="notyet">
        <strong>
          {refused
            ? 'Not scored, and not placed.'
            : 'No agent has scored this hospital-day.'}
        </strong>
        <p>
          {refused
            ? 'NEWS2 is validated in adults, so the urgency agent refuses paediatric specialties rather than scoring a child on an adult scale. That is a statement about what this system covers, not a low position.'
            : 'Everything above was recorded by a clinician and is unaffected. There is no position, no priority arithmetic and no citation chain, because nothing has been computed for this day. Runs happen on the newest day holding data.'}
        </p>
      </div>
    </section>
  )
}
