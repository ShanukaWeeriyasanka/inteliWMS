// Inventory question suggestions for a chat input: debounced, latest-only, and closed by
// Escape, a selection, sending, or clearing the input. Choosing one never sends it.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../services/api'
import { createSuggestionRequester, moveHighlight, shouldSuggest } from './inventorySuggestions'

export function useInventorySuggestions(text, token, { enabled = true } = {}) {
  const [result, setResult] = useState({ text: '', items: [] })
  const [index, setIndex] = useState(-1)
  const [dismissedFor, setDismissedFor] = useState(null) // text the list was closed for

  const requester = useMemo(
    () => createSuggestionRequester(api.fetchInventorySuggestions, (forText, items) => {
      setResult({ text: forText, items })
      setIndex(-1)
    }),
    [],
  )

  useEffect(() => {
    requester.request(enabled ? text : '', token)
    setIndex(-1)
    setDismissedFor((d) => (d === text ? d : null))
  }, [requester, text, token, enabled])

  useEffect(() => () => requester.cancel(), [requester])

  const items = result.items
  const open = enabled && shouldSuggest(text) && items.length > 0 && dismissedFor !== text

  const move = useCallback((delta) => setIndex((i) => moveHighlight(i, delta, items.length)), [items.length])
  // Hide until the text changes again (Escape, or a suggestion just filled the input)
  const close = useCallback((forText = text) => { setDismissedFor(forText); setIndex(-1) }, [text])

  return { items: open ? items : [], open, index: open ? index : -1, setIndex, move, close }
}
