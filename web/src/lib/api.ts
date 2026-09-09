import type { CohortReferral, Decision, ReferralContext, Run, ScoresByPathway } from './types'

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { headers: { Accept: 'application/json' } })
  if (!r.ok) {
    // Name the upstream path, not /api: an error the developer can act on.
    throw new Error(`${path} -> ${r.status} ${r.statusText}`)
  }
  return r.json() as Promise<T>
}

export const api = {
  health: () => get<{ status: string; retrieval: unknown; capacity_direction: string }>('/api/health'),

  cohort: (hospital: string, date: string) =>
    get<{ referrals: CohortReferral[] }>(`/api/cohort/${hospital}/${date}`),

  /** 404 until a run has produced one. The orchestrator serves what it built,
      never GET /decisions, which appends rather than replaces. */
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
        ward_id: string; nominal_beds: number | null; occupancy_pct: number
        gar_status: 'G' | 'A' | 'R' | null
        over_9h: number; over_24h: number; dtoc: number; surge: number; snapshot: string
      }>
      observation_age: {
        n: number; median: number; mean: number; max: number
        over_1y: number; over_2y: number
      } | null
    }>(`/api/operations/${hospital}/${date}`),

  context: (hospital: string, pathway: string) =>
    get<ReferralContext>(`/api/context/${hospital}/${pathway}`),

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
    sorting by the raw code puts Routine above Semi-Urgent. Never sort on cpc. */
export const BANDS = [
  { key: 'Urgent',        cpc: 1,    rank: 1, target: 28,   token: 'urgent'  },
  { key: 'Semi-Urgent',   cpc: 3,    rank: 2, target: 91,   token: 'semi'    },
  { key: 'Routine',       cpc: 2,    rank: 3, target: null, token: 'routine' },
  { key: 'Uncategorised', cpc: null, rank: 4, target: null, token: 'uncat'   },
] as const

export const bandOf = (cpc: number | null): string =>
  BANDS.find((b) => b.cpc === cpc)?.key ?? 'Uncategorised'
