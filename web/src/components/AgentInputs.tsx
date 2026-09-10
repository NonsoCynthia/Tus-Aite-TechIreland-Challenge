import { BedDouble, CalendarDays, Stethoscope, TriangleAlert } from 'lucide-react'
import { Vitals, type AgeStats } from './Vitals'
import { sevOccupancy } from '../lib/severity'
import { SevBar, SevChip } from './Severity'
import type { Observation } from '../lib/types'

/** What actually reached each agent, and (for capacity) what it could not do
 *  with it.
 *
 *  Two lanes, because two agents ran and they read different worlds. The
 *  urgency agent read six numbers about ONE person. The capacity agent read a
 *  ward snapshot and a clinic session about a whole SPECIALTY, and its score is
 *  the same for everybody in that specialty.
 *
 *  The most serious error this page could make is letting the capacity figures
 *  read as a statement about the individual, so the lane opens with the
 *  arithmetic that rules it out: the score is shared by every peer in the
 *  specialty and priority never reads it at all
 *  (coordinator/app/priority.py:158-162). The ward is drawn after that, never
 *  before.
 */

export interface BedStatus {
  snapshot_datetime: string | null
  occupied: number | null
  free: number | null
  occupancy_pct: number | string | null
  outliers: number | null
  surge_capacity_in_use: number | null
  delayed_transfers_of_care: number | null
  awaiting_admission_over_9h: number | null
  awaiting_admission_over_24h: number | null
  gar_status: 'G' | 'A' | 'R' | null
}
export interface CapacityWard {
  ward_id: string
  is_primary: boolean
  nominal_beds: number | null
  latest_bed_status: BedStatus | null
}
export interface ClinicSession {
  clinic_code: string | null
  clinic_name: string | null
  session_date: string
  slots_total: number
  slots_booked: number
  slots_available: number
}
/** `capacity` on GET /context is typed `unknown` in lib/types.ts and is not
 *  mine to widen, so the shape the endpoint really returns is declared here and
 *  narrowed once, in Patient.tsx. */
export interface CapacityContext {
  specialty_hipe: string | null
  wards: CapacityWard[]
  clinic_sessions: ClinicSession[]
}

const GAR_WORD = { G: 'Green', A: 'Amber', R: 'Red' } as const
const GAR_WEIGHT = { G: 1, A: 2, R: 3 } as const

/** --icon and --icon-sm from tokens.css. lucide sizes in JS rather than in CSS,
 *  so the two steps live here as numbers; STROKE is passed on every icon in this
 *  file because lucide's default of 2 renders heavier than the 1.75 hairline
 *  chrome beside it. */
const ICON_PX = 16
const ICON_SM_PX = 14
const STROKE = 1.75

/** The safe-operating line every occupancy figure in this product is read
 *  against. sevOccupancy uses the same number; it is drawn here so the reader
 *  can see where it falls rather than being told. */
const SAFE_OCCUPANCY = 85

const num = (v: unknown): number | null => {
  if (v == null || v === '') return null
  const n = typeof v === 'number' ? v : parseFloat(String(v))
  return Number.isNaN(n) ? null : n
}
const fmt = (n: number) => n.toLocaleString('en-IE')
const n3 = (x: number) => x.toFixed(3)
const dateShort = (s: string) =>
  new Date(s).toLocaleDateString('en-IE', { day: 'numeric', month: 'short' })
const stamp = (s: string | null) =>
  s ? new Date(s).toLocaleString('en-IE', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'

export function AgentInputs({
  obs, recordedTotal, agentTotal, when, ageDays, stats, cited, applied,
  urgencyScore, capacityScore, capacityDetail, capacity, citedWard, citedSession,
  specialty, alpha, peers,
}: {
  obs: Observation | undefined
  recordedTotal: number | null
  agentTotal: number | null
  when: string | null
  ageDays: number | null
  stats: AgeStats | undefined
  cited: Set<string>
  applied: boolean
  urgencyScore: number | null
  capacityScore: number | null
  capacityDetail: { ward_pressure: number | null; clinic_pressure: number | null } | null
  capacity: CapacityContext | undefined
  /** Ward id and session date lifted out of the recorded capacity citations. */
  citedWard: string | null
  citedSession: string | null
  specialty: string
  alpha: number | null
  /** How many referrals carry this exact capacity score, and how many are in
   *  this specialty. Counted from the decision, not asserted. */
  peers: { same: number; inSpecialty: number } | null
}) {
  const wards = capacity?.wards ?? []
  const primary = wards.find((w) => w.ward_id === citedWard)
    ?? wards.find((w) => w.is_primary) ?? wards[0]
  const others = wards.filter((w) => w !== primary)
  const sessions = [...(capacity?.clinic_sessions ?? [])]
    .sort((a, b) => a.session_date.localeCompare(b.session_date))
  const newest = sessions.length ? sessions[sessions.length - 1].session_date : null
  const readDate = citedSession ?? newest

  const wp = capacityDetail?.ward_pressure ?? null
  const cp = capacityDetail?.clinic_pressure ?? null
  // The capacity agent weights the ward snapshot 0.7 and the clinic 0.3. Shown
  // as an equation only when it reproduces the recorded score; otherwise the
  // two components stand alone rather than under a formula that does not hold.
  const blend = wp != null && cp != null ? 0.7 * wp + 0.3 * cp : null
  const blendHolds = blend != null && capacityScore != null && Math.abs(blend - capacityScore) <= 0.002

  return (
    <div className="pt-lanes">
      <section className="pt-lane">
        <header className="pt-lane-h">
          <Stethoscope size={ICON_PX} strokeWidth={STROKE} aria-hidden />
          <span className="pt-lane-k">Urgency agent</span>
          <span className="pt-lane-s num">
            {urgencyScore == null ? 'no score' : n3(urgencyScore)}
          </span>
          <span className="pt-lane-x">
            {applied
              ? `${cited.size} citations · one per NEWS2 parameter, zeros included`
              : 'refused: NEWS2 is validated in adults'}
          </span>
        </header>
        <div className="pt-lane-b">
          <Vitals obs={obs} recordedTotal={recordedTotal} agentTotal={agentTotal}
                  when={when} ageDays={ageDays} stats={stats} cited={cited} applied={applied} />
        </div>
      </section>

      <section className="pt-lane">
        <header className="pt-lane-h">
          <BedDouble size={ICON_PX} strokeWidth={STROKE} aria-hidden />
          <span className="pt-lane-k">Capacity agent</span>
          <span className="pt-lane-s num">
            {capacityScore == null ? 'no score' : n3(capacityScore)}
          </span>
          <span className="pt-lane-x">{specialty}</span>
        </header>

        <div className="pt-lane-b">
          <div className="pt-guard">
            <TriangleAlert size={ICON_PX} strokeWidth={STROKE} aria-hidden />
            <div>
              <strong>Capacity did not move this person.</strong>
              <ul className="pt-guard-l">
                {peers && capacityScore != null && (
                  <li>
                    <span className="num">{n3(capacityScore)}</span> is carried by{' '}
                    <span className="num">{fmt(peers.same)}</span> of the{' '}
                    <span className="num">{fmt(peers.inSpecialty)}</span> placed referrals in this
                    specialty. It is a property of the specialty, not of anyone in it.
                  </li>
                )}
                {alpha != null && (
                  <li>
                    Its only effect is α = <span className="num">{n3(alpha)}</span>, set once for
                    the whole hospital-day and identical on every row.
                  </li>
                )}
                <li>
                  <code>priority</code> never reads a referral's own capacity score
                  (<code>coordinator/app/priority.py:158–162</code>), so it cannot reorder two
                  people inside a band. Everything below is context for the reader.
                </li>
              </ul>
            </div>
          </div>

          {primary ? (
            <WardPanel w={primary} cited={primary.ward_id === citedWard} pressure={wp} />
          ) : (
            <p className="pt-mini">No ward is joined to this specialty.</p>
          )}

          {others.length > 0 && (
            <div className="pt-others">
              <span className="lab">Also backs this specialty, not cited</span>
              {others.map((w) => (
                <span key={w.ward_id} className="pt-other num">
                  {w.ward_id}
                  {w.latest_bed_status && (
                    <> · {num(w.latest_bed_status.occupancy_pct)?.toFixed(1) ?? '—'}% occupied</>
                  )}
                </span>
              ))}
            </div>
          )}

          {sessions.length > 0 && (
            <div className="pt-clinic">
              <div className="pt-clinic-h">
                <CalendarDays size={ICON_SM_PX} strokeWidth={STROKE} aria-hidden />
                <span className="lab">
                  {sessions[0].clinic_name ?? 'Outpatient clinic'}
                  {sessions[0].clinic_code ? ` · ${sessions[0].clinic_code}` : ''}
                </span>
                {cp != null && <span className="pt-clinic-p num">clinic pressure {n3(cp)}</span>}
              </div>
              <ClinicSeries sessions={sessions} readDate={readDate} />
              <p className="pt-mini">
                One session was read. The other{' '}
                <span className="num">{sessions.length - 1}</span> were not scored.
              </p>
            </div>
          )}

          {(wp != null || cp != null) && (
            <div className="pt-blend">
              <span className="lab">How the capacity score was made</span>
              {blendHolds ? (
                <span className="pt-blend-eq num">
                  0.7 × {n3(wp!)} <span className="pt-eq-op">+</span> 0.3 × {n3(cp!)}{' '}
                  <span className="pt-eq-op">=</span>{' '}
                  <strong>{n3(capacityScore!)}</strong>
                </span>
              ) : (
                <span className="pt-blend-eq num">
                  ward {wp == null ? '—' : n3(wp)} · clinic {cp == null ? '—' : n3(cp)}
                  {capacityScore != null && <> · recorded score {n3(capacityScore)}</>}
                  <span className="pt-flag">
                    the two components do not reproduce the recorded score: weights not shown
                  </span>
                </span>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

/** The one ward snapshot the capacity agent cited.
 *
 *  GAR is an escalation status whose own vocabulary is green/amber/red. Those
 *  hues belong to CPC triage categories on this product and are not lent out,
 *  so the status is drawn in ink weight with the word beside it: the same
 *  neutral register MTS gets.
 *
 *  The meter used to span `Math.max(100, pct)` on the theory that occupancy
 *  passes 100 when surge beds are open. It cannot. occupancy_pct is
 *  occupied/(occupied+free), which is bounded at 100 by construction, so the
 *  span was always exactly 100, the 100% tick was pinned to the right edge on
 *  every ward, and the only line a reader actually needs -- 85%, the
 *  safe-operating line -- was absent from this page altogether. 100% is now the
 *  end of the scale, because that is what it is, and 85% is the mark. */
function WardPanel({ w, cited, pressure }: {
  w: CapacityWard; cited: boolean; pressure: number | null
}) {
  const b = w.latest_bed_status
  const pct = num(b?.occupancy_pct)
  const gar = b?.gar_status ?? null
  const sev = sevOccupancy(pct)
  // The word beside the figure names the line the number has crossed, so the
  // fill is never the only channel and the threshold is never implied.
  const state = sev === 0 ? null
    : sev === 1 ? `past the ${SAFE_OCCUPANCY}% safe line`
      : sev === 3 ? 'past 95%'
        : 'no free bed'

  return (
    <div className="pt-ward">
      <div className="pt-ward-h">
        <span className="pt-ward-id num">{w.ward_id}</span>
        {w.is_primary && <span className="pt-tag">primary ward</span>}
        <span className={'pt-tag' + (cited ? ' is-read' : '')}>
          {cited ? 'read by the agent' : 'not the cited snapshot'}
        </span>
        <span className="pt-ward-t num">{stamp(b?.snapshot_datetime ?? null)}</span>
      </div>

      <div className="pt-ward-main">
        <div className="pt-ward-fig">
          <div className="pt-ward-pct num">{pct == null ? '—' : `${pct.toFixed(1)}%`}</div>
          <div className="pt-ward-fig-l">occupied</div>
          {state && <SevChip sev={sev}>{state}</SevChip>}
        </div>
        <div className="pt-ward-meter">
          {/* No snapshot is not 0% occupied. An empty track with the safe line
              drawn across it would say the ward is empty, which is a claim. */}
          {pct == null ? (
            <p className="pt-mini">No bed-status snapshot on this ward, so there is nothing to draw.</p>
          ) : (
            <>
              <SevBar sev={sev} value={pct / 100} of={SAFE_OCCUPANCY / 100} height={12}
                      label={`${pct.toFixed(1)} per cent occupied, against a ${SAFE_OCCUPANCY} per cent safe-operating line`} />
              <div className="pt-ward-scale num">
                <span>0</span>
                <span className="pt-ward-safe" style={{ left: `${SAFE_OCCUPANCY}%` }}>
                  {SAFE_OCCUPANCY}% safe line
                </span>
                <span>100%</span>
              </div>
              <p className="pt-mini">
                Above <span className="num">{SAFE_OCCUPANCY}%</span> a hospital loses the slack it
                needs to admit safely (Bagust, Place &amp; Posnett, BMJ 1999;319:155-8).
              </p>
            </>
          )}
        </div>
      </div>

      <dl className="pt-facts">
        <Fact k="free beds" v={b?.free ?? null} note={b?.free === 0 ? 'none' : undefined} />
        <Fact k="occupied" v={b?.occupied ?? null} />
        <Fact k="nominal beds" v={w.nominal_beds ?? null} />
        <Fact k="outliers" v={b?.outliers ?? null} />
        <Fact k="delayed transfers" v={b?.delayed_transfers_of_care ?? null} />
        <Fact k="surge in use" v={b?.surge_capacity_in_use ?? null} />
        <Fact k="waiting over 9h" v={b?.awaiting_admission_over_9h ?? null} />
        <Fact k="waiting over 24h" v={b?.awaiting_admission_over_24h ?? null} />
        <div className="pt-fact">
          <dt className="lab">escalation</dt>
          <dd className="pt-fact-v">
            {gar ? (
              <span className="pt-gar" data-gar={gar}>
                <span className="pt-pips" aria-hidden>
                  {[0, 1, 2].map((i) => <i key={i} className={i < GAR_WEIGHT[gar] ? 'is-on' : ''} />)}
                </span>
                {GAR_WORD[gar]}
              </span>
            ) : '—'}
            <span className="pt-fact-n">HSE GAR status</span>
          </dd>
        </div>
        {pressure != null && (
          <div className="pt-fact">
            <dt className="lab">ward pressure</dt>
            <dd className="pt-fact-v num">{n3(pressure)}<span className="pt-fact-n">what the agent computed</span></dd>
          </div>
        )}
      </dl>
    </div>
  )
}

function Fact({ k, v, note }: { k: string; v: number | null; note?: string }) {
  return (
    <div className="pt-fact">
      <dt className="lab">{k}</dt>
      <dd className="pt-fact-v num">{v == null ? '—' : fmt(v)}{note && <span className="pt-fact-n">{note}</span>}</dd>
    </div>
  )
}

/** Five sessions in date order, one of them the row that was scored. */
function ClinicSeries({ sessions, readDate }: { sessions: ClinicSession[]; readDate: string | null }) {
  const max = Math.max(1, ...sessions.map((s) => s.slots_total))
  return (
    <div className="pt-sessions">
      {sessions.map((s) => {
        const read = s.session_date === readDate
        const booked = max ? (s.slots_booked / max) * 100 : 0
        const total = max ? (s.slots_total / max) * 100 : 0
        return (
          <div key={s.session_date} className={'pt-session' + (read ? ' is-read' : '')}>
            <span className="pt-session-d num">{dateShort(s.session_date)}</span>
            <span className="pt-session-b" role="img"
                  aria-label={`${s.slots_booked} of ${s.slots_total} slots booked`}>
              <i className="pt-session-t" style={{ width: `${total}%` }} />
              <i className="pt-session-f" style={{ width: `${booked}%` }} />
            </span>
            <span className="pt-session-n num">{s.slots_booked}/{s.slots_total}</span>
            <span className="pt-session-x">
              {read ? 'read by the agent' : 'context, not read'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
