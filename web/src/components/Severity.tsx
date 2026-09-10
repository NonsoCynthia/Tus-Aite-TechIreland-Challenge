import type { ReactNode } from 'react'
import type { Sev } from '../lib/severity'
import './severity.css'

/** The one severity primitive. Every attention state in the product renders
 *  through this, so a reader learns the scale once.
 *
 *  Two shapes, one scale:
 *    <SevChip>  a filled block carrying a value. The distance channel.
 *    <SevBar>   a magnitude drawn against a track, with the same four steps.
 *
 *  The value is ALWAYS rendered. Colour is never the only channel, both because
 *  WCAG 2.2 SC 1.4.1 requires it and because a filled block with no number
 *  tells a clinician nothing they can act on.
 */
export function SevChip({ sev, children, title, tone = 'fill' }: {
  sev: Sev
  children: ReactNode
  title?: string
  /** `fill` escalates to a solid block at 3 and 4 -- the default, and what
   *  makes severity readable across a room. `quiet` keeps the hairline at every
   *  step, for places where a solid block would be the loudest thing on a
   *  surface that has something louder to say. */
  tone?: 'fill' | 'quiet'
}) {
  if (sev === 0) return <>{children}</>
  return (
    <span className={`sev sev-${sev} sev-${tone}`} title={title} data-sev={sev}>
      {children}
    </span>
  )
}

/** A magnitude against a track. `of` is where the reference line sits, as a
 *  fraction, so the eye reads "past this point" rather than a bare length. */
export function SevBar({ sev, value, of, label, height = 6 }: {
  sev: Sev
  /** 0..1 of the track, already clamped by the caller. */
  value: number
  /** 0..1, where the threshold line is drawn. Omit for no line. */
  of?: number
  label?: string
  height?: number
}) {
  return (
    <span className="sevbar" style={{ height }} role="img" aria-label={label}
          data-sev={sev}>
      <i className="sevbar-f" style={{ width: `${Math.max(0, Math.min(100, value * 100))}%` }} />
      {of != null && (
        <i className="sevbar-m" style={{ left: `${Math.max(0, Math.min(100, of * 100))}%` }} />
      )}
    </span>
  )
}
