// Compact front view of one rack: shelves bottom-up (S01 at the bottom), bins
// left to right (B01 left-most, seen from the aisle). Every shelf and bin
// carries data-loc-id; the target bin is filled — "shelf 3, bin 4" at a glance.
import React from 'react'

export default function RackElevation({ rack, layout, targetBins, targetShelves, binLabels, register }) {
  if (!rack) return null
  const shelves = [...(layout.shelvesByRack.get(rack.id) || [])].sort((a, b) => b.level_index - a.level_index)
  const cols = Math.max(1, ...shelves.map((s) => (layout.binsByShelf.get(s.id) || []).length))
  const cell = 22
  const gap = 3
  const labelW = 20
  const width = labelW + cols * (cell + gap)
  const height = shelves.length * (cell + gap) + 14

  return (
    <svg className="twin-elevation" width={width} height={height} viewBox={`0 0 ${width} ${height}`}
      role="img" aria-label={`Front view of ${rack.name}`}>
      {shelves.map((s, row) => {
        const y = row * (cell + gap)
        const bins = [...(layout.binsByShelf.get(s.id) || [])].sort((a, b) => a.position_index - b.position_index)
        return (
          <g key={s.id} data-loc-id={s.id} ref={(el) => register?.(s.id, el)}
            className={`twin-elev-shelf${targetShelves?.has(s.id) ? ' is-target' : ''}`}>
            <text x={0} y={y + cell / 2 + 3} className="twin-elev-axis">S{s.level_index}</text>
            {bins.map((b) => {
              const x = labelW + (b.position_index - 1) * (cell + gap)
              const label = binLabels?.get(b.id)
              const cls = [
                'twin-elev-bin',
                targetBins?.has(b.id) && 'is-target',
                label != null && 'has-stock',
                b.status !== 'active' && 'is-blocked',
              ].filter(Boolean).join(' ')
              return (
                <g key={b.id} data-loc-id={b.id} ref={(el) => register?.(b.id, el)} className={cls}>
                  <title>{`Shelf ${s.level_index}, bin ${b.position_index}${label != null ? ` — ${label}` : ''}`}</title>
                  <rect x={x} y={y} width={cell} height={cell} rx={4} />
                  {label != null && <text x={x + cell / 2} y={y + cell / 2 + 3} textAnchor="middle">{label}</text>}
                </g>
              )
            })}
          </g>
        )
      })}
      {Array.from({ length: cols }, (_, i) => (
        <text key={i} x={labelW + i * (cell + gap) + cell / 2} y={height - 2} textAnchor="middle" className="twin-elev-axis">
          B{i + 1}
        </text>
      ))}
    </svg>
  )
}
