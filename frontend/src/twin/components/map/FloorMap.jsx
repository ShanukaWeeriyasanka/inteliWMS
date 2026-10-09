// The interactive floor plan. One SVG whose viewBox is in metres, so database
// coordinates are drawn as-is. Drag to pan, wheel to zoom, click a rack or a
// stock marker to open its details. Every rack carries data-loc-id = its ID.
import React, { useCallback, useEffect, useRef } from 'react'
import RackShape, { RackName } from './RackShape'
import ConnectorIcon from './ConnectorIcon'
import RouteLayer from './RouteLayer'
import StockMarker from './StockMarker'
import MapText from './MapText'

const ICON_TYPES = new Set(['lift', 'stairs', 'entrance', 'dock', 'charging'])
const DRAG_PX = 4
const ZONE_FILL = { cold: 'is-cold', dock: 'is-dock', charging: 'is-dock' }

// A rack's highlight outline reaches 0.45 m above it (RackShape); the 0.55 m label needs ~0.3 m
// above its centre line. The zone name sits in the zone's corner, lifted when the zone's top
// rack starts so close to the edge that its outline would run through the name.
const HALO = 0.45
const LABEL_HALF = 0.3
export function zoneLabelY(zone, racks) {
  const inZone = racks.filter((r) => r.zone_id === zone.id)
  const topRack = inZone.length ? Math.min(...inZone.map((r) => r.y)) : Infinity
  return Math.min(zone.y + 0.75, topRack - HALO - LABEL_HALF - 0.2)
}

export default function FloorMap({
  svgRef, layout, edges, floorId, vb, view, markers, binQty, route, playback, reducedMotion, registry,
  onRack, onMarker, onHover, onPan, onZoom,
}) {
  const floor = layout.floorsById.get(floorId)
  const drag = useRef(null)
  const dragging = useRef(false)
  const cb = useRef({ onZoom })
  cb.current = { onZoom }

  const register = useCallback((id, el) => {
    if (el) registry.current.set(id, el)
    else registry.current.delete(id)
  }, [registry])

  // Wheel zoom needs a non-passive listener to stop the page from scrolling.
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return undefined
    const onWheel = (e) => {
      e.preventDefault()
      cb.current.onZoom?.(Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY)
    }
    svg.addEventListener('wheel', onWheel, { passive: false })
    return () => svg.removeEventListener('wheel', onWheel)
  }, [svgRef, !!floor])

  if (!floor || !vb) return <svg ref={svgRef} className="twin-svg" />

  const W = floor.width_m
  const H = floor.height_m
  const zones = layout.zonesByFloor.get(floorId) || []
  const racks = layout.racksByFloor.get(floorId) || []
  const nodes = layout.nodesByFloor.get(floorId) || []
  const walkEdges = edges.filter((e) => e.edge_type === 'walk' && e.from_floor_id === floorId)
  const doors = nodes.filter((n) => n.type === 'entrance' || n.type === 'dock')
  const focusing = view.highlight.size > 0 || !!view.zoneId
  const markerFor = new Map(markers.map((m) => [m.rackId, m]))
  const rackState = (r) => (view.selectedRackId === r.id ? 'selected'
    : view.highlight.has(r.id) || (view.zoneId && r.zone_id === view.zoneId) ? 'target'
      : focusing ? 'dim' : 'normal')

  const onPointerDown = (e) => {
    if (e.button !== 0) return
    drag.current = { x: e.clientX, y: e.clientY, moved: false }
  }
  const onPointerMove = (e) => {
    const d = drag.current
    if (!d) return
    const dx = e.clientX - d.x
    const dy = e.clientY - d.y
    if (!d.moved) {
      if (Math.hypot(dx, dy) < DRAG_PX) return
      d.moved = true
      dragging.current = true
      svgRef.current?.setPointerCapture?.(e.pointerId)
      svgRef.current?.classList.add('is-dragging')
      onHover?.(null)
    }
    onPan(dx, dy)
    d.x = e.clientX
    d.y = e.clientY
  }
  const onPointerUp = () => {
    drag.current = null
    svgRef.current?.classList.remove('is-dragging')
    // the click that ends a drag must not select anything
    setTimeout(() => { dragging.current = false }, 0)
  }
  const guard = (fn) => (...args) => { if (!dragging.current) fn(...args) }
  const hover = (kind, id) => ({
    onPointerEnter: (e) => !drag.current && onHover?.({ kind, id, clientX: e.clientX, clientY: e.clientY }),
    onPointerMove: (e) => !drag.current && onHover?.({ kind, id, clientX: e.clientX, clientY: e.clientY }),
    onPointerLeave: () => onHover?.(null),
  })

  return (
    <svg
      ref={svgRef}
      className="twin-svg"
      viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={`Floor plan of ${floor.name}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <defs>
        <filter id="twin-shadow" x="-40%" y="-40%" width="180%" height="190%">
          <feDropShadow dx="0" dy="0.12" stdDeviation="0.16" floodColor="#1E2226" floodOpacity="0.22" />
        </filter>
      </defs>

      <g key={floorId} className={reducedMotion ? undefined : 'twin-floor-enter'}>
        {/* building shell with door notches */}
        <rect data-loc-id={floorId} ref={(el) => register(floorId, el)} className="twin-building"
          x={0} y={0} width={W} height={H} rx={1.4} />
        {[0.3, 0.7].map((f) => (
          <React.Fragment key={f}>
            <rect className="twin-notch" x={W * f - 1.1} y={-0.55} width={2.2} height={1.1} rx={0.3} />
            <rect className="twin-notch" x={W * f - 1.1} y={H - 0.55} width={2.2} height={1.1} rx={0.3} />
          </React.Fragment>
        ))}
        {doors.map((n) => (
          <rect key={n.id} className="twin-notch is-door" x={-0.55} y={n.y - 1.2} width={1.1} height={2.4} rx={0.3} />
        ))}

        {zones.map((z) => (
          <rect key={z.id} data-loc-id={z.id} ref={(el) => register(z.id, el)} x={z.x} y={z.y}
            width={z.width_m} height={z.height_m} rx={0.7}
            className={`twin-zone ${ZONE_FILL[z.type] || ''}${view.zoneId === z.id ? ' is-target' : ''}`} />
        ))}

        <g className="twin-aisles">
          {walkEdges.map((e) => {
            const a = layout.nodesById.get(e.from_node_id)
            const b = layout.nodesById.get(e.to_node_id)
            if (!a || !b) return null
            return <line key={e.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className={e.blocked ? 'is-blocked' : undefined} />
          })}
          {nodes.filter((n) => n.type === 'intersection').map((n) => (
            <circle key={n.id} className="twin-junction" cx={n.x} cy={n.y} r={0.24} />
          ))}
        </g>

        {racks.map((r) => (
          <RackShape key={r.id} rack={r} grid={layout.rackGrid.get(r.id)} binsByShelf={layout.binsByShelf}
            binQty={binQty} state={rackState(r)} targetBins={view.targetBins} targetShelves={view.targetShelves}
            heat={view.heat?.get(r.id)} badge={view.badges.get(r.id)} alert={view.alertRacks.has(r.id)}
            flashKey={view.flash.get(r.id) || 0} register={register}
            onClick={guard(onRack)} hoverProps={hover('rack', r.id)} />
        ))}

        {nodes.filter((n) => ICON_TYPES.has(n.type)).map((n) => <ConnectorIcon key={n.id} node={n} />)}

        <RouteLayer floorId={floorId} segments={route.segments} path={route.data?.path || []}
          playback={playback} reducedMotion={reducedMotion} />

        {markers.map((m) => (
          <StockMarker key={m.rackId} marker={m} onClick={guard(onMarker)} hoverProps={hover('rack', m.rackId)} />
        ))}

        {/* Names last, with a halo: a rack's outline or a stock marker never covers them */}
        <g className="twin-labels" aria-hidden="true">
          {racks.map((r) => <RackName key={r.id} rack={r} state={rackState(r)} marker={markerFor.get(r.id)} />)}
          {zones.map((z) => {
            const [short, desc] = z.name.split(' — ')
            return (
              <MapText key={z.id} className="twin-zone-label" x={z.x + 0.5} y={zoneLabelY(z, racks)} size={0.55} anchor="start">
                {desc ? `${short} · ${desc}` : short}
              </MapText>
            )
          })}
        </g>
      </g>
    </svg>
  )
}
