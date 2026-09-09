import { useQuery } from '@tanstack/react-query'
import { api, bandOf } from '../lib/api'
import { Journey, type Event } from '../components/Journey'
import { Provenance } from '../components/Provenance'
import type { Decision } from '../lib/types'

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
        <div className="p-wait">
          <div className="p-wait-n num">{fmt(wait)}</div>
          <div className="p-wait-l">
            days waiting{target ? <> against a <span className="num">{target}</span>-day target</> : ', no target applies'}
          </div>
        </div>
      </div>

      <Journey events={events} today={date} />

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

      {dec.data && (
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
