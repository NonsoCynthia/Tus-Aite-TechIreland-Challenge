import { BedDouble, CalendarDays, Stethoscope, TriangleAlert } from 'lucide-react'
import { Vitals, type AgeStats } from './Vitals'
import { CROWDED_OCCUPANCY, SAFE_OCCUPANCY, SEV_INTEGRITY, sevOccupancy } from '../lib/severity'
import { SevBar, SevChip } from './Severity'
import { Aside } from './Aside'
import type { Observation } from '../lib/types'

/** What actually reached each agent, and (for capacity) what it could not do
 *  with it.
 *
 *  Capacity is a property of the SPECIALTY, never of the person: the score is
 *  shared by every peer in it, and priority never reads it
 *  (coordinator/app/priority.py:158-162). The guard saying so is drawn before
 *  the ward figures, never after.
 *
 *  WHAT WAS READ IS A CITATION, NEVER A GUESS, AND IT CARRIES ITS DATE. The
 *  evidence is served date-blind, so on any day but 2026-08-30 these figures are
 *  dated FORWARD of the day selected (CapacityAsOf). Never substitute the newest
 *  session for a missing citation -- these four states stay apart:
 *
 *    citation names a row in the series   that row was read, the others not
 *    citation names a row NOT in it       the citation is stated, no row marked
 *    a score, no citation of that kind    which row it read is not on record
 *    no capacity score for this referral  nothing read anything; this is context
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
  /** THIS SPECIALTY'S ALLOCATION to the ward -- NOT the ward's bed
   *  establishment, and never the denominator of occupancy_pct. A /context row
   *  carries one specialty, so the 92-bed W-9001-02 reports 45 here;
   *  /operations sums every specialty's allocation and calls THAT
   *  `nominal_beds` (lib/api.ts:47-50). Draw it as an allocation or not at all. */
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
/** `capacity` on GET /context is typed `unknown` in lib/types.ts, so the shape
 *  the endpoint really returns is declared here and narrowed in Patient.tsx. */
export interface CapacityContext {
  specialty_hipe: string | null
  wards: CapacityWard[]
  clinic_sessions: ClinicSession[]
}

const GAR_WORD = { G: 'Green', A: 'Amber', R: 'Red' } as const
const GAR_WEIGHT = { G: 1, A: 2, R: 3 } as const

/** --icon and --icon-sm from tokens.css; lucide sizes in JS, so the two steps
 *  live here as numbers. STROKE is passed on every icon in this file: lucide's
 *  default of 2 renders heavier than the 1.75 hairline chrome beside it. */
const ICON_PX = 16
const ICON_SM_PX = 14
const STROKE = 1.75

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
/** The Overview's as-of formatter (Overview.tsx:131-132), copied so the two
 *  surfaces print one date one way. */
const longDate = (iso: string) =>
  new Date(iso).toLocaleDateString('en-IE', { day: 'numeric', month: 'long', year: 'numeric' })
/** The calendar day a timestamp falls on, and null when there is not one.
 *  `snapshot_datetime` is nullable here, and slicing anything else would
 *  manufacture a "day" to compare the selected date against. */
const DAY_RE = /^\d{4}-\d{2}-\d{2}(?:$|[T ])/
const dayOf = (s: string | null | undefined): string | null =>
  s != null && DAY_RE.test(s) ? s.slice(0, 10) : null

export function AgentInputs({
  obs, recordedTotal, agentTotal, when, ageDays, stats, cited, applied,
  urgencyScore, capacityScore, capacityDetail, capacity, citedWard, citedSession,
  specialty, alpha, peers, date,
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
  /** The hospital-day selected in the top bar. The evidence below is served
   *  date-blind, so this is the only thing that can date it, and it is used for
   *  NOTHING else: no figure here is fetched, filtered or scored by it. */
  date: string
}) {
  const wards = capacity?.wards ?? []
  const primary = wards.find((w) => w.ward_id === citedWard)
    ?? wards.find((w) => w.is_primary) ?? wards[0]
  const others = wards.filter((w) => w !== primary)
  const sessions = [...(capacity?.clinic_sessions ?? [])]
    .sort((a, b) => a.session_date.localeCompare(b.session_date))

  /** Did the capacity agent score THIS referral at all? A score OR a citation,
   *  not the score alone: a paediatric referral is refused by urgency and never
   *  placed, so no ranking row carries its capacity score -- but the capacity
   *  agent scored it anyway, and its citations reach this component. */
  const capacityRan = capacityScore != null || citedWard != null || citedSession != null
  /** The session the record NAMES. No substitute: see the header. */
  const readDate = citedSession
  /** ...and whether that named session is one of the rows drawn below. If the
   *  citation names a session the context call did not return, the citation is
   *  still true and no row here may wear it. */
  const readInSeries = readDate != null && sessions.some((s) => s.session_date === readDate)

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

          {/* Invariants 7 and 8: a hospital-day with no decision is a normal
              state, so this is said once at the top of the lane -- everything
              below comes from the date-blind context call and is on screen
              either way. */}
          {!capacityRan && (
            <p className="pt-mini">
              No capacity score was recorded for this referral, so nothing below was read by an
              agent. The ward and the clinic sessions are this specialty's context.
            </p>
          )}

          {/* Dated before it is drawn: the ward panel and the clinic series
              below are the same rows on every hospital-day. */}
          <CapacityAsOf ward={primary} sessions={sessions} selected={date} />

          {primary ? (
            <WardPanel w={primary} pressure={wp}
                       read={citedWard != null
                         ? (primary.ward_id === citedWard ? 'cited' : 'other')
                         : capacityRan ? 'uncited' : 'norun'} />
          ) : (
            <p className="pt-mini">No ward is joined to this specialty.</p>
          )}

          {others.length > 0 && (
            <div className="pt-others">
              {/* "not cited" is only sayable once something WAS cited. */}
              <span className="lab">
                Also backs this specialty{citedWard != null && ', not cited'}
              </span>
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
              <ClinicSeries sessions={sessions} readDate={readInSeries ? readDate : null} />
              {readInSeries ? (
                <p className="pt-mini">
                  One session was read. The other{' '}
                  <span className="num">{sessions.length - 1}</span> were not scored.
                </p>
              ) : readDate != null ? (
                <p className="pt-mini">
                  The citation names the session of{' '}
                  <span className="num">{dateShort(readDate)}</span>, which is not among the{' '}
                  <span className="num">{sessions.length}</span> sessions here, so no row above is
                  marked as read.
                </p>
              ) : capacityRan ? (
                <p className="pt-mini">
                  The capacity agent scored this referral but cited no clinic session, so which of
                  these <span className="num">{sessions.length}</span> it read is not on the
                  record.
                </p>
              ) : (
                <p className="pt-mini">
                  None of these <span className="num">{sessions.length}</span> sessions was
                  read by an agent.
                </p>
              )}
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

/** THE AS-OF STATEMENT, borrowed whole from the Overview (Overview.tsx:497-524)
 *  down to the class names, so both surfaces state ONE fact one way.
 *
 *  /api/context is not keyed by hospital-day: the same ward snapshot and the
 *  same sessions come back whatever day is selected. On the default day the
 *  snapshot IS the day selected, so this renders nothing.
 *
 *  Only sessions dated AFTER the selected day are named -- a series running up
 *  to it is an ordinary record of clinics already held. An unreadable snapshot
 *  date is an ABSENCE of information, not a match, and is said in words. No
 *  hospital-day is inferred from the evidence: that is the same guess twice. */
function CapacityAsOf({ ward, sessions, selected }: {
  /** The ward drawn below this line, and the only one it speaks for. */
  ward: CapacityWard | undefined
  sessions: ClinicSession[]
  selected: string
}) {
  const snapDay = ward ? dayOf(ward.latest_bed_status?.snapshot_datetime) : null
  const undated = ward != null && snapDay == null
  const wardOff = snapDay != null && snapDay !== selected
  const ahead = sessions.map((s) => s.session_date).filter((d) => d > selected)
  if (!undated && !wardOff && ahead.length === 0) return null

  const days = [...new Set(snapDay != null && wardOff ? [snapDay, ...ahead] : ahead)].sort()
  const span = days.length === 0 ? null
    : days.length === 1 ? longDate(days[0])
      : `${longDate(days[0])} to ${longDate(days[days.length - 1])}`
  const both = wardOff && ahead.length > 0
  // The subject names exactly what the span covers and no more: a series only
  // PARTLY dated forward must not be described as though all of it were.
  const clinics = ahead.length === sessions.length
    ? 'the clinic sessions below'
    : `${ahead.length} of the ${sessions.length} clinic sessions below`
  const what = both ? `The ward figures and ${clinics}`
    : wardOff ? 'The ward figures below'
      : clinics.charAt(0).toUpperCase() + clinics.slice(1)
  // Only the verb differs from Overview's sentence: singular in the one case
  // where a lone clinic session is dated forward and no ward is.
  const verb = !wardOff && ahead.length === 1 ? 'is' : 'are'
  const source = both
    ? 'core.bed_status and core.clinic_sessions are read latest-first with no date filter, so every hospital-day is served this same snapshot and this same series.'
    : wardOff
      ? 'core.bed_status is read latest-first with no date filter, so every hospital-day is served this same snapshot.'
      : 'core.clinic_sessions is read latest-first with no date filter, so every hospital-day is served this same series.'

  return (
    <div className="ov-asof is-off">
      <SevChip sev={SEV_INTEGRITY}>
        <CalendarDays size={ICON_SM_PX} strokeWidth={STROKE} aria-hidden />
        {span ? <span className="num">{span}</span> : 'no snapshot date'}
      </SevChip>
      <span>
        {undated && (
          <>
            The ward figures below carry no snapshot date this page can read, so it cannot be
            said whether they were taken on {longDate(selected)}, the day selected above.{' '}
          </>
        )}
        {span && <>{what} {verb} as of {span}, not {longDate(selected)}, the day selected above. {source}</>}
      </span>
    </div>
  )
}

/** Whether this ward's snapshot is the one the capacity agent cited -- and if
 *  it is not, WHY it is not. Four states, because they are four different
 *  claims and only one of them is true on a day nothing ran. */
type WardRead = 'cited' | 'other' | 'uncited' | 'norun'
const WARD_READ: Record<WardRead, string> = {
  cited: 'read by the agent',
  other: 'not the cited snapshot',
  uncited: 'no snapshot is cited on the record',
  norun: 'not read: no capacity score',
}

/** The one ward snapshot the capacity agent cited, when one was.
 *
 *  The bed counts here are the WARD's; `nominal_beds` beside them is one
 *  SPECIALTY's allocation and is drawn under its own name, never as the ward's
 *  size. The ward-level count this payload carries is the census, occupied +
 *  free, which is also the denominator occupancy_pct is computed from
 *  (lib/api.ts:53-55), so it is the one figure that may stand beside the
 *  percentage. The ward's nominal establishment is /operations' summed
 *  `nominal_beds` and is deliberately absent rather than approximated: this
 *  panel is given no hospital to key /operations by. See BUILD_LEDGER.md. */
function WardPanel({ w, read, pressure }: {
  w: CapacityWard; read: WardRead; pressure: number | null
}) {
  const b = w.latest_bed_status
  // occupied/(occupied+free), so it is bounded at 100 by construction: 100% is
  // the end of the meter's scale, never a span that surge beds push past.
  const pct = num(b?.occupancy_pct)
  // GAR's own vocabulary is green/amber/red, but those hues belong to CPC triage
  // categories on this product and are not lent out, so it is drawn in ink
  // weight with the word beside it -- the neutral register MTS gets.
  const gar = b?.gar_status ?? null
  const sev = sevOccupancy(pct)
  const occ = b?.occupied ?? null
  const free = b?.free ?? null
  // occupied + free: the census actually recorded on the ward, and the only
  // ward-level bed count in this payload.
  const census = occ != null && free != null ? occ + free : null
  // ...and it stands beside the percentage only while it reproduces it.
  // occupancy_pct arrives rounded to 2dp, hence the 0.05 tolerance.
  const censusHolds = pct != null && census != null && census > 0
    && Math.abs((occ! / census) * 100 - pct) <= 0.05
  // The word beside the figure names the line the number has crossed, so the
  // fill is never the only channel and the threshold is never implied. Both
  // constants come from lib/severity.ts, the same ones sevOccupancy bands on:
  // a second declaration here is how a drawn line and the colour beneath it
  // drift a point apart and stop meaning each other.
  const state = sev === 0 ? null
    : sev === 1 ? `past the ${SAFE_OCCUPANCY}% safe line`
      : sev === 3 ? `past ${CROWDED_OCCUPANCY}%`
        : 'no free bed'

  return (
    <div className="pt-ward">
      <div className="pt-ward-h">
        <span className="pt-ward-id num">{w.ward_id}</span>
        {w.is_primary && <span className="pt-tag">primary ward</span>}
        <span className={'pt-tag' + (read === 'cited' ? ' is-read' : '')}>
          {WARD_READ[read]}
        </span>
        <span className="pt-ward-t num">{stamp(b?.snapshot_datetime ?? null)}</span>
      </div>

      <div className="pt-ward-main">
        <div className="pt-ward-fig">
          <div className="pt-ward-pct num">{pct == null ? '—' : `${pct.toFixed(1)}%`}</div>
          <div className="pt-ward-fig-l">
            occupied
            {censusHolds && <> · <span className="num">{fmt(occ!)} of {fmt(census!)}</span></>}
          </div>
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
              {/* A SPLIT, not a full conversion: WHICH number the percentage
                  divides by stays on the visible line, with both counts in it.
                  Only the argument for it goes behind the toggle -- hiding the
                  denominator would put the panel back where it started. */}
              {census != null && (censusHolds ? (
                <Aside className="pt-mini" label="why occupied + free is the denominator"
                       summary={<>That percentage is <span className="num">{fmt(occ!)}</span> of the{' '}
                         <span className="num">{fmt(census!)}</span> beds recorded on this ward
                         (occupied + free).</>}>
                  It is not measured against a bed establishment.
                  {w.nominal_beds != null && (
                    <> The <span className="num">{fmt(w.nominal_beds)}</span> allocated below is
                      what this ward sets aside for this specialty, which is a share of the ward
                      and not the count the percentage divides by. The ward's own nominal total
                      is in the Overview's ward table.</>
                  )}
                </Aside>
              ) : (
                <p className="pt-mini">
                  <SevChip sev={SEV_INTEGRITY}>census does not reconcile</SevChip>{' '}
                  <span className="num">{fmt(occ ?? 0)}</span> occupied and{' '}
                  <span className="num">{fmt(free ?? 0)}</span> free make{' '}
                  <span className="num">{fmt(census)}</span>, which is not what{' '}
                  <span className="num">{pct.toFixed(1)}%</span> was computed from, so the two are
                  left standing apart.
                </p>
              ))}
            </>
          )}
        </div>
      </div>

      <dl className="pt-facts">
        <Fact k="free beds" v={free} note={free === 0 ? 'none' : undefined} />
        <Fact k="occupied" v={occ} />
        <Fact k="ward census" v={census} note="occupied + free" />
        <Fact k="beds allocated" v={w.nominal_beds ?? null} note="this specialty's share of the ward" />
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

/** The specialty's sessions in date order, and -- only if a citation names one
 *  of them -- which one was read. When `readDate` is null NO row is marked and
 *  none says "not read" either: "context, not read" asserts that something else
 *  WAS read, and on a day no agent ran there is nothing for it to point at. The
 *  caller states which of the four cases this is, underneath. */
function ClinicSeries({ sessions, readDate }: { sessions: ClinicSession[]; readDate: string | null }) {
  const anyRead = readDate != null
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
              {read ? 'read by the agent' : anyRead ? 'context, not read' : 'context'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
