/* Hand-written. Every read handler in retrieval is annotated `-> dict[str, Any]`,
   so /openapi.json carries request schemas only and codegen buys nothing here. */

/** The 14 fields GET /hospitals/{h}/cohort/{date} actually returns. No vitals. */
export interface CohortReferral {
  hospital_hipe: string
  pathway_number: string
  specialty_hipe: string
  referral_date: string
  referral_received_date: string
  triage_status: string
  days_since_referral: number | null
  days_since_received: number | null
  days_awaiting_triage: number | null
  adjusted_wait_days: number | null
  currently_suspended: boolean | null
  /** NTPF clinical prioritisation category. 1 Urgent, 3 Semi-Urgent, 2 Routine, 4 Excluded, null uncategorised. */
  cpc: number | null
  /** null for Routine and Uncategorised: 143 of 308 have no target at all. */
  crt_threshold_days: number | null
  crt_breached: boolean | null
}

/** A ranked placement, as the coordinator produced it and the orchestrator holds it. */
export interface Ranking extends CohortReferral {
  position: number
  band: string
  severity_rank: number | null
  urgency_score: number
  capacity_score: number
  wait_normalised: number
  priority: number
  alpha: number
  scarcity: number
  run_id: string
  rationale_summary?: string
}

export interface Decision {
  decision_id: string
  run_id: string
  hospital_hipe: string
  as_of_date: string
  /** Weight on urgency. The rest goes to waiting time. Set once per hospital-day. */
  alpha: number
  scarcity: number
  /** Always "pressure" — ADR-007. Read as "availability" the whole system inverts. */
  capacity_direction: string
  rule_order_passed: boolean
  rule_tiebreak_passed: boolean
  rankings: Ranking[]
  excluded: Array<{ pathway_number: string; exclusion_reason: string }>
  /** Specialty 0601. A coverage statement, not a low position. */
  refused_paediatric: string[]
  skipped: string[]
  /** Harvested during the urgency pass: news2 is not in the cohort payload. */
  news2: Record<string, number | null>
  built_at: string
}

export type RunStatus =
  | 'queued' | 'scoring_urgency' | 'scoring_capacity' | 'ranking' | 'done' | 'failed'

export interface Run {
  run_id: string
  hospital_hipe: string
  as_of_date: string
  status: RunStatus
  cohort_size: number
  /** Rows actually committed to agent.agent_scores. Cannot advance without work. */
  scored: number
  /** cohort_size x 2: every referral is scored by both agents. */
  total: number
  urgency_scored: number
  capacity_scored: number
  refused_paediatric: number
  skipped: number
  ranked: number
  excluded: number
  alpha: number | null
  scarcity: number | null
  decision_id: string | null
  error: string | null
  started_at: string | null
  finished_at: string | null
}

export interface Observation {
  obs_datetime: string
  hr: number | null; sbp: number | null; dbp: number | null
  rr: number | null; spo2: number | null; temp: number | null
  pain: number | null; avpu: string | null
  news2: number | null
  mts_category: string | null
  icts_category: string | null
  chiefcomplaint: string | null
}

export interface ReferralContext {
  referral: Record<string, unknown>
  observations: Observation[]
  conditions: Array<{ icd10am_code: string; condition_label: string; is_primary: boolean }>
  triage_events: Array<{
    sent_for_triage_date: string | null; triage_date: string | null
    turnaround_days: number | null; triage_outcome: number | null; triage_category: number | null
  }>
  capacity?: unknown
}

/** Citations come from here, never GET /evidence: reads.py collapses repeated
    predicates, so a score citing six observations reads back as one. */
export interface ScoreEntry {
  score: number | string
  method: string
  agent_version: string
  citations: Array<{ evidence_type: string; evidence_key: string }>
}
export type ScoresByPathway = Record<string, Record<'urgency' | 'capacity', ScoreEntry>>
