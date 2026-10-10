import axios from 'axios'

export const API_BASE = import.meta.env.VITE_API_BASE_URL !== undefined 
  ? import.meta.env.VITE_API_BASE_URL 
  : 'http://localhost:8000'

const authHeader = (token) => ({
  headers: { Authorization: `Bearer ${token}` }
})

export const api = {
  login: async (username, password, role) => {
    const res = await axios.post(`${API_BASE}/auth/login`, { username, password, role })
    return res.data
  },

  register: async (username, password, role, name) => {
    const res = await axios.post(`${API_BASE}/auth/register`, { username, password, role, name })
    return res.data
  },

  fetchMe: async (token) => {
    const res = await axios.get(`${API_BASE}/auth/me`, authHeader(token))
    return res.data
  },

  updateSubscription: async (plan, token) => {
    const res = await axios.post(`${API_BASE}/auth/set-plan`, { plan }, authHeader(token))
    return res.data
  },

  executeAction: async (action, token) => {
    const res = await axios.post(
      `${API_BASE}/security/execute-action`,
      { action },
      authHeader(token)
    )
    return res.data
  },

  sendQuery: async (queryText, token, sessionId, threadId = null, optionsOrAgent = {}) => {
    // The token travels only in the Authorization header (the body `token` field is legacy)
    const body = { query: queryText, session_id: sessionId }
    // thread_id continues a saved conversation; leaving it out starts a new one
    if (threadId) body.thread_id = threadId

    let signal
    let selectedAgent
    let inventoryScope

    if (typeof optionsOrAgent === 'string') {
      selectedAgent = optionsOrAgent
    } else if (optionsOrAgent && typeof optionsOrAgent === 'object') {
      signal = optionsOrAgent.signal
      selectedAgent = optionsOrAgent.selectedAgent
      inventoryScope = optionsOrAgent.inventoryScope
    }

    if (selectedAgent && selectedAgent !== 'auto') {
      body.selected_agent = selectedAgent
    }
    if (inventoryScope) body.inventory_scope = inventoryScope

    const res = await axios.post(
      `${API_BASE}/query`,
      // session_id lets inventory answers drive this tab's Digital Twin map
      body,
      { ...authHeader(token), signal }
    )
    return res.data
  },

  // Read-only question autocomplete for the Inventory Agent (never answers or sends anything)
  fetchInventorySuggestions: async (text, token, { signal } = {}) => {
    const res = await axios.get(`${API_BASE}/inventory/suggestions`, { ...authHeader(token), params: { q: text }, signal })
    return res.data
  },

  // Conversations (chat threads) owned by the signed-in user
  listThreads: async (token, { signal } = {}) => {
    const res = await axios.get(`${API_BASE}/threads`, { ...authHeader(token), signal })
    return res.data.threads || []
  },

  getThread: async (token, threadId, { signal } = {}) => {
    const res = await axios.get(`${API_BASE}/threads/${encodeURIComponent(threadId)}`, { ...authHeader(token), signal })
    return res.data
  },

  deleteThread: async (token, threadId) => {
    await axios.delete(`${API_BASE}/threads/${encodeURIComponent(threadId)}`, authHeader(token))
  },

  clearThreads: async (token) => {
    const res = await axios.delete(`${API_BASE}/threads`, authHeader(token))
    return res.data
  },

  // Managers and admins only (staff get 403 FORBIDDEN); limit must be 1..500
  fetchAuditLogs: async (token, { limit = 50, eventType } = {}) => {
    const params = { limit: Math.min(500, Math.max(1, Math.round(Number(limit) || 50))) }
    if (eventType) params.event_type = eventType
    const res = await axios.get(`${API_BASE}/security/audit-logs`, { ...authHeader(token), params })
    return res.data
  },

  testInjection: async (text, token) => {
    const res = await axios.post(`${API_BASE}/security/test-injection`, { text }, authHeader(token))
    return res.data
  },

  testPermission: async (role, action, token) => {
    const res = await axios.post(`${API_BASE}/security/test-permission`, { role, action }, authHeader(token))
    return res.data
  },

  fetchRbacMatrix: async (token) => {
    const res = await axios.get(`${API_BASE}/security/rbac-matrix`, authHeader(token))
    return res.data
  }
}
