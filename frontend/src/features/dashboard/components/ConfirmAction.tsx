import type { ApiErrorBody, PredictResponse } from '../../../lib/api/types'

export interface ConfirmSafetyState {
  blocked: boolean
  reason: string | null
  ackRequired: boolean
  demoBlocked: boolean
}

interface ConfirmActionProps {
  prediction: PredictResponse | null
  isConfirming: boolean
  rejection: ApiErrorBody | null
  ackOverride: boolean
  onAckOverrideChange: (value: boolean) => void
  onConfirm: () => void
}

export function ConfirmAction({ prediction, isConfirming, rejection, ackOverride, onAckOverrideChange, onConfirm }: ConfirmActionProps) {
  const safety = getConfirmSafetyState(prediction)
  const disabled = isConfirming || safety.blocked || (safety.ackRequired && !ackOverride)

  return (
    <div className="action-panel">
      {safety.reason ? <p className="section-copy">{safety.reason}</p> : null}
      {rejection ? <p className="section-copy" role="alert">{rejection.message}</p> : null}
      {safety.ackRequired ? (
        <label className="section-copy">
          <input type="checkbox" checked={ackOverride} onChange={(event) => onAckOverrideChange(event.target.checked)} /> Acknowledge degraded prediction override
        </label>
      ) : null}
      <button className="btn primary" type="button" disabled={disabled} onClick={onConfirm}>
        {isConfirming ? 'Confirming...' : safety.blocked ? 'Confirm blocked by safety gate' : 'Confirm irrigation'}
      </button>
    </div>
  )
}

export function getConfirmSafetyState(prediction: PredictResponse | null): ConfirmSafetyState {
  if (!prediction) {
    return { blocked: true, reason: 'Confirm blocked: no recent prediction.', ackRequired: false, demoBlocked: false }
  }
  if (typeof prediction.trace_id === 'string' && prediction.trace_id.startsWith('demo-')) {
    return { blocked: true, reason: 'Confirm blocked: demo prediction cannot be sent.', ackRequired: false, demoBlocked: true }
  }
  if (prediction.uncertainty > 0.3) {
    return { blocked: true, reason: 'Confirm blocked: prediction uncertainty is above 0.30.', ackRequired: false, demoBlocked: false }
  }
  if (prediction.degraded_mode) {
    return { blocked: false, reason: 'Degraded prediction requires acknowledgement.', ackRequired: true, demoBlocked: false }
  }
  return { blocked: false, reason: null, ackRequired: false, demoBlocked: false }
}
