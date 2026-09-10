import { useEffect, useState } from 'react'

/** True while the viewport is narrower than a width the CALLER names.
 *
 *  The hook holds no breakpoint of its own. surfaces/List.tsx passes
 *  NINE_COL_PX, the width at which the ranked table's nine columns first fit:
 *  the fixed COL widths plus Referral's floor, plus the rail and the page
 *  padding. That number is arithmetic and moves whenever a column does, so it
 *  is stated once at the table and read here rather than restated in this
 *  docstring, where it has already gone stale twice. The `px` default is only a
 *  fallback for a call site that names no width; no call site relies on it.
 *
 *  Done in React rather than CSS because the table is `table-layout: fixed`
 *  with a <colgroup>: hiding a <td> while its <col> and <th> remain would
 *  misalign every row.
 *
 *  BOTH the seed and the subscription come from matchMedia, deliberately.
 *  window.innerWidth INCLUDES a classic (space-taking) scrollbar and a media
 *  query EXCLUDES it, so on Windows and Linux the two disagree by the width of
 *  that scrollbar -- around 15px, and the gap straddles the threshold. Seeding
 *  from innerWidth and only correcting in the effect therefore painted one
 *  frame of nine columns at a width that fits seven, which is the overlapping
 *  cell this hook exists to prevent. One source, asked the same question every
 *  time, so the first paint is already right.
 */
const query = (px: number) => `(max-width: ${px - 1}px)`

export function useNarrow(px = 1440): boolean {
  const [narrow, setNarrow] = useState(
    () => typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      && window.matchMedia(query(px)).matches)
  useEffect(() => {
    const mq = window.matchMedia(query(px))
    const on = () => setNarrow(mq.matches)
    // px may have changed since the seed, and the viewport may have moved
    // between render and commit; re-reading the same query costs nothing.
    on()
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [px])
  return narrow
}
