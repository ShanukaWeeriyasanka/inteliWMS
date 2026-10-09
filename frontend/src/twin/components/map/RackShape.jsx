// One rack, top-down at its real position (metres). Each cell is one bin:
// rows are shelves (top row = highest shelf), columns are bin positions
// (B01 left-most). A cell is solid when the database says the bin holds stock,
// pale when empty, and orange when it is the bin the user asked about.
import React from 'react'
import MapText from './MapText'

const STYLE = {
  pallet_grid: { full: '#7096E0', empty: '#D9E3F5' },
  crate_rack: { full: '#5FB876', empty: '#D2EBD9' },
  shelf_unit: { full: '#8D98A7', empty: '#E0E4E9' },
  cabinet: { full: '#58AEDB', empty: '#D4EAF6' },
}
const RING_STROKE = 0.09 // keep in sync with .twin-cell-ring in twin.css

export const isOutlined = (state) => state === 'target' || state === 'selected'

/**
 * Where the rack's name goes (metres). Normally under the rack — and under its 0.45 m highlight
 * outline when it has one. When the rack's stock marker sits on the aisle right below it, the
 * gap is too small for both, so the name goes beside the marker instead ("Rack 1 ▣ 30"):
 * the marker icon is 1.44 m wide, its count is on its right, the name on its left.
 */
export function rackNamePlacement(rack, state, marker) {
  const bottom = rack.y + rack.depth_m
  const markerBelow = marker && marker.y > bottom && marker.y - bottom < 3.5
    && marker.x > rack.x && marker.x < rack.x + rack.width_m
  if (markerBelow) return { x: marker.x - 1.0, y: marker.y + 0.02, anchor: 'end' }
  return { x: rack.x + rack.width_m / 2, y: bottom + (isOutlined(state) ? 0.95 : 0.6), anchor: 'middle' }
}

/** The rack's name, drawn by FloorMap in the label layer above the stock markers. */
export function RackName({ rack, state, marker }) {
  const p = rackNamePlacement(rack, state, marker)
  return (
    <MapText className={`twin-rack-name is-${state}`} x={p.x} y={p.y} size={0.56} anchor={p.anchor}>
      {rack.name}
    </MapText>
  )
}

/**
 * Outlines around the target bins of one shelf row. Neighbouring target bins share one
 * outline, and every outline stays inside half the gap between bins, so outlines of
 * different bins or shelves never cross each other.
 * cells: [{ col, x }] of the row's target bins.
 */
export function ringRuns(cells, { y, cw, ch, gap }) {
  const sorted = [...cells].sort((a, b) => a.col - b.col)
  const runs = []
  for (const c of sorted) {
    const last = runs[runs.length - 1]
    if (last && c.col === last.endCol + 1) {
      last.endCol = c.col
      last.x2 = c.x + cw
    } else {
      runs.push({ startCol: c.col, endCol: c.col, x1: c.x, x2: c.x + cw })
    }
  }
  const offset = Math.max(0, gap / 2 - RING_STROKE / 2 - 0.005)
  return runs.map((r) => ({
    key: `${r.startCol}-${r.endCol}`,
    x: r.x1 - offset,
    y: y - offset,
    width: r.x2 - r.x1 + offset * 2,
    height: ch + offset * 2,
  }))
}

export default function RackShape({
  rack, grid, binsByShelf, binQty, state, targetBins, targetShelves, heat, badge, alert, flashKey, register,
  onClick, hoverProps,
}) {
  const s = STYLE[rack.type] || STYLE.shelf_unit
  const w = rack.width_m
  const h = rack.depth_m
  const shelves = [...(grid?.shelves || [])].sort((a, b) => b.level_index - a.level_index)
  const rows = Math.max(1, shelves.length)
  const cols = Math.max(1, grid?.cols || 1)
  const pad = Math.min(0.24, w * 0.05)
  const gap = Math.min(0.11, w * 0.025)
  const cw = (w - pad * 2 - gap * (cols - 1)) / cols
  const ch = (h - pad * 2 - gap * (rows - 1)) / rows

  const cells = []
  const rings = []
  shelves.forEach((shelf, row) => {
    const shelfTarget = targetShelves?.has(shelf.id)
    const y = pad + row * (ch + gap)
    const rowTargets = []
    for (const b of binsByShelf.get(shelf.id) || []) {
      const x = pad + (b.position_index - 1) * (cw + gap)
      const qty = binQty.get(b.id) || 0
      const target = targetBins?.has(b.id) || shelfTarget
      const fill = heat || (b.status !== 'active' ? '#F2C4C4' : qty > 0 ? s.full : s.empty)
      cells.push(
        <rect key={b.id} data-loc-id={b.id} x={x} y={y} width={cw} height={ch} rx={0.07}
          className={target ? 'twin-cell is-target' : 'twin-cell'} fill={target ? undefined : fill} />,
      )
      if (target) rowTargets.push({ col: b.position_index, x })
    }
    for (const ring of ringRuns(rowTargets, { y, cw, ch, gap })) {
      rings.push(<rect key={`ring-${shelf.id}-${ring.key}`} className="twin-cell-ring" x={ring.x} y={ring.y}
        width={ring.width} height={ring.height} rx={0.1} />)
    }
  })
  const badgeW = badge != null ? 0.9 + String(badge).length * 0.4 : 0
  const outlined = isOutlined(state)

  return (
    <g ref={(el) => register(rack.id, el)} data-loc-id={rack.id} className={`twin-rack is-${state}`}
      transform={`translate(${rack.x} ${rack.y})`} onClick={() => onClick?.(rack.id)} {...hoverProps}>
      {outlined && (
        <rect className="twin-rack-halo" x={-0.45} y={-0.45} width={w + 0.9} height={h + 0.9} rx={0.55} />
      )}
      <rect className="twin-rack-body" width={w} height={h} rx={0.28} />
      {cells}
      {rings}
      {flashKey > 0 && <rect key={`flash-${flashKey}`} className="twin-rack-flash" width={w} height={h} rx={0.28} />}
      {alert && (
        <g className="twin-alert" transform={`translate(${w} 0)`}>
          <circle r={0.46} />
          <MapText x={0} y={0.03} size={0.52}>!</MapText>
        </g>
      )}
      {badge != null && (
        <g className="twin-badge" transform={`translate(${w / 2} ${-0.8})`}>
          <rect x={-badgeW / 2} y={-0.52} width={badgeW} height={1.04} rx={0.52} filter="url(#twin-shadow)" />
          <MapText x={0} y={0.03} size={0.6}>{badge}</MapText>
        </g>
      )}
    </g>
  )
}
