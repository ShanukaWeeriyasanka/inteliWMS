// REST client for the backend's /twin endpoints (FastAPI → PostgreSQL views/functions).
import { API_BASE } from '../../services/api'

export class TwinApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export function createTwinApi(token) {
  const get = async (path, params = {}) => {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') qs.set(k, Array.isArray(v) ? v.join(',') : v)
    }
    const url = `${API_BASE}/twin${path}${qs.toString() ? `?${qs}` : ''}`
    let res
    try {
      res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    } catch {
      throw new TwinApiError('Cannot reach the IntelliWMS backend. Check that it is running.', 0)
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      // Error envelope: {status: "error", error_code, message, audit} (`detail` is the older shape)
      const detail = typeof body.detail === 'string' ? body.detail : null
      throw new TwinApiError(body.message || detail || `Request failed (${res.status})`, res.status)
    }
    return res.json()
  }

  return {
    status: () => fetch(`${API_BASE}/twin/status`).then((r) => r.json()),
    layout: () => get('/layout'),
    navEdges: () => get('/nav-edges'),
    products: () => get('/products'),
    productLocations: (productIds, locationPrefix) =>
      get('/product-locations', { product_ids: productIds, location_prefix: locationPrefix }),
    rackFill: (floorId) => get('/rack-fill', { floor_id: floorId }),
    locations: (ids) => get('/locations', { ids }),
    alerts: () => get('/alerts'),
    movements: (productId, limit = 12) => get('/movements', { product_id: productId, limit }),
    route: (toId, fromId, prefer = 'lift') => get('/route', { to_id: toId, from_id: fromId, prefer }),
    postCommand: async (sessionId, queryText, payload) => {
      const res = await fetch(`${API_BASE}/twin/commands`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, query_text: queryText, payload }),
      })
      if (!res.ok) throw new TwinApiError(`Could not store command (${res.status})`, res.status)
      return res.json()
    },
    streamUrl: (sessionId) =>
      `${API_BASE}/twin/stream?${new URLSearchParams({ session_id: sessionId || '', access_token: token })}`,
  }
}
