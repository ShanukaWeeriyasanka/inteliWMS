// Fetches one trip from GET /twin/route: find_route geometry + get_directions
// steps computed in the same backend call, so the line and the text agree.
import { useEffect, useMemo, useState } from 'react'
import { routeSummary, splitRouteByFloor } from '../lib/route'

export function useRoute(api, request, version) {
  const [state, setState] = useState({ loading: false, error: null, data: null })

  useEffect(() => {
    if (!request?.toId) {
      setState({ loading: false, error: null, data: null })
      return undefined
    }
    let cancelled = false
    setState({ loading: true, error: null, data: null })
    api.route(request.toId, request.fromId, request.prefer || 'lift')
      .then((data) => { if (!cancelled) setState({ loading: false, error: null, data }) })
      .catch((e) => { if (!cancelled) setState({ loading: false, error: e.message, data: null }) })
    return () => { cancelled = true }
  }, [api, request?.toId, request?.fromId, request?.prefer, request?.key, version])

  const derived = useMemo(() => {
    const data = state.data
    if (!data) return { segments: [], summary: '', errorStep: null, note: null }
    const segments = splitRouteByFloor(data.path)
    const errorStep = data.directions.find((d) => d.kind === 'error') || null
    const note = data.directions.find((d) => d.kind === 'note') || null
    return { segments, summary: routeSummary(data.path, segments), errorStep, note }
  }, [state.data])

  return { ...state, ...derived }
}
