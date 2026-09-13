import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Send, X } from 'lucide-react'
import { api } from '../lib/api'
import { Mark } from './Mark'
import './assistant-panel.css'

type Message = {
  id: number
  role: 'user' | 'assistant'
  text: string
  source?: { decision_id: string; run_id: string } | null
}

/** A question routed through generate_rationale takes about 20s, so this is
    deliberately well clear of that. It exists so a stalled request ends in a
    sentence the clinician can act on rather than in "Thinking" forever. */
const TIMEOUT_MS = 90_000

/** When the wait stops being ordinary and deserves an explanation. Counting
    questions come back in 1-4s; only the rationale path runs past this. */
const SLOW_MS = 6_000

/** The composer grows with the question instead of being a fixed box the
    clinician has to scroll inside. Past this it scrolls, so the log never
    collapses to nothing on a long paste. */
const COMPOSER_MAX_PX = 132

interface Props {
  hospital: string
  date: string
  pathway: string | null
}

export function AssistantPanel({ hospital, date, pathway }: Props) {
  const [open, setOpen] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [sending, setSending] = useState(false)
  const [slow, setSlow] = useState(false)

  const still = useReducedMotion()
  const logRef = useRef<HTMLDivElement>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const nextId = useRef(0)

  const scope = useMemo(
    () => pathway ? `${hospital} / ${date} / ${pathway}` : `${hospital} / ${date}`,
    [date, hospital, pathway],
  )

  // The answer used to land below the fold: the log scrolls, but nothing ever
  // scrolled it, so you asked a question and had to go looking for the reply.
  useEffect(() => {
    const el = logRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, sending, slow, open])

  // Two stages, both true. The second one turns a wait that looks broken into
  // one that is explained, which is the whole job an indeterminate spinner
  // fails at -- and DESIGN_PACK.md:1765 bans the spinner anyway.
  useEffect(() => {
    if (!sending) { setSlow(false); return }
    const timer = window.setTimeout(() => setSlow(true), SLOW_MS)
    return () => window.clearTimeout(timer)
  }, [sending])

  function grow(el: HTMLTextAreaElement | null) {
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, COMPOSER_MAX_PX)}px`
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, shift+enter breaks the line. The Send button stays, so this
    // is a shortcut rather than the only way through.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  function say(row: Omit<Message, 'id'>) {
    setMessages((rows) => [...rows, { ...row, id: nextId.current++ }])
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = question.trim()
    if (!text || sending) return

    setQuestion('')
    grow(composerRef.current)
    setSending(true)
    say({ role: 'user', text })

    const abort = new AbortController()
    const timer = window.setTimeout(() => abort.abort(), TIMEOUT_MS)
    try {
      const reply = await api.chat({
        question: text,
        session_id: sessionId,
        hospital_hipe: hospital,
        as_of_date: date,
        pathway_number: pathway,
      }, abort.signal)
      setSessionId(reply.session_id)
      say({ role: 'assistant', text: reply.answer, source: reply.source })
    } catch (error) {
      // A slow answer and an unreachable service are not the same failure, and
      // saying the assistant could not be reached when it simply took too long
      // sends someone to check the network for a problem that is not there.
      const timedOut = error instanceof DOMException && error.name === 'AbortError'
      say({
        role: 'assistant',
        text: timedOut
          ? 'That question took too long to answer, so I stopped waiting. Nothing was changed. A narrower question, naming one referral, usually comes back quickly.'
          : 'The assistant could not be reached.',
      })
    } finally {
      window.clearTimeout(timer)
      setSending(false)
    }
  }

  const fade = { duration: still ? 0 : 0.16 }
  const rise = { duration: still ? 0 : 0.2 }

  return (
    <>
      <AnimatePresence initial={false}>
        {!open && (
          <motion.button
            key="assistant-launcher"
            className="assistant-launcher"
            onClick={() => setOpen(true)}
            aria-label="Open Tus assistant"
            initial={still ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={fade}
          >
            <span className="assistant-person">
              <Mark size={22} tone="white" />
            </span>
            <span className="assistant-bubble">I am Tus, here to answer your questions</span>
          </motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence initial={false}>
        {open && (
          <motion.aside
            key="assistant-panel"
            className="assistant-panel"
            aria-label="AI assistant"
            initial={still ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            transition={rise}
          >
            <header className="assistant-head">
              <div className="assistant-id">
                {/* The one navy mark, so its clay bar stays the single clay in
                    the composition. Every other mark here is the white tone,
                    whose accent is taupe. */}
                <Mark size={20} tone="navy" />
                <div>
                  <div className="assistant-title">Tús Áite assistant</div>
                  <div className="assistant-scope num">{scope}</div>
                </div>
              </div>
              <button className="assistant-close" onClick={() => setOpen(false)}
                      aria-label="Close assistant">
                <X className="ico-s" aria-hidden />
              </button>
            </header>

            <div className="assistant-log" role="log" aria-live="polite" ref={logRef}>
              {messages.length === 0 ? (
                <div className="assistant-empty">
                  <span className="assistant-person">
                    <Mark size={20} tone="white" />
                  </span>
                  <p>
                    I am Tus. Ask about the list, a referral's place on it, or what
                    the evidence says.
                  </p>
                </div>
              ) : messages.map((message) => (
                <motion.div
                  key={message.id}
                  className={`assistant-msg is-${message.role}`}
                  initial={still ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={fade}
                >
                  <span className="lab">{message.role === 'user' ? 'You' : 'Tus'}</span>
                  <p>{message.text}</p>
                  {message.source && (
                    <p className="assistant-src num">
                      Read from decision {message.source.decision_id.slice(0, 12)}, run{' '}
                      {message.source.run_id}
                    </p>
                  )}
                </motion.div>
              ))}

              {sending && (
                <p className="assistant-wait" role="status">
                  <span className="lab">
                    {slow ? 'Still working. This one needs the full rationale' : 'Reading the decision'}
                  </span>
                  <span className="assistant-dots" aria-hidden>
                    <i /><i /><i />
                  </span>
                </p>
              )}
            </div>

            <form className="assistant-form" onSubmit={submit}>
              <textarea
                ref={composerRef}
                className="assistant-composer"
                value={question}
                onChange={(event) => { setQuestion(event.target.value); grow(event.target) }}
                onKeyDown={onKeyDown}
                rows={1}
                maxLength={1200}
                placeholder="Ask about this list"
                aria-label="Ask the assistant a question"
              />
              <button className="assistant-send" disabled={sending || !question.trim()}
                      aria-label="Send question">
                <Send className="ico-s" aria-hidden />
              </button>
            </form>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  )
}
