// Chat state keyed by conversation. `activeKey` is a thread id, or DRAFT for a new
// conversation that has no thread yet. Every action carries the key it belongs to,
// and anything for a conversation that is no longer on screen is ignored — so a slow
// answer or history load can never land in the wrong chat.

export const DRAFT = 'draft'

export const initialChatState = {
  activeKey: DRAFT,
  loadedKey: DRAFT, // conversation the visible `messages` belong to
  messages: [],
  loadingHistory: false,
  pending: {}, // key → true while a question is waiting for its answer
  threads: [], // sidebar: [{ id, title, timestamp }]
}

export function chatReducer(state, action) {
  switch (action.type) {
    case 'ROUTE_CHANGED': {
      if (action.key === state.activeKey) return state
      const draft = action.key === DRAFT
      return { ...state, activeKey: action.key, loadedKey: draft ? DRAFT : null, messages: [], loadingHistory: false }
    }
    case 'NEW_DRAFT':
      return { ...state, activeKey: DRAFT, loadedKey: DRAFT, messages: action.messages || [], loadingHistory: false }
    case 'LOAD_START':
      return action.key === state.activeKey ? { ...state, loadingHistory: true } : state
    case 'LOAD_OK':
      if (action.key !== state.activeKey) return state
      return { ...state, loadedKey: action.key, messages: action.messages, loadingHistory: false }
    case 'SEND':
      if (action.key !== state.activeKey) return state
      return { ...state, messages: [...state.messages, action.message], pending: { ...state.pending, [action.key]: true } }
    case 'RESPONSE': {
      const pending = { ...state.pending }
      delete pending[action.key]
      if (action.key !== state.activeKey) return { ...state, pending }
      const next = { ...state, pending, messages: [...state.messages, action.message] }
      // First answer of a new conversation: the draft becomes that thread (no reload needed)
      if (action.key === DRAFT && action.threadId) {
        next.activeKey = action.threadId
        next.loadedKey = action.threadId
      }
      return next
    }
    case 'THREADS_LOADED':
      return { ...state, threads: action.threads }
    case 'THREAD_REMOVED':
      return { ...state, threads: state.threads.filter((t) => t.id !== action.id) }
    case 'RESET':
      return initialChatState
    default:
      return state
  }
}
