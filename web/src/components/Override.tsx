import { useEffect, useRef, useState } from 'react'
import { bandOf } from '../lib/api'
import type { Decision, Ranking } from '../lib/types'

// The coordinator's `band` field carries the raw CPC code (1, 3, 2), not a
// name -- and CPC 3 outranks CPC 2, so the number is actively misleading on
// screen. Always resolve through bandOf().

/** The one modal in the product.
 *
 *  Interrupting dialogs are accepted far less often than non-interrupting ones,
 *  so there is exactly one, reserved for the thing a clinician must not do by
 *  accident: moving someone across a clinical category boundary. Every other
 *  action is inline.
 *
 *  RULE-ORDER says every Urgent is seen before every Semi-Urgent. The system
 *  cannot cross that boundary; a clinician can, but only deliberately and on
 *  the record, which is what rule_warning_accepted stores.
 */
const REASONS = [
  'Clinical information not in the record',
  'Patient contacted the service',
  'Capacity or scheduling constraint',
  'Reviewed and the order looks right',
  'Other (described below)',
]

export function Override({ patient, decision, onClose, onDone }: {
  patient: Ranking
  decision: Decision
  onClose: () => void
  onDone: (msg: string) => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const [to, setTo] = useState(String(patient.position))
  const [reason, setReason] = useState(REASONS[0])
  const [detail, setDetail] = useState('')
  const [clinician, setClinician] = useState('clinician-01')
  const [accepted, setAccepted] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => { ref.current?.showModal() }, [])

  const target = decision.rankings.find((r) => r.position === Number(to))
  const fromBand = bandOf(patient.cpc)
  const movingTo = target ? bandOf(target.cpc) : fromBand
  const crosses = !!target && bandOf(target.cpc) !== fromBand
  const isAccept = Number(to) === patient.position
  const needsAttest = crosses && !accepted

  async function submit() {
    setBusy(true); setErr(null)
    try {
      const r = await fetch('/api/overrides', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          override_id: `ovr-${crypto.randomUUID()}`,
          decision_id: decision.decision_id,
          hospital_hipe: patient.hospital_hipe,
          pathway_number: patient.pathway_number,
          clinician_id: clinician,
          from_position: patient.position,
          to_position: Number(to),
          reason: isAccept && reason === REASONS[3]
            ? `ACCEPTED: position confirmed. ${detail}`.trim()
            : `${reason}${detail ? `. ${detail}` : ''}`,
          rule_warning_accepted: crosses,
        }),
      })
      if (!r.ok) throw new Error(`the service rejected it (${r.status})`)
      onDone(isAccept
        ? `Position ${patient.position} confirmed and recorded.`
        : `Moved from ${patient.position} to ${to}, recorded.`)
      ref.current?.close(); onClose()
    } catch (e) {
      setErr(String(e)); setBusy(false)
    }
  }

  return (
    <dialog ref={ref} className="ovr" onCancel={onClose} onClose={onClose}>
      <h2 className="ovr-h">{isAccept ? 'Confirm this position' : 'Move this referral'}</h2>
      <p className="ovr-sub num">
        {patient.pathway_number} &middot; currently position {patient.position} of {decision.rankings.length} &middot; {fromBand}
      </p>

      <label className="ovr-f">
        <span className="ovr-l">Position</span>
        <input className="ovr-in num" type="number" min={1} max={decision.rankings.length}
               value={to} onChange={(e) => setTo(e.target.value)} />
        <span className="ovr-hint">
          {isAccept ? 'unchanged — this records that you reviewed and agreed'
            : `moving into ${movingTo}`}
        </span>
      </label>

      {crosses && (
        <div className="ovr-warn">
          <strong>This crosses a clinical category boundary.</strong>
          <p>
            {fromBand} referrals are seen before {movingTo} ones. The system will not make
            this move; you can, and it is recorded as your decision, not the system's.
          </p>
          <label className="ovr-attest">
            <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} />
            <span>I understand and am making this change deliberately.</span>
          </label>
        </div>
      )}

      <label className="ovr-f">
        <span className="ovr-l">Reason</span>
        <select className="ovr-in" value={reason} onChange={(e) => setReason(e.target.value)}>
          {REASONS.map((r) => <option key={r}>{r}</option>)}
        </select>
      </label>

      <label className="ovr-f">
        <span className="ovr-l">Detail <span className="ovr-opt">optional</span></span>
        <textarea className="ovr-in ovr-ta" rows={2} value={detail}
                  onChange={(e) => setDetail(e.target.value)}
                  placeholder="Anything a colleague reading this later would need to know" />
      </label>

      <label className="ovr-f">
        <span className="ovr-l">Recorded as</span>
        <input className="ovr-in" value={clinician} onChange={(e) => setClinician(e.target.value)} />
        <span className="ovr-hint">Attribution, not authentication: this says who typed it, it does not verify them.</span>
      </label>

      {err && <div className="err ovr-err">{err}</div>}

      <div className="ovr-actions">
        <button className="pg" onClick={() => { ref.current?.close(); onClose() }} disabled={busy}>Cancel</button>
        <button className="run-btn ovr-go" onClick={submit} disabled={busy || needsAttest || !reason}>
          {busy ? 'Recording…' : isAccept ? 'Confirm and record' : 'Move and record'}
        </button>
      </div>
    </dialog>
  )
}
