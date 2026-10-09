// Prompt bar over the map: ask the multi-agent system without leaving the
// map. The latest answer is shown just above it; inventory answers move the map.
import React, { useEffect, useState } from 'react'
import { ArrowUp, Sparkles, X } from 'lucide-react'
import MarkdownText from '../../components/coordinator UI/MarkdownText'
import { CHAT_MAX_CHARS, charCounterLabel } from '../../chat/attachments'

const SUGGESTIONS = ['Where is product number 2?', "What's running low?", 'How many products are in rack 2 on floor 2?', 'Take me to cold 3']

export default function AgentDock({ reply, busy, value, onChange, onSend, inputRef }) {
  const [hidden, setHidden] = useState(false)
  const [expanded, setExpanded] = useState(false)
  useEffect(() => { setHidden(false); setExpanded(false) }, [reply])

  const submit = (e) => {
    e.preventDefault()
    const text = value.trim()
    if (text && !busy) onSend(text)
  }
  const long = (reply || '').length > 220 || (reply || '').split('\n').length > 3
  const counter = charCounterLabel(value.length)

  return (
    <div className="twin-dock">
      {busy && (
        <div className="twin-reply is-busy" role="status">
          <span className="twin-reply-avatar"><Sparkles size={13} /></span>
          <span className="twin-typing"><i /><i /><i /></span>
          <span className="twin-muted">Inventory agent is checking the database…</span>
        </div>
      )}
      {!busy && reply && !hidden && (
        <div className="twin-reply" role="status">
          <span className="twin-reply-avatar"><Sparkles size={13} /></span>
          <div className="twin-reply-body">
            <strong>IntelliWMS agent</strong>
            <MarkdownText className={`twin-reply-text${expanded ? ' is-expanded' : ''}`} text={reply} />
            {long && <button className="twin-link-btn" onClick={() => setExpanded((x) => !x)}>{expanded ? 'Show less' : 'Show more'}</button>}
          </div>
          <button className="twin-icon-btn" onClick={() => setHidden(true)} aria-label="Hide answer"><X size={13} /></button>
        </div>
      )}
      {!busy && !reply && !value && (
        <div className="twin-suggest">
          {SUGGESTIONS.map((s) => <button key={s} onClick={() => onSend(s)}>{s}</button>)}
        </div>
      )}
      <form className="twin-ask" onSubmit={submit}>
        <input ref={inputRef} value={value} onChange={(e) => onChange(e.target.value)} disabled={busy}
          maxLength={CHAT_MAX_CHARS}
          placeholder="Ask about stock, locations or directions…" aria-label="Ask the IntelliWMS agent" />
        {counter && <span className={`twin-ask-count${value.length >= CHAT_MAX_CHARS ? ' is-limit' : ''}`} aria-live="polite">{counter}</span>}
        <button type="submit" disabled={!value.trim() || busy} aria-label="Send"><ArrowUp size={16} /></button>
      </form>
    </div>
  )
}
