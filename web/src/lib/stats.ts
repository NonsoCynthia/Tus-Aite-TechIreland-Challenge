/** Arithmetic shared by more than one surface, so two surfaces can never print
 *  two different answers to the same question. Nothing here grades or decides. */

/** Median wait, in days. ONE convention: on an even n the mean of the two middle
 *  values, ROUNDED -- waits are whole numbers, so two an odd distance apart
 *  average to a half-day. Overview.tsx and List.tsx both import this; a second
 *  copy is how they come to print different medians. ops.observation_age.median
 *  is the API's own median of another quantity. See BUILD_LEDGER.md. */
export function median(xs: number[]): number {
  if (!xs.length) return 0
  const s = [...xs].sort((a, b) => a - b)
  const n = s.length
  return n % 2 ? s[(n - 1) / 2] : Math.round((s[n / 2 - 1] + s[n / 2]) / 2)
}
