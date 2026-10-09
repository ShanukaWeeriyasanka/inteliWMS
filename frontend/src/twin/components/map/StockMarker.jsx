// Stock marker on the aisle in front of a rack (at the rack's access node),
// like a device icon on a fleet map. Label = units there (all products, or the
// selected product only). Selected markers turn blue and pulse.
import React from 'react'
import MapText from './MapText'

const BOX = 'M0 -0.4 L0.36 -0.19 L0.36 0.2 L0 0.41 L-0.36 0.2 L-0.36 -0.19 Z M-0.36 -0.19 L0 0.02 L0.36 -0.19 M0 0.02 L0 0.41'

export default function StockMarker({ marker, onClick, hoverProps }) {
  const { x, y, label, tone, alert, rackId } = marker
  return (
    <g className={`twin-marker is-${tone}`} transform={`translate(${x} ${y})`} data-marker-for={rackId}
      onClick={() => onClick?.(rackId)} {...hoverProps}>
      {tone === 'selected' && <circle className="twin-marker-pulse" r={1.5} />}
      <rect className="twin-marker-body" x={-0.72} y={-0.72} width={1.44} height={1.44} rx={0.36} filter="url(#twin-shadow)" />
      <path className="twin-marker-glyph" d={BOX} />
      {/* the count sits beside the icon, level with it — above-right it ran into the rack name */}
      {label != null && (
        <MapText className="twin-marker-label" x={0.95} y={0.02} size={0.6} anchor="start">{label}</MapText>
      )}
      {alert && (
        <g className="twin-alert" transform="translate(0.72 -0.72)">
          <circle r={0.4} />
          <MapText x={0} y={0.03} size={0.46}>!</MapText>
        </g>
      )}
    </g>
  )
}
