import { useEffect, useState } from 'react'

/** True while the viewport is too narrow for the ranked table's full column set.
 *
 *  The rehearsal machine is 1280x800. With the rail collapsed to 64px that
 *  leaves ~1184px of content, and the table's fixed columns alone come to
 *  ~1154px before the elastic Referral column gets anything — so two columns
 *  have to go rather than the table growing a horizontal scrollbar and cutting
 *  340px off the right-hand side.
 *
 *  Done in React rather than CSS because the table is `table-layout: fixed` with
 *  a <colgroup>: hiding a <td> while its <col> and <th> remain would misalign
 *  every row.
 */
export function useNarrow(px = 1440): boolean {
  const [narrow, setNarrow] = useState(
    () => typeof window !== 'undefined' && window.innerWidth < px)
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${px - 1}px)`)
    const on = () => setNarrow(mq.matches)
    on()
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [px])
  return narrow
}
