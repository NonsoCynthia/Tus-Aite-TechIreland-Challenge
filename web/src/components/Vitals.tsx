import { Activity, Brain, Droplet, HeartPulse, Thermometer, TriangleAlert, Wind } from 'lucide-react'
import { VITALS, positionOf, scoreOf, type Band, type Vital } from '../lib/news2'
import type { Observation } from '../lib/types'

/** NEWS2 as six instruments, not as a sentence.
 *
 *  The page used to print "NEWS2 7 of 17. Add the six by hand and you get the
 *  same number." That is a note asking the reader to do arithmetic. Here the
 *  arithmetic IS the picture: every parameter shows its own sub-score and where
 *  the reading sits on the band table in lib/news2.ts -- the same table the
 *  urgency agent scored against -- and the six sub-scores are summed on screen
 *  and CHECKED against the recorded total. A disagreement is printed, never
 *  hidden behind whichever number happened to be handy.
 *
 *  Sub-scores are weighted in ink, never in --cat-* : those five hues belong to
 *  CPC triage categories and a NEWS2 sub-score of 3 is not a triage category.
 *  The magnitude therefore travels three ways at once -- the numeral, three
 *  pips, and the ink weight -- so colour is never load-bearing on its own.
 */

const ICON: Record<Vital['key'], typeof Activity> = {
  rr: Wind, spo2: Droplet, sbp: Activity, hr: HeartPulse, avpu: Brain, temp: Thermometer,
}

/** core.observations returns temp as a string and spo2 as a number. Both are
 *  readings; neither is trusted to arrive as one type. */
const num = (v: unknown): number | null => {
  if (v == null || v === '') return null
  const n = typeof v === 'number' ? v : parseFloat(String(v))
  return Number.isNaN(n) ? null : n
}
const fmtN = (n: number) => n.toLocaleString('en-IE')
const unitOf = (u: string) =>
  u === '' ? '' : u === '%' || u.startsWith('/') || u.startsWith('°') ? u : ` ${u}`
const dateLong = (s: string) =>
  new Date(s).toLocaleDateString('en-IE', { day: 'numeric', month: 'long', year: 'numeric' })

/** Where each band sits on the meter. The table's edges are inclusive integers
 *  (... 8 | 9 ...), so the drawn boundary is the midpoint between them: any
 *  other choice either overlaps the segments or opens a gap the scale does not
 *  have. */
function spans(v: Vital) {
  const [lo, hi] = v.axis
  return v.bands.map((b, i) => {
    const prev: Band | undefined = v.bands[i - 1]
    const next: Band | undefined = v.bands[i + 1]
    const from = prev ? ((prev.hi ?? lo) + (b.lo ?? lo)) / 2 : lo
    const to = next ? ((b.hi ?? hi) + (next.lo ?? hi)) / 2 : hi
    return { score: b.score, lo: b.lo, hi: b.hi, from: positionOf(v, from), to: positionOf(v, to) }
  })
}

const bandLabel = (b: { lo: number | null; hi: number | null }, unit: string) => {
  const u = unitOf(unit)
  if (b.lo == null) return `≤ ${b.hi}${u}`
  if (b.hi == null) return `≥ ${b.lo}${u}`
  return `${b.lo}–${b.hi}${u}`
}

/** Which band a reading landed in, for the caption under the meter. */
const bandFor = (v: Vital, value: number) =>
  v.bands.find((b) => (b.lo == null || value >= b.lo) && (b.hi == null || value <= b.hi))

/** Age of a reading, as a state rather than as an opinion about the patient. */
export const ageState = (days: number | null): { key: string; word: string } => {
  if (days == null) return { key: 'unknown', word: 'age unknown' }
  if (days <= 30) return { key: 'fresh', word: 'fresh' }
  if (days <= 90) return { key: 'recent', word: 'recent' }
  if (days <= 365) return { key: 'stale', word: 'stale' }
  return { key: 'very', word: 'over a year old' }
}

export interface AgeStats { n: number; median: number; mean: number; max: number; over_1y: number; over_2y: number }

/** The staleness meter, drawn on the reading itself.
 *
 *  Invariant: a stale normal reading is an ABSENCE of information, not
 *  reassurance -- so the age never travels separately from the reading, and the
 *  meter draws this reading's age against the real spread of ages in this
 *  cohort rather than against a round number nobody chose. */
export function Staleness({ when, ageDays, stats }: {
  when: string | null; ageDays: number | null; stats: AgeStats | undefined
}) {
  const st = ageState(ageDays)
  const max = stats?.max ?? null
  const pct = (d: number) => (max && max > 0 ? Math.max(0, Math.min(100, (d / max) * 100)) : 0)

  return (
    <div className="pt-stale">
      <div className="pt-stale-head">
        <span className="lab">Measured</span>
        <span className="pt-stale-when">{when ? dateLong(when) : 'no reading recorded'}</span>
        {ageDays != null && (
          <>
            <span className="pt-stale-age num">{fmtN(ageDays)} days ago</span>
            <span className="pt-stale-state" data-age={st.key}>{st.word}</span>
          </>
        )}
      </div>

      {ageDays != null && max != null && max > 0 ? (
        <>
          <div className="pt-stale-track" role="img"
               aria-label={`${fmtN(ageDays)} days old, against a cohort median of ${fmtN(stats!.median)} and an oldest reading of ${fmtN(max)} days`}>
            <i className="pt-stale-fill" style={{ width: `${pct(ageDays)}%` }} />
            <span className="pt-stale-med" style={{ left: `${pct(stats!.median)}%` }} />
          </div>
          <div className="pt-stale-scale num">
            <span>today</span>
            <span className="pt-stale-med-l">cohort median {fmtN(stats!.median)}d</span>
            <span>oldest here {fmtN(max)}d</span>
          </div>
        </>
      ) : (
        <p className="pt-mini">No cohort age distribution to draw this against.</p>
      )}

      <p className="pt-mini">
        The six readings below are the state of this person on{' '}
        {when ? dateLong(when) : 'the date above'}. Nothing has been measured since.
      </p>
    </div>
  )
}

export function Vitals({ obs, recordedTotal, agentTotal, when, ageDays, stats, cited, applied }: {
  obs: Observation | undefined
  /** core.observations.news2 for this reading. Present whether or not an agent ran. */
  recordedTotal: number | null
  /** What the urgency agent harvested, when there is a decision. Compared, not merged. */
  agentTotal: number | null
  when: string | null
  ageDays: number | null
  stats: AgeStats | undefined
  /** Leaf of each urgency citation: rr, spo2, sbp, hr, avpu, temp. */
  cited: Set<string>
  /** False for a paediatric refusal: the bands are drawn, the scale is not applied. */
  applied: boolean
}) {
  const rows = VITALS.map((v) => {
    const raw = obs ? (obs as unknown as Record<string, unknown>)[v.key] : null
    const score = scoreOf(v.key, raw as number | string | null)
    return { v, raw, score }
  })
  const present = rows.filter((r) => r.score != null)
  const computed = present.reduce((a, r) => a + (r.score ?? 0), 0)
  const complete = present.length === VITALS.length
  const disagrees = complete && recordedTotal != null && computed !== recordedTotal
  // With no scoring pass there is nothing to have been cited, and stamping six
  // cards "not cited" would read as an omission rather than as an absent run.
  const showCites = cited.size > 0
  const agentDiffers = agentTotal != null && recordedTotal != null && agentTotal !== recordedTotal

  if (!obs) {
    return (
      <div className="pt-novitals">
        <TriangleAlert size={15} aria-hidden />
        <div>
          <strong>No observation on this referral.</strong>
          <p>
            NEWS2 needs six readings and there are none, so the urgency agent had nothing to
            score. That is a data-quality gap, not a low score — the two are different states and
            are never merged here.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="pt-vitals">
      <Staleness when={when} ageDays={ageDays} stats={stats} />

      <div className="pt-cards">
        {rows.map(({ v, raw, score }) =>
          v.key === 'avpu'
            ? <AvpuCard key={v.key} v={v} value={raw == null ? null : String(raw)}
                        score={score} cited={!showCites || cited.has(v.key)} applied={applied} />
            : <VitalCard key={v.key} v={v} value={num(raw)} score={score}
                         cited={!showCites || cited.has(v.key)} applied={applied} />)}
      </div>

      <div className="pt-sum" data-applied={applied ? 'yes' : 'no'}>
        <span className="lab">{applied ? 'NEWS2' : 'NEWS2 · not applied'}</span>
        <span className="pt-eq num">
          {rows.map(({ v, score }, i) => (
            <span key={v.key}>
              {i > 0 && <span className="pt-eq-op"> + </span>}
              <span className="pt-eq-t" title={v.label}>{score ?? '—'}</span>
            </span>
          ))}
        </span>
        <span className="pt-eq-op">=</span>
        <span className="pt-total num">{complete ? computed : '—'}</span>
        <span className="pt-of">of 17</span>
        {!complete && (
          <span className="pt-sum-note">
            {present.length} of 6 readings present — the six do not sum to a total
          </span>
        )}
      </div>

      {disagrees && (
        <p className="pt-disc">
          <TriangleAlert size={14} aria-hidden />
          <span>
            <strong>These do not agree.</strong> The six sub-scores above add to{' '}
            <strong className="num">{computed}</strong>; the record carries{' '}
            <strong className="num">{recordedTotal}</strong>. Neither is shown as the answer.
            The band table in <code>lib/news2.ts</code> or the recorded total has moved.
          </span>
        </p>
      )}
      {!disagrees && complete && recordedTotal != null && (
        <p className="pt-mini">
          Checked: the six sub-scores add to the recorded total,{' '}
          <span className="num">{recordedTotal}</span>.
        </p>
      )}
      {agentDiffers && (
        <p className="pt-disc">
          <TriangleAlert size={14} aria-hidden />
          <span>
            The urgency agent harvested <strong className="num">{agentTotal}</strong> where the
            observation record carries <strong className="num">{recordedTotal}</strong>.
          </span>
        </p>
      )}
      {!applied && (
        <p className="pt-mini">
          The bands are drawn so you can see what was declined. NEWS2 is validated in adults and
          the agent refused to run it, so no sub-score above was used by anything.
        </p>
      )}
    </div>
  )
}

function Pips({ score }: { score: number | null }) {
  return (
    <span className="pt-pips" aria-hidden>
      {[0, 1, 2].map((i) => <i key={i} className={score != null && i < score ? 'is-on' : ''} />)}
    </span>
  )
}

function SubScore({ score, applied }: { score: number | null; applied: boolean }) {
  return (
    <span className="pt-sub" data-score={score ?? 'none'} data-applied={applied ? 'yes' : 'no'}>
      <span className="pt-sub-n num">{score == null ? '—' : score}</span>
      <Pips score={score} />
    </span>
  )
}

function VitalCard({ v, value, score, cited, applied }: {
  v: Vital; value: number | null; score: number | null; cited: boolean; applied: boolean
}) {
  const Icon = ICON[v.key]
  const seg = spans(v)
  const band = value == null ? undefined : bandFor(v, value)
  const pos = value == null ? null : positionOf(v, value) * 100
  const offAxis = value != null && (value < v.axis[0] || value > v.axis[1])
  const u = unitOf(v.unit)
  const nLo = positionOf(v, v.zeroBand[0]) * 100
  const nHi = positionOf(v, v.zeroBand[1]) * 100

  return (
    <div className="pt-card">
      <div className="pt-card-h">
        <Icon size={14} aria-hidden />
        <span className="lab">{v.short}</span>
        <SubScore score={score} applied={applied} />
      </div>
      <div className="pt-read num">
        {value == null ? '—' : value}<span className="pt-unit">{u}</span>
      </div>

      <div className="pt-meter" role="img"
           aria-label={value == null
             ? `${v.label}: no reading`
             : `${v.label} ${value}${u}, ${band ? bandLabel(band, v.unit) : 'off scale'}, scores ${score ?? '—'} of 3`}>
        <div className="pt-track">
          {seg.map((s, i) => (
            <i key={i} data-score={s.score}
               style={{ left: `${s.from * 100}%`, width: `${(s.to - s.from) * 100}%` }}
               title={`${bandLabel(s, v.unit)} scores ${s.score}`} />
          ))}
        </div>
        <span className="pt-zero" style={{ left: `${nLo}%`, width: `${nHi - nLo}%` }} aria-hidden />
        {pos != null && (
          <span className={'pt-pin' + (offAxis ? ' is-off' : '')} style={{ left: `${pos}%` }} aria-hidden />
        )}
      </div>

      <div className="pt-axis num">
        <span>{v.axis[0]}</span>
        <span className="pt-zero-l">{v.zeroBand[0]}–{v.zeroBand[1]}{u} scores 0</span>
        <span>{v.axis[1]}</span>
      </div>

      <div className="pt-caption">
        {value == null
          ? <span className="pt-flag">not recorded</span>
          : band
            ? <>lands in <span className="num">{bandLabel(band, v.unit)}</span>, which scores{' '}
                <span className="num">{band.score}</span></>
            : <span className="pt-flag">off the drawn scale — the reading is printed above in full</span>}
        {!cited && <span className="pt-flag pt-flag-cite">not cited</span>}
      </div>
    </div>
  )
}

/** AVPU has no axis: it is Alert or it is not. Drawing a meter across two
 *  categories would invent a continuum the instrument does not have. */
function AvpuCard({ v, value, score, cited, applied }: {
  v: Vital; value: string | null; score: number | null; cited: boolean; applied: boolean
}) {
  const Icon = ICON[v.key]
  const alert = value != null && value.toUpperCase() === 'A'
  const WORD: Record<string, string> = { A: 'Alert', V: 'Voice', P: 'Pain', U: 'Unresponsive' }
  const word = value == null ? null : WORD[value.toUpperCase()] ?? value

  return (
    <div className="pt-card is-cat">
      <div className="pt-card-h">
        <Icon size={14} aria-hidden />
        <span className="lab">{v.short}</span>
        <SubScore score={score} applied={applied} />
      </div>
      <div className="pt-read">{word ?? '—'}</div>

      <div className="pt-states">
        <span className={'pt-state' + (value != null && alert ? ' is-on' : '')}>
          Alert <span className="num">0</span>
        </span>
        <span className={'pt-state' + (value != null && !alert ? ' is-on' : '')}>
          Voice / Pain / Unresponsive <span className="num">3</span>
        </span>
      </div>

      <div className="pt-caption">
        {value == null
          ? <span className="pt-flag">not recorded</span>
          : <>categorical, not a scale — there is no 1 or 2</>}
        {!cited && <span className="pt-flag pt-flag-cite">not cited</span>}
      </div>
    </div>
  )
}
