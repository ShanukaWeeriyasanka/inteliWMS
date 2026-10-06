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

  executeAction: async (action, token) => {
    const res = await axios.post(
      `${API_BASE}/security/execute-action`,
      { action },
      authHeader(token)
    )
    return res.data
  },

  sendQuery: async (queryText, token, sessionId, threadId = null, { signal } = {}) => {
    const body = { query: queryText, token, session_id: sessionId }
    // thread_id continues a saved conversation; leaving it out starts a new one
    if (threadId) body.thread_id = threadId
    const res = await axios.post(
      `${API_BASE}/query`,
      // session_id lets inventory answers drive this tab's Digital Twin map
      body,
      { ...authHeader(token), signal }
    )
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

  fetchAuditLogs: async () => {
    const res = await axios.get(`${API_BASE}/security/audit-logs`)
    return res.data
  },

  testInjection: async (text) => {
    const res = await axios.post(`${API_BASE}/security/test-injection`, { text })
    return res.data
  },

  fetchRbacMatrix: async () => {
    const res = await axios.get(`${API_BASE}/security/rbac-matrix`)
    return res.data
  }
}
