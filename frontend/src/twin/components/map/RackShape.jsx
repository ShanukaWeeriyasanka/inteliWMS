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
    for (const b of binsByShelf.get(shelf.id) || []) {
      const x = pad + (b.position_index - 1) * (cw + gap)
      const y = pad + row * (ch + gap)
      const qty = binQty.get(b.id) || 0
      const target = targetBins?.has(b.id) || shelfTarget
      const fill = heat || (b.status !== 'active' ? '#F2C4C4' : qty > 0 ? s.full : s.empty)
      cells.push(
        <rect key={b.id} data-loc-id={b.id} x={x} y={y} width={cw} height={ch} rx={0.07}
          className={target ? 'twin-cell is-target' : 'twin-cell'} fill={target ? undefined : fill} />,
      )
      if (target) {
        rings.push(<rect key={`ring-${b.id}`} className="twin-cell-ring" x={x - 0.14} y={y - 0.14}
          width={cw + 0.28} height={ch + 0.28} rx={0.14} />)
      }
    }
  })
  const badgeW = badge != null ? 0.9 + String(badge).length * 0.4 : 0

  return (
    <g ref={(el) => register(rack.id, el)} data-loc-id={rack.id} className={`twin-rack is-${state}`}
      transform={`translate(${rack.x} ${rack.y})`} onClick={() => onClick?.(rack.id)} {...hoverProps}>
      {(state === 'target' || state === 'selected') && (
        <rect className="twin-rack-halo" x={-0.45} y={-0.45} width={w + 0.9} height={h + 0.9} rx={0.55} />
      )}
      <rect className="twin-rack-body" width={w} height={h} rx={0.28} />
      {cells}
      {rings}
      {flashKey > 0 && <rect key={`flash-${flashKey}`} className="twin-rack-flash" width={w} height={h} rx={0.28} />}
      <MapText className="twin-rack-name" x={w / 2} y={h + 0.6} size={0.56}>{rack.name}</MapText>
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
