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

export interface Citation { evidence_type: string; evidence_key: string }

/** One rule the coordinator tested against this referral.
 *  All five live in core.ref_rules; `detail` is already human-readable, e.g.
 *  "urgent, day 152 of 28, over by 124". */
export interface RuleCheck {
  rule_id: 'RULE-CRT-URGENT' | 'RULE-CRT-SEMI' | 'RULE-TRIAGE-TURNAROUND'
         | 'RULE-ORDER' | 'RULE-TIEBREAK' | string
  passed: boolean
  detail: string | null
}

/** A ranked placement, as the coordinator produced it and the orchestrator holds it. */
export interface Ranking extends CohortReferral {
  position: number
  /** RAW CPC CODE, not a name. Always resolve through bandOf(). */
  band: string
  severity_rank: number | null
  urgency_score: number
  /** Specialty-level, identical for every referral in a specialty. It sets
   *  alpha for the whole hospital-day and can never reorder two people. */
  capacity_score: number
  wait_normalised: number
  priority: number
  alpha: number
  scarcity: number
  run_id: string
  /** Present on every row. The two agents' own citations, ride-along since the
   *  first run; the UI simply never declared them. Six urgency (one per NEWS2
   *  vital, zeros included), one or two capacity. */
  urgency_citations: Citation[]
  capacity_citations: Citation[]
  /** The coordinator's own deterministic note. Not the LLM rationale — that is
   *  another track's unbuilt feature. */
  rationale_summary: string | null
  /** 2-5 per referral. Computed since the first run and dropped before the UI
   *  saw them until the orchestrator merged them back. */
  rule_checks: RuleCheck[]
  /** What the capacity agent computed on its way to a score. Neither reaches
   *  Postgres or the graph — POST /scores carries only the score — so this is
   *  harvested from the agent pass, the way news2 is. */
  capacity_detail: { ward_pressure: number | null; clinic_pressure: number | null } | null
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


/** The reference layer, from core.ref_*. The UI hardcoded 28 and 91 and printed
 *  bare HIPE codes because retrieval exposes no endpoint for these. */
export interface Reference {
  specialties: Array<{ specialty_hipe: string; specialty_name: string; is_paediatric: boolean }>
  /** Authoritative severity_rank and crt_days. Never hardcode these again. */
  triage_categories: Array<{
    code_value: string; description: string
    severity_rank: number | null; crt_days: number | null
  }>
  rules: Array<{
    rule_id: string; statement: string; applies_to: string; threshold_days: number | null
  }>
  codes: Array<{ code_table: string; code_value: string; description: string }>
}

/** What a clinician actually did. Written since the first build, readable only
 *  since the orchestrator gained a read path. */
export interface OverrideRecord {
  override_id: string
  decision_id: string
  pathway_number: string
  clinician_id: string
  from_position: number | null
  to_position: number | null
  reason: string
  rule_warning_accepted: boolean
  created_at: string
}
export interface Overrides {
  hospital_hipe: string
  as_of_date: string
  /** Newest first, full history. */
  overrides: OverrideRecord[]
  /** The one that stands, per pathway. */
  current: Record<string, OverrideRecord>
}

/** The whole decision as a graph, from one SPARQL query over the run graph. */
export interface GraphNode {
  id: string; label: string
  kind: 'decision' | 'placement' | 'score' | 'referral_state' | 'bed_status'
      | 'clinic_session' | 'condition' | 'triage_event' | 'obs' | 'rule' | 'evidence'
  cites: number
  position?: number
  pathway?: string
}
export interface GraphEdge {
  source: string; target: string
  label: 'hasPlacement' | 'urgency' | 'capacity' | 'timeframe' | 'multi_list'
}
export interface CohortGraph {
  run_id: string
  graph: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  placements: number
  /** Role-tagged edges from placements. NOT a citation count: six cited vitals
   *  arrive as one link to the urgency score, and timeframe links cover rules
   *  and referral states, which are not evidence. */
  evidence_links: number
  /** False on this machine: the batch KG was never loaded, so a cited node has
   *  an identity and a type but no resolved property values. Say so on screen
   *  rather than implying the graph knows more than it does. */
  inputs_graph_loaded: boolean
}
