// Prompt bar over the map: ask the multi-agent system without leaving the
// map. The latest answer is shown just above it; inventory answers move the map.
import React, { useEffect, useId, useState } from 'react'
import { ArrowUp, Sparkles, X } from 'lucide-react'
import MarkdownText from '../../components/coordinator UI/MarkdownText'
import InventorySuggestions from '../../components/coordinator UI/InventorySuggestions'
import { CHAT_MAX_CHARS, charCounterLabel } from '../../chat/attachments'
import { suggestionKeyAction, suggestionOptionId } from '../../chat/inventorySuggestions'
import { useInventorySuggestions } from '../../chat/useInventorySuggestions'

const SUGGESTIONS = ['Where is product number 2?', "What's running low?", 'How many products are in rack 2 on floor 2?', 'Take me to cold 3']

export default function AgentDock({ reply, busy, value, onChange, onSend, inputRef, token }) {
  const [hidden, setHidden] = useState(false)
  const [expanded, setExpanded] = useState(false)
  useEffect(() => { setHidden(false); setExpanded(false) }, [reply])
  const suggestListId = `inv-suggest-${useId().replace(/:/g, '')}`
  const suggest = useInventorySuggestions(value, token, { enabled: !busy })

  // A suggestion only fills the input; the user still decides to send it
  const pickSuggestion = (item) => {
    onChange(item.text)
    suggest.close(item.text)
    inputRef?.current?.focus()
  }
  const onKeyDown = (e) => {
    const action = suggestionKeyAction(e.key, { open: suggest.open, index: suggest.index })
    if (!action) return
    e.preventDefault()
    if (action === 'next') suggest.move(1)
    else if (action === 'prev') suggest.move(-1)
    else if (action === 'close') suggest.close()
    else pickSuggestion(suggest.items[suggest.index])
  }

  const submit = (e) => {
    e.preventDefault()
    const text = value.trim()
    if (text && !busy) { suggest.close(''); onSend(text) }
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
            <MarkdownText className={`twin-reply-text${expanded ? ' is-expanded' : ''}`} text={reply} allowTables />
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
          maxLength={CHAT_MAX_CHARS} onKeyDown={onKeyDown} onBlur={() => suggest.open && suggest.close()}
          role="combobox" aria-autocomplete="list" aria-expanded={suggest.open} aria-controls={suggestListId}
          aria-activedescendant={suggest.index >= 0 ? suggestionOptionId(suggestListId, suggest.index) : undefined}
          placeholder="Ask about stock, locations or directions…" aria-label="Ask the IntelliWMS agent" />
        {counter && <span className={`twin-ask-count${value.length >= CHAT_MAX_CHARS ? ' is-limit' : ''}`} aria-live="polite">{counter}</span>}
        <button type="submit" disabled={!value.trim() || busy} aria-label="Send"><ArrowUp size={16} /></button>
      </form>
      <InventorySuggestions id={suggestListId} items={suggest.items} activeIndex={suggest.index}
        onSelect={pickSuggestion} onHighlight={suggest.setIndex} variant="light" />
    </div>
  )
}
