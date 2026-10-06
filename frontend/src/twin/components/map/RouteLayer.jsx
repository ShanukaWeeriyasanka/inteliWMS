// Draws the route segments that lie on the visible floor, animating the one
// being played (stroke-dash draw + a walker dot), plus start / destination markers.
import React, { useEffect, useRef, useState } from 'react'
import { pointAlong, polylineLength } from '../../lib/route'
import { DRAW_MS } from '../../hooks/useRoutePlayback'

function Walker({ points, runKey }) {
  const [pos, setPos] = useState(points[0])
  const raf = useRef(0)
  useEffect(() => {
    const t0 = performance.now()
    const tick = (now) => {
      const t = Math.min(1, (now - t0) / DRAW_MS)
      setPos(pointAlong(points, t))
      if (t < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
  }, [points, runKey])
  if (!pos) return null
  return <circle className="twin-walker" cx={pos.x} cy={pos.y} r={0.7} />
}

export default function RouteLayer({ floorId, segments, playback, path, reducedMotion }) {
  if (!segments.length) return null
  const { cursor, currentSegment } = playback
  const done = cursor.phase === 'done' || cursor.phase === 'idle'
  const currentIndex = currentSegment?.index ?? -1

  const visible = segments.filter((s) => s.floorId === floorId && s.points.length > 1 && (done || s.index <= currentIndex))
  const start = path[0]
  const end = path[path.length - 1]

  return (
    <g className="twin-route" aria-hidden="true">
      {visible.map((s) => {
        const pts = s.points.map((p) => `${p.x},${p.y}`).join(' ')
        const animating = !done && !reducedMotion && s.index === currentIndex && cursor.phase === 'draw'
        const len = polylineLength(s.points)
        return (
          <g key={`${s.index}-${animating ? cursor.i : 'static'}`}>
            <polyline className="twin-route-halo" points={pts} />
            <polyline
              className={`twin-route-line${animating ? ' is-drawing' : ''}`}
              points={pts}
              pathLength={animating ? 1 : undefined}
              style={animating ? { '--draw-ms': `${DRAW_MS}ms` } : undefined}
            />
            {animating && <Walker points={s.points} runKey={`${cursor.i}-${len}`} />}
          </g>
        )
      })}
      {start?.floor_id === floorId && (
        <g className="twin-you-are-here" transform={`translate(${start.x} ${start.y})`}>
          <circle r={0.6} />
        </g>
      )}
      {end?.floor_id === floorId && (done || currentSegment?.floorId === floorId) && (
        <g className="twin-dest-pin" transform={`translate(${end.x} ${end.y})`}>
          <path d="M0 0 C -0.9 -1.1 -1.1 -1.6 -1.1 -2.1 A 1.1 1.1 0 1 1 1.1 -2.1 C 1.1 -1.6 0.9 -1.1 0 0 Z" />
          <circle cy={-2.1} r={0.38} fill="#fff" />
        </g>
      )}
    </g>
  )
}
