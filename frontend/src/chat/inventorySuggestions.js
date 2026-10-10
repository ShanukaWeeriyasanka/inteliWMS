// Inventory question autocomplete: when to ask, keyboard handling, and a debounced
// requester that never lets an older reply replace suggestions for newer text.
import { latestRequest } from '../twin/lib/latest'

export const SUGGEST_MIN_CHARS = 2
export const SUGGEST_DEBOUNCE_MS = 275
export const SUGGEST_MAX = 5

export const shouldSuggest = (text) => (text || '').replace(/\s/g, '').length >= SUGGEST_MIN_CHARS

// -1 is "nothing highlighted" (the typed text); moving past either end returns there, like a search box
export function moveHighlight(index, delta, length) {
  if (!length) return -1
  const next = index + delta
  if (next < -1) return length - 1
  if (next >= length) return -1
  return next
}

// What a key press means while the list may be open; null leaves the key to the input as before
export function suggestionKeyAction(key, { open, index, shiftKey = false }) {
  if (!open) return null
  if (key === 'ArrowDown') return 'next'
  if (key === 'ArrowUp') return 'prev'
  if (key === 'Escape') return 'close'
  if (key === 'Enter' && !shiftKey && index >= 0) return 'select'
  return null
}

export const suggestionOptionId = (listId, index) => `${listId}-opt-${index}`

// fetcher(text, token, { signal }) → { suggestions: [{ text, kind, sku? }] }
// onResult(text, items) receives only the newest text's answer; failures give [] (the list hides)
export function createSuggestionRequester(fetcher, onResult, { delay = SUGGEST_DEBOUNCE_MS } = {}) {
  const latest = latestRequest()
  let timer = null
  let controller = null

  const stop = () => {
    clearTimeout(timer)
    controller?.abort()
    latest.invalidate()
  }

  return {
    request(text, token) {
      stop()
      if (!token || !shouldSuggest(text)) {
        onResult(text, [])
        return
      }
      const current = controller = new AbortController()
      timer = setTimeout(() => {
        latest.run(
          () => fetcher(text.trim(), token, { signal: current.signal }),
          (data) => onResult(text, Array.isArray(data?.suggestions) ? data.suggestions.slice(0, SUGGEST_MAX) : []),
          () => { if (!current.signal.aborted) onResult(text, []) },
        ).catch(() => {})
      }, delay)
    },
    cancel: stop,
  }
}
