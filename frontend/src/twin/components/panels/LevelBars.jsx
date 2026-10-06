// Three small bars (like a signal meter) for a 0–1 level, coloured by status.
import React from 'react'

export default function LevelBars({ value, status = 'ok' }) {
  const lit = value <= 0 ? 0 : value < 0.34 ? 1 : value < 0.67 ? 2 : 3
  return (
    <span className={`twin-levelbars is-${status}`} aria-hidden="true">
      {[0, 1, 2].map((i) => <i key={i} className={i < lit ? 'is-on' : ''} />)}
    </span>
  )
}

export function Gauge({ value, status = 'ok' }) {
  return (
    <span className={`twin-gauge is-${status}`} aria-hidden="true">
      <i style={{ width: `${Math.round(Math.max(0.04, Math.min(1, value)) * 100)}%` }} />
    </span>
  )
}
