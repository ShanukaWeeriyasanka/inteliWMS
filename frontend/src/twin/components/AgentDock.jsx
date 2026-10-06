// Prompt bar over the map: ask the multi-agent system without leaving the
// map. The latest answer is shown just above it; inventory answers move the map.
import React, { useEffect, useState } from 'react'
import { ArrowUp, Sparkles, X } from 'lucide-react'

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
            <p className={expanded ? 'is-expanded' : ''}>{reply}</p>
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
          placeholder="Ask about stock, locations or directions…" aria-label="Ask the IntelliWMS agent" />
        <button type="submit" disabled={!value.trim() || busy} aria-label="Send"><ArrowUp size={16} /></button>
      </form>
    </div>
  )
}
