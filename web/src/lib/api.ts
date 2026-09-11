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
    /** Which hospital-days hold a decision, and where each came from. */
    decisions_held: Array<{
      hospital_hipe: string; as_of_date: string; run_id: string
      built_at: string; source: 'run' | 'snapshot'
    }>
  }>('/api/health'),

  cohort: (hospital: string, date: string) =>
    get<{ referrals: CohortReferral[] }>(`/api/cohort/${hospital}/${date}`),

  /** `core.hospitals`. Seed data, so it is fetched once and never refetched.
      AN EMPTY ARRAY IS NOT "no hospitals exist": sources.query() returns [] on a
      failed read rather than raising. The table is the FK target of every
      referral, ward and clinic on screen (dataset/db/migrations/003_core.sql),
      so a genuinely empty one cannot coexist with a displayed cohort. */
  hospitals: () => get<{ hospitals: Hospital[] }>('/api/hospitals'),

  /** 404 until a run has produced one. The orchestrator serves what it built,
      never GET /decisions, which appends rather than replaces. `_source` marks a
      decision restored from the snapshot file at boot; see types.ts. */
  decision: (hospital: string, date: string) =>
    get<Decision>(`/api/decision/${hospital}/${date}`),

  run: (runId: string) => get<Run>(`/api/runs/${runId}`),

  scores: (runId: string, hospital: string) =>
    get<{ scores: ScoresByPathway }>(`/api/scores/${runId}/${hospital}`),

  /** Every ward's latest snapshot, and how stale the clinical readings are.
      First call ~3.3s, then cached server-side. */
  operations: (hospital: string, date: string) =>
    get<{
      cohort: number
      wards: Array<{
        ward_id: string
        /** The SUM of what core.ward_specialty allocates to each specialty the
            ward serves. A single context row carries one specialty's allocation,
            never the ward total; `allocations` keeps the split. */
        nominal_beds: number | null
        allocations: Record<string, number>
        /** occupied + free — the recorded census, and occupancy_pct's denominator. */
        census: number | null
        occupancy_pct: number
        /** DATASET_README: `free` is "the answer to how many beds are available". */
        occupied: number | null; free: number | null; outliers: number
        gar_status: 'G' | 'A' | 'R' | null
        over_9h: number; over_24h: number; dtoc: number; surge: number; snapshot: string
        /** De-duplicating ward rows must KEEP these, or the ward panel is
            unjoinable to any referral. */
        specialties: string[]; primary_for: string[]
      }>
      /** The clinic half of the capacity score, 30% of it. `cited_session_date`
          is the ONE row the agent read; `sessions` is context, label it so. */
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
      /** Per-referral clinical facts the cohort payload does not carry. news2
          exists ONLY here. */
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
      /** The Intake panel reads a rise in the counts above as arrivals, which is
          only honest if nobody ever leaves; these two are that claim's evidence.
          NULL means the read FAILED, not zero — drop the line rather than print
          a nought as a finding. */
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

  /** core.ref_*. Seed data, so it is fetched once and never refetched. */
  reference: () => get<Reference>('/api/reference'),

  /** Retrieval exposes no GET for overrides, and the graph keeps only three
      triples per override, so read them back here. */
  overrides: (hospital: string, date: string) =>
    get<Overrides>(`/api/overrides/${hospital}/${date}`),

  /** Every placement and its citations, from one SPARQL query. `limit` caps
      placements for a smaller draw. */
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
    sorting by the raw code puts Routine above Semi-Urgent. NEVER SORT ON cpc.

    `target` here is a FALLBACK for the first paint only. The authoritative
    values are core.ref_codes.crt_days via api.reference(); a component that
    draws a threshold must read them from there. */
export const BANDS = [
  { key: 'Urgent',        cpc: 1,    rank: 1, target: 28,   token: 'urgent'  },
  { key: 'Semi-Urgent',   cpc: 3,    rank: 2, target: 91,   token: 'semi'    },
  { key: 'Routine',       cpc: 2,    rank: 3, target: null, token: 'routine' },
  { key: 'Uncategorised', cpc: null, rank: 4, target: null, token: 'uncat'   },
] as const

export const bandOf = (cpc: number | null): string =>
  BANDS.find((b) => b.cpc === cpc)?.key ?? 'Uncategorised'
