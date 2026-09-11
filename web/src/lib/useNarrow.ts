import { useEffect, useState } from 'react'

/** True while the viewport is narrower than a width the CALLER names -- no
 *  breakpoint of its own: List.tsx passes NINE_COL_PX, arithmetic over that
 *  table's own columns, so it is stated there and never restated here. React
 *  rather than CSS because the table is `table-layout: fixed` with a <colgroup>:
 *  hiding a <td> while its <col> and <th> remain misaligns every row. */
const query = (px: number) => `(max-width: ${px - 1}px)`

export function useNarrow(px = 1440): boolean {
  // Seed AND subscription from matchMedia, deliberately: window.innerWidth
  // INCLUDES a classic scrollbar and a media query EXCLUDES it, so they disagree
  // by ~15px -- enough to paint one frame of nine columns at a seven-column width.
  const [narrow, setNarrow] = useState(
    () => typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      && window.matchMedia(query(px)).matches)
  useEffect(() => {
    const mq = window.matchMedia(query(px))
    const on = () => setNarrow(mq.matches)
    // px may have changed since the seed, and the viewport may have moved
    // between render and commit.
    on()
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [px])
  return narrow
}
