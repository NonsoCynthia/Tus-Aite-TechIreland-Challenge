/** The Tús Áite mark, drawn rather than loaded, so it can animate.
    viewBox 0 0 52 70: a 5-wide stem at x=24 with four 21x5 bars alternating
    left and right. Those four bars are the same object as the rank spine. */
export function Mark({ size = 28, color = 'currentColor', draw = false }: {
  size?: number; color?: string; draw?: boolean
}) {
  const bars = [
    { x: 29, y: 10 }, { x: 3, y: 26 }, { x: 29, y: 42 }, { x: 3, y: 55 },
  ]
  return (
    <svg width={(size * 52) / 70} height={size} viewBox="0 0 52 70" aria-hidden="true"
         style={{ display: 'block', flex: 'none' }}>
      <rect x="24" y="0" width="5" height="70" fill={color}
            style={draw ? { transformOrigin: '26px 0', animation: 'markStem 520ms var(--ease) both' } : undefined} />
      {bars.map((b, i) => (
        <rect key={i} x={b.x} y={b.y} width="21" height="5" fill={color}
              style={draw ? {
                transformOrigin: `${b.x < 24 ? 24 : 29}px ${b.y}px`,
                animation: `markBar 380ms var(--ease) ${360 + i * 90}ms both`,
              } : undefined} />
      ))}
    </svg>
  )
}
