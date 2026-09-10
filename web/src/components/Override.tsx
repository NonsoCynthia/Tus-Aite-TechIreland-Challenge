import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
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
 *
 *  Two things changed here.
 *
 *  The write used to end in a flash message that died on the next navigation,
 *  because nothing could read an override back. GET /overrides exists now, so a
 *  successful POST invalidates ['overrides', hospital, date] and the list
 *  re-reads it: the row moves, keeps a badge naming who moved it and why, and
 *  goes on showing the position the system gave it.
 *
 *  And rule_warning_accepted used to be sent as `crosses` -- the app's own
 *  comparison of the two bands -- while the checkbox only gated the submit
 *  button. The stored attestation was therefore the system's opinion of what
 *  the clinician had done, not the clinician's. It now sends the checkbox.
 */
const REASONS = [
  'Clinical information not in the record',
  'Patient contacted the service',
  'Capacity or scheduling constraint',
  'Reviewed and the order looks right',
  'Other (described below)',
]

export function Override({ patient, decision, displayedOrder, onClose, onDone }: {
  patient: Ranking
  decision: Decision
  /** Pathway numbers in the order actually ON SCREEN: the coordinator's, with
   *  every live override already spliced in. The boundary check must ask about
   *  this list, not about decision.rankings: after one override, position N in
   *  what the clinician sees is a different person. */
  displayedOrder?: string[]
  onClose: () => void
  onDone: (msg: string) => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const qc = useQueryClient()
  const [to, setTo] = useState(String(patient.position))
  const [reason, setReason] = useState(REASONS[0])
  const [detail, setDetail] = useState('')
  const [clinician, setClinician] = useState('clinician-01')
  const [accepted, setAccepted] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => { ref.current?.showModal() }, [])

  const byPathway = new Map(decision.rankings.map((r) => [r.pathway_number, r]))
  // position N in the DISPLAYED list, falling back to the coordinator's own
  // order when no displayed order was supplied
  const targetPw = displayedOrder?.[Number(to) - 1]
  const target = targetPw
    ? byPathway.get(targetPw)
    : decision.rankings.find((r) => r.position === Number(to))
  const fromBand = bandOf(patient.cpc)
  const movingTo = target ? bandOf(target.cpc) : fromBand
  const crosses = !!target && bandOf(target.cpc) !== fromBand
  const isAccept = Number(to) === patient.position
  const needsAttest = crosses && !accepted

  // An attestation belongs to the move it was made for. Editing the position
  // back inside the band retires it, so a tick can never be carried over and
  // stored against a move that never crossed anything.
  useEffect(() => { if (!crosses) setAccepted(false) }, [crosses])

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
          // what the clinician actually attested, not what the app inferred
          rule_warning_accepted: accepted,
        }),
      })
      if (!r.ok) throw new Error(`the service rejected it (${r.status})`)
      // the list reads overrides from here; without this the row would keep
      // showing the system's order until a full reload
      await qc.invalidateQueries({
        queryKey: ['overrides', decision.hospital_hipe, decision.as_of_date],
      })
      onDone(isAccept
        ? `Position ${patient.position} confirmed and recorded. ${patient.pathway_number} keeps its place.`
        : `${patient.pathway_number} moved from ${patient.position} to ${to}, recorded as ${clinician}. The system's position stays on the row.`)
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
          {isAccept ? 'unchanged. this records that you reviewed and agreed'
            : `moving into ${movingTo}`}
        </span>
      </label>

      {crosses && (
        <div className="ovr-warn">
          <strong>This crosses a clinical category boundary.</strong>
          <p>
            {fromBand} referrals are seen before {movingTo} ones. The system will not make
            this move; you can, and it is recorded against the name above.
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
        <span className="ovr-l">Record this against</span>
        <input className="ovr-in" value={clinician} onChange={(e) => setClinician(e.target.value)} />
      </label>

      <p className="ovr-hint ovr-after">
        {isAccept
          ? <>Nothing moves. The list will show this position as confirmed, against the name above.</>
          : <>The row moves to position {to || '—'} in the list and carries the name typed above and reason.
            The position the system gave it (<span className="num">{patient.position}</span>)
            stays on the row, so a colleague can see both.</>}
      </p>

      {err && <div className="err ovr-err">{err}</div>}

      <div className="ovr-actions">
        <button className="pg" onClick={() => { ref.current?.close(); onClose() }} disabled={busy}>Cancel</button>
        <button className="cta ovr-go" onClick={submit} disabled={busy || needsAttest || !reason}>
          {busy ? 'Recording…' : isAccept ? 'Confirm and record' : 'Move and record'}
        </button>
      </div>
    </dialog>
  )
}
