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

  sendQuery: async (queryText, token) => {
    const res = await axios.post(
      `${API_BASE}/query`,
      { query: queryText, token },
      authHeader(token)
    )
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
