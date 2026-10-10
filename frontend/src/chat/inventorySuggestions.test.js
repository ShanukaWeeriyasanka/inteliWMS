import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  SUGGEST_DEBOUNCE_MS,
  createSuggestionRequester,
  moveHighlight,
  shouldSuggest,
  suggestionKeyAction,
} from './inventorySuggestions'

const reply = (...texts) => ({ suggestions: texts.map((text) => ({ text, kind: 'generic' })) })

function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

describe('shouldSuggest', () => {
  it('starts after two non-space characters', () => {
    expect(shouldSuggest('')).toBe(false)
    expect(shouldSuggest('s')).toBe(false)
    expect(shouldSuggest(' s  ')).toBe(false)
    expect(shouldSuggest('st')).toBe(true)
    expect(shouldSuggest('s t')).toBe(true)
  })
})

describe('moveHighlight', () => {
  it('walks the list and returns to the typed text past either end', () => {
    expect(moveHighlight(-1, 1, 3)).toBe(0)
    expect(moveHighlight(0, 1, 3)).toBe(1)
    expect(moveHighlight(2, 1, 3)).toBe(-1)
    expect(moveHighlight(-1, -1, 3)).toBe(2)
    expect(moveHighlight(0, -1, 3)).toBe(-1)
    expect(moveHighlight(1, 1, 0)).toBe(-1)
  })
})

describe('suggestionKeyAction', () => {
  it('leaves every key to the input while the list is closed', () => {
    for (const key of ['ArrowDown', 'ArrowUp', 'Enter', 'Escape']) {
      expect(suggestionKeyAction(key, { open: false, index: 0 })).toBe(null)
    }
  })

  it('maps arrows, Escape and Enter on a highlighted suggestion', () => {
    expect(suggestionKeyAction('ArrowDown', { open: true, index: -1 })).toBe('next')
    expect(suggestionKeyAction('ArrowUp', { open: true, index: 0 })).toBe('prev')
    expect(suggestionKeyAction('Escape', { open: true, index: -1 })).toBe('close')
    expect(suggestionKeyAction('Enter', { open: true, index: 1 })).toBe('select')
  })

  it('keeps Enter as send when nothing is highlighted, and Shift+Enter as a new line', () => {
    expect(suggestionKeyAction('Enter', { open: true, index: -1 })).toBe(null)
    expect(suggestionKeyAction('Enter', { open: true, index: 0, shiftKey: true })).toBe(null)
    expect(suggestionKeyAction('a', { open: true, index: 0 })).toBe(null)
  })
})

describe('createSuggestionRequester', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('debounces typing into one request for the latest text', async () => {
    const fetcher = vi.fn(async (text) => reply(`about ${text}`))
    const onResult = vi.fn()
    const requester = createSuggestionRequester(fetcher, onResult)
    requester.request('st', 'tok')
    requester.request('sto', 'tok')
    requester.request('stoc', 'tok')
    await vi.advanceTimersByTimeAsync(SUGGEST_DEBOUNCE_MS - 1)
    expect(fetcher).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(fetcher.mock.calls[0][0]).toBe('stoc')
    expect(fetcher.mock.calls[0][1]).toBe('tok')
    expect(onResult).toHaveBeenLastCalledWith('stoc', [{ text: 'about stoc', kind: 'generic' }])
  })

  it('never lets a slow older reply replace suggestions for newer text', async () => {
    const slow = deferred()
    const fast = deferred()
    const fetcher = vi.fn().mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise)
    const onResult = vi.fn()
    const requester = createSuggestionRequester(fetcher, onResult)

    requester.request('lo', 'tok')
    await vi.advanceTimersByTimeAsync(SUGGEST_DEBOUNCE_MS)
    requester.request('low st', 'tok')
    await vi.advanceTimersByTimeAsync(SUGGEST_DEBOUNCE_MS)
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(fetcher.mock.calls[0][2].signal.aborted).toBe(true) // the older request was cancelled

    fast.resolve(reply('Which products are low on stock?'))
    await vi.advanceTimersByTimeAsync(0)
    slow.resolve(reply('stale answer for lo'))
    await vi.advanceTimersByTimeAsync(0)

    expect(onResult).toHaveBeenCalledTimes(1)
    expect(onResult).toHaveBeenCalledWith('low st', [{ text: 'Which products are low on stock?', kind: 'generic' }])
  })

  it('hides the list on lookup failure instead of showing anything made up', async () => {
    const onResult = vi.fn()
    const requester = createSuggestionRequester(vi.fn().mockRejectedValue(new Error('503')), onResult)
    requester.request('stock', 'tok')
    await vi.advanceTimersByTimeAsync(SUGGEST_DEBOUNCE_MS)
    expect(onResult).toHaveBeenCalledWith('stock', [])
  })

  it('clears immediately for short or cleared text, or without a sign-in, and skips the request', async () => {
    const fetcher = vi.fn(async () => reply('x'))
    const onResult = vi.fn()
    const requester = createSuggestionRequester(fetcher, onResult)
    requester.request('stock', 'tok')
    requester.request('', 'tok') // message sent / input cleared before the debounce ended
    requester.request('stock', '')
    await vi.advanceTimersByTimeAsync(SUGGEST_DEBOUNCE_MS * 2)
    expect(fetcher).not.toHaveBeenCalled()
    expect(onResult.mock.calls).toEqual([['', []], ['stock', []]])
  })

  it('caps the list at five suggestions', async () => {
    const onResult = vi.fn()
    const many = reply('a?', 'b?', 'c?', 'd?', 'e?', 'f?', 'g?')
    const requester = createSuggestionRequester(async () => many, onResult)
    requester.request('stock', 'tok')
    await vi.advanceTimersByTimeAsync(SUGGEST_DEBOUNCE_MS)
    expect(onResult.mock.calls[0][1]).toHaveLength(5)
  })
})
