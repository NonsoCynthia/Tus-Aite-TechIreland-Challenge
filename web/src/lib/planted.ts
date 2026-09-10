/** The eight planted cases, and what each one is for.
 *
 *  `dataset/tests/test_planted_cases.py` opens with: *"The seven demo cases must
 *  exist at fixed pathway numbers in every run. Random sampling will not
 *  reliably produce them and the demo depends on them."* They are deliberate
 *  fixtures from the dataset track, each planted to exercise a specific rule or
 *  edge, and every one of them is inside the 308.
 *
 *  Unlabelled they read as leftover test data in the middle of a clinical list —
 *  which is the first thing a reviewer would challenge. Labelled, they are the
 *  cases worth pointing at, because each one is a claim the system can be tested
 *  against. Sources are named so nobody has to take this on trust.
 */
export interface Planted { what: string; why: string; source: string }

export const PLANTED: Record<string, Planted> = {
  'PW-DEMO-01': {
    what: 'Urgent, past its timeframe',
    why: 'Planted to breach the 28-day urgent CRT, so RULE-CRT-URGENT always has something to fire on.',
    source: 'dataset/tests/test_planted_cases.py::test_demo_01_is_urgent_and_past_its_timeframe',
  },
  'PW-DEMO-02': {
    what: 'Semi-Urgent, 13-week timeframe',
    why: 'The Semi-Urgent counterpart, so RULE-CRT-SEMI is exercised on every run.',
    source: 'dataset/generator/generate.py',
  },
  'PW-DEMO-03': {
    what: 'Urgent pathway, unremarkable physiology',
    why: 'The thesis case. Vitals alone do not identify urgency — a suspected melanoma is urgent because of the pathway, not the physiology. Planted with NEWS2 ≤ 2.',
    source: 'dataset/tests/test_planted_cases.py::test_demo_03_is_urgent_with_normal_vitals',
  },
  'PW-DEMO-04': {
    what: 'No category recorded',
    why: 'Uncategorised, so nothing can be measured against a timeframe.',
    source: 'dataset/generator/generate.py',
  },
  'PW-DEMO-05': {
    what: 'The invisible population',
    why: 'Awaiting triage with no category, so no timeframe to breach — and the only referral in this hospital-day that RULE-TRIAGE-TURNAROUND fires on.',
    source: 'dataset/tests/test_planted_cases.py::test_demo_05_is_awaiting_triage_with_no_category',
  },
  'PW-DEMO-06': {
    what: 'On two hospitals’ lists',
    why: 'One of a pair planted across 9001 and 9002, so a person waiting in two places is representable.',
    source: 'dataset/tests/test_planted_cases.py::test_demo_06_and_07_span_two_public_hospitals',
  },
  'PW-DEMO-07': {
    what: 'On two hospitals’ lists',
    why: 'The other half of the multi-list pair.',
    source: 'dataset/tests/test_planted_cases.py::test_demo_06_and_07_span_two_public_hospitals',
  },
  'PW-COLLIDE-01': {
    what: 'The same number at two hospitals',
    why: 'A deliberate pathway-number collision across 9001 and 9002: it proves pathway_number alone is not a key and every join has to be on (hospital, pathway).',
    source: 'dataset/tests/test_sample_closure.py::test_sample_has_cross_hospital_collision',
  },
}

export const plantedCase = (pathway: string): Planted | undefined => PLANTED[pathway]
