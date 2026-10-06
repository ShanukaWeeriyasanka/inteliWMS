// Small tooltip that follows the pointer over a rack or stock marker.
import React from 'react'

export default function HoverCard({ hover, data, selectedProductId }) {
  if (!hover) return null
  const rack = data.layout.racksById.get(hover.id)
  if (!rack) return null
  const fill = data.fillByRack.get(rack.id)
  const rows = data.locationsByRack.get(rack.id) || []
  const mine = selectedProductId ? rows.filter((r) => r.product_id === selectedProductId) : []
  const product = selectedProductId && data.productsById.get(selectedProductId)
  return (
    <div className="twin-hover" style={{ left: hover.x, top: hover.y }} role="tooltip">
      <strong>{rack.name}</strong>
      <span className="twin-muted">{data.layout.zonesById.get(rack.zone_id)?.name}</span>
      <span>{fill?.total_units || 0} units · {fill?.distinct_products || 0} products · {Math.round((fill?.fill_ratio || 0) * 100)}% full</span>
      {mine.length > 0 && (
        <span className="twin-hover-mine">
          {product?.name}: {mine.map((r) => `${r.quantity} in S${r.level_index}·B${r.position_index}`).join(', ')}
        </span>
      )}
    </div>
  )
}
