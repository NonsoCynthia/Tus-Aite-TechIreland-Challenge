import { FormEvent, useMemo, useState } from 'react'
import { Bot, Send, UserRound, X } from 'lucide-react'
import { api } from '../lib/api'
import './assistant-panel.css'

type Message = { role: 'user' | 'assistant'; text: string }

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

  const scope = useMemo(
    () => pathway ? `${hospital} / ${date} / ${pathway}` : `${hospital} / ${date}`,
    [date, hospital, pathway],
  )

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = question.trim()
    if (!text || sending) return

    setQuestion('')
    setSending(true)
    setMessages((rows) => [...rows, { role: 'user', text }])
    try {
      const reply = await api.chat({
        question: text,
        session_id: sessionId,
        hospital_hipe: hospital,
        as_of_date: date,
        pathway_number: pathway,
      })
      setSessionId(reply.session_id)
      setMessages((rows) => [...rows, { role: 'assistant', text: reply.answer }])
    } catch {
      setMessages((rows) => [
        ...rows,
        { role: 'assistant', text: 'The assistant could not be reached.' },
      ])
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      {!open && (
        <button
          className="assistant-launcher"
          onClick={() => setOpen(true)}
          aria-label="Open Tus assistant"
          aria-expanded={open}
        >
          <span className="assistant-person">
            <UserRound className="ico" aria-hidden />
          </span>
          <span className="assistant-bubble">I am Tus, here to answer your questions</span>
        </button>
      )}
      {open && (
        <aside className="assistant-panel" aria-label="AI assistant">
          <header className="assistant-head">
            <div>
              <div className="assistant-title">
                <Bot className="ico-s" aria-hidden />
                <span>AI assistant</span>
              </div>
              <div className="assistant-scope">{scope}</div>
            </div>
            <button className="assistant-close" onClick={() => setOpen(false)} aria-label="Close assistant">
              <X className="ico-s" aria-hidden />
            </button>
          </header>

          <div className="assistant-log" role="log" aria-live="polite">
            {messages.length === 0 ? (
              <div className="assistant-empty">
                <span className="assistant-person">
                  <UserRound className="ico" aria-hidden />
                </span>
                <p>I am Tus, here to answer your questions</p>
              </div>
            ) : messages.map((message, index) => (
              <div key={index} className={`assistant-msg is-${message.role}`}>
                <span>{message.role === 'user' ? 'You' : 'Assistant'}</span>
                <p>{message.text}</p>
              </div>
            ))}
            {sending && <p className="assistant-wait">Thinking...</p>}
          </div>

          <form className="assistant-form" onSubmit={submit}>
            <label className="assistant-input">
              <span className="lab">Question</span>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                rows={3}
                maxLength={1200}
              />
            </label>
            <button className="assistant-send" disabled={sending || !question.trim()}>
              <Send className="ico-s" aria-hidden />
              <span>{sending ? 'Sending' : 'Send'}</span>
            </button>
          </form>
        </aside>
      )}
    </>
  )
}
