/** The reference layer, as lookups.
 *
 *  Everything here used to be substituted for in the frontend: specialty codes
 *  were printed raw ("specialty 0600"), the CRT thresholds were hardcoded as 28
 *  and 91 in api.ts, and the five rule statements existed only in seed data. A
 *  change to core.ref_* would have desynced the product silently.
 *
 *  Every helper takes `Reference | undefined` and degrades to something true
 *  rather than wrong: an unresolved specialty renders as its code, not as a
 *  guess, and a rule with no statement renders as its ID.
 */
import type { Reference, RuleCheck } from './types'

export const specialtyName = (ref: Reference | undefined, code: string | null): string => {
  if (!code) return 'unrecorded'
  return ref?.specialties.find((s) => s.specialty_hipe === code)?.specialty_name ?? code
}

/** "Otolaryngology (ENT) · 0600" — the name a clinician recognises, with the
 *  code they will see on the actual record. */
export const specialtyFull = (ref: Reference | undefined, code: string | null): string => {
  if (!code) return 'unrecorded'
  const n = ref?.specialties.find((s) => s.specialty_hipe === code)?.specialty_name
  return n ? `${n} · ${code}` : `specialty ${code}`
}

export const isPaediatric = (ref: Reference | undefined, code: string | null): boolean =>
  !!ref?.specialties.find((s) => s.specialty_hipe === code)?.is_paediatric

/** Authoritative CRT days from core.ref_codes, keyed by raw CPC code. Null is a
 *  real answer for Routine and Uncategorised: 143 of 308 have no target at all,
 *  so nothing in those groups can be "late". */
export const crtDays = (ref: Reference | undefined, cpc: number | null): number | null => {
  if (cpc == null) return null
  return ref?.triage_categories.find((t) => t.code_value === String(cpc))?.crt_days ?? null
}

export const rule = (ref: Reference | undefined, id: string) =>
  ref?.rules.find((r) => r.rule_id === id)

export const ruleStatement = (ref: Reference | undefined, id: string): string =>
  rule(ref, id)?.statement ?? id

/** How a rule check reads on screen. `detail` is already human-readable from the
 *  coordinator — "urgent, day 152 of 28, over by 124" — so it is shown verbatim
 *  rather than re-worded, and the rule ID always travels with it. */
export const checkLabel = (c: RuleCheck): string =>
  c.detail ? `${c.rule_id} · ${c.detail}` : c.rule_id

export const failed = (checks: RuleCheck[] | undefined): RuleCheck[] =>
  (checks ?? []).filter((c) => !c.passed)

/** How a failed rule reads. A CRT rule is a target; the triage-turnaround rule
 *  is a window on how long a referral may sit untriaged, and the referral it
 *  fires on here has no CPC and no target at all — so calling it "past target"
 *  contradicts every other statement on the page about what can be late. */
export const breachPhrase = (ruleId: string, n: number): string =>
  ruleId.startsWith('RULE-CRT-')
    ? `${n.toLocaleString('en-IE')} past target`
    : `${n.toLocaleString('en-IE')} breached`
