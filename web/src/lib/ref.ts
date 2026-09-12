/** The reference layer, as lookups. Never substitute a hardcoded CRT threshold
 *  or specialty name for these: it desyncs from core.ref_* silently. Every
 *  helper takes `Reference | undefined` and degrades to something true rather
 *  than wrong -- an unresolved specialty renders as its code, not a guess. */
import type { Reference, RuleCheck } from './types'

export const specialtyName = (ref: Reference | undefined, code: string | null): string => {
  if (!code) return 'unrecorded'
  return ref?.specialties.find((s) => s.specialty_hipe === code)?.specialty_name ?? code
}

/** "Otolaryngology (ENT) · 0600" — the name, with the code on the record. */
export const specialtyFull = (ref: Reference | undefined, code: string | null): string => {
  if (!code) return 'unrecorded'
  const n = ref?.specialties.find((s) => s.specialty_hipe === code)?.specialty_name
  return n ? `${n} · ${code}` : `specialty ${code}`
}

export const isPaediatric = (ref: Reference | undefined, code: string | null): boolean =>
  !!ref?.specialties.find((s) => s.specialty_hipe === code)?.is_paediatric

/** Authoritative CRT days from core.ref_codes, keyed by raw CPC code. Null is a
 *  real answer for Routine and Uncategorised: nothing there can be "late". */
export const crtDays = (ref: Reference | undefined, cpc: number | null): number | null => {
  if (cpc == null) return null
  return ref?.triage_categories.find((t) => t.code_value === String(cpc))?.crt_days ?? null
}

export const rule = (ref: Reference | undefined, id: string) =>
  ref?.rules.find((r) => r.rule_id === id)

export const ruleStatement = (ref: Reference | undefined, id: string): string =>
  rule(ref, id)?.statement ?? id

/** `detail` is already human-readable from the coordinator ("urgent, day 152 of
 *  28, over by 124"), so it is shown verbatim and the rule ID travels with it. */
export const checkLabel = (c: RuleCheck): string =>
  c.detail ? `${c.rule_id} · ${c.detail}` : c.rule_id

export const failed = (checks: RuleCheck[] | undefined): RuleCheck[] =>
  (checks ?? []).filter((c) => !c.passed)

/** A CRT rule is a target; the triage-turnaround rule is a window and fires on
 *  referrals with no CPC and no target at all, so "past target" would contradict
 *  what the rest of the page says can be late. */
export const breachPhrase = (ruleId: string, n: number): string =>
  ruleId.startsWith('RULE-CRT-')
    ? `${n.toLocaleString('en-IE')} past target`
    : `${n.toLocaleString('en-IE')} breached`


/** Refused by the urgency agent: `urgency-agent/urgency_agent/scoring.py:88`,
 *  tested at `:207` against the referral's OWN specialty. ADR-007 refuses it
 *  unconditionally because NEWS2 is validated in adults. A property of the
 *  SPECIALTY, not of a run -- `decision.refused_paediatric` exists only after a
 *  run and /api/decision 404s on most hospital-days, so derive it here and union
 *  the decision's list on top. */
export const PAEDIATRIC_SPECIALTY = '0601'

export const isRefusedPaediatric = (specialtyHipe: string | null | undefined): boolean =>
  specialtyHipe === PAEDIATRIC_SPECIALTY
