/** NEWS2 scoring bands, so a vital can be drawn against the scale that judged it.
 *
 *  Mirrors urgency-agent/urgency_agent/news2.py. The agent is the authority; this
 *  exists so the UI can SHOW why a reading scored what it scored instead of
 *  printing a total and a sentence telling the reader to add six numbers by hand.
 *
 *  Royal College of Physicians, National Early Warning Score (NEWS) 2, 2017.
 *  Six parameters, 0-3 each, plus a scale-2 oxygen row this dataset never uses.
 */
export interface Band { lo: number | null; hi: number | null; score: 0 | 1 | 2 | 3 }

export interface Vital {
  key: 'rr' | 'spo2' | 'sbp' | 'hr' | 'avpu' | 'temp'
  label: string
  short: string
  unit: string
  /** The span the meter draws across. Chosen to hold every band edge plus a
   *  little air, so the scale is honest rather than cropped to the reading. */
  axis: [number, number]
  bands: Band[]
  /** Where a well person sits. Drawn as the calm region on the meter. */
  normal: [number, number]
}

export const VITALS: Vital[] = [
  {
    key: 'rr', label: 'Respiratory rate', short: 'Resp', unit: '/min', axis: [4, 32],
    normal: [12, 20],
    bands: [
      { lo: null, hi: 8, score: 3 }, { lo: 9, hi: 11, score: 1 },
      { lo: 12, hi: 20, score: 0 }, { lo: 21, hi: 24, score: 2 },
      { lo: 25, hi: null, score: 3 },
    ],
  },
  {
    key: 'spo2', label: 'Oxygen saturation', short: 'SpO₂', unit: '%', axis: [88, 100],
    normal: [96, 100],
    bands: [
      { lo: null, hi: 91, score: 3 }, { lo: 92, hi: 93, score: 2 },
      { lo: 94, hi: 95, score: 1 }, { lo: 96, hi: null, score: 0 },
    ],
  },
  {
    key: 'sbp', label: 'Systolic blood pressure', short: 'Systolic', unit: 'mmHg',
    axis: [80, 230], normal: [111, 219],
    bands: [
      { lo: null, hi: 90, score: 3 }, { lo: 91, hi: 100, score: 2 },
      { lo: 101, hi: 110, score: 1 }, { lo: 111, hi: 219, score: 0 },
      { lo: 220, hi: null, score: 3 },
    ],
  },
  {
    key: 'hr', label: 'Heart rate', short: 'Pulse', unit: 'bpm', axis: [35, 140],
    normal: [51, 90],
    bands: [
      { lo: null, hi: 40, score: 3 }, { lo: 41, hi: 50, score: 1 },
      { lo: 51, hi: 90, score: 0 }, { lo: 91, hi: 110, score: 1 },
      { lo: 111, hi: 130, score: 2 }, { lo: 131, hi: null, score: 3 },
    ],
  },
  {
    key: 'avpu', label: 'Consciousness', short: 'AVPU', unit: '', axis: [0, 1],
    normal: [0, 0], bands: [],
  },
  {
    key: 'temp', label: 'Temperature', short: 'Temp', unit: '°C', axis: [34, 40],
    normal: [36.1, 38.0],
    bands: [
      { lo: null, hi: 35.0, score: 3 }, { lo: 35.1, hi: 36.0, score: 1 },
      { lo: 36.1, hi: 38.0, score: 0 }, { lo: 38.1, hi: 39.0, score: 1 },
      { lo: 39.1, hi: null, score: 2 },
    ],
  },
]

/** AVPU is categorical: Alert scores 0, anything else scores 3. */
export function scoreOf(key: Vital['key'], value: number | string | null | undefined): number | null {
  if (value == null || value === '') return null
  if (key === 'avpu') return String(value).toUpperCase() === 'A' ? 0 : 3
  const v = typeof value === 'string' ? parseFloat(value) : value
  if (Number.isNaN(v)) return null
  const vital = VITALS.find((x) => x.key === key)
  if (!vital) return null
  for (const b of vital.bands) {
    if ((b.lo == null || v >= b.lo) && (b.hi == null || v <= b.hi)) return b.score
  }
  return null
}

/** Position on the meter, 0-1, clamped. A reading past the axis pins to the end
 *  and the value is still printed, so an off-scale number is never hidden. */
export function positionOf(vital: Vital, value: number): number {
  const [lo, hi] = vital.axis
  return Math.max(0, Math.min(1, (value - lo) / (hi - lo)))
}
