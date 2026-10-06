// URL ↔ conversation mapping (no router dependency).
//
//   /                      new, unsaved conversation (the first answer creates the thread)
//   /chat/<thread-uuid>    a saved conversation
//   ...?view=map           the Warehouse Digital Twin map is open over that conversation
//
// Kept free of React so it can be unit-tested with a fake window. Paths avoid the
// prefixes nginx proxies to the API (/auth, /query, /threads, /twin, ...).

export const THREAD_ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const CHAT_PATH = /^\/chat\/([^/]+)\/?$/

export function parseLocation({ pathname = '/', search = '' } = {}) {
  const view = new URLSearchParams(search).get('view') === 'map' ? 'map' : null
  const match = CHAT_PATH.exec(pathname)
  if (!match) return { threadId: null, invalidThreadId: null, view }
  let raw
  try {
    raw = decodeURIComponent(match[1])
  } catch {
    raw = match[1]
  }
  return THREAD_ID_RE.test(raw)
    ? { threadId: raw.toLowerCase(), invalidThreadId: null, view }
    : { threadId: null, invalidThreadId: raw, view }
}

export function buildPath({ threadId = null, view = null } = {}) {
  const base = threadId ? `/chat/${encodeURIComponent(threadId)}` : '/'
  return view === 'map' ? `${base}?view=map` : base
}

// Tiny history-backed store: React subscribes with useSyncExternalStore.
export function createThreadNavigator(win = window) {
  const keyOf = () => `${win.location.pathname}${win.location.search}`
  let key = keyOf()
  let snapshot = parseLocation(win.location)
  const listeners = new Set()

  const refresh = () => {
    const next = keyOf()
    if (next !== key) {
      key = next
      snapshot = parseLocation(win.location)
    }
    listeners.forEach((fn) => fn())
  }
  win.addEventListener('popstate', refresh)

  const go = (method) => (route, state = {}) => {
    const path = buildPath(route)
    if (path === key) return false
    win.history[method]({ ...state, intelliwms: true }, '', path)
    refresh()
    return true
  }

  return {
    current: () => snapshot,
    push: go('pushState'),
    replace: go('replaceState'),
    back: () => win.history.back(),
    // True when the current entry was pushed by this app with the given flag (e.g. opening the map)
    pushedWith: (flag) => !!(win.history.state && win.history.state[flag]),
    subscribe: (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    destroy: () => win.removeEventListener('popstate', refresh),
  }
}
