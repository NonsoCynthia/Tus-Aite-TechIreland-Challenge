import type {
  CohortGraph, CohortReferral, Decision, Hospital, Overrides, Reference,
  ReferralContext, Run, ScoresByPathway,
} from './types'

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { headers: { Accept: 'application/json' } })
  if (!r.ok) {
    // Name the upstream path, not /api: an error the developer can act on.
    throw new Error(`${path} -> ${r.status} ${r.statusText}`)
  }
  return r.json() as Promise<T>
}

export const api = {
  health: () => get<{
    status: string; retrieval: unknown; capacity_direction: string
    sources: { postgres: string; oxigraph: string }
    /** Which hospital-days hold a decision, and whether it came from a run in
        this process or from the snapshot restored on boot. */
    decisions_held: Array<{
      hospital_hipe: string; as_of_date: string; run_id: string
      built_at: string; source: 'run' | 'snapshot'
    }>
  }>('/api/health'),

  cohort: (hospital: string, date: string) =>
    get<{ referrals: CohortReferral[] }>(`/api/cohort/${hospital}/${date}`),

  /** Which hospitals exist, and what they are called: `core.hospitals`, which
      has held both since the seed while App.tsx carried them as a literal.
      Seed data, so it is fetched once and never refetched, like the reference
      layer.

      AN EMPTY ARRAY IS NOT "no hospitals exist". sources.query() returns [] on
      a failed read rather than raising, and the orchestrator cannot tell the
      two apart, so [] has to be read as "the roster could not be read". The
      table is the FK target of every referral, ward and clinic on screen
      (dataset/db/migrations/003_core.sql), so a genuinely empty one cannot
      coexist with a cohort being displayed. */
  hospitals: () => get<{ hospitals: Hospital[] }>('/api/hospitals'),

  /** 404 until a run has produced one. The orchestrator serves what it built,
      never GET /decisions, which appends rather than replaces.

      The payload carries `_source: "snapshot"` when this decision was restored
      from the snapshot file at boot rather than produced by a run in this
      process. Absent means a run produced it. */
  decision: (hospital: string, date: string) =>
    get<Decision>(`/api/decision/${hospital}/${date}`),

  run: (runId: string) => get<Run>(`/api/runs/${runId}`),

  scores: (runId: string, hospital: string) =>
    get<{ scores: ScoresByPathway }>(`/api/scores/${runId}/${hospital}`),

  /** Hospital-level operational context: every ward's latest snapshot, and how
      stale the clinical readings are. First call ~3.3s, then cached server-side. */
  operations: (hospital: string, date: string) =>
    get<{
      cohort: number
      wards: Array<{
        ward_id: string
        /** The ward's nominal capacity: the SUM of what core.ward_specialty
            allocates to each specialty it serves. A single context row carries
            only one specialty's allocation, which is why a 92-bed ward used to
            report 45. `allocations` keeps the split. */
        nominal_beds: number | null
        allocations: Record<string, number>
        /** occupied + free — the census actually recorded against the ward,
            which is the denominator occupancy_pct uses. */
        census: number | null
        occupancy_pct: number
        /** DATASET_README calls `free` "the answer to how many beds are
            available". It was never fetched until now. */
        occupied: number | null; free: number | null; outliers: number
        gar_status: 'G' | 'A' | 'R' | null
        over_9h: number; over_24h: number; dtoc: number; surge: number; snapshot: string
        /** Which specialties this ward backs. Dropped during de-duplication
            before, which left the ward panel unjoinable to any referral. */
        specialties: string[]; primary_for: string[]
      }>
      /** The clinic half of the capacity score — 30% of it, and previously
          discarded. `cited_session_date` is the ONE row the agent read; the
          rest of the series is context and must be labelled as such. */
      clinics: Array<{
        specialty_hipe: string; clinic_code: string | null; clinic_name: string | null
        cited_session_date: string | null; cited_pressure: number
        slots_booked: number; slots_total: number; slots_available: number
        sessions: Array<{
          session_date: string; slots_total: number
          slots_booked: number; slots_available: number
        }>
      }>
      observation_age: {
        n: number; median: number; mean: number; max: number
        over_1y: number; over_2y: number
      } | null
      /** Per-referral clinical facts the cohort payload does not carry: news2
          only exists here, and the reading's age is the point. */
      clinical: Record<string, {
        news2: number | null
        obs_datetime: string | null
        reading_age_days: number | null
        pain: number | null
        mts_category: string | null
        /** A weighted random draw over the specialty's mix, independent of
            acuity. A record field, never evidence. */
        icd10am_code: string | null
        referral_date: string | null
        referral_received_date: string | null
        sent_for_triage_date: string | null
        triage_date: string | null
        turnaround_days: number | null
      }>
    }>(`/api/operations/${hospital}/${date}`),

  /** Which hospital-days actually hold a cohort, discovered from the data.
   *  `runnable` is the newest of them: evidence is date-blind, so scoring an
   *  earlier day would cite readings taken later. Everything else is readable. */
  hospitalDays: (hospital: string) =>
    get<{
      hospital_hipe: string
      days: Array<{ date: string; referrals: number }>
      runnable: string | null
      today: string
      today_has_cohort: boolean
      /** How many referral-day rows this hospital holds, and how many carry a
          removal date. The Intake panel reads a rise in the counts above as
          arrivals, which is only honest if nobody ever leaves, and these two are
          that claim's evidence.
          NULL means the read FAILED, not that the answer is zero: the panel
          drops the line rather than printing a nought as though it were a
          finding. */
      referral_days: number | null
      removed: number | null
    }>(`/api/hospital-days/${hospital}`),

  refreshDays: async (hospital: string) => {
    const r = await fetch(`/api/hospital-days/${hospital}/refresh`, { method: 'POST' })
    if (!r.ok) throw new Error(`could not refresh: ${r.status}`)
    return r.json()
  },

  context: (hospital: string, pathway: string) =>
    get<ReferralContext>(`/api/context/${hospital}/${pathway}`),

  /** core.ref_* — specialty names, the authoritative CRT days, the five rule
      statements. Seed data, so it is fetched once and never refetched. */
  reference: () => get<Reference>('/api/reference'),

  /** Overrides, read back. Nothing could read one before: retrieval has no GET
      and the graph keeps only three triples per override. */
  overrides: (hospital: string, date: string) =>
    get<Overrides>(`/api/overrides/${hospital}/${date}`),

  /** The whole decision as a graph — 305 placements and their citations, from
      one SPARQL query. `limit` caps placements for a smaller draw. */
  cohortGraph: (runId: string, limit = 0) =>
    get<CohortGraph>(`/api/graph/cohort/${runId}${limit ? `?limit=${limit}` : ''}`),

  startRun: async (hospital: string, date: string): Promise<{ run_id: string }> => {
    const r = await fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hospital_hipe: hospital, as_of_date: date }),
    })
    if (!r.ok) throw new Error(`could not start a run: ${r.status}`)
    return r.json()
  },
}

/** SEVERITY_RANK, coordinator/app/bands.py. Note cpc 3 outranks cpc 2, so
    sorting by the raw code puts Routine above Semi-Urgent. Never sort on cpc.

    The `target` days here are a FALLBACK for the first paint only. The
    authoritative values are core.ref_codes.crt_days via api.reference(), and a
    component that draws a threshold reads them from there — otherwise a change
    to the seed desyncs the product silently. */
export const BANDS = [
  { key: 'Urgent',        cpc: 1,    rank: 1, target: 28,   token: 'urgent'  },
  { key: 'Semi-Urgent',   cpc: 3,    rank: 2, target: 91,   token: 'semi'    },
  { key: 'Routine',       cpc: 2,    rank: 3, target: null, token: 'routine' },
  { key: 'Uncategorised', cpc: null, rank: 4, target: null, token: 'uncat'   },
] as const

export const bandOf = (cpc: number | null): string =>
  BANDS.find((b) => b.cpc === cpc)?.key ?? 'Uncategorised'
