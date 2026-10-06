// Route helpers. The browser NEVER computes a route: paths and steps come from
// the database functions find_route() + get_directions() via GET /twin/route.
// These helpers only reshape that answer for drawing and reading.

/**
 * Split a find_route path into per-floor walking segments.
 * A new segment starts at every node reached `via` lift or stairs.
 * Each segment: { index, floorId, floorLevel, points: [{node_id,x,y,…}], arrivedVia, connectorLabel, passThrough }
 * `arrivedVia` / `connectorLabel` describe how you got onto this floor ("lift", "Lift A").
 * `passThrough` marks a floor the lift/stairs only passes (one point, nothing to walk).
 */
export function splitRouteByFloor(path) {
  const segments = []
  let prev = null
  for (const p of path || []) {
    const vertical = p.via === 'lift' || p.via === 'stairs'
    const current = segments[segments.length - 1]
    if (!current || vertical) {
      segments.push({
        index: segments.length,
        floorId: p.floor_id,
        floorLevel: p.floor_level,
        points: [p],
        arrivedVia: vertical ? p.via : null,
        connectorLabel: vertical ? (prev?.label || p.label || (p.via === 'lift' ? 'Lift' : 'Stairs')) : null,
      })
    } else {
      current.points.push(p)
    }
    prev = p
  }
  return segments.map((s) => ({
    ...s,
    passThrough: s.points.length === 1 && s.index > 0 && s.index < segments.length - 1,
  }))
}

export function formatDuration(seconds) {
  const s = Number(seconds || 0)
  if (s < 90) return `about ${Math.round(s)} s`
  return `about ${(Math.round((s / 60) * 10) / 10).toString()} min`
}

/** Header line for the route card: "52 m · about 1.5 min · via Lift A". */
export function routeSummary(path, segments) {
  if (!path?.length) return ''
  const last = path[path.length - 1]
  const connectors = [...new Set(segments.filter((s) => s.connectorLabel).map((s) => s.connectorLabel))]
  const bits = [`${Math.round(last.total_m)} m`, formatDuration(last.total_s)]
  if (connectors.length) bits.push(`via ${connectors.join(', ')}`)
  return bits.join(' · ')
}

/** Polyline length in metres (for the walker animation). */
export function polylineLength(points) {
  let len = 0
  for (let i = 1; i < points.length; i++) {
    len += Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y)
  }
  return len
}

/** Point at fraction t (0–1) along a polyline. */
export function pointAlong(points, t) {
  if (!points.length) return null
  if (points.length === 1 || t <= 0) return points[0]
  const total = polylineLength(points)
  let target = Math.min(1, t) * total
  for (let i = 1; i < points.length; i++) {
    const seg = Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y)
    if (target <= seg && seg > 0) {
      const f = target / seg
      return {
        x: points[i - 1].x + (points[i].x - points[i - 1].x) * f,
        y: points[i - 1].y + (points[i].y - points[i - 1].y) * f,
      }
    }
    target -= seg
  }
  return points[points.length - 1]
}
