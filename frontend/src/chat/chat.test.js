import { describe, expect, it } from 'vitest'
import { buildPath, createThreadNavigator, parseLocation } from './threadRoute'
import { chatReducer, DRAFT, initialChatState } from './chatState'
import { agentLabel, storedToUiMessages, toAssistantMessage } from './messageMapping'

const T1 = '3f1c2b8e-1111-4a2b-9c3d-000000000001'
const T2 = '3f1c2b8e-1111-4a2b-9c3d-000000000002'

// Minimal browser history: entries + index, popstate on back/forward
function fakeWindow(start = '/') {
  const listeners = []
  const parse = (url) => {
    const [pathname, query] = url.split('?')
    return { pathname, search: query ? `?${query}` : '' }
  }
  let entries = [{ url: start, state: null }]
  let index = 0
  const win = {
    location: parse(start),
    history: {
      get state() { return entries[index].state },
      pushState(state, _t, url) {
        entries = entries.slice(0, index + 1).concat({ url, state })
        index += 1
        win.location = parse(url)
      },
      replaceState(state, _t, url) {
        entries[index] = { url, state }
        win.location = parse(url)
      },
      back() { win.go(-1) },
    },
    go(delta) {
      index = Math.max(0, Math.min(entries.length - 1, index + delta))
      win.location = parse(entries[index].url)
      listeners.forEach((fn) => fn())
    },
    addEventListener: (type, fn) => type === 'popstate' && listeners.push(fn),
    removeEventListener: () => {},
  }
  return win
}

describe('threadRoute', () => {
  it('parses conversation urls and the map view', () => {
    expect(parseLocation({ pathname: '/' })).toEqual({ threadId: null, invalidThreadId: null, view: null })
    expect(parseLocation({ pathname: `/chat/${T1.toUpperCase()}`, search: '?view=map' }))
      .toEqual({ threadId: T1, invalidThreadId: null, view: 'map' })
    expect(parseLocation({ pathname: '/chat/not-a-thread' }).invalidThreadId).toBe('not-a-thread')
    expect(parseLocation({ pathname: '/twin/stream' }).threadId).toBeNull()
  })

  it('builds paths that round-trip', () => {
    expect(buildPath({ threadId: null })).toBe('/')
    expect(buildPath({ threadId: T1, view: 'map' })).toBe(`/chat/${T1}?view=map`)
    const url = buildPath({ threadId: T2, view: 'map' })
    const [pathname, query] = url.split('?')
    expect(parseLocation({ pathname, search: `?${query}` })).toMatchObject({ threadId: T2, view: 'map' })
  })

  it('push / replace / back / forward keep the active thread in sync', () => {
    const win = fakeWindow('/')
    const nav = createThreadNavigator(win)
    let notified = 0
    nav.subscribe(() => { notified += 1 })

    nav.push({ threadId: T1 })
    nav.push({ threadId: T2 })
    expect(nav.current().threadId).toBe(T2)

    win.history.back()
    expect(nav.current().threadId).toBe(T1)
    win.go(1)
    expect(nav.current().threadId).toBe(T2)

    nav.replace({ threadId: T2, view: 'map' })
    expect(nav.current()).toMatchObject({ threadId: T2, view: 'map' })
    expect(nav.push({ threadId: T2, view: 'map' })).toBe(false) // same url: no duplicate history entry
    expect(notified).toBeGreaterThanOrEqual(4)
  })

  it('returns a stable snapshot until the url changes (useSyncExternalStore contract)', () => {
    const nav = createThreadNavigator(fakeWindow(`/chat/${T1}`))
    expect(nav.current()).toBe(nav.current())
  })

  it('knows when the map entry was pushed by the app', () => {
    const win = fakeWindow(`/chat/${T1}`)
    const nav = createThreadNavigator(win)
    nav.push({ threadId: T1, view: 'map' }, { mapPushed: true })
    expect(nav.pushedWith('mapPushed')).toBe(true)
    nav.back()
    expect(nav.current().view).toBeNull()
  })
})

describe('chatReducer', () => {
  const msg = (id) => ({ id, role: 'assistant', content: id })

  it('a late answer for a conversation no longer on screen is not shown there', () => {
    let s = chatReducer(initialChatState, { type: 'ROUTE_CHANGED', key: T1 })
    s = chatReducer(s, { type: 'LOAD_OK', key: T1, messages: [] })
    s = chatReducer(s, { type: 'SEND', key: T1, message: msg('q1') })
    s = chatReducer(s, { type: 'ROUTE_CHANGED', key: T2 })
    s = chatReducer(s, { type: 'RESPONSE', key: T1, message: msg('a1') })
    expect(s.activeKey).toBe(T2)
    expect(s.messages).toEqual([])
    expect(s.pending[T1]).toBeUndefined()
  })

  it('stale history loads are ignored', () => {
    let s = chatReducer(initialChatState, { type: 'ROUTE_CHANGED', key: T1 })
    s = chatReducer(s, { type: 'ROUTE_CHANGED', key: T2 })
    s = chatReducer(s, { type: 'LOAD_OK', key: T1, messages: [msg('old')] })
    expect(s.messages).toEqual([])
    s = chatReducer(s, { type: 'LOAD_OK', key: T2, messages: [msg('t2')] })
    expect(s.messages.map((m) => m.id)).toEqual(['t2'])
  })

  it('the first answer turns the draft into its thread without a reload', () => {
    let s = chatReducer(initialChatState, { type: 'SEND', key: DRAFT, message: msg('q') })
    s = chatReducer(s, { type: 'RESPONSE', key: DRAFT, message: msg('a'), threadId: T1 })
    expect(s.activeKey).toBe(T1)
    expect(s.loadedKey).toBe(T1) // nothing to fetch
    expect(chatReducer(s, { type: 'ROUTE_CHANGED', key: T1 })).toBe(s) // the URL catching up is a no-op
  })

  it('new chat and logout start clean', () => {
    let s = chatReducer(initialChatState, { type: 'ROUTE_CHANGED', key: T1 })
    s = chatReducer(s, { type: 'LOAD_OK', key: T1, messages: [msg('x')] })
    expect(chatReducer(s, { type: 'NEW_DRAFT' })).toMatchObject({ activeKey: DRAFT, messages: [] })
    expect(chatReducer(s, { type: 'RESET' })).toEqual(initialChatState)
  })
})

describe('messageMapping', () => {
  const item = { sku: 'SKU-1001', name: 'Thermal Label Printer', location: 'Aisle 5', aisle: 5, shelf: 'A1',
    tier: 'A', bay: null, quantity_on_hand: 15, available_quantity: 13, unit: 'units', status: 'LOW_STOCK' }
  const live = {
    status: 'success', agent_used: 'inventory_agent', response: 'ok', routing: { target_agent: 'inventory_agent' },
    inventory_details: { items: [item] },
  }

  it('builds inventory cards only from returned items', () => {
    const m = toAssistantMessage(live, { text: 'how many printers' })
    expect(m.skuData).toMatchObject({ sku: 'SKU-1001', stock: '15 units (LOW STOCK)', available: 13, bay: null })
    const none = toAssistantMessage({ ...live, response: 'I couldn\'t find **SKU-9999**', inventory_details: { items: [] } },
      { text: 'where is SKU-9999' })
    expect(none.skuData).toBeNull() // no placeholder SKU-4521 card
  })

  it('restored history renders like the live answer, without auto-playing the map', () => {
    const stored = storedToUiMessages([
      { id: 1, role: 'user', content: 'how many printers', created_at: '2026-10-06T08:00:00Z' },
      { id: 2, role: 'assistant', content: 'ok', agent_used: 'inventory_agent', status: 'success',
        meta: { routing: { target_agent: 'inventory_agent' }, inventory_details: { items: [item] },
          ui_command: { id: 'c1', payload: { action: 'clear' } } } },
    ])
    expect(stored[0]).toMatchObject({ role: 'user', content: 'how many printers' })
    expect(stored[1].skuData).toEqual(toAssistantMessage(live, { text: 'how many printers' }).skuData)
    expect(stored[1].origin).toBe('stored')
    expect(stored[1].uiCommand.id).toBe('c1')
  })

  it('a stored blocked prompt renders as blocked', () => {
    const [, blocked] = storedToUiMessages([
      { id: 1, role: 'user', content: '[message blocked by the security filter]' },
      { id: 2, role: 'assistant', content: 'Security Alert', status: 'blocked',
        meta: { error_code: 'PROMPT_INJECTION_DETECTED' } },
    ])
    expect(blocked.status).toBe('blocked')
  })

  it('a live prompt-injection block is still a blocked bubble', () => {
    const m = toAssistantMessage({ status: 'error', error_code: 'PROMPT_INJECTION_DETECTED',
      message: 'Security Alert: the request matched the security filter (rule: ignore_instructions). Request blocked.' })
    expect(m.status).toBe('blocked')
    expect(m.content).toContain('rule: ignore_instructions')
  })

  it('an empty question is a plain error, not a security block', () => {
    const m = toAssistantMessage({ status: 'error', error_code: 'EMPTY_QUERY', message: 'Type a question before sending.',
      response: 'Type a question before sending.', routing: { rule_id: 'input.empty_query', status: 'blocked' } })
    expect(m.status).toBe('error')
    expect(m.content).toBe('Type a question before sending.')
    expect(m.routing.status).not.toBe('blocked')
  })

  it('an error envelope without a response shows its message', () => {
    expect(toAssistantMessage({ status: 'error', error_code: 'AGENT_FAILED', message: 'Inventory is unavailable' }).content)
      .toBe('Inventory is unavailable')
  })

  it('a stored question with files shows the typed text and file chips', () => {
    const [user] = storedToUiMessages([
      { id: 1, role: 'user', content: 'Is this late?\n\n[Attached file: supplier.eml]\nSubject: delay' },
    ])
    expect(user).toMatchObject({ role: 'user', content: 'Is this late?', attachments: [{ name: 'supplier.eml' }] })
  })

  it('labels the routed agent without a doubled AGENT', () => {
    expect(agentLabel('inventory_agent')).toBe('INVENTORY')
    expect(agentLabel('INVENTORY_AGENT')).toBe('INVENTORY')
    expect(agentLabel('security_sanitizer')).toBe('SECURITY SANITIZER')
    expect(agentLabel('fulfillment')).toBe('FULFILLMENT')
  })
})
