/** The Tús Áite mark, drawn rather than loaded so it can animate.
 *  viewBox 0 0 52 70: a 5-wide stem at x=24, four 21x5 bars alternating sides.
 *  One bar is clay rather than navy on purpose -- the kit's clay means "the one
 *  being seen next" -- so the mark reads as a waiting list. */
const BARS = [
  { x: 29, y: 10, accent: true },
  { x: 3,  y: 26, accent: false },
  { x: 29, y: 42, accent: false },
  { x: 3,  y: 55, accent: false },
]

export function Mark({ size = 28, tone = 'navy', draw = false }: {
  size?: number; tone?: 'navy' | 'white'; draw?: boolean
}) {
  const stem = tone === 'white' ? '#FAFAF8' : '#122056'
  const accent = tone === 'white' ? '#C4B6A6' : '#7A5B4D'
  return (
    <svg width={(size * 52) / 70} height={size} viewBox="0 0 52 70"
         role="img" aria-label="Tús Áite" style={{ display: 'block', flex: 'none' }}>
      <rect x="24" y="0" width="5" height="70" fill={stem}
            style={draw ? { transformOrigin: '26px 0px', animation: 'markStem 520ms var(--ease) both' } : undefined} />
      {BARS.map((b, i) => (
        <rect key={i} x={b.x} y={b.y} width="21" height="5"
              fill={b.accent ? accent : stem}
              style={draw ? {
                transformOrigin: `${b.x < 24 ? 24 : 29}px ${b.y}px`,
                animation: `markBar 380ms var(--ease) ${340 + i * 95}ms both`,
              } : undefined} />
      ))}
    </svg>
  )
}
