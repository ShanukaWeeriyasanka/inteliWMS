// SVG text sized in metres. Chrome renders sub-pixel font sizes badly
// ("Rack 1" → garbled), so text is drawn at a normal size and scaled down.
import React from 'react'

const SCALE = 0.05

export default function MapText({ x, y, size, anchor = 'middle', baseline = 'central', className, children }) {
  return (
    <text transform={`translate(${x} ${y}) scale(${SCALE})`} fontSize={size / SCALE} textAnchor={anchor}
      dominantBaseline={baseline} className={className}>
      {children}
    </text>
  )
}
